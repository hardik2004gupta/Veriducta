"""Tests for observability.evidence_log — EvidenceLogWriter."""

import gzip
from collections.abc import Generator
from pathlib import Path

import orjson
import pytest

from observability.evidence_log import EvidenceLogWriter
from schemas.models import GenerationTrace, PipelineTrace, RetrievalTrace


@pytest.fixture()
def writer(tmp_path: Path) -> Generator[EvidenceLogWriter, None, None]:
    w = EvidenceLogWriter(
        log_dir=tmp_path / "logs",
        db_path=tmp_path / "index.db",
    )
    yield w
    w.close()


def _make_retrieval_trace(**kwargs: object) -> RetrievalTrace:
    defaults: dict[str, object] = {"query": "What is a fault?", "query_date": "2024-01-15"}
    defaults.update(kwargs)
    return RetrievalTrace.model_validate(defaults)


def _make_generation_trace(retrieval_trace_id: str = "rt-001", **kwargs: object) -> GenerationTrace:
    defaults: dict[str, object] = {
        "retrieval_trace_id": retrieval_trace_id,
        "query": "What is a fault?",
    }
    defaults.update(kwargs)
    return GenerationTrace.model_validate(defaults)


def _make_pipeline_trace(**kwargs: object) -> PipelineTrace:
    defaults: dict[str, object] = {"query": "What is a fault?"}
    defaults.update(kwargs)
    return PipelineTrace.model_validate(defaults)


# ---------------------------------------------------------------------------
# Write and index round-trips
# ---------------------------------------------------------------------------


def test_write_retrieval_trace_creates_jsonl(writer: EvidenceLogWriter, tmp_path: Path) -> None:
    trace = _make_retrieval_trace()
    writer.write_retrieval_trace(trace)

    log_files = list((tmp_path / "logs").glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_bytes().splitlines()
    assert len(lines) == 1
    payload = orjson.loads(lines[0])
    assert payload["type"] == "retrieval"
    assert payload["data"]["trace_id"] == trace.trace_id


def test_write_generation_trace_indexed(writer: EvidenceLogWriter) -> None:
    gt = _make_generation_trace()
    writer.write_generation_trace(gt)

    entry = writer.index.lookup(gt.trace_id)
    assert entry is not None
    assert entry.pipeline_stage == "generation"
    assert entry.retrieval_trace_id == gt.retrieval_trace_id


def test_write_pipeline_trace_indexed(writer: EvidenceLogWriter) -> None:
    pt = _make_pipeline_trace(query_hash="qh-abc", request_id="r-001", quality_score=0.8)
    writer.write_pipeline_trace(pt)

    entry = writer.index.lookup(pt.pipeline_trace_id)
    assert entry is not None
    assert entry.pipeline_stage == "pipeline"
    assert entry.query_hash == "qh-abc"
    assert entry.quality_score == pytest.approx(0.8)


def test_multiple_writes_accumulate_in_same_file(writer: EvidenceLogWriter, tmp_path: Path) -> None:
    for i in range(5):
        writer.write_retrieval_trace(_make_retrieval_trace(query=f"query-{i}"))

    log_files = list((tmp_path / "logs").glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_bytes().splitlines()
    assert len(lines) == 5


# ---------------------------------------------------------------------------
# read_line round-trip
# ---------------------------------------------------------------------------


def test_read_line_retrieves_correct_entry(writer: EvidenceLogWriter, tmp_path: Path) -> None:
    t1 = _make_retrieval_trace(query="first")
    t2 = _make_retrieval_trace(query="second")
    writer.write_retrieval_trace(t1)
    writer.write_retrieval_trace(t2)

    e1 = writer.index.lookup(t1.trace_id)
    e2 = writer.index.lookup(t2.trace_id)
    assert e1 is not None and e2 is not None

    payload1 = writer.read_line(e1.log_file, e1.byte_offset)
    payload2 = writer.read_line(e2.log_file, e2.byte_offset)

    assert payload1["data"]["query"] == "first"
    assert payload2["data"]["query"] == "second"


def test_read_line_from_compressed_file(tmp_path: Path) -> None:
    # Use a dedicated writer so we can close it (releasing the file lock)
    # before manually compressing the JSONL — required on Windows.
    log_dir = tmp_path / "logs2"
    w = EvidenceLogWriter(log_dir=log_dir, db_path=tmp_path / "index2.db")
    trace = _make_retrieval_trace(query="archived")
    w.write_retrieval_trace(trace)
    entry = w.index.lookup(trace.trace_id)
    assert entry is not None
    log_file_name = entry.log_file
    byte_offset = entry.byte_offset
    w.close()  # release the open file handle before compressing

    plain = log_dir / log_file_name
    gz = log_dir / (log_file_name + ".gz")
    with plain.open("rb") as src, gzip.open(gz, "wb") as dst:
        dst.write(src.read())
    plain.unlink()

    # Re-open to call read_line
    w2 = EvidenceLogWriter(log_dir=log_dir, db_path=tmp_path / "index2.db")
    payload = w2.read_line(log_file_name, byte_offset)
    w2.close()
    assert payload["data"]["query"] == "archived"


def test_read_line_raises_for_missing_file(writer: EvidenceLogWriter) -> None:
    with pytest.raises(FileNotFoundError):
        writer.read_line("9999-99-99.jsonl", 0)


# ---------------------------------------------------------------------------
# Size-based rotation
# ---------------------------------------------------------------------------


def test_size_based_rotation_creates_sequence_files(tmp_path: Path) -> None:
    size_writer = EvidenceLogWriter(
        log_dir=tmp_path / "logs",
        db_path=tmp_path / "index.db",
        max_size_bytes=1,  # 1 byte triggers rotation after first write
    )
    size_writer.write_retrieval_trace(_make_retrieval_trace(query="first"))
    size_writer.write_retrieval_trace(_make_retrieval_trace(query="second"))
    size_writer.close()

    log_files = list((tmp_path / "logs").glob("*.jsonl"))
    assert len(log_files) >= 2


# ---------------------------------------------------------------------------
# compress_stale_logs
# ---------------------------------------------------------------------------


def test_compress_stale_logs_compresses_old_file(writer: EvidenceLogWriter, tmp_path: Path) -> None:
    old = tmp_path / "logs" / "2000-01-01.jsonl"
    old.write_bytes(b'{"old": true}\n')

    compressed = writer.compress_stale_logs()
    assert any("2000-01-01" in str(p) for p in compressed)
    assert not old.exists()
