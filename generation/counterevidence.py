"""5-step counterevidence retrieval for claim integrity scanning.

Implements the contrastive BM25 search + NLI classification algorithm
specified in the MVP.  Only claims with at least ``min_entities_for_search``
key entities trigger a search; entity-sparse claims receive
``verification_status="not_searched"`` with reason ``"insufficient_entity_signal"``.

5-step algorithm:
  1. Extract key_entities from all claims; flatten, deduplicate, remove stopwords.
  2. Construct contrastive query: ``{entities} exception OR limitation OR ...``
     (max 10 entities).
  3. BM25-only retrieval with optional temporal filtering, top-k candidates.
  4. NLI batch inference: score all candidates against all claims.
  5. Classify each candidate-claim pair; update verification_status.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from config.settings import VerificationSettings, get_settings
from generation.entailment import NLIEntailmentVerifier
from generation.schemas import CounterEvidenceCandidate
from schemas.models import Claim, RetrievalCandidate, VerificationStatus

_FilterFn = Callable[[list[RetrievalCandidate], str], list[RetrievalCandidate]]

logger = structlog.get_logger(__name__)

# Contrastive qualifier terms appended to the entity-based query
_CONTRASTIVE_TERMS = (
    "exception OR limitation OR superseded OR contraindicated OR contradicts "
    'OR "shall not" OR "not applicable" OR warning OR caution OR prohibited'
)

# Words that appear frequently in technical documents but carry no entity signal
_DOMAIN_STOPWORDS: frozenset[str] = frozenset(
    {
        "section",
        "table",
        "figure",
        "appendix",
        "page",
        "document",
        "specification",
        "standard",
        "code",
        "requirement",
        "requirements",
        "shall",
        "should",
        "may",
        "must",
        "will",
        "not",
        "the",
        "and",
        "or",
        "for",
        "with",
        "this",
        "that",
        "these",
        "those",
        "all",
        "any",
        "each",
        "every",
        "including",
        "provided",
        "pursuant",
        "accordance",
        "per",
        "under",
        "applicable",
        "general",
        "specific",
        "following",
        "above",
        "below",
    }
)


def _extract_entities(claims: list[Claim], stopwords: frozenset[str]) -> list[str]:
    """Flatten, deduplicate, and filter key_entities from *claims*.

    Args:
        claims: Claims whose ``key_entities`` to aggregate.
        stopwords: Domain stopwords to exclude.

    Returns:
        Deduplicated list of entity strings, stopwords removed.
    """
    seen: set[str] = set()
    result: list[str] = []
    for claim in claims:
        for entity in claim.key_entities:
            normalised = entity.strip()
            lower = normalised.lower()
            if normalised and lower not in stopwords and lower not in seen:
                seen.add(lower)
                result.append(normalised)
    return result


def _build_contrastive_query(entities: list[str], max_entities: int = 10) -> str:
    """Build the contrastive BM25 query from *entities*.

    At most *max_entities* entities are used to keep the query tractable.

    Args:
        entities: Deduplicated entity list (already stopword-filtered).
        max_entities: Cap on entities included in the query.

    Returns:
        Query string like ``"entity1 entity2 exception OR limitation OR ..."``
    """
    capped = entities[:max_entities]
    entity_str = " ".join(capped)
    return f"{entity_str} {_CONTRASTIVE_TERMS}"


class CounterEvidenceSearcher:
    """Executes the 5-step counterevidence scan over the BM25 index.

    Args:
        bm25_retrieve: Callable that accepts a query string and returns a list
                       of :class:`~schemas.models.RetrievalCandidate`.
        chunk_texts: Mapping of chunk_id → chunk text for NLI inference.
        nli_verifier: :class:`~generation.entailment.NLIEntailmentVerifier`.
        temporal_filter_fn: Optional callable that filters
                            ``list[RetrievalCandidate]`` by ``query_date``.
                            When ``None``, temporal filtering is skipped.
        settings: :class:`~config.settings.VerificationSettings`.
    """

    def __init__(
        self,
        bm25_retrieve: object,
        chunk_texts: dict[str, str],
        nli_verifier: NLIEntailmentVerifier,
        temporal_filter_fn: object | None = None,
        settings: VerificationSettings | None = None,
    ) -> None:
        self._retrieve: Callable[[str], list[RetrievalCandidate]] = bm25_retrieve  # type: ignore[assignment]
        self._chunk_texts = chunk_texts
        self._nli = nli_verifier
        self._filter_fn: _FilterFn | None = temporal_filter_fn  # type: ignore[assignment]
        self._settings = settings or get_settings().verification

    def search(
        self, claims: list[Claim], query_date: str
    ) -> tuple[list[Claim], list[CounterEvidenceCandidate]]:
        """Run the 5-step counterevidence scan for *claims*.

        Claims with fewer than ``min_entities_for_search`` key entities are
        marked ``not_searched`` and skipped.

        Args:
            claims: Claims to scan (may be modified in returned list).
            query_date: ISO-8601 date for temporal validity filtering.

        Returns:
            Tuple of (updated_claims, counterevidence_candidates).
        """
        min_entities = self._settings.min_entities_for_search
        top_k = self._settings.counterevidence_top_k

        # Step 1 — separate entity-rich and entity-sparse claims
        searchable = [c for c in claims if len(c.key_entities) >= min_entities]
        sparse = [c for c in claims if len(c.key_entities) < min_entities]

        sparse_updated = [
            c.model_copy(
                update={
                    "verification_status": VerificationStatus.NOT_SEARCHED,
                }
            )
            for c in sparse
        ]

        if not searchable:
            logger.info(
                "counterevidence_skipped_all_sparse",
                claim_count=len(claims),
            )
            return sparse_updated, []

        # Step 2 — build contrastive query
        entities = _extract_entities(searchable, _DOMAIN_STOPWORDS)
        query = _build_contrastive_query(entities)
        logger.debug(
            "counterevidence_query_built",
            entity_count=len(entities),
            query_preview=query[:120],
        )

        # Step 3 — BM25 retrieval with optional temporal filter
        raw_candidates: list[RetrievalCandidate] = self._retrieve(query)
        if self._filter_fn is not None:
            raw_candidates = self._filter_fn(raw_candidates, query_date)
        top_candidates = raw_candidates[:top_k]

        # Step 4 — NLI batch inference: each candidate vs each searchable claim
        ce_candidates: list[CounterEvidenceCandidate] = []
        claim_updates: dict[str, dict[str, Any]] = {c.claim_id: {} for c in searchable}

        for cand in top_candidates:
            chunk_text = self._chunk_texts.get(cand.chunk_id, "")
            if not chunk_text:
                continue

            pairs = [(chunk_text, c.text) for c in searchable]
            probs_list = self._nli.classify_batch(pairs)

            contradicts: list[str] = []
            ambiguous: list[str] = []
            best_contradiction_score = 0.0
            best_entailment_score = 0.0
            best_neutral_score = 0.0

            for claim, probs in zip(searchable, probs_list, strict=False):
                status = self._nli.apply_heuristic(probs)
                c_score = probs["contradiction"]
                e_score = probs["entailment"]
                n_score = probs["neutral"]

                if c_score > best_contradiction_score:
                    best_contradiction_score = c_score
                if e_score > best_entailment_score:
                    best_entailment_score = e_score
                if n_score > best_neutral_score:
                    best_neutral_score = n_score

                if status == VerificationStatus.CONTRADICTED:
                    contradicts.append(claim.claim_id)
                    existing = claim_updates[claim.claim_id]
                    existing["verification_status"] = VerificationStatus.CONTRADICTED
                    existing.setdefault("contradicting_chunk_ids", [])
                    existing["contradicting_chunk_ids"].append(cand.chunk_id)
                    existing["requires_expert_review"] = True

                elif status == VerificationStatus.AMBIGUOUS_CONDITIONAL:
                    ambiguous.append(claim.claim_id)
                    existing = claim_updates[claim.claim_id]
                    if existing.get("verification_status") != VerificationStatus.CONTRADICTED:
                        existing["verification_status"] = VerificationStatus.AMBIGUOUS_CONDITIONAL
                    existing.setdefault("conditional_conflict_chunk_ids", [])
                    existing["conditional_conflict_chunk_ids"].append(cand.chunk_id)
                    existing["requires_expert_review"] = True

            doc_id = cand.chunk.document_id if cand.chunk else ""
            overall_status = (
                VerificationStatus.CONTRADICTED
                if contradicts
                else (
                    VerificationStatus.AMBIGUOUS_CONDITIONAL
                    if ambiguous
                    else VerificationStatus.UNRESOLVED
                )
            )
            ce_candidates.append(
                CounterEvidenceCandidate(
                    chunk_id=cand.chunk_id,
                    document_id=doc_id,
                    text=chunk_text,
                    contrastive_query=query,
                    nli_contradiction_score=best_contradiction_score,
                    nli_entailment_score=best_entailment_score,
                    nli_neutral_score=best_neutral_score,
                    contradicts_claim_ids=contradicts,
                    ambiguous_claim_ids=ambiguous,
                    verification_status_assigned=overall_status,
                )
            )

        # Step 5 — apply updates to searchable claims
        updated_searchable: list[Claim] = []
        for claim in searchable:
            updates = claim_updates.get(claim.claim_id, {})
            if updates:
                updated_searchable.append(claim.model_copy(update=updates))
            else:
                updated_searchable.append(claim)

        logger.info(
            "counterevidence_scan_complete",
            searchable_claims=len(searchable),
            candidates_evaluated=len(ce_candidates),
            contradictions_found=sum(1 for c in ce_candidates if c.contradicts_claim_ids),
        )

        # Preserve original claim order: searchable updated + sparse marked
        claim_id_order = [c.claim_id for c in claims]
        merged: dict[str, Claim] = {c.claim_id: c for c in updated_searchable + sparse_updated}
        ordered: list[Claim] = [merged[cid] for cid in claim_id_order if cid in merged]

        return ordered, ce_candidates
