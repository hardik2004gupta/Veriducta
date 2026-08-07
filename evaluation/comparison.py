"""Cross-run metric comparison for evaluation harness.

:class:`RunComparator` produces a :class:`ComparisonReport` from two
:class:`~schemas.models.EvaluationMetrics` instances.  Each :class:`MetricDelta`
records the absolute and relative change, and a direction label (``"improved"``,
``"degraded"``, or ``"unchanged"``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.models import EvaluationMetrics

# Changes smaller than this absolute magnitude are treated as "unchanged".
_UNCHANGED_THRESHOLD = 0.001


@dataclass
class MetricDelta:
    """Signed difference between two values for one metric."""

    metric_path: str
    baseline_value: float
    current_value: float
    absolute_delta: float
    relative_delta: float
    direction: str  # "improved" | "degraded" | "unchanged"


@dataclass
class ComparisonReport:
    """Complete metric-level comparison between two evaluation runs."""

    baseline_run_id: str
    current_run_id: str
    deltas: list[MetricDelta] = field(default_factory=list)

    @property
    def improvements(self) -> list[MetricDelta]:
        """Return deltas where the current run is better than the baseline."""
        return [d for d in self.deltas if d.direction == "improved"]

    @property
    def regressions(self) -> list[MetricDelta]:
        """Return deltas where the current run is worse than the baseline."""
        return [d for d in self.deltas if d.direction == "degraded"]


class RunComparator:
    """Compare two evaluation runs metric by metric.

    Usage::

        comparator = RunComparator()
        report = comparator.compare(baseline_metrics, current_metrics)
        print(f"{len(report.regressions)} regressions detected")
    """

    def compare(
        self,
        baseline: EvaluationMetrics,
        current: EvaluationMetrics,
    ) -> ComparisonReport:
        """Produce a :class:`ComparisonReport` with one :class:`MetricDelta` per metric.

        Args:
            baseline: Reference metrics (e.g. stored CI baseline).
            current: Metrics from the run under evaluation.

        Returns:
            :class:`ComparisonReport` with per-metric direction and delta values.
        """
        deltas: list[MetricDelta] = []
        deltas.extend(self._compare_retrieval(baseline, current))
        deltas.extend(self._compare_answer_quality(baseline, current))
        deltas.extend(self._compare_causal_attribution(baseline, current))
        deltas.extend(self._compare_operational(baseline, current))
        return ComparisonReport(
            baseline_run_id=baseline.run_id,
            current_run_id=current.run_id,
            deltas=deltas,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _delta(
        self,
        path: str,
        baseline_val: float,
        current_val: float,
        higher_is_better: bool = True,
    ) -> MetricDelta:
        absolute = current_val - baseline_val
        relative = absolute / baseline_val if abs(baseline_val) > 1e-9 else 0.0

        if abs(absolute) < _UNCHANGED_THRESHOLD:
            direction = "unchanged"
        elif (absolute > 0) == higher_is_better:
            direction = "improved"
        else:
            direction = "degraded"

        return MetricDelta(
            metric_path=path,
            baseline_value=baseline_val,
            current_value=current_val,
            absolute_delta=absolute,
            relative_delta=relative,
            direction=direction,
        )

    def _compare_retrieval(
        self,
        baseline: EvaluationMetrics,
        current: EvaluationMetrics,
    ) -> list[MetricDelta]:
        b, c = baseline.retrieval, current.retrieval
        return [
            self._delta("retrieval.recall_at_5", b.recall_at_5, c.recall_at_5),
            self._delta("retrieval.recall_at_10", b.recall_at_10, c.recall_at_10),
            self._delta("retrieval.mrr", b.mrr, c.mrr),
            self._delta("retrieval.ndcg_at_10", b.ndcg_at_10, c.ndcg_at_10),
            self._delta(
                "retrieval.temporal_valid_retrieval_rate",
                b.temporal_valid_retrieval_rate,
                c.temporal_valid_retrieval_rate,
            ),
            self._delta(
                "retrieval.evidence_diversity",
                b.evidence_diversity,
                c.evidence_diversity,
            ),
        ]

    def _compare_answer_quality(
        self,
        baseline: EvaluationMetrics,
        current: EvaluationMetrics,
    ) -> list[MetricDelta]:
        b, c = baseline.answer_quality, current.answer_quality
        return [
            self._delta(
                "answer_quality.claim_accuracy",
                b.claim_accuracy,
                c.claim_accuracy,
            ),
            self._delta(
                "answer_quality.citation_entailment_rate",
                b.citation_entailment_rate,
                c.citation_entailment_rate,
            ),
            self._delta(
                "answer_quality.omission_rate",
                b.omission_rate,
                c.omission_rate,
                higher_is_better=False,
            ),
            self._delta(
                "answer_quality.contradiction_acknowledgment_rate",
                b.contradiction_acknowledgment_rate,
                c.contradiction_acknowledgment_rate,
            ),
        ]

    def _compare_causal_attribution(
        self,
        baseline: EvaluationMetrics,
        current: EvaluationMetrics,
    ) -> list[MetricDelta]:
        b, c = baseline.causal_attribution, current.causal_attribution
        return [
            self._delta(
                "causal_attribution.root_cause_localization_accuracy",
                b.root_cause_localization_accuracy,
                c.root_cause_localization_accuracy,
            ),
            self._delta(
                "causal_attribution.realistic_boundary_error_accuracy",
                b.realistic_boundary_error_accuracy,
                c.realistic_boundary_error_accuracy,
            ),
            self._delta(
                "causal_attribution.chunking_ablation_recovery_rate",
                b.chunking_ablation_recovery_rate,
                c.chunking_ablation_recovery_rate,
            ),
        ]

    def _compare_operational(
        self,
        baseline: EvaluationMetrics,
        current: EvaluationMetrics,
    ) -> list[MetricDelta]:
        b, c = baseline.operational, current.operational
        return [
            self._delta(
                "operational.p50_latency_ms",
                b.p50_latency_ms,
                c.p50_latency_ms,
                higher_is_better=False,
            ),
            self._delta(
                "operational.p95_latency_ms",
                b.p95_latency_ms,
                c.p95_latency_ms,
                higher_is_better=False,
            ),
            self._delta(
                "operational.p99_latency_ms",
                b.p99_latency_ms,
                c.p99_latency_ms,
                higher_is_better=False,
            ),
            self._delta(
                "operational.mean_cost_per_query_usd",
                b.mean_cost_per_query_usd,
                c.mean_cost_per_query_usd,
                higher_is_better=False,
            ),
            self._delta(
                "operational.cache_hit_rate",
                b.cache_hit_rate,
                c.cache_hit_rate,
            ),
        ]
