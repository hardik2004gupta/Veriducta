"""Reciprocal Rank Fusion (RRF) of BM25 and dense retrieval results.

Implements score(d) = Σ_r 1 / (k + rank_r(d)) with k=60 per Cormack et al.
(2009).  Candidates absent from a list receive implicit rank 101.
"""

import structlog

from schemas.models import RetrievalCandidate

logger = structlog.get_logger(__name__)

# RRF constant k=60 is the standard value from Cormack et al. (2009).
# Changing it requires re-benchmarking retrieval quality.
_DEFAULT_RRF_K = 60

# Rank assigned to candidates absent from a retrieval list.
_IMPLICIT_RANK = 101


def fuse(
    bm25_candidates: list[RetrievalCandidate],
    dense_candidates: list[RetrievalCandidate],
    rrf_k: int = _DEFAULT_RRF_K,
) -> list[RetrievalCandidate]:
    """Merge BM25 and dense candidates using Reciprocal Rank Fusion.

    Each candidate's RRF score is the sum of 1/(k + rank) across both lists.
    Candidates absent from a list receive implicit rank :data:`_IMPLICIT_RANK`.
    All per-list scores and ranks are preserved in the returned candidates.

    Args:
        bm25_candidates: BM25 results ordered by descending score.
        dense_candidates: Dense results ordered by descending score.
        rrf_k: RRF fusion constant (default 60).

    Returns:
        Unified list sorted by descending RRF score with ``rrf_score`` and
        ``rrf_rank`` set on every candidate.
    """
    bm25_map = {c.chunk_id: c for c in bm25_candidates}
    dense_map = {c.chunk_id: c for c in dense_candidates}
    all_ids = set(bm25_map) | set(dense_map)

    merged: list[RetrievalCandidate] = []

    for chunk_id in all_ids:
        bm25_c = bm25_map.get(chunk_id)
        dense_c = dense_map.get(chunk_id)

        bm25_rank = (
            bm25_c.bm25_rank if (bm25_c and bm25_c.bm25_rank is not None) else _IMPLICIT_RANK
        )
        dense_rank = (
            dense_c.dense_rank if (dense_c and dense_c.dense_rank is not None) else _IMPLICIT_RANK
        )

        rrf_score = 1.0 / (rrf_k + bm25_rank) + 1.0 / (rrf_k + dense_rank)

        base = bm25_c if bm25_c is not None else dense_c
        if base is None:
            continue  # unreachable - chunk_id is in at least one map

        chunk = (bm25_c.chunk if bm25_c else None) or (dense_c.chunk if dense_c else None)

        merged.append(
            base.model_copy(
                update={
                    "bm25_score": bm25_c.bm25_score if bm25_c else None,
                    "bm25_rank": bm25_c.bm25_rank if bm25_c else None,
                    "dense_score": dense_c.dense_score if dense_c else None,
                    "dense_rank": dense_c.dense_rank if dense_c else None,
                    "rrf_score": rrf_score,
                    "chunk": chunk,
                }
            )
        )

    sorted_candidates = sorted(merged, key=lambda c: c.rrf_score or 0.0, reverse=True)

    result: list[RetrievalCandidate] = [
        c.model_copy(update={"rrf_rank": rank}) for rank, c in enumerate(sorted_candidates, start=1)
    ]

    logger.debug(
        "rrf_fusion_done",
        bm25_count=len(bm25_candidates),
        dense_count=len(dense_candidates),
        merged_count=len(result),
        rrf_k=rrf_k,
    )
    return result
