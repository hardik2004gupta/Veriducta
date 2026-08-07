"""Evidence log writer for generation traces.

Mirrors :mod:`retrieval.trace` in structure: appends
:class:`~schemas.models.GenerationTrace` objects to a daily JSONL file and
maintains an in-memory index for O(1) intra-process lookup.

The full SQLite-backed persistence layer (with byte-offset indexing for
cross-process lookup) is implemented in Phase 14 (observability/evidence_log.py).
"""

from datetime import UTC, datetime
from pathlib import Path

import structlog

from core.exceptions import NotFoundError
from schemas.models import GenerationTrace
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


class GenerationTraceWriter:
    """Appends GenerationTrace objects to a daily JSONL file.

    Args:
        log_dir: Directory for JSONL evidence log files.  Created if absent.
    """

    def __init__(self, log_dir: str | Path) -> None:
        self._log_dir = Path(log_dir)
        ensure_dir(self._log_dir)
        self._in_memory: dict[str, GenerationTrace] = {}

    def write(self, trace: GenerationTrace) -> None:
        """Append *trace* to today's JSONL file and cache in memory.

        The log file is named ``YYYY-MM-DD.jsonl`` and opened in append mode.

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
