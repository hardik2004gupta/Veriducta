"""Tests for retrieval/trace.py."""

import json
from pathlib import Path

import pytest

from core.exceptions import NotFoundError
from retrieval.trace import RetrievalTraceWriter
from schemas.models import RetrievalTrace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trace(trace_id: str = "trace-001", query: str = "test query") -> RetrievalTrace:
    return RetrievalTrace(
        trace_id=trace_id,
        query=query,
        query_date="2024-01-01",
        bm25_top100=[],
        dense_top100=[],
        rrf_ranked=[],
        pre_rerank_top40=[],
        post_rerank_top8=[],
        parent_expansion_log=[],
        temporal_filter_log=[],
        config_hash="abc123",
        latency_ms=42.0,
    )


# ---------------------------------------------------------------------------
# write / get
# ---------------------------------------------------------------------------


def test_write_creates_jsonl_file(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    trace = _make_trace()
    writer.write(trace)
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1


def test_write_file_contains_valid_json(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    trace = _make_trace(trace_id="abc-001")
    writer.write(trace)
    content = next(iter(tmp_path.glob("*.jsonl"))).read_text(encoding="utf-8")
    parsed = json.loads(content.strip())
    assert parsed["trace_id"] == "abc-001"


def test_get_returns_written_trace(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    trace = _make_trace(trace_id="my-trace")
    writer.write(trace)
    retrieved = writer.get("my-trace")
    assert retrieved.trace_id == "my-trace"
    assert retrieved.query == "test query"


def test_get_missing_raises_not_found_error(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    with pytest.raises(NotFoundError):
        writer.get("nonexistent-trace-id")


def test_get_or_none_returns_trace(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    trace = _make_trace(trace_id="t1")
    writer.write(trace)
    result = writer.get_or_none("t1")
    assert result is not None
    assert result.trace_id == "t1"


def test_get_or_none_returns_none_for_missing(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    result = writer.get_or_none("does-not-exist")
    assert result is None


def test_trace_count_increments(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    assert writer.trace_count == 0
    writer.write(_make_trace("t1"))
    writer.write(_make_trace("t2"))
    assert writer.trace_count == 2


def test_write_multiple_traces_single_file(tmp_path: Path) -> None:
    writer = RetrievalTraceWriter(tmp_path)
    writer.write(_make_trace("t1"))
    writer.write(_make_trace("t2"))
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_write_appends_to_existing_file(tmp_path: Path) -> None:
    writer1 = RetrievalTraceWriter(tmp_path)
    writer1.write(_make_trace("t1"))

    # Second writer to same directory
    writer2 = RetrievalTraceWriter(tmp_path)
    writer2.write(_make_trace("t2"))

    files = list(tmp_path.glob("*.jsonl"))
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_log_dir_created_if_missing(tmp_path: Path) -> None:
    nested = tmp_path / "evidence_logs" / "sub"
    writer = RetrievalTraceWriter(nested)
    assert nested.exists()
    writer.write(_make_trace())
    assert writer.trace_count == 1
