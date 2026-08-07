"""Tests for evaluation/benchmark.py."""

import json

from evaluation.benchmark import BenchmarkResult, BenchmarkRunner
from evaluation.runner import EvaluationRunner
from evaluation.schemas import AnswerType, Difficulty, GoldenQAItem
from schemas.models import EvaluationMetrics


def _make_golden(question_id="qa-001"):
    return GoldenQAItem(
        question_id=question_id,
        question="What is the limit?",
        gold_answer="The limit is 100.",
        supporting_chunk_ids=["doc-001-ch-0001"],
        expected_entities=["limit"],
        expected_citations=["doc-001-ch-0001"],
        difficulty=Difficulty.EASY,
        domain="engineering",
        answer_type=AnswerType.FACTUAL,
    )


def _write_golden_file(tmp_path, items=None):
    golden_dir = tmp_path / "golden"
    golden_dir.mkdir(parents=True)
    items = items or [_make_golden()]
    path = golden_dir / "golden_qa.jsonl"
    path.write_text(
        "\n".join(item.model_dump_json() for item in items),
        encoding="utf-8",
    )
    return path


class TestBenchmarkRunner:
    def test_run_returns_benchmark_result(self, tmp_path):
        _write_golden_file(tmp_path)
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark.run()
        assert isinstance(result, BenchmarkResult)

    def test_run_has_run_id(self, tmp_path):
        _write_golden_file(tmp_path)
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark.run()
        assert result.run_id != ""

    def test_run_has_metrics(self, tmp_path):
        _write_golden_file(tmp_path)
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark.run()
        assert isinstance(result.metrics, EvaluationMetrics)

    def test_run_no_baseline_skips_regression(self, tmp_path):
        _write_golden_file(tmp_path)
        from evaluation.regression import RegressionEngine

        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(
            runner=runner,
            regression_engine=RegressionEngine(),
            dataset_dir=tmp_path,
        )
        result = benchmark.run()  # no baseline_metrics_path provided
        assert result.regression_result is None

    def test_run_with_baseline_file_runs_regression(self, tmp_path):
        _write_golden_file(tmp_path)
        # Write a baseline file
        baseline_metrics = EvaluationMetrics()
        baseline_path = tmp_path / "ci_baseline.json"
        baseline_path.write_text(
            json.dumps({"metrics": baseline_metrics.model_dump(mode="json")}),
            encoding="utf-8",
        )

        from evaluation.regression import RegressionEngine

        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(
            runner=runner,
            regression_engine=RegressionEngine(),
            dataset_dir=tmp_path,
        )
        result = benchmark.run(baseline_metrics_path=str(baseline_path))
        assert result.regression_result is not None
        assert result.regression_result.passed  # identical metrics → no violations

    def test_run_missing_baseline_file_skips_regression(self, tmp_path):
        _write_golden_file(tmp_path)
        from evaluation.regression import RegressionEngine

        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(
            runner=runner,
            regression_engine=RegressionEngine(),
            dataset_dir=tmp_path,
        )
        result = benchmark.run(baseline_metrics_path=str(tmp_path / "nonexistent.json"))
        assert result.regression_result is None

    def test_run_baseline_results_empty_without_runner(self, tmp_path):
        _write_golden_file(tmp_path)
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark.run()
        assert result.baseline_results == []

    def test_run_ragas_empty_without_adapter(self, tmp_path):
        _write_golden_file(tmp_path)
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark.run()
        assert result.ragas_metrics == {}

    def test_run_comparison_report_with_baseline(self, tmp_path):
        _write_golden_file(tmp_path)
        baseline_metrics = EvaluationMetrics()
        baseline_path = tmp_path / "ci_baseline.json"
        baseline_path.write_text(
            json.dumps({"metrics": baseline_metrics.model_dump(mode="json")}),
            encoding="utf-8",
        )

        from evaluation.regression import RegressionEngine

        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(
            runner=runner,
            regression_engine=RegressionEngine(),
            dataset_dir=tmp_path,
        )
        result = benchmark.run(baseline_metrics_path=str(baseline_path))
        assert result.comparison_report is not None

    def test_load_baseline_metrics_valid_json(self, tmp_path):
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)

        metrics = EvaluationMetrics()
        path = tmp_path / "baseline.json"
        path.write_text(metrics.model_dump_json(), encoding="utf-8")

        loaded = benchmark._load_baseline_metrics(path)
        assert loaded is not None
        assert isinstance(loaded, EvaluationMetrics)

    def test_load_baseline_metrics_missing_returns_none(self, tmp_path):
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        result = benchmark._load_baseline_metrics(tmp_path / "missing.json")
        assert result is None

    def test_load_baseline_metrics_nested_under_metrics_key(self, tmp_path):
        runner = EvaluationRunner()
        benchmark = BenchmarkRunner(runner=runner, dataset_dir=tmp_path)
        metrics = EvaluationMetrics()
        data = {"run_id": "abc", "metrics": metrics.model_dump(mode="json")}
        path = tmp_path / "report.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        # _load_baseline_metrics expects raw metrics, not nested under "metrics"
        # The method tries model_validate on the full dict - let's verify
        loaded = benchmark._load_baseline_metrics(path)
        # The full report has extra keys; model_validate still works since
        # EvaluationMetrics has model_config extra="ignore" or the keys align
        assert loaded is not None
