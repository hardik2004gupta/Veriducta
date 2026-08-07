"""Run the regression gate against a stored baseline.

Usage::

  python scripts/regression_check.py --current evaluation_report.json
                                     --baseline ci_baseline.json
                                     [--exposure-rate 0.0]

Exits with code 0 when all five regression conditions pass.
Exits with code 1 when one or more conditions fail.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.regression import RegressionEngine
from schemas.models import EvaluationMetrics

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check evaluation metrics against the CI regression baseline."
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to the current evaluation_report.json.",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to ci_baseline.json.",
    )
    parser.add_argument(
        "--exposure-rate",
        type=float,
        default=0.0,
        help="Unauthorised evidence exposure rate (default 0.0).",
    )
    return parser.parse_args()


def _load_metrics(path: str) -> EvaluationMetrics:
    """Load EvaluationMetrics from a JSON report file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # The report embeds metrics under a "metrics" key
    raw = data.get("metrics", data)
    return EvaluationMetrics.model_validate(raw)


def main() -> int:
    """Entry point for the regression check script.

    Returns:
        0 if all gates pass, 1 if any gate fails.
    """
    args = _parse_args()

    try:
        current = _load_metrics(args.current)
        baseline = _load_metrics(args.baseline)
    except Exception as exc:
        logger.error("metrics_load_failed", error=str(exc))
        return 1

    engine = RegressionEngine()
    result = engine.check(current, baseline, unauthorised_exposure_rate=args.exposure_rate)

    if result.passed:
        logger.info("regression_gate_passed")
        return 0

    logger.error("regression_gate_failed", summary=result.summary)
    for v in result.violations:
        logger.error(
            "regression_violation",
            condition=v.condition,
            baseline=v.baseline_value,
            current=v.current_value,
            delta=v.delta,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
