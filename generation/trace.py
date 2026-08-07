"""Evidence log writer for generation traces.

Mirrors :mod:`retrieval.trace` in structure: appends
:class:`~schemas.models.GenerationTrace` objects to a daily JSONL file and
maintains an in-memory index for O(1) intra-process lookup.

When an :class:`~observability.evidence_log.EvidenceLogWriter` is supplied,
all writes are delegated to the fully instrumented Phase 14 implementation
(SQLite byte-offset index, thread-safe locking, gzip rotation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import structlog

from core.exceptions import NotFoundError
from schemas.models import GenerationTrace
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


class GenerationTraceWriter:
    """Appends GenerationTrace objects to a daily JSONL file.

    When *evidence_log* is provided, writes are also forwarded to the fully
    indexed :class:`~observability.evidence_log.EvidenceLogWriter`.

    Args:
        log_dir: Directory for JSONL evidence log files.  Created if absent.
        evidence_log: Optional Phase 14 evidence log writer.  When provided,
                      every trace is registered in the SQLite byte-offset index.
    """

    def __init__(
        self,
        log_dir: str | Path,
        evidence_log: object | None = None,
    ) -> None:
        self._log_dir = Path(log_dir)
        ensure_dir(self._log_dir)
        self._in_memory: dict[str, GenerationTrace] = {}
        self._evidence_log = evidence_log

    def write(self, trace: GenerationTrace) -> None:
        """Append *trace* to today's JSONL file and cache in memory.

        The log file is named ``YYYY-MM-DD.jsonl`` and opened in append mode.

        When an evidence log writer is configured, the trace is also delegated
        to it for SQLite indexing.

        Args:
            trace: Completed :class:`~schemas.models.GenerationTrace` to persist.
        """
        log_path = self._log_dir / f"{datetime.now(UTC).date().isoformat()}.jsonl"
        line = trace.model_dump_json() + "\n"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        self._in_memory[trace.trace_id] = trace
        logger.debug(
            "generation_trace_written",
            trace_id=trace.trace_id,
            retrieval_trace_id=trace.retrieval_trace_id,
            log_file=log_path.name,
        )
        if self._evidence_log is not None:
            self._evidence_log.write_generation_trace(trace)  # type: ignore[attr-defined]

    def get(self, trace_id: str) -> GenerationTrace:
        """Return the trace for *trace_id* from the in-memory cache.

        Args:
            trace_id: UUID string identifying the trace.

        Returns:
            :class:`~schemas.models.GenerationTrace`.

        Raises:
            NotFoundError: If the trace is not in the in-memory cache.
        """
        trace = self._in_memory.get(trace_id)
        if trace is None:
            raise NotFoundError("generation_trace", trace_id)
        return trace

    def get_or_none(self, trace_id: str) -> GenerationTrace | None:
        """Return the trace or ``None`` if not found.

        Args:
            trace_id: UUID string identifying the trace.
        """
        return self._in_memory.get(trace_id)

    @property
    def trace_count(self) -> int:
        """Number of traces held in the in-memory cache."""
        return len(self._in_memory)
