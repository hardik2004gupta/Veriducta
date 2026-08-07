"""Shared Pydantic schemas used across all pipeline stages.

These are data-transfer objects and domain value types - they carry no
business logic. Concrete implementations fill them; abstract interfaces
reference them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VerificationStatus(StrEnum):
    """Possible outcomes of NLI entailment checking for a single claim."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    AMBIGUOUS_CONDITIONAL = "ambiguous_conditional"
    NOT_SEARCHED = "not_searched"
    UNRESOLVED = "unresolved"


class ConfidenceTag(StrEnum):
    """Generator-assigned confidence level for a claim."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class TemporalValidityTag(StrEnum):
    """Whether a claim is temporally bounded or superseded."""

    VALID = "valid"
    SUPERSEDED = "superseded"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    UNKNOWN = "unknown"


class FailureMode(StrEnum):
    """Root-cause failure label used in golden QA and corruption benchmark."""

    CHUNKING_BOUNDARY = "chunking_boundary"
    RETRIEVAL_MISS = "retrieval_miss"
    OMISSION = "omission"
    TEMPORAL_CONFUSION = "temporal_confusion"
    HALLUCINATION = "hallucination"
    CONTRADICTION = "contradiction"
    NONE = "none"


class RootCauseStage(StrEnum):
    """Pipeline stage attributed as root cause by the replay engine."""

    CHUNKING = "chunking"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    GENERATION = "generation"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentMetadata(BaseModel):
    """Metadata sidecar for a corpus document."""

    document_id: str = Field(..., description="Stable unique identifier, e.g. 'usgs-2021-001'.")
    title: str
    source: str = Field(..., description="URL or repository path of the source document.")
    document_type: str = Field(..., description="E.g. 'technical_report', 'standard', 'guidance'.")
    effective_date: str = Field(..., description="ISO-8601 date when this version took effect.")
    expiry_date: str | None = Field(None, description="ISO-8601 date when this version expires.")
    supersedes: list[str] = Field(default_factory=list, description="Document IDs this supersedes.")
    superseded_by: list[str] = Field(default_factory=list)
    version_hash: str = Field(..., description="SHA-256 of the raw PDF bytes.")
    filename: str
    page_count: int = Field(..., ge=1)
    has_tables: bool = False
    has_figures: bool = False
    figures_in_scope: bool = False
    primary_entities: list[str] = Field(default_factory=list)
    chunking_variant: str = Field(default="boundary_aware")


class Document(BaseModel):
    """A corpus document with its metadata and extracted text."""

    metadata: DocumentMetadata
    raw_text: str = Field(default="", description="Full extracted text (populated by parser).")
    page_texts: list[str] = Field(default_factory=list, description="Per-page extracted text.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------


class Chunk(BaseModel):
    """A single text chunk produced by the chunking pipeline."""

    chunk_id: str = Field(
        ...,
        description=(
            "Child format: '{document_id}-ch-{zero_padded_index}'. "
            "Parent format: '{document_id}-par-{zero_padded_index}'."
        ),
    )
    parent_chunk_id: str | None = Field(
        None,
        description="Parent chunk ID ('{document_id}-par-{index}'). None for parent chunks.",
    )
    document_id: str
    text: str
    page_number: int | None = None
    token_count: int = Field(..., ge=0)
    chunk_index: int = Field(..., ge=0)
    is_table: bool = False
    effective_date: str | None = None
    expiry_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------


class Citation(BaseModel):
    """A reference from a claim to a supporting chunk."""

    chunk_id: str
    document_id: str
    excerpt: str = Field(..., description="Short verbatim excerpt from the chunk.")
    page_number: int | None = None


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------


class Claim(BaseModel):
    """A single verifiable assertion extracted from a generated answer."""

    claim_id: str = Field(default_factory=lambda: str(uuid4()))
    text: str = Field(..., description="Claim text as generated.")
    citation_chunk_id: str = Field(..., description="Primary supporting chunk ID.")
    citation: Citation | None = None
    key_entities: list[str] = Field(
        default_factory=list,
        description="Specific technical entities in the claim - at least two.",
    )
    confidence: ConfidenceTag = ConfidenceTag.UNCERTAIN
    temporal_validity: TemporalValidityTag = TemporalValidityTag.UNKNOWN
    verification_status: VerificationStatus = VerificationStatus.UNRESOLVED
    requires_expert_review: bool = False
    nli_entailment_probability: float | None = Field(None, ge=0.0, le=1.0)
    nli_contradiction_probability: float | None = Field(None, ge=0.0, le=1.0)
    nli_neutral_probability: float | None = Field(None, ge=0.0, le=1.0)
    contradicting_chunk_ids: list[str] = Field(default_factory=list)
    conditional_conflict_chunk_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Retrieval result
# ---------------------------------------------------------------------------


class RetrievalCandidate(BaseModel):
    """A single chunk candidate produced by the retrieval pipeline."""

    chunk_id: str
    bm25_score: float | None = None
    bm25_rank: int | None = None
    dense_score: float | None = None
    dense_rank: int | None = None
    rrf_score: float | None = None
    rrf_rank: int | None = None
    reranker_score: float | None = None
    post_rerank_rank: int | None = None
    temporal_filter_rejected: bool = False
    rejection_reason: str | None = None
    chunk: Chunk | None = None
    parent_chunk: Chunk | None = None


class RetrievalResult(BaseModel):
    """Complete output of the retrieval pipeline for a single query."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    query_date: str
    top_k: int
    candidates: list[RetrievalCandidate]
    temporal_rejections: list[RetrievalCandidate] = Field(default_factory=list)
    pre_rerank_top40: list[RetrievalCandidate] = Field(default_factory=list)
    retrieval_config_hash: str = Field(default="")
    latency_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Trace (evidence log entry)
# ---------------------------------------------------------------------------


class RetrievalTrace(BaseModel):
    """Full evidence log entry for the retrieval stage."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    query_date: str
    bm25_top100: list[RetrievalCandidate] = Field(default_factory=list)
    dense_top100: list[RetrievalCandidate] = Field(default_factory=list)
    rrf_ranked: list[RetrievalCandidate] = Field(default_factory=list)
    pre_rerank_top40: list[RetrievalCandidate] = Field(default_factory=list)
    post_rerank_top8: list[RetrievalCandidate] = Field(default_factory=list)
    parent_expansion_log: list[dict[str, str]] = Field(default_factory=list)
    temporal_filter_log: list[dict[str, Any]] = Field(default_factory=list)
    config_hash: str = Field(default="")
    latency_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GenerationTrace(BaseModel):
    """Full evidence log entry for the generation and verification stage."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    retrieval_trace_id: str
    query: str
    structured_answer: dict[str, Any] = Field(default_factory=dict)
    verification_report: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    generation_latency_ms: float = 0.0
    schema_validation_attempts: int = 1
    config_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Configuration snapshot
# ---------------------------------------------------------------------------


class ConfigurationSnapshot(BaseModel):
    """Versioned, hashable snapshot of pipeline configuration parameters."""

    snapshot_id: UUID = Field(default_factory=uuid4)
    stage: str = Field(..., description="Pipeline stage this config governs.")
    parameters: dict[str, Any] = Field(..., description="Serialisable parameter dict.")
    hash: str = Field(..., description="SHA-256 of the canonical JSON serialisation.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class RetrievalMetrics(BaseModel):
    """Retrieval quality metrics computed over the evaluation dataset."""

    recall_at_5: float = Field(0.0, ge=0.0, le=1.0)
    recall_at_10: float = Field(0.0, ge=0.0, le=1.0)
    mrr: float = Field(0.0, ge=0.0, le=1.0)
    ndcg_at_10: float = Field(0.0, ge=0.0, le=1.0)
    temporal_valid_retrieval_rate: float = Field(0.0, ge=0.0, le=1.0)
    evidence_diversity: float = Field(0.0, ge=0.0)


class AnswerQualityMetrics(BaseModel):
    """Answer quality metrics computed against the golden QA dataset."""

    claim_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    citation_entailment_rate: float = Field(0.0, ge=0.0, le=1.0)
    omission_rate: float = Field(0.0, ge=0.0, le=1.0)
    contradiction_acknowledgment_rate: float = Field(0.0, ge=0.0, le=1.0)


class CausalAttributionMetrics(BaseModel):
    """Causal replay engine accuracy metrics."""

    root_cause_localization_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    realistic_boundary_error_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    chunking_ablation_recovery_rate: float = Field(0.0, ge=0.0, le=1.0)
    mean_quality_delta_per_stage: dict[str, float] = Field(default_factory=dict)


class OperationalMetrics(BaseModel):
    """Latency, cost, and cache metrics from the evaluation run."""

    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    mean_cost_per_query_usd: float = 0.0
    cache_hit_rate: float = Field(0.0, ge=0.0, le=1.0)


class EvaluationMetrics(BaseModel):
    """Aggregated metrics for a complete evaluation run."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    retrieval: RetrievalMetrics = Field(default_factory=RetrievalMetrics)
    answer_quality: AnswerQualityMetrics = Field(default_factory=AnswerQualityMetrics)
    causal_attribution: CausalAttributionMetrics = Field(default_factory=CausalAttributionMetrics)
    operational: OperationalMetrics = Field(default_factory=OperationalMetrics)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Pipeline trace (Phase 14 - unified evidence log entry)
# ---------------------------------------------------------------------------


class PipelineTrace(BaseModel):
    """Unified evidence log entry linking retrieval, generation, and verification.

    Cross-references the individual stage traces by ID.  The full stage data
    (candidates, structured answer) lives in the corresponding
    :class:`RetrievalTrace` and :class:`GenerationTrace` entries.
    This record provides aggregated metrics and links needed by the replay engine.
    """

    pipeline_trace_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str = ""
    query: str
    query_hash: str = ""
    query_date: str = ""

    retrieval_trace_id: str = ""
    generation_trace_id: str = ""

    total_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0

    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    retrieval_config_hash: str = ""
    generation_config_hash: str = ""
    prompt_hash: str = ""

    requires_expert_review: bool = False
    quality_score: float | None = None

    serialization_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
