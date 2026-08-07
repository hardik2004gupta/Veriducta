"""Tests for retrieval/bm25_retriever.py."""

import pickle
from pathlib import Path

import pytest
from rank_bm25 import BM25Okapi

from core.exceptions import NotFoundError
from retrieval.bm25_retriever import BM25Retriever, _tokenise
from schemas.models import RetrievalCandidate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pkl(tmp_path: Path, texts: list[str], chunk_ids: list[str] | None = None) -> Path:
    """Write a BM25 pickle compatible with the ingestion pipeline format."""
    if chunk_ids is None:
        chunk_ids = [f"doc-ch-{i:04d}" for i in range(len(texts))]
    tokenised = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenised)
    payload = {"bm25": bm25, "chunk_ids": chunk_ids, "texts": texts}
    path = tmp_path / "bm25_index.pkl"
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    return path


# ---------------------------------------------------------------------------
# _tokenise
# ---------------------------------------------------------------------------


def test_tokenise_lowercases() -> None:
    assert _tokenise("Hello World") == ["hello", "world"]


def test_tokenise_whitespace_split() -> None:
    assert _tokenise("a b  c") == ["a", "b", "c"]


def test_tokenise_empty_string() -> None:
    assert _tokenise("") == []


# ---------------------------------------------------------------------------
# BM25Retriever.load
# ---------------------------------------------------------------------------


def test_retriever_loads_from_pkl(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["hello world", "foo bar"])
    r = BM25Retriever(path)
    assert r.chunk_count == 2
    assert r.is_loaded


def test_retriever_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        BM25Retriever(tmp_path / "nonexistent.pkl")


# ---------------------------------------------------------------------------
# BM25Retriever.retrieve
# ---------------------------------------------------------------------------


def test_retrieve_returns_candidates(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["maximum permissible exposure limits", "unrelated topic"])
    r = BM25Retriever(path, top_k=2)
    results = r.retrieve("maximum exposure")
    assert len(results) == 2
    for cand in results:
        assert isinstance(cand, RetrievalCandidate)


def test_retrieve_top_k_respected(tmp_path: Path) -> None:
    texts = [f"chunk text number {i}" for i in range(20)]
    path = _build_pkl(tmp_path, texts)
    r = BM25Retriever(path, top_k=5)
    results = r.retrieve("chunk text")
    assert len(results) == 5


def test_retrieve_ranks_assigned(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["alpha beta gamma", "delta epsilon"])
    r = BM25Retriever(path, top_k=2)
    results = r.retrieve("alpha beta")
    ranks = [c.bm25_rank for c in results]
    assert ranks == [1, 2]


def test_retrieve_scores_non_negative(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["hello world", "foo bar baz"])
    r = BM25Retriever(path, top_k=2)
    results = r.retrieve("hello")
    for c in results:
        assert c.bm25_score is not None
        assert c.bm25_score >= 0.0


def test_retrieve_exact_match_ranks_first(tmp_path: Path) -> None:
    texts = ["maximum permissible exposure", "unrelated document content here"]
    ids = ["target-ch-0000", "other-ch-0000"]
    path = _build_pkl(tmp_path, texts, ids)
    r = BM25Retriever(path, top_k=2)
    results = r.retrieve("maximum permissible exposure")
    assert results[0].chunk_id == "target-ch-0000"


def test_retrieve_chunk_field_is_none(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["sample text"])
    r = BM25Retriever(path, top_k=1)
    results = r.retrieve("sample")
    assert results[0].chunk is None


def test_retrieve_no_matches_still_returns_results(tmp_path: Path) -> None:
    path = _build_pkl(tmp_path, ["alpha bravo charlie", "delta echo foxtrot"])
    r = BM25Retriever(path, top_k=2)
    results = r.retrieve("zzzzz totally absent term")
    assert len(results) == 2
    for c in results:
        assert c.bm25_score is not None
