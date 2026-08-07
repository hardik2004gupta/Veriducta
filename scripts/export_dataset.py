"""Export the evaluation dataset to JSONL, CSV, and Markdown formats.

Usage:
  python scripts/export_dataset.py [--dataset-dir data] [--formats jsonl csv markdown]
                                   [--export-dir data/exports]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.logging import get_logger
from evaluation.dataset import DatasetManager

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Veriducta evaluation dataset.")
    parser.add_argument(
        "--dataset-dir",
        default="data",
        help="Root directory for dataset files (default: data).",
    )
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Output directory for exports (default: {dataset-dir}/exports).",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["jsonl", "csv", "markdown"],
        default=["jsonl", "csv", "markdown"],
        help="Export formats to generate (default: all three).",
    )
    parser.add_argument(
        "--from-seed",
        action="store_true",
        help="Load from embedded seed data instead of disk files.",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point for the export_dataset script.

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

    export_dir = args.export_dir or str(Path(args.dataset_dir) / "exports")
    try:
        written = manager.export(formats=args.formats, export_dir=export_dir)
    except Exception as exc:
        logger.error("dataset_export_failed", error=str(exc))
        return 1

    for key, path in written.items():
        logger.info("exported", name=key, path=str(path))

    logger.info("export_complete", file_count=len(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
