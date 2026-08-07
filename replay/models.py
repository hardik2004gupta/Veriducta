"""Replay-specific data models for the causal ablation engine.

All types in this module are owned exclusively by ``replay/`` and are not
shared across other pipeline packages.  Cross-stage exchange types
(:class:`~schemas.models.RetrievalResult`, :class:`~generation.schemas.StructuredAnswer`,
:class:`~generation.schemas.VerificationReport`) are imported from their
owning packages.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas.models import RootCauseStage

# ---------------------------------------------------------------------------
# Corruption benchmark types
# ---------------------------------------------------------------------------


class CorruptionCase(BaseModel):
    """One entry from ``data/synthetic_corruptions/corruptions.jsonl``.

    Defines which pipeline stage was deliberately degraded, the expected
    root-cause label, and the parameters that describe the corruption.
    """

    case_id: str
    corruption_type: str = Field(
        ..., description="E.g. 'retrieval_swap', 'chunking_boundary_naive'."
    )
    ground_truth_root_cause: RootCauseStage
    is_realistic_boundary_error: bool = False
    pipeline_trace_id: str = ""
    question_id: str = ""
    corruption_parameters: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


# ---------------------------------------------------------------------------
# Override tracking
# ---------------------------------------------------------------------------


class ReplayOverride(BaseModel):
    """A single documented parameter override in a replay run.

    Tracking overrides explicitly makes every replay deterministic and
    auditable - the evidence log entry contains the full override list.
    """

    parameter: str = Field(..., description="Dotted parameter name, e.g. 'retrieval.rrf_k'.")
    original_value: Any
    override_value: Any
    stage: str = Field(..., description="'retrieval', 'generation', 'verification', 'chunking'.")
    rationale: str = ""


# ---------------------------------------------------------------------------
# Replay configuration
# ---------------------------------------------------------------------------


class ReplayConfiguration(BaseModel):
    """Complete configuration for a single replay execution.

    Holds per-stage parameter overrides and a list of
    :class:`ReplayOverride` records for audit purposes.  An empty
    ``ReplayConfiguration`` (all dicts empty) means "replay with the
    original configuration" - a deterministic no-op.
    """

    config_id: str = Field(default_factory=lambda: str(uuid4()))
    label: str = Field(
        default="", description="Human-readable label for this configuration variant."
    )
    retrieval_overrides: dict[str, Any] = Field(default_factory=dict)
    generation_overrides: dict[str, Any] = Field(default_factory=dict)
    verification_overrides: dict[str, Any] = Field(default_factory=dict)
    chunking_overrides: dict[str, Any] = Field(default_factory=dict)
    overrides: list[ReplayOverride] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_empty(self) -> bool:
        """Return True when no overrides are set (baseline replay)."""
        return not any(
            [
                self.retrieval_overrides,
                self.generation_overrides,
                self.verification_overrides,
                self.chunking_overrides,
            ]
        )


# ---------------------------------------------------------------------------
# Quality measurement
# ---------------------------------------------------------------------------


class QualitySnapshot(BaseModel):
    """Point-in-time quality metrics extracted from a VerificationReport.

    Used as input to :class:`QualityDelta` so the delta calculator only
    needs two snapshots, not the full report objects.
    """

    faithfulness: float = Field(0.0, ge=0.0, le=1.0, description="supported / total claims.")
    citation_rate: float = Field(0.0, ge=0.0, le=1.0, description="Claims with citation / total.")
    contradiction_rate: float = Field(0.0, ge=0.0, le=1.0, description="contradicted / total.")
    confidence_rate: float = Field(0.0, ge=0.0, le=1.0, description="high+medium / total.")
    claim_count: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class QualityDelta(BaseModel):
    """Signed difference between replayed and original quality.

    Positive values mean the replay is *better* than the original.
    Negative values mean the intervention *degraded* quality.
    """

    faithfulness_delta: float = 0.0
    citation_delta: float = 0.0
    contradiction_delta: float = 0.0
    confidence_delta: float = 0.0
    coverage_delta: float = 0.0
    latency_delta_ms: float = 0.0
    cost_delta_usd: float = 0.0
    overall_delta: float = Field(0.0, description="Weighted composite delta (faithfulness-heavy).")
    is_degradation: bool = Field(False, description="True when overall_delta < negative threshold.")

    original: QualitySnapshot = Field(default_factory=QualitySnapshot)
    replayed: QualitySnapshot = Field(default_factory=QualitySnapshot)


# ---------------------------------------------------------------------------
# Stage results and attribution
# ---------------------------------------------------------------------------


class StageReplayResult(BaseModel):
    """Output of replaying one ablation stage.

    Stores the replayed artifacts alongside the quality delta so the
    full replay report can reconstruct what changed at each stage.
    """

    stage: str = Field(..., description="'stage1_chunking', 'stage2_retrieval', etc.")
    config: ReplayConfiguration = Field(default_factory=ReplayConfiguration)
    quality_delta: QualityDelta = Field(default_factory=QualityDelta)
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage-specific artifacts (e.g. recall deltas, cutoff comparisons).",
    )


class StageAttribution(BaseModel):
    """Percentage of quality degradation attributed to each pipeline stage.

    All percentages sum to 1.0 (or 0.0 when no degradation was detected).
    """

    chunking_pct: float = Field(0.0, ge=0.0, le=1.0)
    retrieval_pct: float = Field(0.0, ge=0.0, le=1.0)
    reranking_pct: float = Field(0.0, ge=0.0, le=1.0)
    generation_pct: float = Field(0.0, ge=0.0, le=1.0)
    primary_root_cause: RootCauseStage = RootCauseStage.UNKNOWN
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Attribution confidence score.")


# ---------------------------------------------------------------------------
# Full replay report
# ---------------------------------------------------------------------------


class ReplayReport(BaseModel):
    """Complete output of a four-stage causal ablation run.

    This is the primary deliverable of the replay engine.  It links the
    original pipeline execution (via ``pipeline_trace_id``) to the
    per-stage replay results and the final root-cause attribution.
    """

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_trace_id: str
    question_id: str = ""

    stage_results: dict[str, StageReplayResult] = Field(default_factory=dict)
    stage_attributions: dict[str, float] = Field(
        default_factory=dict,
        description="Stage name -> percentage attribution (0.0-1.0).",
    )
    primary_root_cause: RootCauseStage = RootCauseStage.UNKNOWN
    attribution: StageAttribution = Field(default_factory=StageAttribution)

    total_latency_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
