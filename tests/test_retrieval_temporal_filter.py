"""Tests for retrieval/temporal_filter.py."""

from retrieval.temporal_filter import TemporalFilter, TemporalFilterResult
from schemas.models import Chunk, RetrievalCandidate

# ---------------------------------------------------------------------------
# Minimal mock version graph
# ---------------------------------------------------------------------------


class _MockVersionGraph:
    def __init__(
        self, valid_docs: list[str], superseded_map: dict[str, bool] | None = None
    ) -> None:
        self._valid = set(valid_docs)
        self._superseded = superseded_map or {}

    def get_valid_documents(self, query_date: str) -> list[str]:
        return list(self._valid)

    def is_superseded_by(self, document_id: str, query_date: str) -> bool:
        return self._superseded.get(document_id, False)


def _make_chunk(doc_id: str, effective_date: str | None = "2020-01-01") -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}-ch-0000",
        document_id=doc_id,
        text="Sample text.",
        token_count=3,
        chunk_index=0,
        effective_date=effective_date,
    )


def _make_candidate(doc_id: str, effective_date: str | None = "2020-01-01") -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=f"{doc_id}-ch-0000",
        bm25_score=1.0,
        bm25_rank=1,
        chunk=_make_chunk(doc_id, effective_date),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_filter_accepts_valid_document() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-a"])
    filt = TemporalFilter(graph)
    cand = _make_candidate("doc-a")
    result = filt.apply([cand], "2024-01-01")
    assert len(result.accepted) == 1
    assert len(result.rejected) == 0


def test_filter_rejects_superseded_document() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-b"])
    filt = TemporalFilter(graph)
    cand = _make_candidate("doc-a")  # doc-a is NOT in valid_docs
    result = filt.apply([cand], "2024-01-01")
    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].temporal_filter_rejected is True
    assert result.rejected[0].rejection_reason == "superseded"


def test_filter_rejects_not_yet_effective() -> None:
    graph = _MockVersionGraph(valid_docs=[])  # nothing valid
    filt = TemporalFilter(graph)
    # effective_date is in the future relative to query_date
    cand = _make_candidate("doc-x", effective_date="2025-01-01")
    result = filt.apply([cand], "2024-01-01")
    assert len(result.rejected) == 1
    assert result.rejected[0].rejection_reason == "not_yet_effective"


def test_filter_accepts_candidate_without_doc_id() -> None:
    graph = _MockVersionGraph(valid_docs=[])
    filt = TemporalFilter(graph)
    # Candidate with no chunk — cannot determine validity
    cand = RetrievalCandidate(chunk_id="orphan-ch-0000", bm25_score=1.0, bm25_rank=1)
    result = filt.apply([cand], "2024-01-01")
    assert len(result.accepted) == 1


def test_filter_empty_candidates() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-a"])
    filt = TemporalFilter(graph)
    result = filt.apply([], "2024-01-01")
    assert result.accepted == []
    assert result.rejected == []


def test_filter_preserves_accepted_candidate_fields() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-a"])
    filt = TemporalFilter(graph)
    cand = _make_candidate("doc-a")
    result = filt.apply([cand], "2024-01-01")
    accepted = result.accepted[0]
    assert accepted.bm25_score == 1.0
    assert accepted.bm25_rank == 1


def test_filter_mixed_accepted_and_rejected() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-valid"])
    filt = TemporalFilter(graph)
    candidates = [
        _make_candidate("doc-valid"),
        _make_candidate("doc-old"),
    ]
    result = filt.apply(candidates, "2024-01-01")
    assert len(result.accepted) == 1
    assert len(result.rejected) == 1
    assert result.accepted[0].chunk_id == "doc-valid-ch-0000"


def test_filter_result_is_temporal_filter_result() -> None:
    graph = _MockVersionGraph(valid_docs=["doc-a"])
    filt = TemporalFilter(graph)
    result = filt.apply([], "2024-01-01")
    assert isinstance(result, TemporalFilterResult)
