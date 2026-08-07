"""CLI: validate every sidecar in the corpus sidecar directory.

Usage::

    python -m scripts.validate_sidecars [--sidecar-dir corpus/sidecars]

Exit code 0 = all sidecars valid.
Exit code 1 = one or more sidecars failed validation.
"""

import argparse
import sys
from pathlib import Path

import structlog

from core.exceptions import ValidationError
from core.logging import configure_logging
from ingestion.sidecar import load_sidecar
from utils.filesystem import project_root

logger = structlog.get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate all sidecar JSON files in a directory.")
    parser.add_argument(
        "--sidecar-dir",
        default=str(project_root() / "corpus" / "sidecars"),
        help="Directory containing sidecar .json files (default: corpus/sidecars).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate sidecars and return an exit code.

    Args:
        argv: Command-line arguments; uses ``sys.argv`` when ``None``.

    Returns:
        0 if all sidecars are valid, 1 if any fail.
    """
    configure_logging()
    args = _parse_args(argv)
    sidecar_dir = Path(args.sidecar_dir)

    if not sidecar_dir.exists():
        logger.error("sidecar_dir_not_found", path=str(sidecar_dir))
        return 1

    json_files = sorted(sidecar_dir.glob("*.json"))
    if not json_files:
        logger.warning("no_sidecars_found", directory=str(sidecar_dir))
        return 0

    passed = 0
    failed = 0
    for path in json_files:
        try:
            meta = load_sidecar(path)
            logger.info("sidecar_valid", document_id=meta.document_id, path=str(path))
            passed += 1
        except (ValidationError, ValueError) as exc:
            logger.error("sidecar_invalid", path=str(path), error=str(exc))
            failed += 1
        except Exception as exc:
            logger.error("sidecar_error", path=str(path), error=str(exc))
            failed += 1

    total = passed + failed
    logger.info(
        "validation_summary",
        total=total,
        passed=passed,
        failed=failed,
    )

    if failed:
        print(f"FAILED: {failed}/{total} sidecars are invalid.", file=sys.stderr)
        return 1
    print(f"OK: all {total} sidecars are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
