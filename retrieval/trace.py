"""Evidence log writer for retrieval traces.

Appends :class:`~schemas.models.RetrievalTrace` objects to a daily JSONL
evidence log and maintains an in-process index for O(1) trace lookup.

The full SQLite-backed persistence layer (with byte-offset indexing for
cross-process lookup) is implemented in Phase 14 (observability/evidence_log.py).
This module provides the minimal writer and in-memory reader sufficient for
Phase 2 and integration testing.
"""

from datetime import UTC, datetime
from pathlib import Path

import structlog

from core.exceptions import NotFoundError
from schemas.models import RetrievalTrace
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


class RetrievalTraceWriter:
    """Appends RetrievalTrace objects to a daily JSONL file.

    Traces are also cached in memory for O(1) intra-process lookup via
    :meth:`get`.  The SQLite index that enables cross-process and cross-session
    trace retrieval is added in Phase 14.

    Args:
        log_dir: Directory for JSONL evidence log files.
    """

    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        ensure_dir(self._log_dir)
        self._in_memory: dict[str, RetrievalTrace] = {}

    def write(self, trace: RetrievalTrace) -> None:
        """Append *trace* to today's JSONL file and cache in memory.

        The log file is named ``YYYY-MM-DD.jsonl`` and opened in append mode.
        Each entry is a single JSON line terminated by ``\\n``.

        Args:
            trace: Completed :class:`~schemas.models.RetrievalTrace` to persist.
        """
        log_path = self._log_dir / f"{datetime.now(UTC).date().isoformat()}.jsonl"
        line = trace.model_dump_json() + "\n"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        self._in_memory[trace.trace_id] = trace
        logger.debug(
            "retrieval_trace_written",
            trace_id=trace.trace_id,
            log_file=log_path.name,
        )

    def get(self, trace_id: str) -> RetrievalTrace:
        """Return the trace for *trace_id* from the in-memory cache.

        Args:
            trace_id: UUID string identifying the trace.

        Returns:
            :class:`~schemas.models.RetrievalTrace`.

        Raises:
            NotFoundError: If the trace is not in the in-memory cache
                           (e.g. from a previous process run).
        """
        trace = self._in_memory.get(trace_id)
        if trace is None:
            raise NotFoundError("retrieval_trace", trace_id)
        return trace

    def get_or_none(self, trace_id: str) -> RetrievalTrace | None:
        """Return the trace or ``None`` if not found.

        Args:
            trace_id: UUID string identifying the trace.
        """
        return self._in_memory.get(trace_id)

    @property
    def trace_count(self) -> int:
        """Number of traces held in the in-memory cache."""
        return len(self._in_memory)
