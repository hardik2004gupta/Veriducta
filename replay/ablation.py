"""VeriductaReplayEngine — four-stage gold ablation engine.

Implements :class:`~core.interfaces.BaseReplayEngine` by composing
:class:`~replay.loader.TraceLoader`, :class:`~replay.executor.ReplayExecutor`,
and :class:`~replay.report.ReplayReportAssembler`.

Four-stage ablation:

1. **Chunking** — replay retrieval with boundary-naive config. Tests whether
   chunking failures prevented the relevant text from entering the retrieval
   candidates.
2. **Retrieval** — inject gold supporting chunks. Tests whether the retrieval
   component missed the relevant text despite it being correctly chunked.
3. **Reranker** — test different top-N cutoffs from ``pre_rerank_top40``. Tests
   whether the cross-encoder assigned an incorrect rank to the most relevant
   chunk.
4. **Generation** — replay with original context + generation overrides. Tests
   whether the prompt or generation parameters caused the quality failure.
"""

from __future__ import annotations

import time

import structlog

from core.exceptions import ReplayError
from core.interfaces import BaseReplayEngine
from generation.schemas import StructuredAnswer, VerificationReport
from observability.metrics import REPLAY_ABLATIONS_RUN, REPLAY_LATENCY, ROOT_CAUSE_ATTRIBUTED
from replay.configuration import ReplayConfigurationBuilder
from replay.executor import STAGE1, STAGE2, STAGE3, STAGE4, ReplayExecutor
from replay.loader import TraceLoader
from replay.models import CorruptionCase, ReplayReport, StageReplayResult
from replay.report import ReplayReportAssembler
from schemas.models import GenerationTrace

logger = structlog.get_logger(__name__)


class VeriductaReplayEngine(BaseReplayEngine):
    """Four-stage causal ablation engine implementing :class:`~core.interfaces.BaseReplayEngine`.

    Args:
        loader: :class:`~replay.loader.TraceLoader` that provides historical traces.
        executor: :class:`~replay.executor.ReplayExecutor` wrapping the pipeline components.
        assembler: :class:`~replay.report.ReplayReportAssembler` for building reports.
        reranker_cutoffs: Top-N cutoffs tested in Stage 3. Defaults to ``[1, 3, 5, 8]``.
    """

    def __init__(
        self,
        loader: TraceLoader,
        executor: ReplayExecutor,
        assembler: ReplayReportAssembler | None = None,
        reranker_cutoffs: list[int] | None = None,
    ) -> None:
        self._loader = loader
        self._executor = executor
        self._assembler = assembler or ReplayReportAssembler()
        self._reranker_cutoffs = reranker_cutoffs or [1, 3, 5, 8]

    # ------------------------------------------------------------------
    # BaseReplayEngine interface
    # ------------------------------------------------------------------

    def run_ablation(self, trace_id: str, question_id: str) -> ReplayReport:
        """Execute four-stage gold ablation for a historical trace.

        Args:
            trace_id: UUID of the :class:`~schemas.models.PipelineTrace` to ablate.
            question_id: Matching entry in ``data/golden_qa.jsonl`` (may be empty).

        Returns:
            :class:`~replay.models.ReplayReport` with per-stage attributions.

        Raises:
            ReplayError: If the pipeline trace or its stage traces cannot be loaded.
        """
        total_start = time.monotonic()

        # Load the parent pipeline trace.
        pipeline_trace = self._loader.load_pipeline_trace(trace_id)
        retrieval_trace, generation_trace = self._loader.load_traces_for_pipeline(pipeline_trace)

        if retrieval_trace is None:
            raise ReplayError(
                message="retrieval_trace required for ablation but not found",
                details={"pipeline_trace_id": trace_id},
            )
        if generation_trace is None:
            raise ReplayError(
                message="generation_trace required for ablation but not found",
                details={"pipeline_trace_id": trace_id},
            )

        # Load original answer and verification report from generation trace.
        original_answer, original_verification = _decode_generation_trace(generation_trace)

        # Load golden annotation (may be None).
        annotation = self._loader.load_gold_annotation(question_id)
        gold_chunk_ids = annotation.supporting_chunk_ids if annotation else None

        logger.info(
            "ablation_started",
            trace_id=trace_id,
            question_id=question_id,
            has_golden_data=annotation is not None,
        )

        stage_results: dict[str, StageReplayResult] = {}

        # Stage 1 — Chunking
        stage1_config = (
            ReplayConfigurationBuilder(label="stage1_boundary_naive")
            .with_chunking_override(
                "boundary_aware",
                override=False,
                original=True,
                rationale="Test boundary-naive chunking variant",
            )
            .build()
        )
        stage_results[STAGE1] = self._executor.execute_stage1_chunking(
            retrieval_trace=retrieval_trace,
            gen_trace=generation_trace,
            original_answer=original_answer,
            original_verification=original_verification,
            config=stage1_config,
        )
        REPLAY_ABLATIONS_RUN.labels(stage=STAGE1).inc()

        # Stage 2 — Retrieval
        stage2_config = ReplayConfigurationBuilder(label="stage2_gold_retrieval").build()
        stage_results[STAGE2] = self._executor.execute_stage2_retrieval(
            retrieval_trace=retrieval_trace,
            original_answer=original_answer,
            original_verification=original_verification,
            config=stage2_config,
            gold_chunk_ids=gold_chunk_ids,
        )
        REPLAY_ABLATIONS_RUN.labels(stage=STAGE2).inc()

        # Stage 3 — Reranker
        stage3_config = ReplayConfigurationBuilder(label="stage3_reranker_cutoffs").build()
        stage_results[STAGE3] = self._executor.execute_stage3_reranker(
            retrieval_trace=retrieval_trace,
            original_answer=original_answer,
            original_verification=original_verification,
            config=stage3_config,
            cutoffs=self._reranker_cutoffs,
        )
        REPLAY_ABLATIONS_RUN.labels(stage=STAGE3).inc()

        # Stage 4 — Generation
        stage4_config = ReplayConfigurationBuilder(label="stage4_baseline_generation").build()
        stage_results[STAGE4] = self._executor.execute_stage4_generation(
            retrieval_trace=retrieval_trace,
            original_answer=original_answer,
            original_verification=original_verification,
            config=stage4_config,
        )
        REPLAY_ABLATIONS_RUN.labels(stage=STAGE4).inc()

        report = self._assembler.assemble(
            pipeline_trace_id=trace_id,
            question_id=question_id,
            stage_results=stage_results,
        )

        total_ms = (time.monotonic() - total_start) * 1000.0
        REPLAY_LATENCY.observe(total_ms)
        ROOT_CAUSE_ATTRIBUTED.labels(root_cause_stage=str(report.primary_root_cause)).inc()

        logger.info(
            "ablation_complete",
            trace_id=trace_id,
            primary_root_cause=str(report.primary_root_cause),
            total_latency_ms=f"{total_ms:.1f}",
        )
        return report

    def run_corruption(self, corruption_case: CorruptionCase) -> ReplayReport:
        """Run ablation on a single synthetic corruption case.

        Loads the trace identified by ``corruption_case.pipeline_trace_id`` and
        executes the four-stage ablation, then returns the report.

        Args:
            corruption_case: One entry from ``data/synthetic_corruptions/corruptions.jsonl``.

        Returns:
            :class:`~replay.models.ReplayReport` with attributed root-cause stage.

        Raises:
            ReplayError: If the pipeline trace cannot be loaded.
        """
        logger.info(
            "corruption_ablation_started",
            case_id=corruption_case.case_id,
            corruption_type=corruption_case.corruption_type,
            ground_truth=str(corruption_case.ground_truth_root_cause),
        )

        if not corruption_case.pipeline_trace_id:
            raise ReplayError(
                message="CorruptionCase has no pipeline_trace_id",
                details={"case_id": corruption_case.case_id},
            )

        return self.run_ablation(
            trace_id=corruption_case.pipeline_trace_id,
            question_id=corruption_case.question_id,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _decode_generation_trace(
    gen_trace: GenerationTrace,
) -> tuple[StructuredAnswer, VerificationReport]:
    """Deserialize a :class:`~schemas.models.GenerationTrace` into typed objects.

    Args:
        gen_trace: Generation trace from the evidence log.

    Returns:
        Tuple of ``(StructuredAnswer, VerificationReport)``.

    Raises:
        ReplayError: If the structured answer or verification report cannot be decoded.
    """
    try:
        answer = StructuredAnswer.model_validate(gen_trace.structured_answer)
    except Exception as exc:
        raise ReplayError(
            message="Failed to decode StructuredAnswer from generation trace",
            details={"trace_id": gen_trace.trace_id, "error": str(exc)},
        ) from exc

    try:
        verification = VerificationReport.model_validate(gen_trace.verification_report)
    except Exception as exc:
        raise ReplayError(
            message="Failed to decode VerificationReport from generation trace",
            details={"trace_id": gen_trace.trace_id, "error": str(exc)},
        ) from exc

    return answer, verification
