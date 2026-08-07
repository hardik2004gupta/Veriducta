"""Historical trace loading for the causal replay engine.

:class:`TraceLoader` is the single entry point for loading pipeline traces
from the evidence log. It wraps :class:`~observability.trace_store.TraceStore`
and adds optional golden QA annotation loading.

Golden annotations (supporting chunk IDs, expected root cause) are read from
``data/golden_qa.jsonl`` when available. If the file does not yet exist
(Phase 16 deliverable), annotation loading degrades gracefully by returning
``None`` rather than raising.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from core.exceptions import NotFoundError, ReplayError
from observability.trace_store import TraceStore
from schemas.models import GenerationTrace, PipelineTrace, RetrievalTrace, RootCauseStage

logger = structlog.get_logger(__name__)


class GoldenAnnotation:
    """Minimal golden QA annotation used by Stage 2 ablation.

    Attributes:
        question_id: Identifier matching the golden QA dataset.
        question_text: Original question text.
        supporting_chunk_ids: Chunk IDs known to contain the correct answer.
        expected_root_cause: Ground-truth root cause from annotators.
        difficulty: Difficulty label (``"easy"``, ``"medium"``, ``"hard"``).
    """

    def __init__(
        self,
        question_id: str,
        question_text: str,
        supporting_chunk_ids: list[str],
        expected_root_cause: RootCauseStage = RootCauseStage.UNKNOWN,
        difficulty: str = "medium",
    ) -> None:
        self.question_id = question_id
        self.question_text = question_text
        self.supporting_chunk_ids = supporting_chunk_ids
        self.expected_root_cause = expected_root_cause
        self.difficulty = difficulty


class TraceLoader:
    """Load historical pipeline traces and optional golden annotations.

    Args:
        store: The :class:`~observability.trace_store.TraceStore` backing the evidence log.
        golden_qa_path: Path to the golden QA JSONL file. ``None`` to skip annotation loading.
    """

    def __init__(
        self,
        store: TraceStore,
        golden_qa_path: str | Path | None = None,
    ) -> None:
        self._store = store
        self._golden_qa_path = Path(golden_qa_path) if golden_qa_path else None
        self._annotation_cache: dict[str, GoldenAnnotation] | None = None

    # ------------------------------------------------------------------
    # Trace loading
    # ------------------------------------------------------------------

    def load_pipeline_trace(self, trace_id: str) -> PipelineTrace:
        """Load a :class:`~schemas.models.PipelineTrace` by ID.

        Args:
            trace_id: UUID string of the pipeline trace.

        Returns:
            Deserialized :class:`~schemas.models.PipelineTrace`.

        Raises:
            ReplayError: If the trace is missing or not a pipeline trace.
        """
        try:
            return self._store.read_pipeline_trace(trace_id)
        except (NotFoundError, ValueError) as exc:
            raise ReplayError(
                message=f"Pipeline trace not found: {trace_id}",
                details={"trace_id": trace_id, "error": str(exc)},
            ) from exc

    def load_retrieval_trace(self, trace_id: str) -> RetrievalTrace:
        """Load a :class:`~schemas.models.RetrievalTrace` by ID.

        Args:
            trace_id: UUID string of the retrieval trace.

        Returns:
            Deserialized :class:`~schemas.models.RetrievalTrace`.

        Raises:
            ReplayError: If the trace is missing or not a retrieval trace.
        """
        try:
            return self._store.read_retrieval_trace(trace_id)
        except (NotFoundError, ValueError) as exc:
            raise ReplayError(
                message=f"Retrieval trace not found: {trace_id}",
                details={"trace_id": trace_id, "error": str(exc)},
            ) from exc

    def load_generation_trace(self, trace_id: str) -> GenerationTrace:
        """Load a :class:`~schemas.models.GenerationTrace` by ID.

        Args:
            trace_id: UUID string of the generation trace.

        Returns:
            Deserialized :class:`~schemas.models.GenerationTrace`.

        Raises:
            ReplayError: If the trace is missing or not a generation trace.
        """
        try:
            return self._store.read_generation_trace(trace_id)
        except (NotFoundError, ValueError) as exc:
            raise ReplayError(
                message=f"Generation trace not found: {trace_id}",
                details={"trace_id": trace_id, "error": str(exc)},
            ) from exc

    def load_traces_for_pipeline(
        self,
        pipeline_trace: PipelineTrace,
    ) -> tuple[RetrievalTrace | None, GenerationTrace | None]:
        """Load the retrieval and generation traces linked by a pipeline trace.

        Args:
            pipeline_trace: The parent :class:`~schemas.models.PipelineTrace` containing
                            ``retrieval_trace_id`` and ``generation_trace_id``.

        Returns:
            Tuple of ``(retrieval_trace, generation_trace)``. Either may be ``None``
            if the corresponding trace ID is empty or not found.
        """
        retrieval_trace: RetrievalTrace | None = None
        generation_trace: GenerationTrace | None = None

        if pipeline_trace.retrieval_trace_id:
            try:
                retrieval_trace = self.load_retrieval_trace(pipeline_trace.retrieval_trace_id)
            except ReplayError:
                logger.warning(
                    "retrieval_trace_not_found",
                    trace_id=pipeline_trace.retrieval_trace_id,
                )

        if pipeline_trace.generation_trace_id:
            try:
                generation_trace = self.load_generation_trace(pipeline_trace.generation_trace_id)
            except ReplayError:
                logger.warning(
                    "generation_trace_not_found",
                    trace_id=pipeline_trace.generation_trace_id,
                )

        return retrieval_trace, generation_trace

    # ------------------------------------------------------------------
    # Golden annotation loading
    # ------------------------------------------------------------------

    def load_gold_annotation(self, question_id: str) -> GoldenAnnotation | None:
        """Return the golden annotation for *question_id*, or ``None``.

        Reads ``data/golden_qa.jsonl`` on first call and caches all annotations.
        If the file does not exist (Phase 16 not yet implemented), returns ``None``
        without raising.

        Args:
            question_id: Question ID matching an entry in ``golden_qa.jsonl``.

        Returns:
            :class:`GoldenAnnotation` if found, otherwise ``None``.
        """
        if self._annotation_cache is None:
            self._annotation_cache = self._load_all_annotations()

        return self._annotation_cache.get(question_id)

    def _load_all_annotations(self) -> dict[str, GoldenAnnotation]:
        """Read all golden annotations from JSONL. Returns empty dict if file absent."""
        if self._golden_qa_path is None or not self._golden_qa_path.exists():
            logger.info(
                "golden_qa_not_available",
                path=str(self._golden_qa_path),
            )
            return {}

        annotations: dict[str, GoldenAnnotation] = {}
        try:
            with self._golden_qa_path.open(encoding="utf-8") as fh:
                for _line_num, raw in enumerate(fh, start=1):
                    line = raw.strip()
                    if not line:
                        continue
                    record: dict[str, Any] = json.loads(line)
                    qid = record.get("question_id", "")
                    if not qid:
                        continue
                    annotations[qid] = GoldenAnnotation(
                        question_id=qid,
                        question_text=record.get("question", ""),
                        supporting_chunk_ids=record.get("supporting_chunk_ids", []),
                        expected_root_cause=RootCauseStage(
                            record.get("failure_mode_root_cause", "unknown")
                        ),
                        difficulty=record.get("difficulty", "medium"),
                    )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.error("golden_qa_load_failed", error=str(exc))
            return {}

        logger.info("golden_annotations_loaded", count=len(annotations))
        return annotations
