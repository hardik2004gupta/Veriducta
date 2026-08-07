"""Tests for observability.trace_store - TraceStore."""

from collections.abc import Generator
from pathlib import Path

import pytest

from core.exceptions import NotFoundError
from observability.trace_store import TraceStore
from schemas.models import GenerationTrace, PipelineTrace, RetrievalTrace


@pytest.fixture()
def store(tmp_path: Path) -> Generator[TraceStore, None, None]:
    s = TraceStore(
        log_dir=tmp_path / "logs",
        db_path=tmp_path / "index.db",
    )
    yield s
    s.close()


def _retrieval_trace(query: str = "test query") -> RetrievalTrace:
    return RetrievalTrace(query=query, query_date="2024-01-15")


def _generation_trace(retrieval_trace_id: str = "rt-001") -> GenerationTrace:
    return GenerationTrace(retrieval_trace_id=retrieval_trace_id, query="test query")


def _pipeline_trace(**kwargs: object) -> PipelineTrace:
    return PipelineTrace(query="test query", **kwargs)


# ---------------------------------------------------------------------------
# Write round-trips
# ---------------------------------------------------------------------------


def test_write_and_find_retrieval_trace(store: TraceStore) -> None:
    rt = _retrieval_trace()
    store.write_retrieval_trace(rt)
    entry = store.find_trace(rt.trace_id)
    assert entry is not None
    assert entry.trace_id == rt.trace_id
    assert entry.pipeline_stage == "retrieval"


def test_write_and_load_retrieval_trace(store: TraceStore) -> None:
    rt = _retrieval_trace(query="fault mechanism")
    store.write_retrieval_trace(rt)
    loaded = store.read_retrieval_trace(rt.trace_id)
    assert loaded.query == "fault mechanism"
    assert loaded.trace_id == rt.trace_id


def test_write_and_load_generation_trace(store: TraceStore) -> None:
    gt = _generation_trace(retrieval_trace_id="rt-999")
    store.write_generation_trace(gt)
    loaded = store.read_generation_trace(gt.trace_id)
    assert loaded.retrieval_trace_id == "rt-999"


def test_write_and_load_pipeline_trace(store: TraceStore) -> None:
    pt = _pipeline_trace(query_hash="qh123", quality_score=0.85)
    store.write_pipeline_trace(pt)
    loaded = store.read_pipeline_trace(pt.pipeline_trace_id)
    assert loaded.query_hash == "qh123"
    assert loaded.quality_score == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Not-found errors
# ---------------------------------------------------------------------------


def test_find_trace_returns_none_for_missing(store: TraceStore) -> None:
    assert store.find_trace("does-not-exist") is None


def test_load_trace_raises_not_found_for_missing(store: TraceStore) -> None:
    with pytest.raises(NotFoundError):
        store.load_trace("does-not-exist")


def test_read_retrieval_trace_raises_not_found_for_missing(store: TraceStore) -> None:
    with pytest.raises(NotFoundError):
        store.read_retrieval_trace("missing")


# ---------------------------------------------------------------------------
# Type mismatch errors
# ---------------------------------------------------------------------------


def test_read_retrieval_trace_raises_value_error_for_wrong_type(store: TraceStore) -> None:
    gt = _generation_trace()
    store.write_generation_trace(gt)
    with pytest.raises(ValueError, match="generation"):
        store.read_retrieval_trace(gt.trace_id)


def test_read_generation_trace_raises_value_error_for_wrong_type(store: TraceStore) -> None:
    rt = _retrieval_trace()
    store.write_retrieval_trace(rt)
    with pytest.raises(ValueError, match="retrieval"):
        store.read_generation_trace(rt.trace_id)


# ---------------------------------------------------------------------------
# Search operations
# ---------------------------------------------------------------------------


def test_search_by_hash_returns_matching_traces(store: TraceStore) -> None:
    pt1 = PipelineTrace(query="q1", query_hash="hash-abc")
    pt2 = PipelineTrace(query="q2", query_hash="hash-abc")
    pt3 = PipelineTrace(query="q3", query_hash="hash-xyz")
    store.write_pipeline_trace(pt1)
    store.write_pipeline_trace(pt2)
    store.write_pipeline_trace(pt3)

    results = store.search_by_hash("hash-abc")
    trace_ids = {r.trace_id for r in results}
    assert pt1.pipeline_trace_id in trace_ids
    assert pt2.pipeline_trace_id in trace_ids
    assert pt3.pipeline_trace_id not in trace_ids


def test_search_by_date_returns_correct_subset(store: TraceStore) -> None:
    from datetime import UTC, datetime

    rt = _retrieval_trace()
    store.write_retrieval_trace(rt)
    year_prefix = str(datetime.now(UTC).year)
    results = store.search_by_date(year_prefix)
    assert len(results) >= 1


def test_list_traces_returns_all_entries(store: TraceStore) -> None:
    store.write_retrieval_trace(_retrieval_trace())
    store.write_generation_trace(_generation_trace())
    store.write_pipeline_trace(_pipeline_trace())
    entries = store.list_traces()
    assert len(entries) == 3


# ---------------------------------------------------------------------------
# Delete and maintenance
# ---------------------------------------------------------------------------


def test_delete_trace_removes_from_index(store: TraceStore) -> None:
    rt = _retrieval_trace()
    store.write_retrieval_trace(rt)
    assert store.find_trace(rt.trace_id) is not None
    store.delete_trace(rt.trace_id)
    assert store.find_trace(rt.trace_id) is None


def test_compress_stale_logs_returns_list(store: TraceStore, tmp_path: Path) -> None:
    old = tmp_path / "logs" / "2000-01-01.jsonl"
    old.write_bytes(b'{"old": true}\n')
    compressed = store.compress_stale_logs()
    assert isinstance(compressed, list)
    assert any("2000-01-01" in str(p) for p in compressed)
