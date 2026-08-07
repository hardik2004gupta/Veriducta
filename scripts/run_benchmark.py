"""Run the full Veriducta benchmark (evaluation + corruption benchmark).

Usage::

  python scripts/run_benchmark.py [--dataset-dir data]
                                  [--golden-path data/golden/golden_qa.jsonl]
                                  [--corruptions-path data/synthetic/corruptions.jsonl]
                                  [--baseline ci_baseline.json]
                                  [--output-dir evaluation_reports]
                                  [--top-k 8]
                                  [--formats json markdown csv]

Runs all 40 golden QA items and all 60 corruption cases, writes the benchmark
report, and checks the regression gate if ``--baseline`` is provided.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.benchmark import BenchmarkRunner
from evaluation.metrics import MetricsComputer
from evaluation.ragas_adapter import RAGASAdapter
from evaluation.regression import RegressionEngine
from evaluation.report import ReportWriter
from evaluation.runner import EvaluationRunner

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Veriducta benchmark.")
    parser.add_argument("--dataset-dir", default="data", help="Dataset root directory.")
    parser.add_argument(
        "--golden-path",
        default=None,
        help="Override golden QA path.",
    )
    parser.add_argument(
        "--corruptions-path",
        default=None,
        help="Override corruption cases path.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        dest="baseline_path",
        help="Path to ci_baseline.json for regression checking.",
    )
    parser.add_argument("--top-k", type=int, default=8, help="Retrieval top-k.")
    parser.add_argument(
        "--output-dir",
        default="evaluation_reports",
        help="Report output directory.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["json", "markdown", "csv"],
        choices=["json", "markdown", "csv", "html"],
    )
    return parser.parse_args()


def main() -> int:
    """Entry point for the benchmark runner script.

    Returns:
        Exit code: 0 for success (or regression passed), 1 for failure.
    """
    args = _parse_args()

    runner = EvaluationRunner()
    regression_engine = RegressionEngine() if args.baseline_path else None

    benchmark = BenchmarkRunner(
        runner=runner,
        metrics_computer=MetricsComputer(),
        ragas_adapter=RAGASAdapter(),
        regression_engine=regression_engine,
        dataset_dir=args.dataset_dir,
    )
    writer = ReportWriter(output_dir=args.output_dir)

    try:
        result = benchmark.run(
            golden_path=args.golden_path,
            corruptions_path=args.corruptions_path,
            baseline_metrics_path=args.baseline_path,
            top_k=args.top_k,
        )
        paths = writer.write_all(result, formats=args.formats)
        for fmt, path in paths.items():
            logger.info("report_written", format=fmt, path=str(path))

        if result.regression_result is not None and not result.regression_result.passed:
            logger.error(
                "regression_gate_failed",
                summary=result.regression_result.summary,
            )
            return 1

        return 0
    except Exception as exc:
        logger.error("benchmark_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
