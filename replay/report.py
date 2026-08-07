"""Replay report assembly and JSON serialization.

:class:`ReplayReportAssembler` takes the per-stage results from
:class:`~replay.executor.ReplayExecutor`, computes attributions via
:class:`~replay.attribution.RootCauseAttributor`, and builds the final
:class:`~replay.models.ReplayReport`.
"""

from __future__ import annotations

import structlog

from replay.attribution import RootCauseAttributor
from replay.models import ReplayReport, StageAttribution, StageReplayResult

logger = structlog.get_logger(__name__)


class ReplayReportAssembler:
    """Assemble a complete :class:`~replay.models.ReplayReport` from stage results.

    Args:
        attributor: Optional :class:`~replay.attribution.RootCauseAttributor`.
                    Defaults to a new instance with ``min_confidence=0.5``.
    """

    def __init__(self, attributor: RootCauseAttributor | None = None) -> None:
        self._attributor = attributor or RootCauseAttributor()

    def assemble(
        self,
        pipeline_trace_id: str,
        question_id: str,
        stage_results: dict[str, StageReplayResult],
    ) -> ReplayReport:
        """Build a :class:`~replay.models.ReplayReport` from the four stage results.

        Args:
            pipeline_trace_id: UUID of the original pipeline trace.
            question_id: Corresponding golden QA question ID (empty if unknown).
            stage_results: Dict mapping stage name → :class:`~replay.models.StageReplayResult`.

        Returns:
            Fully assembled :class:`~replay.models.ReplayReport`.
        """
        # Compute attribution from successful stages only.
        stage_deltas = {
            stage: result.quality_delta for stage, result in stage_results.items() if result.success
        }
        attribution: StageAttribution = self._attributor.attribute(stage_deltas)

        # Flatten attribution percentages.
        stage_attributions: dict[str, float] = {
            "stage1_chunking": attribution.chunking_pct,
            "stage2_retrieval": attribution.retrieval_pct,
            "stage3_reranker": attribution.reranking_pct,
            "stage4_generation": attribution.generation_pct,
        }

        total_latency = sum(r.latency_ms for r in stage_results.values())
        primary_root_cause = attribution.primary_root_cause

        report = ReplayReport(
            pipeline_trace_id=pipeline_trace_id,
            question_id=question_id,
            stage_results=stage_results,
            stage_attributions=stage_attributions,
            primary_root_cause=primary_root_cause,
            attribution=attribution,
            total_latency_ms=total_latency,
        )

        logger.info(
            "replay_report_assembled",
            report_id=report.report_id,
            pipeline_trace_id=pipeline_trace_id,
            primary_root_cause=primary_root_cause,
            confidence=f"{attribution.confidence:.3f}",
            total_latency_ms=f"{total_latency:.1f}",
        )
        return report
