"""Deterministic hashing utilities."""

import hashlib
import json
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_str(text: str, *, encoding: str = "utf-8") -> str:
    """Return hex-encoded SHA-256 digest of a UTF-8 string."""
    return sha256_bytes(text.encode(encoding))


def sha256_json(obj: Any) -> str:
    """Return hex-encoded SHA-256 of a deterministically serialised object.

    Keys are sorted to ensure identical objects always produce the same hash
    regardless of insertion order.
    """
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_str(canonical)


def sha256_file(path: str) -> str:
    """Return hex-encoded SHA-256 digest of the contents of a file.

    Args:
        path: Absolute file path to hash.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()
