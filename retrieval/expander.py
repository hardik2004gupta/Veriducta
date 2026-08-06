"""Parent-child context expansion.

For each post-rerank candidate, fetches the parent chunk from Qdrant and
attaches it to the candidate.  The expansion log records which chunks were
successfully expanded and which parents were not found.
"""

from dataclasses import dataclass
from typing import Any

import structlog
from qdrant_client import QdrantClient

from core.exceptions import VectorStoreError
from retrieval._chunk_utils import payload_to_chunk
from schemas.models import Chunk, RetrievalCandidate
from utils.hashing import stable_point_id

logger = structlog.get_logger(__name__)

_COLLECTION = "veriducta_chunks"
_SECTION_BREAK = "\n\n[SECTION]\n"


@dataclass
class ExpansionLogEntry:
    """Record of a single parent-child expansion attempt.

    Args:
        child_chunk_id: Child chunk that was processed.
        parent_chunk_id: Parent chunk ID referenced in the child's payload.
        expanded: True if the parent chunk was successfully retrieved.
    """

    child_chunk_id: str
    parent_chunk_id: str | None
    expanded: bool


class ParentChildExpander:
    """Fetches parent chunks from Qdrant and enriches candidates.

    For each candidate whose ``chunk.parent_chunk_id`` is set, the parent
    chunk is retrieved from Qdrant and attached as ``candidate.parent_chunk``.
    The expansion log records every attempt for trace completeness.

    Args:
        qdrant_client: Connected :class:`~qdrant_client.QdrantClient`.
        collection_name: Qdrant collection to query.
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str = _COLLECTION,
    ) -> None:
        self._client = qdrant_client
        self._collection = collection_name

    def expand(
        self,
        candidates: list[RetrievalCandidate],
    ) -> tuple[list[RetrievalCandidate], list[ExpansionLogEntry]]:
        """Fetch parent chunks for *candidates* and build expansion log.

        Args:
            candidates: Post-rerank candidates, ideally with ``chunk`` set.

        Returns:
            Tuple of (enriched_candidates, expansion_log).
            Each enriched candidate has ``parent_chunk`` set when retrieval
            succeeded; the log records the outcome for every candidate.
        """
        expanded: list[RetrievalCandidate] = []
        log: list[ExpansionLogEntry] = []

        for cand in candidates:
            parent_id = cand.chunk.parent_chunk_id if cand.chunk else None

            if not parent_id:
                expanded.append(cand)
                log.append(
                    ExpansionLogEntry(
                        child_chunk_id=cand.chunk_id,
                        parent_chunk_id=None,
                        expanded=False,
                    )
                )
                continue

            parent_chunk = self._fetch_parent(parent_id)

            if parent_chunk:
                expanded.append(cand.model_copy(update={"parent_chunk": parent_chunk}))
                log.append(
                    ExpansionLogEntry(
                        child_chunk_id=cand.chunk_id,
                        parent_chunk_id=parent_id,
                        expanded=True,
                    )
                )
                logger.debug("parent_expanded", child_id=cand.chunk_id, parent_id=parent_id)
            else:
                expanded.append(cand)
                log.append(
                    ExpansionLogEntry(
                        child_chunk_id=cand.chunk_id,
                        parent_chunk_id=parent_id,
                        expanded=False,
                    )
                )
                logger.warning("parent_not_found", child_id=cand.chunk_id, parent_id=parent_id)

        logger.info(
            "expansion_done",
            total=len(candidates),
            expanded=sum(1 for e in log if e.expanded),
        )
        return expanded, log

    def _fetch_parent(self, parent_chunk_id: str) -> Chunk | None:
        """Retrieve a single parent chunk from Qdrant by its chunk_id."""
        point_id = stable_point_id(parent_chunk_id)
        try:
            points = self._client.retrieve(
                collection_name=self._collection,
                ids=[point_id],
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(
                "Failed to fetch parent chunk from Qdrant",
                details={"parent_chunk_id": parent_chunk_id, "error": str(exc)},
            ) from exc

        if not points:
            return None
        payload: dict[str, Any] = points[0].payload or {}
        return payload_to_chunk(payload)


def build_generation_context(candidates: list[RetrievalCandidate]) -> str:
    """Assemble the generation context string from expanded candidates.

    Each candidate contributes its child chunk text followed by the parent
    section text (if available), separated by :data:`_SECTION_BREAK`.
    Candidates are joined by double newlines.

    Args:
        candidates: Expanded candidates with ``chunk`` and optional
                    ``parent_chunk`` populated.

    Returns:
        Assembled context string ready for the structured generator.
    """
    parts: list[str] = []
    for cand in candidates:
        if not cand.chunk:
            continue
        text = cand.chunk.text
        if cand.parent_chunk and cand.parent_chunk.text:
            text += _SECTION_BREAK + cand.parent_chunk.text
        parts.append(text)
    return "\n\n".join(parts)
