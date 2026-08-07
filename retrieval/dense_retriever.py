"""Dense (vector) retrieval via Qdrant.

Embeds the query using BAAI/bge-large-en-v1.5 and queries the Qdrant
``veriducta_chunks`` collection.  An in-process LRU cache with TTL prevents
re-embedding identical queries within a session.
"""

import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

import structlog
from qdrant_client import QdrantClient

from core.exceptions import RetrievalError, VectorStoreError
from models.embedding import BGELargeEmbedding
from observability.metrics import (
    DENSE_RETRIEVAL_LATENCY,
    EMBEDDING_CACHE_HITS,
    EMBEDDING_CACHE_MISSES,
)
from retrieval._chunk_utils import payload_to_chunk
from schemas.models import RetrievalCandidate
from utils.timers import timer

logger = structlog.get_logger(__name__)

_COLLECTION = "veriducta_chunks"


@dataclass
class _CacheEntry:
    vector: list[float]
    created_at: float = field(default_factory=monotonic)


class _QueryEmbeddingCache:
    """LRU cache with TTL for query embedding vectors.

    Thread-unsafe — use only within a single-threaded request context.

    Args:
        max_size: Maximum number of entries; 0 disables caching.
        ttl_seconds: Time-to-live in seconds.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600.0) -> None:
        self._max = max_size
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        """Return cached vector or ``None`` on miss / expiry."""
        if self._max == 0 or key not in self._store:
            EMBEDDING_CACHE_MISSES.inc()
            return None
        entry = self._store[key]
        if monotonic() - entry.created_at > self._ttl:
            del self._store[key]
            EMBEDDING_CACHE_MISSES.inc()
            return None
        self._store.move_to_end(key)
        EMBEDDING_CACHE_HITS.inc()
        return entry.vector

    def put(self, key: str, vector: list[float]) -> None:
        """Insert or refresh *vector* under *key*, evicting LRU if full."""
        if self._max == 0:
            return
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = _CacheEntry(vector=vector)
            return
        if len(self._store) >= self._max:
            self._store.popitem(last=False)
        self._store[key] = _CacheEntry(vector=vector)

    @property
    def size(self) -> int:
        """Current number of unexpired entries (approximate — no sweep)."""
        return len(self._store)


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()


class DenseRetriever:
    """Dense retrieval via BAAI/bge-large-en-v1.5 + Qdrant.

    Embeds the query (with BGE retrieval prefix), checks the embedding cache,
    and runs a Qdrant ANN search returning the top-k scored candidates.

    Args:
        embedding_model: Loaded :class:`~models.embedding.BGELargeEmbedding`.
        qdrant_client: Connected :class:`~qdrant_client.QdrantClient`.
        top_k: Number of candidates to return (default 100).
        collection_name: Qdrant collection to search.
        cache_size: Maximum embedding cache size.
        cache_ttl_seconds: Cache TTL in seconds.
    """

    def __init__(
        self,
        embedding_model: BGELargeEmbedding,
        qdrant_client: QdrantClient,
        top_k: int = 100,
        collection_name: str = _COLLECTION,
        cache_size: int = 1000,
        cache_ttl_seconds: float = 3600.0,
    ) -> None:
        self._model = embedding_model
        self._client = qdrant_client
        self._top_k = top_k
        self._collection = collection_name
        self._cache = _QueryEmbeddingCache(max_size=cache_size, ttl_seconds=cache_ttl_seconds)

    def retrieve(self, query: str) -> list[RetrievalCandidate]:
        """Return top-k dense candidates for *query*.

        Each candidate has ``dense_score``, ``dense_rank``, and ``chunk``
        (reconstructed from the Qdrant payload) populated.

        Args:
            query: Natural-language query string.

        Returns:
            List of :class:`~schemas.models.RetrievalCandidate` ordered by
            descending cosine similarity score.

        Raises:
            RetrievalError: If embedding fails.
            VectorStoreError: If Qdrant search fails.
        """
        with timer("dense_retrieval") as t:
            query_vector = self._get_or_embed(query)
            hits = self._search(query_vector)

        DENSE_RETRIEVAL_LATENCY.observe(t.elapsed_ms)
        logger.debug("dense_retrieval_done", latency_ms=t.elapsed_ms, hit_count=len(hits))

        candidates: list[RetrievalCandidate] = []
        for rank, hit in enumerate(hits, start=1):
            payload: dict[str, Any] = hit.payload or {}
            chunk = payload_to_chunk(payload)
            chunk_id: str = str(payload.get("chunk_id", str(hit.id)))
            candidates.append(
                RetrievalCandidate(
                    chunk_id=chunk_id,
                    dense_score=float(hit.score),
                    dense_rank=rank,
                    chunk=chunk,
                )
            )
        return candidates

    def _get_or_embed(self, query: str) -> list[float]:
        """Return cached or freshly computed query embedding."""
        key = _query_hash(query)
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("embedding_cache_hit", query_hash=key[:8])
            return cached
        try:
            vector = self._model.embed_query(query)
        except Exception as exc:
            raise RetrievalError(
                "Failed to embed query",
                details={"query_hash": key[:8], "error": str(exc)},
            ) from exc
        self._cache.put(key, vector)
        return vector

    def _search(self, query_vector: list[float]) -> list[Any]:
        """Run Qdrant ANN search and return raw ScoredPoint list."""
        try:
            return self._client.search(  # type: ignore[attr-defined, no-any-return]
                collection_name=self._collection,
                query_vector=query_vector,
                limit=self._top_k,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(
                "Qdrant dense search failed",
                details={"collection": self._collection, "error": str(exc)},
            ) from exc

    @property
    def cache(self) -> _QueryEmbeddingCache:
        """Embedding cache instance (for monitoring and testing)."""
        return self._cache
