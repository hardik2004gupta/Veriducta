"""Root-cause attribution from per-stage quality deltas.

:class:`RootCauseAttributor` accepts a mapping of stage name → quality delta
and produces a :class:`~replay.models.StageAttribution` that assigns percentage
responsibility to each pipeline stage.

Attribution percentages are computed from the absolute **degradation** at each
stage (negative ``overall_delta`` values only — improvements are ignored for
attribution purposes).  If no stage caused any degradation the attribution is
all-zero and the root cause is ``RootCauseStage.UNKNOWN``.
"""

from __future__ import annotations

import structlog

from replay.models import QualityDelta, StageAttribution
from schemas.models import RootCauseStage

logger = structlog.get_logger(__name__)

# Canonical stage names used throughout the replay engine.
STAGES = ("stage1_chunking", "stage2_retrieval", "stage3_reranker", "stage4_generation")

# Maps each stage label to the ``StageAttribution`` percentage field name.
_STAGE_TO_FIELD: dict[str, str] = {
    "stage1_chunking": "chunking_pct",
    "stage2_retrieval": "retrieval_pct",
    "stage3_reranker": "reranking_pct",
    "stage4_generation": "generation_pct",
}

# Maps each stage label to its ``RootCauseStage`` enum value.
_STAGE_TO_ROOT_CAUSE: dict[str, RootCauseStage] = {
    "stage1_chunking": RootCauseStage.CHUNKING,
    "stage2_retrieval": RootCauseStage.RETRIEVAL,
    "stage3_reranker": RootCauseStage.RERANKING,
    "stage4_generation": RootCauseStage.GENERATION,
}


class RootCauseAttributor:
    """Assign percentage attribution of quality degradation to pipeline stages.

    Args:
        min_confidence: Minimum ratio of the top stage's degradation to total
                        degradation required to label attribution as "confident".
                        Defaults to 0.5.
    """

    def __init__(self, min_confidence: float = 0.5) -> None:
        self._min_confidence = min_confidence

    def attribute(
        self,
        stage_deltas: dict[str, QualityDelta],
    ) -> StageAttribution:
        """Compute attribution percentages from per-stage quality deltas.

        Only negative overall deltas (degradations) contribute to attribution.
        Stages that improved quality or produced no change are excluded from
        the attribution denominator.

        Args:
            stage_deltas: Mapping of stage name → :class:`~replay.models.QualityDelta`.
                          Use ``STAGES`` constants for canonical names.

        Returns:
            :class:`~replay.models.StageAttribution` with per-stage percentages,
            primary root cause, and confidence score.
        """
        # Collect absolute degradation magnitudes (positive = degradation).
        degradations: dict[str, float] = {}
        for stage, delta in stage_deltas.items():
            if delta.overall_delta < 0.0:
                degradations[stage] = abs(delta.overall_delta)

        if not degradations:
            logger.info("no_degradation_detected", stage_count=len(stage_deltas))
            return StageAttribution(primary_root_cause=RootCauseStage.UNKNOWN, confidence=0.0)

        total = sum(degradations.values())

        # Compute normalised percentages.
        percentages: dict[str, float] = {stage: deg / total for stage, deg in degradations.items()}

        # Determine primary root cause (stage with largest degradation).
        primary_stage = max(degradations, key=lambda s: degradations[s])
        primary_root_cause = _STAGE_TO_ROOT_CAUSE.get(primary_stage, RootCauseStage.UNKNOWN)
        confidence = min(percentages.get(primary_stage, 0.0), 1.0)

        # Build the attribution object.
        kwargs: dict[str, float | RootCauseStage] = {
            "chunking_pct": 0.0,
            "retrieval_pct": 0.0,
            "reranking_pct": 0.0,
            "generation_pct": 0.0,
        }
        for stage, pct in percentages.items():
            field = _STAGE_TO_FIELD.get(stage)
            if field is not None:
                kwargs[field] = pct

        attribution = StageAttribution(
            primary_root_cause=primary_root_cause,
            confidence=confidence,
            **kwargs,
        )

        logger.info(
            "root_cause_attributed",
            primary_root_cause=primary_root_cause,
            confidence=f"{confidence:.3f}",
            degradation_stages=list(degradations.keys()),
        )
        return attribution
