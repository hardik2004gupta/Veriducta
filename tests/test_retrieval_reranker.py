"""Tests for retrieval/reranker.py."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.exceptions import RetrievalError
from retrieval.reranker import CrossEncoderReranker
from schemas.models import Chunk, RetrievalCandidate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candidate(chunk_id: str, text: str | None = "some text") -> RetrievalCandidate:
    chunk = None
    if text is not None:
        chunk = Chunk(
            chunk_id=chunk_id,
            document_id="doc-a",
            text=text,
            token_count=3,
            chunk_index=0,
        )
    return RetrievalCandidate(chunk_id=chunk_id, chunk=chunk, rrf_score=0.5, rrf_rank=1)


def _make_reranker(scores: list[float]) -> CrossEncoderReranker:
    """Build a CrossEncoderReranker with a mocked CrossEncoder model."""
    with patch("retrieval.reranker.CrossEncoder") as mock_cls:
        model = MagicMock()
        model.predict.return_value = np.array(scores)
        mock_cls.return_value = model
        reranker = CrossEncoderReranker("mock-model")
    # Attach the mock model so tests can inspect calls
    reranker._model = model
    return reranker


# ---------------------------------------------------------------------------
# rerank basic behaviour
# ---------------------------------------------------------------------------


def test_rerank_returns_all_candidates() -> None:
    scores = [2.0, 1.0, 0.5]
    candidates = [
        _make_candidate("a", "text a"),
        _make_candidate("b", "text b"),
        _make_candidate("c", "text c"),
    ]
    r = _make_reranker(scores)
    result = r.rerank("query", candidates)
    assert len(result) == 3


def test_rerank_sorts_by_descending_score() -> None:
    candidates = [
        _make_candidate("low", "low relevance"),
        _make_candidate("high", "high relevance"),
    ]
    r = _make_reranker([0.5, 2.0])  # low=0.5, high=2.0
    result = r.rerank("query", candidates)
    assert result[0].chunk_id == "high"
    assert result[1].chunk_id == "low"


def test_rerank_sets_post_rerank_rank() -> None:
    candidates = [_make_candidate("a", "text"), _make_candidate("b", "text2")]
    r = _make_reranker([1.0, 0.5])
    result = r.rerank("query", candidates)
    assert result[0].post_rerank_rank == 1
    assert result[1].post_rerank_rank == 2


def test_rerank_sets_reranker_score() -> None:
    candidates = [_make_candidate("a", "text")]
    r = _make_reranker([3.14])
    result = r.rerank("query", candidates)
    assert result[0].reranker_score == pytest.approx(3.14)


def test_rerank_empty_candidates_returns_empty() -> None:
    r = _make_reranker([])
    result = r.rerank("query", [])
    assert result == []


# ---------------------------------------------------------------------------
# Candidates without text
# ---------------------------------------------------------------------------


def test_rerank_candidate_without_chunk_gets_neg_inf() -> None:
    no_text = _make_candidate("no-text", text=None)
    with_text = _make_candidate("has-text", text="relevant")
    r = _make_reranker([1.0])
    result = r.rerank("query", [no_text, with_text])
    no_text_result = next(c for c in result if c.chunk_id == "no-text")
    assert no_text_result.reranker_score == float("-inf")


def test_rerank_all_missing_text_returns_neg_inf_for_all() -> None:
    candidates = [_make_candidate("a", text=None), _make_candidate("b", text=None)]
    r = _make_reranker([])
    result = r.rerank("query", candidates)
    assert all(c.reranker_score == float("-inf") for c in result)


# ---------------------------------------------------------------------------
# Inference failure
# ---------------------------------------------------------------------------


def test_rerank_inference_failure_raises_retrieval_error() -> None:
    with patch("retrieval.reranker.CrossEncoder") as mock_cls:
        model = MagicMock()
        model.predict.side_effect = RuntimeError("GPU OOM")
        mock_cls.return_value = model
        reranker = CrossEncoderReranker("mock-model")
        reranker._model = model

    candidates = [_make_candidate("a", "text")]
    with pytest.raises(RetrievalError):
        reranker.rerank("query", candidates)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def test_get_reranker_returns_singleton() -> None:
    """get_reranker() must return the same instance on repeated calls."""
    import retrieval.reranker as reranker_mod

    original = reranker_mod._reranker_instance
    try:
        reranker_mod._reranker_instance = None
        with patch("retrieval.reranker.CrossEncoder") as mock_cls:
            mock_cls.return_value = MagicMock()
            r1 = reranker_mod.get_reranker("mock")
            r2 = reranker_mod.get_reranker("mock")
        assert r1 is r2
    finally:
        reranker_mod._reranker_instance = original


def test_reranker_model_id_property() -> None:
    with patch("retrieval.reranker.CrossEncoder") as mock_cls:
        mock_cls.return_value = MagicMock()
        r = CrossEncoderReranker("my-model")
    assert r.model_id == "my-model"
