"""Internal helper: reconstruct Chunk objects from Qdrant point payloads.

Used by dense_retriever, expander, and retriever to convert raw Qdrant
payload dicts into typed :class:`~schemas.models.Chunk` objects.
"""

from typing import Any

from schemas.models import Chunk


def payload_to_chunk(payload: dict[str, Any]) -> Chunk | None:
    """Reconstruct a :class:`~schemas.models.Chunk` from a Qdrant point payload.

    Args:
        payload: Raw payload dict from a Qdrant ``ScoredPoint`` or ``Record``.

    Returns:
        :class:`~schemas.models.Chunk` if all required fields are present,
        ``None`` if the payload is missing ``chunk_id`` or ``document_id``.
    """
    try:
        return Chunk(
            chunk_id=payload["chunk_id"],
            document_id=payload["document_id"],
            text=payload.get("text", ""),
            parent_chunk_id=payload.get("parent_chunk_id"),
            token_count=int(payload.get("token_count", 0)),
            chunk_index=int(payload.get("chunk_index", 0)),
            is_table=bool(payload.get("is_table", False)),
            effective_date=payload.get("effective_date"),
            expiry_date=payload.get("expiry_date"),
            page_number=payload.get("page_number"),
        )
    except (KeyError, TypeError, ValueError):
        return None
