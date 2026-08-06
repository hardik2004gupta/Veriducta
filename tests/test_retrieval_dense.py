"""Tests for retrieval/dense_retriever.py."""

from unittest.mock import MagicMock

import pytest

from core.exceptions import RetrievalError, VectorStoreError
from retrieval.dense_retriever import DenseRetriever, _query_hash, _QueryEmbeddingCache
from schemas.models import RetrievalCandidate

# ---------------------------------------------------------------------------
# _query_hash
# ---------------------------------------------------------------------------


def test_query_hash_deterministic() -> None:
    assert _query_hash("hello") == _query_hash("hello")


def test_query_hash_different_queries_differ() -> None:
    assert _query_hash("hello") != _query_hash("world")


# ---------------------------------------------------------------------------
# _QueryEmbeddingCache
# ---------------------------------------------------------------------------


def test_cache_miss_on_empty() -> None:
    cache = _QueryEmbeddingCache(max_size=10)
    assert cache.get("key") is None


def test_cache_put_and_get() -> None:
    cache = _QueryEmbeddingCache(max_size=10)
    vec = [0.1, 0.2, 0.3]
    cache.put("k", vec)
    assert cache.get("k") == vec


def test_cache_size_zero_disables_caching() -> None:
    cache = _QueryEmbeddingCache(max_size=0)
    cache.put("k", [1.0])
    assert cache.get("k") is None


def test_cache_evicts_lru_when_full() -> None:
    cache = _QueryEmbeddingCache(max_size=2)
    cache.put("a", [1.0])
    cache.put("b", [2.0])
    cache.put("c", [3.0])  # evicts "a"
    assert cache.get("a") is None
    assert cache.get("b") is not None
    assert cache.get("c") is not None


def test_cache_size_property() -> None:
    cache = _QueryEmbeddingCache(max_size=5)
    assert cache.size == 0
    cache.put("x", [1.0])
    assert cache.size == 1


def test_cache_ttl_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    cache = _QueryEmbeddingCache(max_size=10, ttl_seconds=1.0)
    cache.put("k", [1.0])
    # Simulate TTL expiry by replacing created_at
    entry = cache._store["k"]
    from dataclasses import replace

    cache._store["k"] = replace(entry, created_at=time.monotonic() - 2.0)
    assert cache.get("k") is None


# ---------------------------------------------------------------------------
# DenseRetriever
# ---------------------------------------------------------------------------


def _make_hit(chunk_id: str, score: float, doc_id: str = "doc-a") -> MagicMock:
    hit = MagicMock()
    hit.id = 12345
    hit.score = score
    hit.payload = {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "text": f"text for {chunk_id}",
        "parent_chunk_id": None,
        "token_count": 10,
        "chunk_index": 0,
        "is_table": False,
        "effective_date": "2022-01-01",
        "expiry_date": None,
        "page_number": 1,
    }
    return hit


def _make_retriever(
    hits: list[MagicMock] | None = None, embed_return: list[float] | None = None
) -> DenseRetriever:
    model = MagicMock()
    model.embed_query.return_value = embed_return or [0.1] * 1024
    client = MagicMock()
    client.search.return_value = hits or []
    return DenseRetriever(
        embedding_model=model,
        qdrant_client=client,
        top_k=10,
        cache_size=100,
    )


def test_retrieve_returns_candidates() -> None:
    hits = [_make_hit("doc-a-ch-0000", 0.9), _make_hit("doc-a-ch-0001", 0.8)]
    r = _make_retriever(hits=hits)
    results = r.retrieve("test query")
    assert len(results) == 2
    assert all(isinstance(c, RetrievalCandidate) for c in results)


def test_retrieve_ranks_assigned() -> None:
    hits = [_make_hit("doc-a-ch-0000", 0.9), _make_hit("doc-a-ch-0001", 0.8)]
    r = _make_retriever(hits=hits)
    results = r.retrieve("query")
    assert results[0].dense_rank == 1
    assert results[1].dense_rank == 2


def test_retrieve_scores_set() -> None:
    hits = [_make_hit("doc-a-ch-0000", 0.75)]
    r = _make_retriever(hits=hits)
    results = r.retrieve("query")
    assert results[0].dense_score == pytest.approx(0.75)


def test_retrieve_populates_chunk() -> None:
    hits = [_make_hit("doc-a-ch-0000", 0.9)]
    r = _make_retriever(hits=hits)
    results = r.retrieve("query")
    assert results[0].chunk is not None
    assert results[0].chunk.chunk_id == "doc-a-ch-0000"


def test_retrieve_uses_embedding_cache() -> None:
    model = MagicMock()
    model.embed_query.return_value = [0.1] * 1024
    client = MagicMock()
    client.search.return_value = [_make_hit("doc-a-ch-0000", 0.9)]
    r = DenseRetriever(embedding_model=model, qdrant_client=client, top_k=10, cache_size=100)
    r.retrieve("same query")
    r.retrieve("same query")
    # embed_query should be called only once (cache hit on second call)
    assert model.embed_query.call_count == 1


def test_retrieve_embed_failure_raises_retrieval_error() -> None:
    model = MagicMock()
    model.embed_query.side_effect = RuntimeError("model failure")
    client = MagicMock()
    r = DenseRetriever(embedding_model=model, qdrant_client=client, cache_size=0)
    with pytest.raises(RetrievalError):
        r.retrieve("query")


def test_retrieve_qdrant_failure_raises_vector_store_error() -> None:
    model = MagicMock()
    model.embed_query.return_value = [0.1] * 1024
    client = MagicMock()
    client.search.side_effect = RuntimeError("qdrant down")
    r = DenseRetriever(embedding_model=model, qdrant_client=client, cache_size=0)
    with pytest.raises(VectorStoreError):
        r.retrieve("query")


def test_retrieve_empty_results() -> None:
    r = _make_retriever(hits=[])
    results = r.retrieve("query")
    assert results == []


def test_cache_property_accessible() -> None:
    r = _make_retriever()
    assert isinstance(r.cache, _QueryEmbeddingCache)
