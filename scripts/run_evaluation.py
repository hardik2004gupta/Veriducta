"""Run the Veriducta evaluation harness (golden QA queries only).

Usage::

  python scripts/run_evaluation.py [--dataset-dir data] [--top-k 8]
                                   [--output-dir evaluation_reports]
                                   [--formats json markdown csv]

The script runs golden QA items through the pipeline (when pipeline components
are available) and writes the evaluation report to ``--output-dir``.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.benchmark import BenchmarkRunner
from evaluation.metrics import MetricsComputer
from evaluation.report import ReportWriter
from evaluation.runner import EvaluationRunner

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Veriducta evaluation harness.")
    parser.add_argument("--dataset-dir", default="data", help="Dataset root directory.")
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
        help="Report formats to write.",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point for the evaluation runner script.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    runner = EvaluationRunner()
    benchmark = BenchmarkRunner(
        runner=runner,
        metrics_computer=MetricsComputer(),
        dataset_dir=args.dataset_dir,
    )
    writer = ReportWriter(output_dir=args.output_dir)

    try:
        result = benchmark.run(top_k=args.top_k)
        paths = writer.write_all(result, formats=args.formats)
        for fmt, path in paths.items():
            logger.info("report_written", format=fmt, path=str(path))
        return 0
    except Exception as exc:
        logger.error("evaluation_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
