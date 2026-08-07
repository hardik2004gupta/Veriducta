"""Build the evaluation dataset from seed data.

Generates:
  data/golden/golden_qa.jsonl       - 40 golden QA pairs
  data/synthetic/corruptions.jsonl  - 60 synthetic corruption cases
  data/annotations/annotation_schema.json

Usage:
  python scripts/build_dataset.py [--dataset-dir data]
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from core.logging import get_logger
from evaluation.dataset import DatasetManager

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Veriducta evaluation dataset from embedded seed data."
    )
    parser.add_argument(
        "--dataset-dir",
        default="data",
        help="Root directory for dataset files (default: data).",
    )
    parser.add_argument(
        "--golden-path",
        default=None,
        help="Override path for golden QA JSONL output.",
    )
    parser.add_argument(
        "--corruptions-path",
        default=None,
        help="Override path for corruptions JSONL output.",
    )
    parser.add_argument(
        "--schema-path",
        default=None,
        help="Override path for annotation schema JSON output.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip validation after building (not recommended).",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point for the build_dataset script.

    Returns:
        Exit code: 0 for success, 1 for validation errors.
    """
    args = _parse_args()
    start = time.monotonic()

    manager = DatasetManager(dataset_dir=args.dataset_dir)

    logger.info("build_dataset_started", dataset_dir=args.dataset_dir)

    manager.build_and_write(
        golden_path=args.golden_path,
        corruptions_path=args.corruptions_path,
        annotation_schema_path=args.schema_path,
    )

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("dataset_files_written", elapsed_ms=round(elapsed_ms, 1))

    if args.skip_validation:
        logger.warning("validation_skipped")
        return 0

    # Reload from files to validate the written output.
    manager.load_from_files()
    results = manager.validate()

    all_valid = True
    for check, result in results.items():
        if not result.is_valid:
            all_valid = False
            logger.error(
                "validation_failed",
                check=check,
                errors=result.errors_count,
                warnings=result.warnings_count,
            )
            for issue in result.issues:
                if issue.severity == "error":
                    logger.error(
                        "validation_issue",
                        type=issue.issue_type,
                        item=issue.item_id,
                        message=issue.message,
                    )
        else:
            logger.info(
                "validation_passed",
                check=check,
                warnings=result.warnings_count,
            )

    stats = manager.compute_stats()
    logger.info(
        "dataset_build_complete",
        golden_count=stats.total_questions,
        corruptions_count=stats.total_corruptions,
        realistic_boundary_errors=stats.realistic_boundary_error_count,
        elapsed_ms=round(elapsed_ms, 1),
    )

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
