"""Evaluation-specific data models for the dataset and annotation subsystem.

Types in this module are owned by ``evaluation/`` and are not shared with
upstream pipeline packages.  They import only shared enumerations from
``schemas.models`` for field typing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from schemas.models import FailureMode, RootCauseStage, TemporalValidityTag

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Difficulty(StrEnum):
    """Annotated difficulty of answering a golden QA question."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnswerType(StrEnum):
    """Category of expected answer structure."""

    FACTUAL = "factual"
    NUMERICAL_THRESHOLD = "numerical_threshold"
    PROCEDURAL = "procedural"
    COMPARATIVE = "comparative"
    TEMPORAL = "temporal"


class HallucinationRisk(StrEnum):
    """Annotated risk that a model will fabricate content for this question."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CitationRequirement(StrEnum):
    """Whether inline citations are mandatory for a correct answer."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    NONE = "none"


class ReviewStatus(StrEnum):
    """Annotation review lifecycle stage."""

    DRAFT = "draft"
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"


class TemporalConstraintType(StrEnum):
    """Type of temporal dependency in the question."""

    NONE = "none"
    DATE_SPECIFIC = "date_specific"
    VERSION_DEPENDENT = "version_dependent"


class CorruptionSeverity(StrEnum):
    """Expected magnitude of quality degradation from a corruption."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationIssueSeverity(StrEnum):
    """Whether a validation issue blocks use of the dataset."""

    ERROR = "error"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Mapping: FailureMode → RootCauseStage
# ---------------------------------------------------------------------------

FAILURE_MODE_TO_ROOT_CAUSE: dict[FailureMode, RootCauseStage] = {
    FailureMode.CHUNKING_BOUNDARY: RootCauseStage.CHUNKING,
    FailureMode.RETRIEVAL_MISS: RootCauseStage.RETRIEVAL,
    FailureMode.OMISSION: RootCauseStage.RETRIEVAL,
    FailureMode.TEMPORAL_CONFUSION: RootCauseStage.RETRIEVAL,
    FailureMode.HALLUCINATION: RootCauseStage.GENERATION,
    FailureMode.CONTRADICTION: RootCauseStage.GENERATION,
    FailureMode.NONE: RootCauseStage.UNKNOWN,
}


# ---------------------------------------------------------------------------
# Golden QA item
# ---------------------------------------------------------------------------


class GoldenQAItem(BaseModel):
    """One fully annotated golden QA pair from the evaluation dataset.

    Combines question metadata, ground-truth annotation, and quality flags
    into a single model used by the evaluation harness.
    """

    question_id: str = Field(..., pattern=r"^qa-\d{3}$")
    question: str
    gold_answer: str
    supporting_chunk_ids: list[str]
    counterevidence_chunk_ids: list[str] = Field(default_factory=list)
    expected_entities: list[str]
    expected_citations: list[str]
    temporal_validity: TemporalValidityTag = TemporalValidityTag.VALID
    difficulty: Difficulty
    domain: str
    answer_type: AnswerType
    verification_required: bool = False
    failure_mode: FailureMode = FailureMode.NONE
    expected_failure_modes: list[FailureMode] = Field(default_factory=list)
    hallucination_risk: HallucinationRisk = HallucinationRisk.LOW
    citation_requirement: CitationRequirement = CitationRequirement.REQUIRED
    temporal_constraints: TemporalConstraintType = TemporalConstraintType.NONE
    quality_notes: str = ""
    annotator_notes: str = ""
    review_status: ReviewStatus = ReviewStatus.APPROVED

    @property
    def expected_root_cause(self) -> RootCauseStage:
        """Return the RootCauseStage inferred from the failure_mode annotation."""
        return FAILURE_MODE_TO_ROOT_CAUSE.get(self.failure_mode, RootCauseStage.UNKNOWN)


# ---------------------------------------------------------------------------
# Evaluation corruption case (richer than replay.models.CorruptionCase)
# ---------------------------------------------------------------------------


class EvaluationCorruptionCase(BaseModel):
    """One synthetic corruption case for the 60-case benchmark.

    Extends the minimal :class:`~replay.models.CorruptionCase` with
    evaluation-specific metadata: severity, human-readable description,
    expected quality delta, and the corrupted configuration parameters.
    """

    case_id: str = Field(..., pattern=r"^corr-[a-z]+-\d{3}$")
    question_id: str = Field(..., pattern=r"^qa-\d{3}$")
    corruption_type: str
    ground_truth_root_cause: RootCauseStage
    is_realistic_boundary_error: bool = False
    severity: CorruptionSeverity
    description: str
    corrupted_configuration: dict[str, Any] = Field(default_factory=dict)
    expected_quality_delta: float = Field(..., description="Negative value = expected degradation.")
    pipeline_trace_id: str = ""
    corruption_parameters: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


# ---------------------------------------------------------------------------
# Dataset statistics
# ---------------------------------------------------------------------------


class DatasetStats(BaseModel):
    """Aggregate statistics for a loaded dataset."""

    total_questions: int = 0
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    domain_distribution: dict[str, int] = Field(default_factory=dict)
    failure_mode_distribution: dict[str, int] = Field(default_factory=dict)
    answer_type_distribution: dict[str, int] = Field(default_factory=dict)
    temporal_validity_distribution: dict[str, int] = Field(default_factory=dict)
    review_status_distribution: dict[str, int] = Field(default_factory=dict)
    total_corruptions: int = 0
    corruption_type_distribution: dict[str, int] = Field(default_factory=dict)
    root_cause_distribution: dict[str, int] = Field(default_factory=dict)
    realistic_boundary_error_count: int = 0
    total_supporting_chunks: int = 0
    mean_supporting_chunks: float = 0.0


# ---------------------------------------------------------------------------
# Dataset manifest
# ---------------------------------------------------------------------------


class DatasetManifest(BaseModel):
    """Version metadata for a dataset snapshot."""

    version: str = "1.0"
    golden_qa_count: int = 0
    corruptions_count: int = 0
    annotation_schema_version: str = "1.0"
    generated_at: str = ""
    checksum: str = ""


# ---------------------------------------------------------------------------
# Validation types
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    """A single dataset validation finding."""

    severity: ValidationIssueSeverity
    issue_type: str
    item_id: str
    message: str


class ValidationResult(BaseModel):
    """Aggregated result of a dataset validation pass."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0
