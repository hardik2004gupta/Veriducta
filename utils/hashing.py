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


# Mask ensures the result fits in a signed 64-bit integer, which satisfies
# Qdrant's requirement for integer point IDs.
_POINT_ID_MASK = 0x7FFFFFFFFFFFFFFF


def stable_point_id(chunk_id: str) -> int:
    """Convert a string chunk ID to a stable unsigned 63-bit Qdrant point ID.

    Uses SHA-256 → first 8 bytes → big-endian uint64 masked to 63 bits.
    The deterministic mapping enables idempotent upserts and O(1) point lookup.

    Args:
        chunk_id: String chunk ID, e.g. ``"usgs-2021-001-ch-0042"``.

    Returns:
        Unsigned 63-bit integer suitable for use as a Qdrant point ID.
    """
    digest = hashlib.sha256(chunk_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") & _POINT_ID_MASK
