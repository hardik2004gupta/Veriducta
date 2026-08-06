"""Tests for retrieval/fusion.py — pure function, no mocks needed."""

import pytest

from retrieval.fusion import _DEFAULT_RRF_K, _IMPLICIT_RANK, fuse
from schemas.models import RetrievalCandidate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bm25(chunk_id: str, score: float, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(chunk_id=chunk_id, bm25_score=score, bm25_rank=rank)


def _dense(chunk_id: str, score: float, rank: int) -> RetrievalCandidate:
    return RetrievalCandidate(chunk_id=chunk_id, dense_score=score, dense_rank=rank)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_fuse_empty_inputs() -> None:
    result = fuse([], [])
    assert result == []


def test_fuse_bm25_only() -> None:
    bm25 = [_bm25("a", 5.0, 1), _bm25("b", 3.0, 2)]
    result = fuse(bm25, [])
    assert len(result) == 2
    for c in result:
        assert c.rrf_score is not None
        assert c.rrf_rank is not None


def test_fuse_dense_only() -> None:
    dense = [_dense("a", 0.9, 1), _dense("b", 0.7, 2)]
    result = fuse([], dense)
    assert len(result) == 2
    for c in result:
        assert c.rrf_score is not None


def test_fuse_returns_all_unique_ids() -> None:
    bm25 = [_bm25("a", 5.0, 1), _bm25("b", 3.0, 2)]
    dense = [_dense("b", 0.9, 1), _dense("c", 0.7, 2)]
    result = fuse(bm25, dense)
    ids = {c.chunk_id for c in result}
    assert ids == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


def test_fuse_rrf_score_formula() -> None:
    bm25 = [_bm25("a", 5.0, 1)]
    dense = [_dense("a", 0.9, 2)]
    result = fuse(bm25, dense)
    expected = 1.0 / (60 + 1) + 1.0 / (60 + 2)
    assert result[0].rrf_score == pytest.approx(expected)


def test_fuse_implicit_rank_for_absent_candidate() -> None:
    # "a" only in BM25 at rank 1; dense absent → implicit rank 101
    bm25 = [_bm25("a", 5.0, 1)]
    dense = [_dense("b", 0.9, 1)]
    result = fuse(bm25, dense)
    a = next(c for c in result if c.chunk_id == "a")
    expected_a = 1.0 / (60 + 1) + 1.0 / (60 + 101)
    assert a.rrf_score == pytest.approx(expected_a)


def test_fuse_overlap_candidate_higher_score_than_single_list() -> None:
    # "overlap" appears in both lists; "bm25only" appears only in BM25
    bm25 = [_bm25("overlap", 10.0, 1), _bm25("bm25only", 5.0, 2)]
    dense = [_dense("overlap", 0.9, 1), _dense("denseonly", 0.7, 2)]
    result = fuse(bm25, dense)
    score_overlap = next(c.rrf_score for c in result if c.chunk_id == "overlap")
    score_bm25only = next(c.rrf_score for c in result if c.chunk_id == "bm25only")
    assert score_overlap is not None and score_bm25only is not None
    assert score_overlap > score_bm25only


# ---------------------------------------------------------------------------
# Ranking and ordering
# ---------------------------------------------------------------------------


def test_fuse_results_sorted_by_descending_rrf_score() -> None:
    bm25 = [_bm25("a", 10.0, 1), _bm25("b", 5.0, 2)]
    dense = [_dense("a", 0.9, 1)]
    result = fuse(bm25, dense)
    scores = [c.rrf_score for c in result]
    assert all(s is not None for s in scores)
    non_null_scores = [s for s in scores if s is not None]
    assert non_null_scores == sorted(non_null_scores, reverse=True)


def test_fuse_rrf_ranks_are_1_indexed_sequential() -> None:
    bm25 = [_bm25("a", 5.0, 1), _bm25("b", 3.0, 2), _bm25("c", 1.0, 3)]
    result = fuse(bm25, [])
    ranks = sorted(r for c in result if (r := c.rrf_rank) is not None)
    assert ranks == [1, 2, 3]


# ---------------------------------------------------------------------------
# Score propagation
# ---------------------------------------------------------------------------


def test_fuse_preserves_bm25_score_on_overlap_candidate() -> None:
    bm25 = [_bm25("a", 7.5, 1)]
    dense = [_dense("a", 0.8, 1)]
    result = fuse(bm25, dense)
    a = next(c for c in result if c.chunk_id == "a")
    assert a.bm25_score == pytest.approx(7.5)
    assert a.dense_score == pytest.approx(0.8)


def test_fuse_none_scores_for_absent_list() -> None:
    bm25 = [_bm25("a", 5.0, 1)]
    result = fuse(bm25, [])
    a = result[0]
    assert a.dense_score is None
    assert a.dense_rank is None


def test_fuse_custom_rrf_k() -> None:
    bm25 = [_bm25("a", 5.0, 1)]
    result_k60 = fuse(bm25, [], rrf_k=60)
    result_k30 = fuse(bm25, [], rrf_k=30)
    # smaller k → larger score
    assert result_k30[0].rrf_score is not None and result_k60[0].rrf_score is not None
    assert result_k30[0].rrf_score > result_k60[0].rrf_score


def test_fuse_default_rrf_k_constant() -> None:
    assert _DEFAULT_RRF_K == 60


def test_fuse_implicit_rank_constant() -> None:
    assert _IMPLICIT_RANK == 101
