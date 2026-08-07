"""JSONL log rotation with daily and size-based triggers.

Finished log files (any date before today) are gzip-compressed so they remain
decompressible for historical trace reads while consuming less disk space.
"""

from __future__ import annotations

import gzip
import shutil
from datetime import UTC, datetime
from pathlib import Path

import structlog

from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)

_JSONL_SUFFIX = ".jsonl"
_GZ_SUFFIX = ".jsonl.gz"


def _today_stem() -> str:
    return datetime.now(UTC).date().isoformat()


def _compress(source: Path, dest: Path) -> None:
    """Gzip-compress *source* to *dest* using a crash-safe `.tmp` intermediate."""
    tmp = dest.with_suffix(".tmp")
    try:
        with source.open("rb") as src_fh, gzip.open(tmp, "wb") as gz_fh:
            shutil.copyfileobj(src_fh, gz_fh)
        tmp.rename(dest)
        source.unlink()
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


class LogRotator:
    """Manages daily JSONL evidence log files with optional size-based rotation.

    Exactly one file is active at any moment - ``YYYY-MM-DD.jsonl`` for today.
    When the date changes, the previous file is compressed to
    ``YYYY-MM-DD.jsonl.gz`` on the next :meth:`compress_stale` call.
    Within a single day, sequential size-based rotation creates
    ``YYYY-MM-DD.1.jsonl``, ``YYYY-MM-DD.2.jsonl``, etc.

    Args:
        log_dir: Directory for JSONL and compressed files.
        max_size_bytes: Rotate within the same day when the active file reaches
                        this size.  ``0`` disables size-based rotation.
    """

    def __init__(self, log_dir: str | Path, max_size_bytes: int = 0) -> None:
        self._log_dir = Path(log_dir)
        ensure_dir(self._log_dir)
        self._max_size = max_size_bytes
        self._sequence: int = 0

    def active_path(self) -> Path:
        """Return the path of the current active JSONL file."""
        stem = _today_stem()
        if self._sequence == 0:
            return self._log_dir / f"{stem}{_JSONL_SUFFIX}"
        return self._log_dir / f"{stem}.{self._sequence}{_JSONL_SUFFIX}"

    def should_rotate(self) -> bool:
        """Return True if the active file has exceeded :attr:`_max_size`.

        Returns:
            ``False`` when size-based rotation is disabled or the file fits.
        """
        if self._max_size <= 0:
            return False
        path = self.active_path()
        return path.exists() and path.stat().st_size >= self._max_size

    def rotate_active(self) -> None:
        """Increment the sequence counter, making the next write go to a new file."""
        self._sequence += 1

    def compress_stale(self) -> list[Path]:
        """Gzip-compress all JSONL files older than today's active prefix.

        Returns:
            List of newly created ``.jsonl.gz`` paths.
        """
        today = _today_stem()
        compressed: list[Path] = []
        for jsonl_file in sorted(self._log_dir.glob(f"*{_JSONL_SUFFIX}")):
            if jsonl_file.name.startswith(today):
                continue  # still active today
            gz_path = self._log_dir / (jsonl_file.name + ".gz")
            if gz_path.exists():
                jsonl_file.unlink(missing_ok=True)
                continue
            _compress(jsonl_file, gz_path)
            compressed.append(gz_path)
            logger.info("log_file_compressed", source=jsonl_file.name, dest=gz_path.name)
        return compressed
