"""Tests for replay.quality_delta - QualityDeltaCalculator."""

import pytest

from generation.schemas import VerificationReport
from replay.quality_delta import QualityDeltaCalculator
from schemas.models import Claim, ConfidenceTag, VerificationStatus


def _make_claim(
    status: VerificationStatus = VerificationStatus.SUPPORTED,
    confidence: ConfidenceTag = ConfidenceTag.HIGH,
    citation_chunk_id: str = "doc-001-ch-0001",
) -> Claim:
    return Claim(
        text="test claim",
        citation_chunk_id=citation_chunk_id,
        verification_status=status,
        confidence=confidence,
    )


def _make_report(
    supported: int = 0,
    contradicted: int = 0,
    ambiguous: int = 0,
    unresolved: int = 0,
    claims: list[Claim] | None = None,
) -> VerificationReport:
    if claims is None:
        claims = (
            [_make_claim(VerificationStatus.SUPPORTED)] * supported
            + [_make_claim(VerificationStatus.CONTRADICTED)] * contradicted
            + [_make_claim(VerificationStatus.AMBIGUOUS_CONDITIONAL)] * ambiguous
            + [_make_claim(VerificationStatus.UNRESOLVED)] * unresolved
        )
    return VerificationReport(
        answer_id="ans-001",
        verified_claims=claims,
        supported_count=supported,
        contradicted_count=contradicted,
        ambiguous_count=ambiguous,
        unresolved_count=unresolved,
    )


def test_snapshot_from_report_all_supported() -> None:
    report = _make_report(supported=4)
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report)
    assert snap.faithfulness == pytest.approx(1.0)
    assert snap.claim_count == 4
    assert snap.contradiction_rate == pytest.approx(0.0)


def test_snapshot_from_report_mixed_statuses() -> None:
    report = _make_report(supported=2, contradicted=1, unresolved=1)
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report)
    assert snap.faithfulness == pytest.approx(0.5)
    assert snap.contradiction_rate == pytest.approx(0.25)


def test_snapshot_from_report_empty_claims() -> None:
    report = _make_report()
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report)
    assert snap.faithfulness == pytest.approx(0.0)
    assert snap.claim_count == 0


def test_snapshot_citation_rate() -> None:
    claims = [
        _make_claim(citation_chunk_id="chunk-001"),
        _make_claim(citation_chunk_id="chunk-002"),
        Claim(
            text="no citation",
            citation_chunk_id="",
            verification_status=VerificationStatus.UNRESOLVED,
        ),
    ]
    report = VerificationReport(
        answer_id="ans-001",
        verified_claims=claims,
        unresolved_count=1,
    )
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report)
    # 2 out of 3 have non-empty citation_chunk_id
    assert snap.citation_rate == pytest.approx(2 / 3)


def test_snapshot_confidence_rate() -> None:
    claims = [
        _make_claim(confidence=ConfidenceTag.HIGH),
        _make_claim(confidence=ConfidenceTag.MEDIUM),
        _make_claim(confidence=ConfidenceTag.LOW),
        _make_claim(confidence=ConfidenceTag.UNCERTAIN),
    ]
    report = VerificationReport(answer_id="a", verified_claims=claims)
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report)
    assert snap.confidence_rate == pytest.approx(0.5)  # 2/4


def test_snapshot_includes_latency_and_cost() -> None:
    report = _make_report(supported=1)
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_from_report(report, latency_ms=123.4, cost_usd=0.01)
    assert snap.latency_ms == pytest.approx(123.4)
    assert snap.cost_usd == pytest.approx(0.01)


def test_compute_positive_delta_not_degradation() -> None:
    from replay.models import QualitySnapshot

    original = QualitySnapshot(faithfulness=0.5)
    replayed = QualitySnapshot(faithfulness=0.8)
    calc = QualityDeltaCalculator(threshold=0.05)
    delta = calc.compute(original, replayed)
    assert delta.faithfulness_delta == pytest.approx(0.3)
    assert delta.overall_delta > 0.0
    assert delta.is_degradation is False


def test_compute_negative_delta_is_degradation() -> None:
    from replay.models import QualitySnapshot

    original = QualitySnapshot(faithfulness=0.8)
    replayed = QualitySnapshot(faithfulness=0.5)
    calc = QualityDeltaCalculator(threshold=0.05)
    delta = calc.compute(original, replayed)
    assert delta.faithfulness_delta == pytest.approx(-0.3)
    assert delta.overall_delta < 0.0
    assert delta.is_degradation is True


def test_compute_small_delta_not_degradation() -> None:
    from replay.models import QualitySnapshot

    original = QualitySnapshot(faithfulness=0.80)
    replayed = QualitySnapshot(faithfulness=0.78)
    calc = QualityDeltaCalculator(threshold=0.05)
    delta = calc.compute(original, replayed)
    # overall_delta = 0.5 * (0.78 - 0.80) = -0.01, below threshold 0.05
    assert delta.is_degradation is False


def test_neutral_delta_returns_zero() -> None:
    calc = QualityDeltaCalculator()
    delta = calc.neutral_delta()
    assert delta.overall_delta == 0.0
    assert delta.is_degradation is False


def test_snapshot_placeholder_returns_zeros() -> None:
    calc = QualityDeltaCalculator()
    snap = calc.snapshot_placeholder()
    assert snap.faithfulness == 0.0
    assert snap.claim_count == 0
