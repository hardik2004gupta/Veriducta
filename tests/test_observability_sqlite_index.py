"""Tests for observability.sqlite_index - EvidenceIndex."""

from collections.abc import Generator
from pathlib import Path

import pytest

from observability.sqlite_index import EvidenceIndex, IndexEntry


@pytest.fixture()
def index(tmp_path: Path) -> Generator[EvidenceIndex, None, None]:
    idx = EvidenceIndex(tmp_path / "test_index.db")
    yield idx
    idx.close()


def _make_entry(
    trace_id: str = "t1",
    log_file: str = "2024-01-01.jsonl",
    byte_offset: int = 0,
    created_at: str = "2024-01-01T10:00:00+00:00",
    pipeline_stage: str = "pipeline",
    retrieval_trace_id: str = "",
    generation_trace_id: str = "",
    query_hash: str = "",
    request_id: str = "",
    latency_ms: float | None = None,
    quality_score: float | None = None,
    failure_flag: bool = False,
    verified: bool = False,
) -> IndexEntry:
    return IndexEntry(
        trace_id=trace_id,
        log_file=log_file,
        byte_offset=byte_offset,
        created_at=created_at,
        pipeline_stage=pipeline_stage,
        retrieval_trace_id=retrieval_trace_id,
        generation_trace_id=generation_trace_id,
        query_hash=query_hash,
        request_id=request_id,
        latency_ms=latency_ms,
        quality_score=quality_score,
        failure_flag=failure_flag,
        verified=verified,
    )


def test_insert_and_lookup_roundtrip(index: EvidenceIndex) -> None:
    entry = _make_entry(trace_id="abc-123", byte_offset=512)
    index.insert(entry)
    found = index.lookup("abc-123")
    assert found is not None
    assert found.trace_id == "abc-123"
    assert found.byte_offset == 512


def test_lookup_returns_none_for_missing_trace(index: EvidenceIndex) -> None:
    assert index.lookup("nonexistent") is None


def test_insert_or_replace_updates_existing(index: EvidenceIndex) -> None:
    entry = _make_entry(trace_id="dup", byte_offset=0)
    index.insert(entry)
    updated = _make_entry(trace_id="dup", byte_offset=999, quality_score=0.9)
    index.insert(updated)
    found = index.lookup("dup")
    assert found is not None
    assert found.byte_offset == 999
    assert found.quality_score == pytest.approx(0.9)


def test_delete_removes_entry(index: EvidenceIndex) -> None:
    entry = _make_entry(trace_id="del-me")
    index.insert(entry)
    index.delete("del-me")
    assert index.lookup("del-me") is None


def test_delete_nonexistent_is_silent(index: EvidenceIndex) -> None:
    index.delete("never-existed")  # must not raise


def test_count_reflects_insertions(index: EvidenceIndex) -> None:
    assert index.count() == 0
    index.insert(_make_entry("x1"))
    index.insert(_make_entry("x2"))
    assert index.count() == 2


def test_search_by_query_hash_returns_matching_entries(index: EvidenceIndex) -> None:
    index.insert(_make_entry("q1", query_hash="hash-abc"))
    index.insert(_make_entry("q2", query_hash="hash-abc"))
    index.insert(_make_entry("q3", query_hash="hash-xyz"))

    results = index.search_by_query_hash("hash-abc")
    trace_ids = {r.trace_id for r in results}
    assert trace_ids == {"q1", "q2"}


def test_search_by_query_hash_respects_limit(index: EvidenceIndex) -> None:
    for i in range(5):
        index.insert(_make_entry(f"lim-{i}", query_hash="same"))
    results = index.search_by_query_hash("same", limit=3)
    assert len(results) == 3


def test_search_by_date_prefix(index: EvidenceIndex) -> None:
    index.insert(_make_entry("d1", created_at="2024-01-15T10:00:00+00:00"))
    index.insert(_make_entry("d2", created_at="2024-01-16T10:00:00+00:00"))
    index.insert(_make_entry("d3", created_at="2024-02-01T10:00:00+00:00"))

    jan_results = index.search_by_date("2024-01")
    jan_ids = {r.trace_id for r in jan_results}
    assert "d1" in jan_ids
    assert "d2" in jan_ids
    assert "d3" not in jan_ids


def test_list_recent_returns_newest_first(index: EvidenceIndex) -> None:
    index.insert(_make_entry("r1", created_at="2024-01-01T09:00:00+00:00"))
    index.insert(_make_entry("r2", created_at="2024-01-01T11:00:00+00:00"))
    index.insert(_make_entry("r3", created_at="2024-01-01T10:00:00+00:00"))

    results = index.list_recent(limit=10)
    ids = [r.trace_id for r in results]
    assert ids.index("r2") < ids.index("r3") < ids.index("r1")


def test_list_recent_respects_limit(index: EvidenceIndex) -> None:
    for i in range(10):
        index.insert(_make_entry(f"rec-{i}"))
    assert len(index.list_recent(limit=4)) == 4


def test_entry_optional_fields_stored_and_retrieved(index: EvidenceIndex) -> None:
    entry = _make_entry(
        trace_id="full",
        retrieval_trace_id="r-trace",
        generation_trace_id="g-trace",
        query_hash="qhash",
        request_id="req-id",
        latency_ms=123.45,
        quality_score=0.75,
        failure_flag=True,
        verified=True,
    )
    index.insert(entry)
    found = index.lookup("full")
    assert found is not None
    assert found.retrieval_trace_id == "r-trace"
    assert found.generation_trace_id == "g-trace"
    assert found.query_hash == "qhash"
    assert found.request_id == "req-id"
    assert found.latency_ms == pytest.approx(123.45)
    assert found.quality_score == pytest.approx(0.75)
    assert found.failure_flag is True
    assert found.verified is True


def test_index_created_in_nested_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c" / "index.db"
    idx = EvidenceIndex(nested)
    idx.insert(_make_entry("nested-ok"))
    assert idx.count() == 1
    idx.close()
