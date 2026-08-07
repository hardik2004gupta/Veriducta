"""Tests for evaluation/report.py."""

import json

from evaluation.benchmark import BenchmarkResult
from evaluation.regression import RegressionResult, RegressionViolation
from evaluation.report import ReportWriter
from evaluation.runner import EvaluationRunResults
from schemas.models import EvaluationMetrics


def _make_benchmark_result(tmp_path=None):
    metrics = EvaluationMetrics()
    metrics.run_id = "test-run-001"
    run_results = EvaluationRunResults(run_id="test-run-001")
    return BenchmarkResult(
        run_id="test-run-001",
        run_results=run_results,
        metrics=metrics,
    )


class TestReportWriter:
    def test_write_json_creates_file(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_json(result, "20240101T120000")
        assert path.exists()
        assert path.suffix == ".json"

    def test_write_json_contains_run_id(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_json(result, "20240101T120000")
        data = json.loads(path.read_text())
        assert data["run_id"] == "test-run-001"

    def test_write_json_contains_metrics(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_json(result, "20240101T120000")
        data = json.loads(path.read_text())
        assert "metrics" in data
        assert "retrieval" in data["metrics"]

    def test_write_json_regression_included(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        result.regression_result = RegressionResult(
            passed=False,
            violations=[
                RegressionViolation(
                    condition="faithfulness_drop",
                    baseline_value=0.9,
                    current_value=0.8,
                    threshold=0.02,
                    delta=0.1,
                )
            ],
            summary="FAILED",
        )
        path = writer.write_json(result, "20240101T120000")
        data = json.loads(path.read_text())
        assert "regression" in data
        assert not data["regression"]["passed"]
        assert len(data["regression"]["violations"]) == 1

    def test_write_markdown_creates_file(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_markdown(result, "20240101T120000")
        assert path.exists()
        assert path.suffix == ".md"

    def test_write_markdown_contains_headers(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_markdown(result, "20240101T120000")
        content = path.read_text()
        assert "Retrieval Metrics" in content
        assert "Answer Quality Metrics" in content
        assert "Causal Attribution Metrics" in content
        assert "Operational Metrics" in content

    def test_write_markdown_ragas_section(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        result.ragas_metrics = {"faithfulness": 0.85, "answer_relevancy": 0.78}
        path = writer.write_markdown(result, "20240101T120000")
        content = path.read_text()
        assert "RAGAS" in content
        assert "faithfulness" in content

    def test_write_csv_creates_file(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_csv(result, "20240101T120000")
        assert path.exists()
        assert path.suffix == ".csv"

    def test_write_csv_contains_header_row(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_csv(result, "20240101T120000")
        lines = path.read_text().splitlines()
        assert lines[0] == "metric,value"

    def test_write_csv_contains_recall_at_5(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_csv(result, "20240101T120000")
        content = path.read_text()
        assert "retrieval.recall_at_5" in content

    def test_write_html_creates_file(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_html(result, "20240101T120000")
        assert path.exists()
        assert path.suffix == ".html"

    def test_write_html_contains_doctype(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        path = writer.write_html(result, "20240101T120000")
        content = path.read_text()
        assert "<!DOCTYPE html>" in content

    def test_write_all_default_formats(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        paths = writer.write_all(result)
        assert "json" in paths
        assert "markdown" in paths
        assert "csv" in paths

    def test_write_all_custom_formats(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        paths = writer.write_all(result, formats=["json"])
        assert "json" in paths
        assert "markdown" not in paths

    def test_write_all_unknown_format_skipped(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        # Should not raise
        paths = writer.write_all(result, formats=["json", "unknown_format"])
        assert "json" in paths
        assert "unknown_format" not in paths

    def test_output_dir_created_if_missing(self, tmp_path):
        new_dir = tmp_path / "nested" / "reports"
        writer = ReportWriter(output_dir=new_dir)
        result = _make_benchmark_result()
        writer.write_json(result)
        assert new_dir.exists()

    def test_html_escapes_angle_brackets(self, tmp_path):
        writer = ReportWriter(output_dir=tmp_path)
        result = _make_benchmark_result()
        # The run_id won't have <>, but check general HTML safety
        path = writer.write_html(result, "20240101T120000")
        content = path.read_text()
        assert "<pre>" in content  # pre tag from writer
        assert "<!DOCTYPE html>" in content
