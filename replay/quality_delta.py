"""Quality delta computation between original and replayed pipeline executions.

:class:`QualityDeltaCalculator` converts :class:`~generation.schemas.VerificationReport`
objects into numeric :class:`~replay.models.QualitySnapshot` values and computes a
signed :class:`~replay.models.QualityDelta` from any two snapshots.

A **positive** delta means the replayed execution produced a *better* answer.
A **negative** delta means the replay's intervention *degraded* quality,
implicating the overridden stage as a root-cause candidate.
"""

from __future__ import annotations

from generation.schemas import VerificationReport
from replay.models import QualityDelta, QualitySnapshot
from schemas.models import ConfidenceTag

# Faithfulness weights a 50 % of the composite quality score.
_WEIGHTS: dict[str, float] = {
    "faithfulness": 0.50,
    "citation": 0.20,
    "contradiction": 0.20,
    "confidence": 0.10,
}


class QualityDeltaCalculator:
    """Compute quality deltas from :class:`~generation.schemas.VerificationReport` pairs.

    Args:
        threshold: Absolute magnitude of ``overall_delta`` below which the delta
                   is **not** classified as a degradation (default: 0.05).
    """

    def __init__(self, threshold: float = 0.05) -> None:
        self._threshold = threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot_from_report(
        self,
        report: VerificationReport,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
    ) -> QualitySnapshot:
        """Extract a :class:`~replay.models.QualitySnapshot` from a verification report.

        Args:
            report: Completed :class:`~generation.schemas.VerificationReport`.
            latency_ms: Total generation + verification latency for this answer.
            cost_usd: Estimated LLM cost for this answer.

        Returns:
            :class:`~replay.models.QualitySnapshot` with normalised quality metrics.
        """
        claims = report.verified_claims
        total = max(len(claims), 1)

        faithfulness = report.supported_count / total
        contradiction_rate = report.contradicted_count / total
        citation_rate = sum(1 for c in claims if c.citation_chunk_id) / total
        confidence_rate = (
            sum(1 for c in claims if c.confidence in (ConfidenceTag.HIGH, ConfidenceTag.MEDIUM))
            / total
        )

        return QualitySnapshot(
            faithfulness=min(faithfulness, 1.0),
            citation_rate=min(citation_rate, 1.0),
            contradiction_rate=min(contradiction_rate, 1.0),
            confidence_rate=min(confidence_rate, 1.0),
            claim_count=len(claims),
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )

    def compute(
        self,
        original: QualitySnapshot,
        replayed: QualitySnapshot,
    ) -> QualityDelta:
        """Compute a signed quality delta between two snapshots.

        Args:
            original: Snapshot from the original pipeline execution.
            replayed: Snapshot from the replayed (modified) execution.

        Returns:
            :class:`~replay.models.QualityDelta` with per-metric and overall deltas.
        """
        faithfulness_delta = replayed.faithfulness - original.faithfulness
        citation_delta = replayed.citation_rate - original.citation_rate
        # Contradiction delta: negative means more contradictions (degradation).
        contradiction_delta = original.contradiction_rate - replayed.contradiction_rate
        confidence_delta = replayed.confidence_rate - original.confidence_rate
        coverage_delta = float(replayed.claim_count - original.claim_count)
        latency_delta_ms = replayed.latency_ms - original.latency_ms
        cost_delta_usd = replayed.cost_usd - original.cost_usd

        overall_delta = (
            _WEIGHTS["faithfulness"] * faithfulness_delta
            + _WEIGHTS["citation"] * citation_delta
            + _WEIGHTS["contradiction"] * contradiction_delta
            + _WEIGHTS["confidence"] * confidence_delta
        )

        return QualityDelta(
            faithfulness_delta=faithfulness_delta,
            citation_delta=citation_delta,
            contradiction_delta=contradiction_delta,
            confidence_delta=confidence_delta,
            coverage_delta=coverage_delta,
            latency_delta_ms=latency_delta_ms,
            cost_delta_usd=cost_delta_usd,
            overall_delta=overall_delta,
            is_degradation=(overall_delta < -self._threshold),
            original=original,
            replayed=replayed,
        )

    def snapshot_placeholder(self) -> QualitySnapshot:
        """Return a zero :class:`~replay.models.QualitySnapshot`.

        Used when a stage could not be executed (missing data or components).

        Returns:
            :class:`~replay.models.QualitySnapshot` with all zeros.
        """
        return QualitySnapshot()

    def neutral_delta(self) -> QualityDelta:
        """Return a zero :class:`~replay.models.QualityDelta`.

        Used when a stage could not be executed.

        Returns:
            :class:`~replay.models.QualityDelta` with all zeros and ``is_degradation=False``.
        """
        return QualityDelta()
