"""High-level trace store API wrapping EvidenceLogWriter and EvidenceIndex.

``TraceStore`` is the single entrypoint for all evidence log operations from
pipeline code.  It wires together the log writer and the SQLite index so
callers do not need to manage either directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from core.exceptions import NotFoundError
from observability.evidence_log import EvidenceLogWriter
from observability.sqlite_index import EvidenceIndex, IndexEntry
from schemas.models import GenerationTrace, PipelineTrace, RetrievalTrace

logger = structlog.get_logger(__name__)


class TraceStore:
    """Unified store for pipeline traces backed by JSONL and SQLite.

    Provides O(1) retrieval by trace ID via SQLite byte-offset lookup.

    Args:
        log_dir: Directory for JSONL evidence log files.
        db_path: Path to the SQLite index database.
        max_size_bytes: Intra-day file rotation threshold. ``0`` disables.
    """

    def __init__(
        self,
        log_dir: str | Path,
        db_path: str | Path,
        max_size_bytes: int = 0,
    ) -> None:
        self._writer = EvidenceLogWriter(
            log_dir=log_dir,
            db_path=db_path,
            max_size_bytes=max_size_bytes,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def write_retrieval_trace(self, trace: RetrievalTrace) -> None:
        """Persist *trace* to the evidence log and index.

        Args:
            trace: :class:`RetrievalTrace` produced by the retrieval pipeline.
        """
        self._writer.write_retrieval_trace(trace)
        logger.info("retrieval_trace_stored", trace_id=trace.trace_id)

    def write_generation_trace(self, trace: GenerationTrace) -> None:
        """Persist *trace* to the evidence log and index.

        Args:
            trace: :class:`GenerationTrace` produced by the generation pipeline.
        """
        self._writer.write_generation_trace(trace)
        logger.info("generation_trace_stored", trace_id=trace.trace_id)

    def write_pipeline_trace(self, trace: PipelineTrace) -> None:
        """Persist *trace* to the evidence log and index.

        Args:
            trace: Unified :class:`PipelineTrace` for a complete query run.
        """
        self._writer.write_pipeline_trace(trace)
        logger.info("pipeline_trace_stored", trace_id=trace.pipeline_trace_id)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def find_trace(self, trace_id: str) -> IndexEntry | None:
        """Return the :class:`IndexEntry` for *trace_id*, or None.

        Args:
            trace_id: UUID string identifying the trace.
        """
        return self._writer.index.lookup(trace_id)

    def load_trace(self, trace_id: str) -> dict[str, Any]:
        """Load the full JSON payload for *trace_id* from the evidence log.

        Args:
            trace_id: UUID string identifying the trace.

        Returns:
            Deserialized JSON dict with ``type`` and ``data`` keys.

        Raises:
            NotFoundError: If the trace ID is not in the index.
        """
        entry = self._writer.index.lookup(trace_id)
        if entry is None:
            raise NotFoundError(resource="trace", identifier=trace_id)
        return self._writer.read_line(entry.log_file, entry.byte_offset)

    def read_retrieval_trace(self, trace_id: str) -> RetrievalTrace:
        """Load and deserialize a :class:`RetrievalTrace`.

        Args:
            trace_id: UUID string identifying the retrieval trace.

        Returns:
            Deserialized :class:`RetrievalTrace`.

        Raises:
            NotFoundError: If no trace with the given ID exists.
            ValueError: If the stored entry is not a retrieval trace.
        """
        payload = self.load_trace(trace_id)
        trace_type = payload.get("type")
        if trace_type != "retrieval":
            raise ValueError(f"Trace {trace_id!r} has type {trace_type!r}, expected 'retrieval'")
        return RetrievalTrace.model_validate(payload["data"])

    def read_generation_trace(self, trace_id: str) -> GenerationTrace:
        """Load and deserialize a :class:`GenerationTrace`.

        Args:
            trace_id: UUID string identifying the generation trace.

        Returns:
            Deserialized :class:`GenerationTrace`.

        Raises:
            NotFoundError: If no trace with the given ID exists.
            ValueError: If the stored entry is not a generation trace.
        """
        payload = self.load_trace(trace_id)
        trace_type = payload.get("type")
        if trace_type != "generation":
            raise ValueError(f"Trace {trace_id!r} has type {trace_type!r}, expected 'generation'")
        return GenerationTrace.model_validate(payload["data"])

    def read_pipeline_trace(self, trace_id: str) -> PipelineTrace:
        """Load and deserialize a :class:`PipelineTrace`.

        Args:
            trace_id: UUID string identifying the pipeline trace.

        Returns:
            Deserialized :class:`PipelineTrace`.

        Raises:
            NotFoundError: If no trace with the given ID exists.
            ValueError: If the stored entry is not a pipeline trace.
        """
        payload = self.load_trace(trace_id)
        trace_type = payload.get("type")
        if trace_type != "pipeline":
            raise ValueError(f"Trace {trace_id!r} has type {trace_type!r}, expected 'pipeline'")
        return PipelineTrace.model_validate(payload["data"])

    # ------------------------------------------------------------------
    # Search operations
    # ------------------------------------------------------------------

    def search_by_hash(self, query_hash: str, limit: int = 50) -> list[IndexEntry]:
        """Return up to *limit* entries matching *query_hash*, newest first.

        Args:
            query_hash: SHA-256 hash of the query string.
            limit: Maximum number of results.
        """
        return self._writer.index.search_by_query_hash(query_hash, limit=limit)

    def search_by_date(self, date_prefix: str, limit: int = 100) -> list[IndexEntry]:
        """Return entries whose ``created_at`` starts with *date_prefix*.

        Args:
            date_prefix: ISO-8601 date prefix, e.g. ``"2024-01-15"``.
            limit: Maximum number of results.
        """
        return self._writer.index.search_by_date(date_prefix, limit=limit)

    def list_traces(self, limit: int = 100) -> list[IndexEntry]:
        """Return the *limit* most recently written index entries.

        Args:
            limit: Maximum number of results.
        """
        return self._writer.index.list_recent(limit=limit)

    def delete_trace(self, trace_id: str) -> None:
        """Remove a trace from the SQLite index.

        Does NOT modify the JSONL files (the log is append-only).

        Args:
            trace_id: UUID string of the trace to de-index.
        """
        self._writer.index.delete(trace_id)
        logger.info("trace_de_indexed", trace_id=trace_id)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def compress_stale_logs(self) -> list[Path]:
        """Compress JSONL files from previous days.

        Returns:
            List of newly created ``.jsonl.gz`` paths.
        """
        return self._writer.compress_stale_logs()

    # ------------------------------------------------------------------
    # Internal access for tests
    # ------------------------------------------------------------------

    @property
    def index(self) -> EvidenceIndex:
        """Return the underlying :class:`EvidenceIndex`."""
        return self._writer.index

    def close(self) -> None:
        """Flush, close the log file and SQLite connection."""
        self._writer.close()
