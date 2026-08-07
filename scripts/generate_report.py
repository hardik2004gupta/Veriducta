"""Generate evaluation reports from an existing JSON evaluation file.

Usage::

  python scripts/generate_report.py --input evaluation_report.json
                                    [--output-dir evaluation_reports]
                                    [--formats json markdown csv html]

Re-renders a previously written evaluation JSON report in additional formats.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.report import ReportWriter
from schemas.models import EvaluationMetrics

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-render evaluation reports from an existing JSON file."
    )
    parser.add_argument("--input", required=True, help="Path to evaluation_report.json.")
    parser.add_argument(
        "--output-dir",
        default="evaluation_reports",
        help="Report output directory.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["markdown", "csv"],
        choices=["json", "markdown", "csv", "html"],
    )
    return parser.parse_args()


class _MinimalResult:
    """Minimal duck-typed wrapper so ReportWriter can operate on loaded JSON."""

    def __init__(self, data: dict) -> None:  # type: ignore[type-arg]
        self.run_id: str = data.get("run_id", "unknown")
        self.created_at: str = data.get("created_at", "")
        self.metrics: EvaluationMetrics = EvaluationMetrics.model_validate(data.get("metrics", {}))
        self.ragas_metrics: dict[str, float] = data.get("ragas_metrics", {})
        self.regression_result = None
        self.comparison_report = None


def main() -> int:
    """Entry point for the report generator script.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = _MinimalResult(data)
    except Exception as exc:
        logger.error("input_load_failed", error=str(exc))
        return 1

    writer = ReportWriter(output_dir=args.output_dir)
    try:
        paths = writer.write_all(result, formats=args.formats)
        for fmt, path in paths.items():
            logger.info("report_generated", format=fmt, path=str(path))
        return 0
    except Exception as exc:
        logger.error("report_generation_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
