"""Tests for evaluation/comparison.py."""

import pytest

from evaluation.comparison import RunComparator
from schemas.models import (
    AnswerQualityMetrics,
    CausalAttributionMetrics,
    EvaluationMetrics,
    OperationalMetrics,
    RetrievalMetrics,
)


def _make_metrics(
    recall5=0.8,
    faithfulness=0.9,
    omission=0.1,
    p95_ms=3000.0,
    root_cause_acc=0.75,
) -> EvaluationMetrics:
    m = EvaluationMetrics()
    m.retrieval = RetrievalMetrics(recall_at_5=recall5)
    m.answer_quality = AnswerQualityMetrics(
        citation_entailment_rate=faithfulness,
        omission_rate=omission,
    )
    m.causal_attribution = CausalAttributionMetrics(root_cause_localization_accuracy=root_cause_acc)
    m.operational = OperationalMetrics(p95_latency_ms=p95_ms)
    return m


class TestRunComparator:
    def setup_method(self):
        self.comparator = RunComparator()

    def test_identical_metrics_all_unchanged(self):
        m = _make_metrics()
        report = self.comparator.compare(m, m)
        # None should be "degraded" or "improved" (all unchanged or near-unchanged)
        non_unchanged = [d for d in report.deltas if d.direction != "unchanged"]
        assert non_unchanged == []

    def test_improved_recall_detected(self):
        baseline = _make_metrics(recall5=0.7)
        current = _make_metrics(recall5=0.9)
        report = self.comparator.compare(baseline, current)
        r5_delta = next(d for d in report.deltas if d.metric_path == "retrieval.recall_at_5")
        assert r5_delta.direction == "improved"
        assert r5_delta.absolute_delta == pytest.approx(0.2)

    def test_degraded_faithfulness_detected(self):
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.7)
        report = self.comparator.compare(baseline, current)
        faith_delta = next(
            d for d in report.deltas if d.metric_path == "answer_quality.citation_entailment_rate"
        )
        assert faith_delta.direction == "degraded"

    def test_omission_rate_lower_is_better(self):
        # Omission rate going DOWN (lower) is an improvement
        baseline = _make_metrics(omission=0.3)
        current = _make_metrics(omission=0.1)
        report = self.comparator.compare(baseline, current)
        om_delta = next(d for d in report.deltas if d.metric_path == "answer_quality.omission_rate")
        assert om_delta.direction == "improved"

    def test_p95_latency_higher_is_worse(self):
        # p95 going UP is a regression
        baseline = _make_metrics(p95_ms=3000.0)
        current = _make_metrics(p95_ms=5000.0)
        report = self.comparator.compare(baseline, current)
        p95_delta = next(d for d in report.deltas if d.metric_path == "operational.p95_latency_ms")
        assert p95_delta.direction == "degraded"

    def test_improvements_property(self):
        baseline = _make_metrics(recall5=0.7, faithfulness=0.7)
        current = _make_metrics(recall5=0.9, faithfulness=0.95)
        report = self.comparator.compare(baseline, current)
        assert len(report.improvements) >= 2

    def test_regressions_property(self):
        baseline = _make_metrics(recall5=0.9)
        current = _make_metrics(recall5=0.6)
        report = self.comparator.compare(baseline, current)
        assert len(report.regressions) >= 1

    def test_run_ids_in_report(self):
        baseline = _make_metrics()
        current = _make_metrics()
        baseline.run_id = "run-aaa"
        current.run_id = "run-bbb"
        report = self.comparator.compare(baseline, current)
        assert report.baseline_run_id == "run-aaa"
        assert report.current_run_id == "run-bbb"

    def test_relative_delta_computed(self):
        baseline = _make_metrics(recall5=0.8)
        current = _make_metrics(recall5=1.0)
        report = self.comparator.compare(baseline, current)
        r5_delta = next(d for d in report.deltas if d.metric_path == "retrieval.recall_at_5")
        assert r5_delta.relative_delta == pytest.approx(0.25)  # 0.2/0.8 = 0.25

    def test_zero_baseline_relative_delta_is_zero(self):
        baseline = _make_metrics(recall5=0.0)
        current = _make_metrics(recall5=0.5)
        report = self.comparator.compare(baseline, current)
        r5_delta = next(d for d in report.deltas if d.metric_path == "retrieval.recall_at_5")
        assert r5_delta.relative_delta == pytest.approx(0.0)

    def test_all_metric_paths_present(self):
        m = _make_metrics()
        report = self.comparator.compare(m, m)
        paths = {d.metric_path for d in report.deltas}
        expected = {
            "retrieval.recall_at_5",
            "retrieval.recall_at_10",
            "retrieval.mrr",
            "retrieval.ndcg_at_10",
            "retrieval.temporal_valid_retrieval_rate",
            "retrieval.evidence_diversity",
            "answer_quality.claim_accuracy",
            "answer_quality.citation_entailment_rate",
            "answer_quality.omission_rate",
            "answer_quality.contradiction_acknowledgment_rate",
            "causal_attribution.root_cause_localization_accuracy",
            "causal_attribution.realistic_boundary_error_accuracy",
            "causal_attribution.chunking_ablation_recovery_rate",
            "operational.p50_latency_ms",
            "operational.p95_latency_ms",
            "operational.p99_latency_ms",
            "operational.mean_cost_per_query_usd",
            "operational.cache_hit_rate",
        }
        assert expected.issubset(paths)
