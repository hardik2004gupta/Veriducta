"""Evaluation report writer - JSON, Markdown, CSV, and HTML output formats.

:class:`ReportWriter` writes the output of a :class:`~evaluation.benchmark.BenchmarkResult`
to disk in one or more formats.  All methods are side-effect free except for file I/O.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from schemas.models import EvaluationMetrics

logger = structlog.get_logger(__name__)


class ReportWriter:
    """Write evaluation results to various output formats.

    Args:
        output_dir: Directory to write reports into.  Created if absent.
    """

    def __init__(self, output_dir: str | Path = "evaluation_reports") -> None:
        self._output_dir = Path(output_dir)

    def write_all(
        self,
        result: Any,
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """Write reports in all requested formats.

        Args:
            result: :class:`~evaluation.benchmark.BenchmarkResult` from
                :meth:`~evaluation.benchmark.BenchmarkRunner.run`.
            formats: Format list.  Defaults to ``["json", "markdown", "csv"]``.

        Returns:
            Dict mapping format name to the written file path.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        formats = formats or ["json", "markdown", "csv"]
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")

        paths: dict[str, Path] = {}
        for fmt in formats:
            if fmt == "json":
                paths[fmt] = self.write_json(result, timestamp)
            elif fmt == "markdown":
                paths[fmt] = self.write_markdown(result, timestamp)
            elif fmt == "csv":
                paths[fmt] = self.write_csv(result, timestamp)
            elif fmt == "html":
                paths[fmt] = self.write_html(result, timestamp)
            else:
                logger.warning("unknown_report_format", format=fmt)

        return paths

    def write_json(self, result: Any, timestamp: str = "") -> Path:
        """Write the full benchmark result as a JSON file.

        Args:
            result: :class:`~evaluation.benchmark.BenchmarkResult`.
            timestamp: ISO timestamp suffix.  Generated if empty.

        Returns:
            Path to the written file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self._output_dir / f"evaluation_report_{timestamp}.json"

        data: dict[str, Any] = {
            "run_id": result.run_id,
            "created_at": result.created_at,
            "metrics": result.metrics.model_dump(mode="json"),
            "ragas_metrics": result.ragas_metrics,
        }

        if result.regression_result is not None:
            data["regression"] = {
                "passed": result.regression_result.passed,
                "summary": result.regression_result.summary,
                "violations": [
                    {
                        "condition": v.condition,
                        "baseline_value": v.baseline_value,
                        "current_value": v.current_value,
                        "threshold": v.threshold,
                        "delta": v.delta,
                    }
                    for v in result.regression_result.violations
                ],
            }

        if result.comparison_report is not None:
            data["comparison"] = {
                "baseline_run_id": result.comparison_report.baseline_run_id,
                "current_run_id": result.comparison_report.current_run_id,
                "improvements": len(result.comparison_report.improvements),
                "regressions": len(result.comparison_report.regressions),
                "deltas": [
                    {
                        "metric": d.metric_path,
                        "baseline": d.baseline_value,
                        "current": d.current_value,
                        "delta": d.absolute_delta,
                        "direction": d.direction,
                    }
                    for d in result.comparison_report.deltas
                ],
            }

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("report_written", format="json", path=str(path))
        return path

    def write_markdown(self, result: Any, timestamp: str = "") -> Path:
        """Write an evaluation summary as a Markdown file.

        Args:
            result: :class:`~evaluation.benchmark.BenchmarkResult`.
            timestamp: ISO timestamp suffix.  Generated if empty.

        Returns:
            Path to the written file.
        """
        timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self._output_dir / f"evaluation_summary_{timestamp}.md"
        m: EvaluationMetrics = result.metrics

        lines = [
            "# Veriducta Evaluation Report",
            "",
            f"**Run ID**: `{result.run_id}`  ",
            f"**Date**: {result.created_at}",
            "",
            "## Retrieval Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Recall@5 | {m.retrieval.recall_at_5:.4f} |",
            f"| Recall@10 | {m.retrieval.recall_at_10:.4f} |",
            f"| MRR | {m.retrieval.mrr:.4f} |",
            f"| nDCG@10 | {m.retrieval.ndcg_at_10:.4f} |",
            (
                f"| Temporal-Valid Retrieval Rate"
                f" | {m.retrieval.temporal_valid_retrieval_rate:.4f} |"
            ),
            f"| Evidence Diversity | {m.retrieval.evidence_diversity:.2f} |",
            "",
            "## Answer Quality Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Claim Accuracy | {m.answer_quality.claim_accuracy:.4f} |",
            (
                "| Citation Entailment Rate (Faithfulness)"
                f" | {m.answer_quality.citation_entailment_rate:.4f} |"
            ),
            f"| Omission Rate | {m.answer_quality.omission_rate:.4f} |",
            (
                "| Contradiction Acknowledgment Rate"
                f" | {m.answer_quality.contradiction_acknowledgment_rate:.4f} |"
            ),
            "",
            "## Causal Attribution Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            (
                "| Root-Cause Localisation Accuracy"
                f" | {m.causal_attribution.root_cause_localization_accuracy:.4f} |"
            ),
            (
                "| Realistic Boundary Error Accuracy"
                f" | {m.causal_attribution.realistic_boundary_error_accuracy:.4f} |"
            ),
            (
                "| Chunking Ablation Recovery Rate"
                f" | {m.causal_attribution.chunking_ablation_recovery_rate:.4f} |"
            ),
            "",
            "## Operational Metrics",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| p50 Latency | {m.operational.p50_latency_ms:.1f} ms |",
            f"| p95 Latency | {m.operational.p95_latency_ms:.1f} ms |",
            f"| p99 Latency | {m.operational.p99_latency_ms:.1f} ms |",
            f"| Mean Cost / Query | ${m.operational.mean_cost_per_query_usd:.6f} |",
            f"| Cache Hit Rate | {m.operational.cache_hit_rate:.4f} |",
        ]

        if result.ragas_metrics:
            lines += [
                "",
                "## RAGAS Comparison",
                "",
                "| Metric | Value |",
                "| --- | --- |",
            ]
            for k, v in sorted(result.ragas_metrics.items()):
                lines.append(f"| {k} | {v:.4f} |")

        if result.regression_result is not None:
            status = "PASSED" if result.regression_result.passed else "FAILED"
            lines += [
                "",
                "## Regression Gate",
                "",
                f"**Status**: {status}  ",
                f"**Summary**: {result.regression_result.summary}",
            ]
            for v in result.regression_result.violations:
                lines.append(
                    f"- **{v.condition}**: baseline={v.baseline_value:.4f},"
                    f" current={v.current_value:.4f},"
                    f" delta={v.delta:.4f} (threshold={v.threshold:.4f})"
                )

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("report_written", format="markdown", path=str(path))
        return path

    def write_csv(self, result: Any, timestamp: str = "") -> Path:
        """Write evaluation metrics as a flat two-column CSV.

        Args:
            result: :class:`~evaluation.benchmark.BenchmarkResult`.
            timestamp: ISO timestamp suffix.  Generated if empty.

        Returns:
            Path to the written file.
        """
        timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self._output_dir / f"evaluation_metrics_{timestamp}.csv"
        m: EvaluationMetrics = result.metrics

        rows: list[tuple[str, Any]] = [
            ("run_id", result.run_id),
            ("created_at", result.created_at),
            ("retrieval.recall_at_5", m.retrieval.recall_at_5),
            ("retrieval.recall_at_10", m.retrieval.recall_at_10),
            ("retrieval.mrr", m.retrieval.mrr),
            ("retrieval.ndcg_at_10", m.retrieval.ndcg_at_10),
            ("retrieval.temporal_valid_retrieval_rate", m.retrieval.temporal_valid_retrieval_rate),
            ("retrieval.evidence_diversity", m.retrieval.evidence_diversity),
            ("answer_quality.claim_accuracy", m.answer_quality.claim_accuracy),
            ("answer_quality.citation_entailment_rate", m.answer_quality.citation_entailment_rate),
            ("answer_quality.omission_rate", m.answer_quality.omission_rate),
            (
                "answer_quality.contradiction_acknowledgment_rate",
                m.answer_quality.contradiction_acknowledgment_rate,
            ),
            (
                "causal_attribution.root_cause_localization_accuracy",
                m.causal_attribution.root_cause_localization_accuracy,
            ),
            (
                "causal_attribution.realistic_boundary_error_accuracy",
                m.causal_attribution.realistic_boundary_error_accuracy,
            ),
            (
                "causal_attribution.chunking_ablation_recovery_rate",
                m.causal_attribution.chunking_ablation_recovery_rate,
            ),
            ("operational.p50_latency_ms", m.operational.p50_latency_ms),
            ("operational.p95_latency_ms", m.operational.p95_latency_ms),
            ("operational.p99_latency_ms", m.operational.p99_latency_ms),
            ("operational.mean_cost_per_query_usd", m.operational.mean_cost_per_query_usd),
            ("operational.cache_hit_rate", m.operational.cache_hit_rate),
        ]
        for k, v in result.ragas_metrics.items():
            rows.append((f"ragas.{k}", v))

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["metric", "value"])
            writer.writerows(rows)

        logger.info("report_written", format="csv", path=str(path))
        return path

    def write_html(self, result: Any, timestamp: str = "") -> Path:
        """Write a minimal self-contained HTML evaluation report.

        The HTML wraps a ``<pre>`` block containing the Markdown report.
        A full rendered Markdown-to-HTML conversion is intentionally out of
        scope for the MVP to avoid a runtime dependency.

        Args:
            result: :class:`~evaluation.benchmark.BenchmarkResult`.
            timestamp: ISO timestamp suffix.  Generated if empty.

        Returns:
            Path to the written file.
        """
        timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        path = self._output_dir / f"evaluation_report_{timestamp}.html"

        md_path = self._output_dir / f"evaluation_summary_{timestamp}.md"
        if not md_path.exists():
            self.write_markdown(result, timestamp)
        md_content = md_path.read_text(encoding="utf-8")

        # Escape HTML special characters in the Markdown content
        safe_content = md_content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            f"<title>Veriducta Evaluation Report - {result.run_id}</title>\n"
            "<style>\n"
            "body{font-family:system-ui,sans-serif;max-width:900px;"
            "margin:2rem auto;padding:0 1rem}\n"
            "pre{background:#f5f5f5;padding:1rem;overflow:auto;white-space:pre-wrap}\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"<pre>{safe_content}</pre>\n"
            "</body>\n"
            "</html>"
        )

        path.write_text(html, encoding="utf-8")
        logger.info("report_written", format="html", path=str(path))
        return path
