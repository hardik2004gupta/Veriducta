"""Tests for generation/schemas.py."""

from __future__ import annotations

from generation.schemas import (
    CounterEvidenceCandidate,
    StructuredAnswer,
    VerificationReport,
)
from schemas.models import VerificationStatus


def test_structured_answer_defaults() -> None:
    ans = StructuredAnswer(answer="hello")
    assert ans.answer == "hello"
    assert ans.claims == []
    assert ans.citations == []
    assert ans.schema_validation_attempts == 1
    assert ans.answer_id  # auto-generated UUID


def test_structured_answer_answer_id_unique() -> None:
    a1 = StructuredAnswer(answer="x")
    a2 = StructuredAnswer(answer="x")
    assert a1.answer_id != a2.answer_id


def test_structured_answer_cost_default_zero() -> None:
    ans = StructuredAnswer(answer="test")
    assert ans.estimated_cost_usd == 0.0
    assert ans.input_tokens == 0
    assert ans.output_tokens == 0


def test_counterevidence_candidate_defaults() -> None:
    cand = CounterEvidenceCandidate(
        chunk_id="doc-ch-0000",
        document_id="doc",
        text="some text",
        contrastive_query="query",
    )
    assert cand.nli_contradiction_score is None
    assert cand.contradicts_claim_ids == []
    assert cand.ambiguous_claim_ids == []
    assert cand.verification_status_assigned == VerificationStatus.UNRESOLVED


def test_counterevidence_candidate_with_scores() -> None:
    cand = CounterEvidenceCandidate(
        chunk_id="doc-ch-0001",
        document_id="doc",
        text="text",
        contrastive_query="q",
        nli_contradiction_score=0.9,
        nli_entailment_score=0.05,
        nli_neutral_score=0.05,
        contradicts_claim_ids=["claim-1"],
        verification_status_assigned=VerificationStatus.CONTRADICTED,
    )
    assert cand.nli_contradiction_score == 0.9
    assert "claim-1" in cand.contradicts_claim_ids
    assert cand.verification_status_assigned == VerificationStatus.CONTRADICTED


def test_verification_report_defaults() -> None:
    report = VerificationReport(answer_id="ans-1")
    assert report.answer_id == "ans-1"
    assert report.verified_claims == []
    assert report.counterevidence_candidates == []
    assert report.overall_requires_expert_review is False
    assert report.supported_count == 0
    assert report.report_id  # auto-generated


def test_verification_report_counts() -> None:
    report = VerificationReport(
        answer_id="a",
        supported_count=3,
        contradicted_count=1,
        ambiguous_count=2,
    )
    assert report.supported_count == 3
    assert report.contradicted_count == 1
    assert report.ambiguous_count == 2


def test_verification_report_expert_review_flag() -> None:
    report = VerificationReport(
        answer_id="a",
        overall_requires_expert_review=True,
        contradicted_count=1,
    )
    assert report.overall_requires_expert_review is True
