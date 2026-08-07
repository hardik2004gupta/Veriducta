"""Temporal validity filter for retrieval candidates.

Rejects chunks whose source document is not valid on the query date:
- not yet effective (``effective_date > query_date``), or
- superseded by another document effective on or before ``query_date``.

A :class:`_VersionGraphLike` Protocol decouples this module from the
``ingestion`` package, preserving the strict downward dependency rule.
"""

from dataclasses import dataclass, field
from typing import Protocol

import structlog

from observability.metrics import TEMPORAL_FILTER_REJECTIONS
from schemas.models import RetrievalCandidate

logger = structlog.get_logger(__name__)


class _VersionGraphLike(Protocol):
    """Minimal interface required from the version graph at retrieval time."""

    def get_valid_documents(self, query_date: str) -> list[str]:
        """Return document IDs valid on *query_date*."""
        ...

    def is_superseded_by(self, document_id: str, query_date: str) -> bool:
        """Return True if *document_id* is superseded on *query_date*."""
        ...


@dataclass
class TemporalFilterResult:
    """Output of a single temporal filter pass.

    Args:
        accepted: Candidates whose source document is temporally valid.
        rejected: Candidates whose source document is invalid, with
                  ``temporal_filter_rejected=True`` and ``rejection_reason`` set.
    """

    accepted: list[RetrievalCandidate] = field(default_factory=list)
    rejected: list[RetrievalCandidate] = field(default_factory=list)


class TemporalFilter:
    """Filters retrieval candidates by temporal document validity.

    Computes valid document IDs once per :meth:`apply` call and classifies
    each candidate as accepted or rejected.  The rejection reason is either
    ``"not_yet_effective"`` (effective_date > query_date) or ``"superseded"``
    (a newer version exists on the query date).

    Args:
        version_graph: Object satisfying :class:`_VersionGraphLike`.
    """

    def __init__(self, version_graph: _VersionGraphLike) -> None:
        self._graph = version_graph

    def apply(
        self,
        candidates: list[RetrievalCandidate],
        query_date: str,
    ) -> TemporalFilterResult:
        """Filter *candidates* against *query_date*.

        Candidates missing chunk metadata (no ``chunk`` object or no
        ``document_id``) are accepted with a warning - they cannot be
        classified without document metadata.

        Args:
            candidates: Candidates to filter.  Each should have ``chunk``
                        populated with ``document_id`` and ``effective_date``.
            query_date: ISO-8601 date string, e.g. ``"2024-06-01"``.

        Returns:
            :class:`TemporalFilterResult` with accepted and rejected lists.
        """
        valid_docs: set[str] = set(self._graph.get_valid_documents(query_date))

        accepted: list[RetrievalCandidate] = []
        rejected: list[RetrievalCandidate] = []

        for cand in candidates:
            doc_id = cand.chunk.document_id if cand.chunk else None
            eff_date = cand.chunk.effective_date if cand.chunk else None

            if doc_id is None:
                logger.warning("temporal_filter_no_doc_id", chunk_id=cand.chunk_id)
                accepted.append(cand)
                continue

            if doc_id in valid_docs:
                accepted.append(cand)
                continue

            # Determine specific reason
            reason = "not_yet_effective" if (eff_date and eff_date > query_date) else "superseded"
            rejected_cand = cand.model_copy(
                update={"temporal_filter_rejected": True, "rejection_reason": reason}
            )
            rejected.append(rejected_cand)
            TEMPORAL_FILTER_REJECTIONS.labels(rejection_reason=reason).inc()
            logger.debug(
                "temporal_filter_rejected",
                chunk_id=cand.chunk_id,
                document_id=doc_id,
                reason=reason,
                query_date=query_date,
            )

        logger.info(
            "temporal_filter_applied",
            query_date=query_date,
            total=len(candidates),
            accepted=len(accepted),
            rejected=len(rejected),
        )
        return TemporalFilterResult(accepted=accepted, rejected=rejected)
