"""Stable identifier generation utilities."""

import uuid


def new_uuid() -> str:
    """Return a new UUID4 as a lowercase string."""
    return str(uuid.uuid4())


def chunk_id(document_id: str, index: int) -> str:
    """Generate a stable child chunk ID.

    Args:
        document_id: Owning document identifier.
        index: Zero-based chunk index within the document.
    """
    return f"{document_id}-ch-{index:04d}"


def parent_chunk_id(document_id: str, index: int) -> str:
    """Generate a stable parent chunk ID.

    Args:
        document_id: Owning document identifier.
        index: Zero-based parent index within the document.
    """
    return f"{document_id}-par-{index:04d}"


def trace_id() -> str:
    """Return a new trace UUID for pipeline execution tracking."""
    return str(uuid.uuid4())
