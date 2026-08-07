"""Benchmark runner — orchestrates the full evaluation pipeline.

:class:`BenchmarkRunner` is the top-level orchestrator that combines:

- Primary evaluation (:class:`~evaluation.runner.EvaluationRunner`)
- Metrics computation (:class:`~evaluation.metrics.MetricsComputer`)
- Baseline comparisons (:class:`~evaluation.baseline.BaselineRunner`)
- Optional RAGAS baseline (:class:`~evaluation.ragas_adapter.RAGASAdapter`)
- Regression gate (:class:`~evaluation.regression.RegressionEngine`)
- Cross-run comparison (:class:`~evaluation.comparison.RunComparator`)

The :meth:`BenchmarkRunner.run` method returns a :class:`BenchmarkResult`
that :class:`~evaluation.report.ReportWriter` can serialise to disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from evaluation.baseline import BaselineResult, BaselineRunner
from evaluation.comparison import ComparisonReport, RunComparator
from evaluation.loader import DatasetLoader
from evaluation.metrics import MetricsComputer
from evaluation.ragas_adapter import RAGASAdapter
from evaluation.regression import RegressionEngine, RegressionResult
from evaluation.runner import EvaluationRunner, EvaluationRunResults
from schemas.models import EvaluationMetrics

logger = structlog.get_logger(__name__)


@dataclass
class BenchmarkResult:
    """Complete benchmark output aggregating all evaluation components."""

    run_id: str
    run_results: EvaluationRunResults
    metrics: EvaluationMetrics
    baseline_results: list[BaselineResult] = field(default_factory=list)
    ragas_metrics: dict[str, float] = field(default_factory=dict)
    regression_result: RegressionResult | None = None
    comparison_report: ComparisonReport | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class BenchmarkRunner:
    """Orchestrate full evaluation, baselines, RAGAS comparison, and regression gate.

    Args:
        runner: Primary :class:`~evaluation.runner.EvaluationRunner` (full pipeline).
        metrics_computer: Computes :class:`~schemas.models.EvaluationMetrics`.
            Defaults to a freshly constructed :class:`~evaluation.metrics.MetricsComputer`.
        baseline_runner: Optional baseline runner with registered variants.
        ragas_adapter: Optional RAGAS adapter (gracefully skipped when unavailable).
        regression_engine: Optional regression engine.
        comparator: Optional run comparator.
        dataset_dir: Root directory for golden QA and corruption datasets.
    """

    def __init__(
        self,
        runner: EvaluationRunner,
        metrics_computer: MetricsComputer | None = None,
        baseline_runner: BaselineRunner | None = None,
        ragas_adapter: RAGASAdapter | None = None,
        regression_engine: RegressionEngine | None = None,
        comparator: RunComparator | None = None,
        dataset_dir: str | Path = "data",
    ) -> None:
        self._runner = runner
        self._metrics_computer = metrics_computer or MetricsComputer()
        self._baseline_runner = baseline_runner
        self._ragas_adapter = ragas_adapter
        self._regression_engine = regression_engine
        self._comparator = comparator or RunComparator()
        self._loader = DatasetLoader(dataset_dir=dataset_dir)

    def run(
        self,
        golden_path: str | Path | None = None,
        corruptions_path: str | Path | None = None,
        baseline_metrics_path: str | Path | None = None,
        top_k: int = 8,
    ) -> BenchmarkResult:
        """Execute the full benchmark.

        Args:
            golden_path: Path to ``golden_qa.jsonl``.  Defaults to
                ``{dataset_dir}/golden/golden_qa.jsonl``.
            corruptions_path: Path to ``corruptions.jsonl``.
            baseline_metrics_path: Path to ``ci_baseline.json`` for regression
                gate.  When ``None`` the regression check is skipped.
            top_k: Retrieval top-k for all runs.

        Returns:
            :class:`BenchmarkResult` with all populated components.
        """
        run_id = str(uuid4())
        logger.info("benchmark_started", run_id=run_id)

        # Load dataset
        golden_items = self._loader.load_golden_qa(path=golden_path)
        logger.info("golden_qa_loaded", count=len(golden_items))

        corruption_cases = []
        if corruptions_path is not None:
            corruption_cases = self._loader.load_corruptions(path=corruptions_path)
            logger.info("corruptions_loaded", count=len(corruption_cases))

        # Primary evaluation
        query_results = self._runner.run_golden_qa(golden_items, top_k=top_k)
        corruption_results = (
            self._runner.run_corruption_benchmark(corruption_cases) if corruption_cases else []
        )
        run_results = self._runner.build_run_results(query_results, corruption_results)
        run_results.run_id = run_id

        # Metrics
        metrics = self._metrics_computer.compute(run_results, golden_items)
        metrics.run_id = run_id
        logger.info("metrics_computed", run_id=run_id)

        # Baselines
        baseline_results: list[BaselineResult] = []
        if self._baseline_runner is not None:
            baseline_results = self._baseline_runner.run_all(golden_items, top_k=top_k)
            logger.info("baselines_complete", count=len(baseline_results))

        # RAGAS
        ragas_metrics: dict[str, float] = {}
        if self._ragas_adapter is not None and self._ragas_adapter.is_available():
            ragas_metrics = self._run_ragas(query_results, golden_items)

        # Regression gate and comparison
        regression_result: RegressionResult | None = None
        comparison_report: ComparisonReport | None = None
        if baseline_metrics_path is not None and self._regression_engine is not None:
            stored = self._load_baseline_metrics(Path(baseline_metrics_path))
            if stored is not None:
                regression_result = self._regression_engine.check(metrics, stored)
                comparison_report = self._comparator.compare(stored, metrics)

        result = BenchmarkResult(
            run_id=run_id,
            run_results=run_results,
            metrics=metrics,
            baseline_results=baseline_results,
            ragas_metrics=ragas_metrics,
            regression_result=regression_result,
            comparison_report=comparison_report,
        )
        logger.info(
            "benchmark_complete",
            run_id=run_id,
            regression_passed=(regression_result.passed if regression_result is not None else None),
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_ragas(
        self,
        query_results: list[Any],
        golden_items: list[Any],
    ) -> dict[str, float]:
        """Extract pipeline outputs for RAGAS and run the adapter."""
        assert self._ragas_adapter is not None
        golden_by_id = {item.question_id: item for item in golden_items}
        questions: list[str] = []
        answers: list[str] = []
        contexts: list[list[str]] = []
        ground_truths: list[str] = []

        for result in query_results:
            if result.structured_answer is None:
                continue
            golden = golden_by_id.get(result.question_id)
            if golden is None:
                continue
            context_texts = [
                c.chunk.text
                for c in (result.retrieval_result.candidates if result.retrieval_result else [])
                if c.chunk is not None
            ]
            questions.append(result.question)
            answers.append(result.structured_answer.answer)
            contexts.append(context_texts)
            ground_truths.append(golden.gold_answer)

        return self._ragas_adapter.compute(questions, answers, contexts, ground_truths)

    def _load_baseline_metrics(self, path: Path) -> EvaluationMetrics | None:
        """Load baseline :class:`~schemas.models.EvaluationMetrics` from a JSON file."""
        if not path.exists():
            logger.warning("baseline_metrics_not_found", path=str(path))
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return EvaluationMetrics.model_validate(data)
        except Exception as exc:
            logger.error("baseline_metrics_load_failed", path=str(path), error=str(exc))
            return None
