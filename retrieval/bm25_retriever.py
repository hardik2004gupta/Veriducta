"""BM25 retrieval over the indexed chunk corpus.

Loads the serialised BM25 index produced by the ingestion pipeline and
returns the top-k scored candidates for a query.  The tokeniser used here
must match exactly the one used at index-build time (lowercase whitespace split).
"""

import pickle
from pathlib import Path
from typing import Any

import structlog
from rank_bm25 import BM25Okapi

from core.exceptions import NotFoundError, RetrievalError
from observability.metrics import BM25_RETRIEVAL_LATENCY
from schemas.models import RetrievalCandidate
from utils.timers import timer

logger = structlog.get_logger(__name__)


def _tokenise(text: str) -> list[str]:
    """Lowercase whitespace tokeniser — must match ingestion/bm25_indexer exactly."""
    return text.lower().split()


class BM25Retriever:
    """BM25 retrieval over the indexed child chunks.

    Loads the pickled BM25 index produced by the ingestion pipeline and
    exposes :meth:`retrieve` for query-time search.

    The pickle file format is a dict with keys:
    ``"bm25"`` (BM25Okapi), ``"chunk_ids"`` (list[str]), ``"texts"`` (list[str]).

    Args:
        index_path: Path to the ``.pkl`` file produced by ingestion.
        top_k: Number of candidates to return (default 100).
    """

    def __init__(self, index_path: str | Path, top_k: int = 100) -> None:
        self._top_k = top_k
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []
        self._load(Path(index_path))

    def _load(self, path: Path) -> None:
        if not path.exists():
            raise NotFoundError("bm25_index", str(path))
        with path.open("rb") as fh:
            payload: dict[str, Any] = pickle.load(fh)  # noqa: S301
        self._bm25 = payload["bm25"]
        self._chunk_ids = payload["chunk_ids"]
        self._texts: list[str] = payload.get("texts", [])
        logger.info(
            "bm25_retriever_loaded",
            path=str(path),
            chunk_count=len(self._chunk_ids),
        )

    def retrieve(self, query: str) -> list[RetrievalCandidate]:
        """Return top-k BM25 candidates for *query*.

        Candidates have ``bm25_score`` and ``bm25_rank`` populated.  The
        ``chunk`` field is left empty and populated downstream by the
        retrieval orchestrator via Qdrant payload fetch.

        Args:
            query: Natural-language query string.

        Returns:
            List of :class:`~schemas.models.RetrievalCandidate` ordered by
            descending BM25 score.

        Raises:
            RetrievalError: If the index has not been loaded.
        """
        if self._bm25 is None:
            raise RetrievalError(
                "BM25 retriever not loaded",
                details={"chunk_count": 0},
            )

        with timer("bm25_retrieval") as t:
            tokens = _tokenise(query)
            scores = self._bm25.get_scores(tokens)
            indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        BM25_RETRIEVAL_LATENCY.observe(t.elapsed_ms)
        logger.debug("bm25_retrieval_done", latency_ms=t.elapsed_ms, top_k=self._top_k)

        results: list[RetrievalCandidate] = []
        for rank, (idx, score) in enumerate(indexed[: self._top_k], start=1):
            results.append(
                RetrievalCandidate(
                    chunk_id=self._chunk_ids[idx],
                    bm25_score=float(score),
                    bm25_rank=rank,
                )
            )
        return results

    @property
    def chunk_count(self) -> int:
        """Number of chunks in the loaded index."""
        return len(self._chunk_ids)

    @property
    def is_loaded(self) -> bool:
        """True if the index has been successfully loaded."""
        return self._bm25 is not None

    @property
    def chunk_texts(self) -> dict[str, str]:
        """Mapping from chunk_id to chunk text for counterevidence NLI lookups.

        Returns an empty dict when the index was built without a ``texts`` key
        (older index format).
        """
        return dict(zip(self._chunk_ids, self._texts, strict=False))
