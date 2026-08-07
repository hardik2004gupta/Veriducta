"""Tests for evaluation/regression.py."""

import pytest

from evaluation.regression import RegressionEngine
from schemas.models import (
    AnswerQualityMetrics,
    CausalAttributionMetrics,
    EvaluationMetrics,
    OperationalMetrics,
    RetrievalMetrics,
)


def _make_metrics(
    faithfulness=0.9,
    recall5=0.8,
    p95_ms=3000.0,
    root_cause_acc=0.75,
) -> EvaluationMetrics:
    m = EvaluationMetrics()
    m.retrieval = RetrievalMetrics(recall_at_5=recall5)
    m.answer_quality = AnswerQualityMetrics(citation_entailment_rate=faithfulness)
    m.causal_attribution = CausalAttributionMetrics(root_cause_localization_accuracy=root_cause_acc)
    m.operational = OperationalMetrics(p95_latency_ms=p95_ms)
    return m


class TestRegressionEngine:
    def setup_method(self):
        self.engine = RegressionEngine()

    def test_all_pass_returns_passed(self):
        baseline = _make_metrics()
        current = _make_metrics()  # identical = no regressions
        result = self.engine.check(current, baseline)
        assert result.passed
        assert result.violations == []

    def test_faithfulness_drop_triggers_violation(self):
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.85)  # 0.05 drop > 0.02 threshold
        result = self.engine.check(current, baseline)
        assert not result.passed
        condition_names = [v.condition for v in result.violations]
        assert "faithfulness_drop" in condition_names

    def test_faithfulness_drop_within_threshold_passes(self):
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.89)  # 0.01 drop < 0.02 threshold
        result = self.engine.check(current, baseline)
        assert result.passed

    def test_recall5_drop_triggers_violation(self):
        baseline = _make_metrics(recall5=0.8)
        current = _make_metrics(recall5=0.76)  # 0.04 drop > 0.03 threshold
        result = self.engine.check(current, baseline)
        assert not result.passed
        assert any(v.condition == "recall_at_5_drop" for v in result.violations)

    def test_p95_latency_increase_triggers_violation(self):
        baseline = _make_metrics(p95_ms=3000.0)
        current = _make_metrics(p95_ms=3700.0)  # 23% increase > 20% threshold
        result = self.engine.check(current, baseline)
        assert not result.passed
        assert any(v.condition == "p95_latency_increase" for v in result.violations)

    def test_p95_latency_within_threshold_passes(self):
        baseline = _make_metrics(p95_ms=3000.0)
        current = _make_metrics(p95_ms=3500.0)  # ~16% increase < 20% threshold
        result = self.engine.check(current, baseline)
        assert result.passed

    def test_p95_zero_baseline_skips_latency_check(self):
        baseline = _make_metrics(p95_ms=0.0)
        current = _make_metrics(p95_ms=9999.0)
        result = self.engine.check(current, baseline)
        # No latency violation when baseline is 0
        assert not any(v.condition == "p95_latency_increase" for v in result.violations)

    def test_root_cause_accuracy_drop_triggers_violation(self):
        baseline = _make_metrics(root_cause_acc=0.75)
        current = _make_metrics(root_cause_acc=0.69)  # 0.06 drop > 0.05 threshold
        result = self.engine.check(current, baseline)
        assert not result.passed
        assert any(v.condition == "root_cause_accuracy_drop" for v in result.violations)

    def test_unauthorised_exposure_triggers_violation(self):
        baseline = _make_metrics()
        current = _make_metrics()
        result = self.engine.check(current, baseline, unauthorised_exposure_rate=0.01)
        assert not result.passed
        assert any(v.condition == "unauthorised_evidence_exposure" for v in result.violations)

    def test_zero_exposure_passes_condition5(self):
        baseline = _make_metrics()
        current = _make_metrics()
        result = self.engine.check(current, baseline, unauthorised_exposure_rate=0.0)
        assert not any(v.condition == "unauthorised_evidence_exposure" for v in result.violations)

    def test_multiple_violations_captured(self):
        baseline = _make_metrics(faithfulness=0.9, recall5=0.8)
        current = _make_metrics(faithfulness=0.80, recall5=0.70)
        result = self.engine.check(current, baseline)
        assert not result.passed
        assert len(result.violations) >= 2

    def test_violation_fields_populated(self):
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.80)
        result = self.engine.check(current, baseline)
        v = next(viol for viol in result.violations if viol.condition == "faithfulness_drop")
        assert v.baseline_value == pytest.approx(0.9)
        assert v.current_value == pytest.approx(0.80)
        assert v.threshold == pytest.approx(0.02)
        assert v.delta == pytest.approx(0.10)
        assert v.is_blocking

    def test_summary_includes_condition_names(self):
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.80)
        result = self.engine.check(current, baseline)
        assert "faithfulness_drop" in result.summary

    def test_custom_thresholds_honoured(self):
        engine = RegressionEngine(faithfulness_drop_max=0.15)
        baseline = _make_metrics(faithfulness=0.9)
        current = _make_metrics(faithfulness=0.80)  # 0.10 drop < 0.15 custom threshold
        result = engine.check(current, baseline)
        assert not any(v.condition == "faithfulness_drop" for v in result.violations)

    def test_improvement_does_not_trigger_violation(self):
        baseline = _make_metrics(faithfulness=0.8)
        current = _make_metrics(faithfulness=0.95)  # improvement
        result = self.engine.check(current, baseline)
        assert not any(v.condition == "faithfulness_drop" for v in result.violations)
