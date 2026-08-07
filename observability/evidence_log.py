"""Append-only JSONL evidence log with thread-safe writing and O(1) lookup.

Every retrieval, generation, and pipeline trace is appended to a daily JSONL
file and simultaneously registered in the :class:`EvidenceIndex` SQLite
database so any trace can be retrieved in O(1) via a byte-offset seek.

Storage layout::

    evidence_logs/
        2024-01-15.jsonl          ← active file for today
        2024-01-14.jsonl.gz       ← compressed yesterday
        index.db                  ← SQLite byte-offset index
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import IO, Any

import orjson
import structlog

from observability.rotation import LogRotator
from observability.sqlite_index import EvidenceIndex, IndexEntry
from schemas.models import GenerationTrace, PipelineTrace, RetrievalTrace
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


class EvidenceLogWriter:
    """Thread-safe, append-only JSONL evidence log backed by an SQLite index.

    Instances are process-scoped singletons - one per application process.

    Args:
        log_dir: Directory for JSONL and compressed log files.
        db_path: Path to the SQLite index database.
        max_size_bytes: Trigger intra-day file rotation when the active JSONL
                        reaches this size.  ``0`` disables size-based rotation.
    """

    def __init__(
        self,
        log_dir: str | Path,
        db_path: str | Path,
        max_size_bytes: int = 0,
    ) -> None:
        self._log_dir = Path(log_dir)
        ensure_dir(self._log_dir)
        self._rotator = LogRotator(self._log_dir, max_size_bytes=max_size_bytes)
        self._index = EvidenceIndex(db_path)
        self._lock = threading.Lock()
        self._fh: IO[bytes] | None = None
        self._current_path: Path | None = None

    # ------------------------------------------------------------------
    # Public write helpers
    # ------------------------------------------------------------------

    def write_retrieval_trace(self, trace: RetrievalTrace) -> int:
        """Append a :class:`RetrievalTrace` to the evidence log.

        Args:
            trace: The retrieval trace to persist.

        Returns:
            Byte offset at which the entry was written.
        """
        payload = {"type": "retrieval", "data": trace.model_dump(mode="json")}
        offset = self._append(payload)
        log_file = self._current_path.name if self._current_path else ""
        self._index.insert(
            IndexEntry(
                trace_id=trace.trace_id,
                log_file=log_file,
                byte_offset=offset,
                created_at=trace.created_at.isoformat(),
                pipeline_stage="retrieval",
                latency_ms=trace.latency_ms,
            )
        )
        logger.debug("retrieval_trace_written", trace_id=trace.trace_id, offset=offset)
        return offset

    def write_generation_trace(self, trace: GenerationTrace) -> int:
        """Append a :class:`GenerationTrace` to the evidence log.

        Args:
            trace: The generation trace to persist.

        Returns:
            Byte offset at which the entry was written.
        """
        payload = {"type": "generation", "data": trace.model_dump(mode="json")}
        offset = self._append(payload)
        log_file = self._current_path.name if self._current_path else ""
        self._index.insert(
            IndexEntry(
                trace_id=trace.trace_id,
                retrieval_trace_id=trace.retrieval_trace_id,
                log_file=log_file,
                byte_offset=offset,
                created_at=trace.created_at.isoformat(),
                pipeline_stage="generation",
                latency_ms=trace.generation_latency_ms,
            )
        )
        logger.debug("generation_trace_written", trace_id=trace.trace_id, offset=offset)
        return offset

    def write_pipeline_trace(self, trace: PipelineTrace) -> int:
        """Append a :class:`PipelineTrace` to the evidence log.

        Args:
            trace: The unified pipeline trace to persist.

        Returns:
            Byte offset at which the entry was written.
        """
        payload = {"type": "pipeline", "data": trace.model_dump(mode="json")}
        offset = self._append(payload)
        log_file = self._current_path.name if self._current_path else ""
        self._index.insert(
            IndexEntry(
                trace_id=trace.pipeline_trace_id,
                retrieval_trace_id=trace.retrieval_trace_id,
                generation_trace_id=trace.generation_trace_id,
                query_hash=trace.query_hash,
                request_id=trace.request_id,
                log_file=log_file,
                byte_offset=offset,
                created_at=trace.created_at.isoformat(),
                pipeline_stage="pipeline",
                latency_ms=trace.total_latency_ms,
                quality_score=trace.quality_score,
                failure_flag=trace.requires_expert_review,
            )
        )
        logger.debug(
            "pipeline_trace_written",
            trace_id=trace.pipeline_trace_id,
            offset=offset,
        )
        return offset

    # ------------------------------------------------------------------
    # Public read helpers
    # ------------------------------------------------------------------

    def read_line(self, log_file: str, byte_offset: int) -> dict[str, Any]:
        """Read a single JSONL entry at the given byte offset.

        Supports both ``.jsonl`` (direct seek) and ``.jsonl.gz`` (sequential
        scan to offset - O(N) for historical compressed files).

        Args:
            log_file: Filename (not full path) of the JSONL or gzip file.
            byte_offset: Byte position returned when the entry was written.

        Returns:
            Deserialized JSON dict.

        Raises:
            FileNotFoundError: If neither the plain nor compressed file exists.
            ValueError: If the byte offset does not point to valid JSON.
        """
        plain = self._log_dir / log_file
        gz = self._log_dir / (log_file + ".gz")

        if plain.exists():
            return _seek_plain(plain, byte_offset)
        if gz.exists():
            return _scan_gz(gz, byte_offset)
        raise FileNotFoundError(f"Evidence log not found: {log_file}")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def compress_stale_logs(self) -> list[Path]:
        """Compress all JSONL files from previous days.

        Returns:
            List of newly created ``.jsonl.gz`` files.
        """
        return self._rotator.compress_stale()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def index(self) -> EvidenceIndex:
        """Return the :class:`EvidenceIndex` for direct queries."""
        return self._index

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, payload: dict[str, Any]) -> int:
        """Serialize *payload* as JSON and append it to the active JSONL file.

        Args:
            payload: Dict to serialize.

        Returns:
            Byte offset where the entry starts (position BEFORE the write).
        """
        encoded = orjson.dumps(payload) + b"\n"
        with self._lock:
            self._ensure_file_open()
            assert self._fh is not None
            if self._rotator.should_rotate():
                self._rotate()
            offset = self._fh.tell()
            self._fh.write(encoded)
            self._fh.flush()
        return offset

    def _ensure_file_open(self) -> None:
        """Open the active log file if not already open or if it changed."""
        active = self._rotator.active_path()
        if self._fh is None or self._current_path != active:
            if self._fh is not None:
                self._fh.close()
            self._fh = active.open("ab")
            self._current_path = active

    def _rotate(self) -> None:
        """Perform intra-day size-based rotation."""
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        self._rotator.rotate_active()
        active = self._rotator.active_path()
        self._fh = active.open("ab")
        self._current_path = active
        logger.info("log_rotated", new_file=active.name)

    def close(self) -> None:
        """Flush and close the active log file and SQLite connection."""
        with self._lock:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
        self._index.close()


# ---------------------------------------------------------------------------
# Low-level file readers
# ---------------------------------------------------------------------------


def _seek_plain(path: Path, offset: int) -> dict[str, Any]:
    """Seek directly to *offset* in *path* and read one JSONL line.

    Args:
        path: Path to a ``.jsonl`` file.
        offset: Byte position of the desired entry.

    Returns:
        Deserialized dict.

    Raises:
        ValueError: If the line at the offset is not valid JSON.
    """
    with path.open("rb") as fh:
        fh.seek(offset)
        line = fh.readline()
    if not line:
        raise ValueError(f"No data at offset {offset} in {path.name}")
    result: dict[str, Any] = orjson.loads(line)
    return result


def _scan_gz(path: Path, offset: int) -> dict[str, Any]:
    """Scan a gzip-compressed JSONL file to find the entry at *offset*.

    Compressed files do not support random access, so we must read
    sequentially until we reach the accumulated byte position.

    Args:
        path: Path to a ``.jsonl.gz`` file.
        offset: Byte offset in the original (uncompressed) file.

    Returns:
        Deserialized dict.

    Raises:
        ValueError: If the offset is not found in the compressed file.
    """
    import gzip

    accumulated = 0
    with gzip.open(path, "rb") as fh:
        for raw_line in fh:
            if accumulated == offset:
                result: dict[str, Any] = orjson.loads(raw_line)
                return result
            accumulated += len(raw_line)
    raise ValueError(f"Offset {offset} not found in compressed log {path.name}")
