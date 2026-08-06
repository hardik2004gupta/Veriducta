"""Filesystem helper utilities."""

import os
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """Create *path* and all parent directories if they do not exist.

    Args:
        path: Directory path to create.

    Returns:
        Resolved Path object.
    """
    resolved = Path(path).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def project_root() -> Path:
    """Return the project root directory.

    Walks up from this file until it finds ``pyproject.toml``.
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not locate pyproject.toml — is this a Veriducta project?")


def safe_filename(name: str) -> str:
    """Return a filesystem-safe version of *name*.

    Replaces characters that are invalid in file names across platforms.
    """
    keep = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    return "".join(c if c in keep else "_" for c in name)


def file_size_bytes(path: str | Path) -> int:
    """Return the byte size of the file at *path*.

    Args:
        path: Absolute or relative path to an existing file.
    """
    return os.path.getsize(path)
