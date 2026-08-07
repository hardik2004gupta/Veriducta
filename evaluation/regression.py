"""Regression gate - enforces five blocking quality thresholds between runs.

Five blocking conditions (CLAUDE.md Phase 18):

1. Faithfulness (``citation_entailment_rate``) drops > 2% from baseline.
2. Recall@5 drops > 3% from baseline.
3. p95 latency increases > 20% from baseline.
4. Root-cause localisation accuracy drops > 5% from baseline.
5. Unauthorised evidence exposure rate > 0%.

:class:`RegressionEngine` returns a :class:`RegressionResult` with a boolean
``passed`` flag and a list of :class:`RegressionViolation` records.  CLI callers
should exit with code 1 when ``passed is False``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from schemas.models import EvaluationMetrics

logger = structlog.get_logger(__name__)


@dataclass
class RegressionViolation:
    """One blocking regression condition that fired."""

    condition: str
    baseline_value: float
    current_value: float
    threshold: float
    delta: float
    is_blocking: bool = True


@dataclass
class RegressionResult:
    """Outcome of a full regression gate check."""

    passed: bool
    violations: list[RegressionViolation] = field(default_factory=list)
    summary: str = ""


class RegressionEngine:
    """Check whether current evaluation metrics pass all five regression gates.

    Args:
        faithfulness_drop_max: Max allowed drop in citation entailment rate
            (absolute, e.g. 0.02 = 2%).
        recall5_drop_max: Max allowed drop in Recall@5 (absolute).
        p95_latency_increase_max: Max allowed *fractional* increase in p95
            latency (e.g. 0.20 = 20%).
        root_cause_drop_max: Max allowed drop in root-cause accuracy (absolute).
        evidence_exposure_max: Max allowed unauthorised evidence exposure rate.
    """

    def __init__(
        self,
        faithfulness_drop_max: float = 0.02,
        recall5_drop_max: float = 0.03,
        p95_latency_increase_max: float = 0.20,
        root_cause_drop_max: float = 0.05,
        evidence_exposure_max: float = 0.0,
    ) -> None:
        self._faithfulness_drop_max = faithfulness_drop_max
        self._recall5_drop_max = recall5_drop_max
        self._p95_latency_increase_max = p95_latency_increase_max
        self._root_cause_drop_max = root_cause_drop_max
        self._evidence_exposure_max = evidence_exposure_max

    def check(
        self,
        current: EvaluationMetrics,
        baseline: EvaluationMetrics,
        unauthorised_exposure_rate: float = 0.0,
    ) -> RegressionResult:
        """Run all five blocking regression conditions.

        Args:
            current: Metrics from the evaluation run under test.
            baseline: Metrics from the stored baseline (``ci_baseline.json``).
            unauthorised_exposure_rate: Rate of unauthorised evidence exposures
                (Condition 5).  Caller must compute this from evidence log audits.

        Returns:
            :class:`RegressionResult` with ``passed=True`` iff all conditions pass.
        """
        violations: list[RegressionViolation] = []

        # Condition 1 - faithfulness drop
        faith_drop = (
            baseline.answer_quality.citation_entailment_rate
            - current.answer_quality.citation_entailment_rate
        )
        if faith_drop > self._faithfulness_drop_max:
            violations.append(
                RegressionViolation(
                    condition="faithfulness_drop",
                    baseline_value=baseline.answer_quality.citation_entailment_rate,
                    current_value=current.answer_quality.citation_entailment_rate,
                    threshold=self._faithfulness_drop_max,
                    delta=faith_drop,
                )
            )

        # Condition 2 - Recall@5 drop
        r5_drop = baseline.retrieval.recall_at_5 - current.retrieval.recall_at_5
        if r5_drop > self._recall5_drop_max:
            violations.append(
                RegressionViolation(
                    condition="recall_at_5_drop",
                    baseline_value=baseline.retrieval.recall_at_5,
                    current_value=current.retrieval.recall_at_5,
                    threshold=self._recall5_drop_max,
                    delta=r5_drop,
                )
            )

        # Condition 3 - p95 latency increase (fractional)
        p95_base = baseline.operational.p95_latency_ms
        p95_cur = current.operational.p95_latency_ms
        if p95_base > 0.0:
            p95_increase = (p95_cur - p95_base) / p95_base
            if p95_increase > self._p95_latency_increase_max:
                violations.append(
                    RegressionViolation(
                        condition="p95_latency_increase",
                        baseline_value=p95_base,
                        current_value=p95_cur,
                        threshold=self._p95_latency_increase_max,
                        delta=p95_increase,
                    )
                )

        # Condition 4 - root-cause accuracy drop
        rca_drop = (
            baseline.causal_attribution.root_cause_localization_accuracy
            - current.causal_attribution.root_cause_localization_accuracy
        )
        if rca_drop > self._root_cause_drop_max:
            violations.append(
                RegressionViolation(
                    condition="root_cause_accuracy_drop",
                    baseline_value=(baseline.causal_attribution.root_cause_localization_accuracy),
                    current_value=(current.causal_attribution.root_cause_localization_accuracy),
                    threshold=self._root_cause_drop_max,
                    delta=rca_drop,
                )
            )

        # Condition 5 - unauthorised evidence exposure
        if unauthorised_exposure_rate > self._evidence_exposure_max:
            violations.append(
                RegressionViolation(
                    condition="unauthorised_evidence_exposure",
                    baseline_value=self._evidence_exposure_max,
                    current_value=unauthorised_exposure_rate,
                    threshold=self._evidence_exposure_max,
                    delta=unauthorised_exposure_rate,
                )
            )

        passed = len(violations) == 0
        if passed:
            summary = "All regression gates passed."
        else:
            names = ", ".join(v.condition for v in violations)
            summary = f"Regression FAILED - {len(violations)} violation(s): {names}"

        logger.info(
            "regression_gate_result",
            passed=passed,
            violation_count=len(violations),
            summary=summary,
        )
        return RegressionResult(passed=passed, violations=violations, summary=summary)
