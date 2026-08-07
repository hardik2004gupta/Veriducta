"""Validate the evaluation dataset JSONL files on disk.

Runs all structural and semantic validation checks and exits non-zero if any
ERROR-severity issues are found.  WARNING-severity issues are reported but do
not cause a non-zero exit.

Usage:
  python scripts/validate_dataset.py [--dataset-dir data] [--strict]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.dataset import DatasetManager

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Veriducta evaluation dataset files.")
    parser.add_argument(
        "--dataset-dir",
        default="data",
        help="Root directory for dataset files (default: data).",
    )
    parser.add_argument(
        "--golden-path",
        default=None,
        help="Override path for golden QA JSONL.",
    )
    parser.add_argument(
        "--corruptions-path",
        default=None,
        help="Override path for corruptions JSONL.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point for the validate_dataset script.

    Returns:
        Exit code: 0 for pass, 1 for errors (or warnings with --strict).
    """
    args = _parse_args()

    manager = DatasetManager(dataset_dir=args.dataset_dir)
    try:
        manager.load_from_files(
            golden_path=args.golden_path,
            corruptions_path=args.corruptions_path,
        )
    except Exception as exc:
        logger.error("dataset_load_failed", error=str(exc))
        return 1

    results = manager.validate()

    exit_code = 0
    for check, result in results.items():
        has_blocking = result.errors_count > 0 or (args.strict and result.warnings_count > 0)
        if has_blocking:
            exit_code = 1

        logger.info(
            "validation_check",
            check=check,
            is_valid=result.is_valid,
            errors=result.errors_count,
            warnings=result.warnings_count,
        )
        for issue in result.issues:
            if issue.severity == "error":
                logger.error(
                    "validation_error",
                    type=issue.issue_type,
                    item=issue.item_id,
                    message=issue.message,
                )
            else:
                logger.warning(
                    "validation_warning",
                    type=issue.issue_type,
                    item=issue.item_id,
                    message=issue.message,
                )

    if exit_code == 0:
        logger.info("validation_all_passed", strict=args.strict)
    else:
        logger.error("validation_failed", strict=args.strict)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
