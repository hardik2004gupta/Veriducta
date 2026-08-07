"""Generation-specific Pydantic schemas.

These types are owned by the generation pipeline and are not shared across
all pipeline stages (those live in schemas/models.py).  StructuredAnswer and
VerificationReport are the primary exchange types between generation and
the causal replay engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas.models import (
    Citation,
    Claim,
    ConfidenceTag,
    TemporalValidityTag,
    VerificationStatus,
)


class StructuredAnswer(BaseModel):
    """A fully structured, citation-grounded answer from VeriductaGenerator.

    Produced by :class:`~generation.generator.VeriductaGenerator` and consumed
    by :class:`~generation.verifier.VeriductaVerifier` and the replay engine.
    """

    answer_id: str = Field(default_factory=lambda: str(uuid4()))
    answer: str = Field(..., description="Complete prose answer to the question.")
    claims: list[Claim] = Field(default_factory=list, description="Verifiable claim assertions.")
    citations: list[Citation] = Field(default_factory=list, description="Supporting citations.")
    confidence: ConfidenceTag = ConfidenceTag.UNCERTAIN
    temporal_validity: TemporalValidityTag = TemporalValidityTag.UNKNOWN
    key_entities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_id: str = Field(default="")
    generation_latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    schema_validation_attempts: int = 1
    prompt_hash: str = Field(default="")
    config_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CounterEvidenceCandidate(BaseModel):
    """A chunk retrieved and scored during the 5-step counterevidence scan."""

    chunk_id: str
    document_id: str
    text: str
    contrastive_query: str
    nli_contradiction_score: float | None = None
    nli_entailment_score: float | None = None
    nli_neutral_score: float | None = None
    contradicts_claim_ids: list[str] = Field(default_factory=list)
    ambiguous_claim_ids: list[str] = Field(default_factory=list)
    verification_status_assigned: VerificationStatus = VerificationStatus.UNRESOLVED


class VerificationReport(BaseModel):
    """Verification result for a complete StructuredAnswer.

    Produced by :class:`~generation.verifier.VeriductaVerifier`.  The
    ``verified_claims`` list replaces the original answer claims with
    updated :attr:`~schemas.models.Claim.verification_status` values.
    """

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    answer_id: str
    verified_claims: list[Claim] = Field(default_factory=list)
    counterevidence_candidates: list[CounterEvidenceCandidate] = Field(default_factory=list)
    overall_requires_expert_review: bool = False
    supported_count: int = 0
    contradicted_count: int = 0
    ambiguous_count: int = 0
    not_searched_count: int = 0
    unresolved_count: int = 0
    nli_model_id: str = Field(default="")
    verification_latency_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
