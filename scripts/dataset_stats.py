"""Print summary statistics for the evaluation dataset.

Usage:
  python scripts/dataset_stats.py [--dataset-dir data] [--from-seed]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.dataset import DatasetManager

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print Veriducta dataset statistics.")
    parser.add_argument(
        "--dataset-dir",
        default="data",
        help="Root directory for dataset files (default: data).",
    )
    parser.add_argument(
        "--from-seed",
        action="store_true",
        help="Load from embedded seed data instead of disk files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output statistics as JSON instead of formatted text.",
    )
    return parser.parse_args()


def _print_distribution(title: str, dist: dict[str, Any]) -> None:
    print(f"\n  {title}:")
    for key, count in sorted(dist.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 30)
        print(f"    {key:<30} {bar} {count}")


def main() -> int:
    """Entry point for the dataset_stats script.

    Returns:
        Exit code: 0 for success, 1 for failure.
    """
    args = _parse_args()

    manager = DatasetManager(dataset_dir=args.dataset_dir)
    try:
        if args.from_seed:
            manager.load_from_seed()
        else:
            manager.load_from_files()
    except Exception as exc:
        logger.error("dataset_load_failed", error=str(exc))
        return 1

    stats = manager.compute_stats()

    if args.json_output:
        print(json.dumps(stats.model_dump(), indent=2))
        return 0

    print("=" * 60)
    print("  VERIDUCTA EVALUATION DATASET STATISTICS")
    print("=" * 60)

    print(f"\nGolden QA: {stats.total_questions} items")
    _print_distribution("Difficulty", stats.difficulty_distribution)
    _print_distribution("Domain", stats.domain_distribution)
    _print_distribution("Failure Mode", stats.failure_mode_distribution)
    _print_distribution("Answer Type", stats.answer_type_distribution)
    _print_distribution("Review Status", stats.review_status_distribution)
    print(f"\n  Avg supporting chunks: {stats.mean_supporting_chunks}")
    print(f"  Total supporting chunks: {stats.total_supporting_chunks}")

    print(f"\nCorruption Cases: {stats.total_corruptions} items")
    _print_distribution("Root Cause", stats.root_cause_distribution)
    _print_distribution("Corruption Type", stats.corruption_type_distribution)
    print(f"\n  Realistic boundary errors: {stats.realistic_boundary_error_count}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
