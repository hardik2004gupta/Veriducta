"""Compare two evaluation runs metric by metric.

Usage::

  python scripts/compare_runs.py --baseline evaluation_report_baseline.json
                                 --current evaluation_report_current.json
                                 [--output comparison.json]

Writes a JSON comparison report and prints a summary to stdout.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.comparison import RunComparator
from schemas.models import EvaluationMetrics

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two Veriducta evaluation runs.")
    parser.add_argument("--baseline", required=True, help="Baseline report JSON path.")
    parser.add_argument("--current", required=True, help="Current report JSON path.")
    parser.add_argument(
        "--output",
        default=None,
        help="Write comparison output to this JSON file.",
    )
    return parser.parse_args()


def _load_metrics(path: str) -> EvaluationMetrics:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = data.get("metrics", data)
    return EvaluationMetrics.model_validate(raw)


def main() -> int:
    """Entry point for the comparison script.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    try:
        baseline = _load_metrics(args.baseline)
        current = _load_metrics(args.current)
    except Exception as exc:
        logger.error("load_failed", error=str(exc))
        return 1

    report = RunComparator().compare(baseline, current)

    summary = {
        "baseline_run_id": report.baseline_run_id,
        "current_run_id": report.current_run_id,
        "improvements": len(report.improvements),
        "regressions": len(report.regressions),
        "deltas": [
            {
                "metric": d.metric_path,
                "baseline": d.baseline_value,
                "current": d.current_value,
                "delta": d.absolute_delta,
                "direction": d.direction,
            }
            for d in report.deltas
        ],
    }

    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info("comparison_written", path=args.output)

    logger.info(
        "comparison_summary",
        improvements=len(report.improvements),
        regressions=len(report.regressions),
    )
    for d in report.regressions:
        logger.warning(
            "metric_regression",
            metric=d.metric_path,
            baseline=d.baseline_value,
            current=d.current_value,
            delta=d.absolute_delta,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
