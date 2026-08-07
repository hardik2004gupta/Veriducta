"""Tests for generation/trace.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import NotFoundError
from generation.trace import GenerationTraceWriter
from schemas.models import GenerationTrace


def _make_trace(
    trace_id: str = "trace-001", retrieval_trace_id: str = "ret-001"
) -> GenerationTrace:
    return GenerationTrace(
        trace_id=trace_id,
        retrieval_trace_id=retrieval_trace_id,
        query="What is the safety standard?",
        structured_answer={"answer": "test"},
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=0.001,
        generation_latency_ms=1200.0,
        schema_validation_attempts=1,
        config_hash="abc123",
    )


def test_write_and_get(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    trace = _make_trace()
    writer.write(trace)
    retrieved = writer.get(trace.trace_id)
    assert retrieved.trace_id == trace.trace_id
    assert retrieved.query == trace.query


def test_get_unknown_raises_not_found(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    with pytest.raises(NotFoundError):
        writer.get("nonexistent-trace")


def test_get_or_none_returns_none_for_unknown(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    assert writer.get_or_none("nonexistent") is None


def test_get_or_none_returns_trace_after_write(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    trace = _make_trace()
    writer.write(trace)
    result = writer.get_or_none(trace.trace_id)
    assert result is not None
    assert result.trace_id == trace.trace_id


def test_trace_count_increments(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    assert writer.trace_count == 0
    writer.write(_make_trace("t1"))
    writer.write(_make_trace("t2"))
    assert writer.trace_count == 2


def test_write_creates_jsonl_file(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    writer.write(_make_trace())
    jsonl_files = list(tmp_path.glob("*.jsonl"))
    assert len(jsonl_files) == 1
    content = jsonl_files[0].read_text(encoding="utf-8")
    assert "trace-001" in content


def test_write_appends_to_existing_file(tmp_path: Path) -> None:
    writer = GenerationTraceWriter(log_dir=tmp_path)
    writer.write(_make_trace("t1"))
    writer.write(_make_trace("t2"))
    jsonl_files = list(tmp_path.glob("*.jsonl"))
    lines = jsonl_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_log_dir_created_if_absent(tmp_path: Path) -> None:
    nested_dir = tmp_path / "nested" / "dir"
    writer = GenerationTraceWriter(log_dir=nested_dir)
    assert nested_dir.exists()
    _ = writer.trace_count  # confirm object is usable
