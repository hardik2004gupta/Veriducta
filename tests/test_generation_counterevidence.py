"""Tests for generation/counterevidence.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from config.settings import VerificationSettings
from generation.counterevidence import (
    CounterEvidenceSearcher,
    _build_contrastive_query,
    _extract_entities,
)
from schemas.models import (
    Claim,
    ConfidenceTag,
    RetrievalCandidate,
    TemporalValidityTag,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------


def _make_claim(entities: list[str], cid: str = "c1") -> Claim:
    return Claim(
        claim_id=cid,
        text="test claim",
        citation_chunk_id="chunk-0001",
        confidence=ConfidenceTag.HIGH,
        temporal_validity=TemporalValidityTag.VALID,
        key_entities=entities,
    )


def test_extract_entities_deduplicates() -> None:
    claims = [
        _make_claim(["ASTM", "astm"], "c1"),
        _make_claim(["ASTM", "ISO"], "c2"),
    ]
    from generation.counterevidence import _DOMAIN_STOPWORDS

    result = _extract_entities(claims, _DOMAIN_STOPWORDS)
    assert result.count("ASTM") == 1
    assert "ISO" in result


def test_extract_entities_removes_stopwords() -> None:
    from generation.counterevidence import _DOMAIN_STOPWORDS

    claims = [_make_claim(["section", "shall", "OSHA"], "c1")]
    result = _extract_entities(claims, _DOMAIN_STOPWORDS)
    assert "section" not in result
    assert "shall" not in result
    assert "OSHA" in result


def test_extract_entities_empty_claims() -> None:
    from generation.counterevidence import _DOMAIN_STOPWORDS

    result = _extract_entities([], _DOMAIN_STOPWORDS)
    assert result == []


def test_extract_entities_strips_whitespace() -> None:
    from generation.counterevidence import _DOMAIN_STOPWORDS

    claims = [_make_claim([" NFPA "], "c1")]
    result = _extract_entities(claims, _DOMAIN_STOPWORDS)
    assert "NFPA" in result


# ---------------------------------------------------------------------------
# _build_contrastive_query
# ---------------------------------------------------------------------------


def test_build_contrastive_query_includes_entities_and_terms() -> None:
    query = _build_contrastive_query(["OSHA", "NFPA"])
    assert "OSHA" in query
    assert "NFPA" in query
    assert "exception" in query


def test_build_contrastive_query_caps_entities() -> None:
    entities = [f"entity{i}" for i in range(20)]
    query = _build_contrastive_query(entities, max_entities=5)
    # Only first 5 entities should appear by name
    for i in range(5):
        assert f"entity{i}" in query
    assert "entity5" not in query


def test_build_contrastive_query_empty_entities() -> None:
    query = _build_contrastive_query([])
    assert "exception" in query


# ---------------------------------------------------------------------------
# CounterEvidenceSearcher.search
# ---------------------------------------------------------------------------


def _make_candidate(chunk_id: str, text: str = "chunk text") -> RetrievalCandidate:
    from schemas.models import Chunk

    chunk = Chunk(
        chunk_id=chunk_id,
        document_id="doc-a",
        text=text,
        token_count=10,
        chunk_index=0,
    )
    return RetrievalCandidate(chunk_id=chunk_id, chunk=chunk, rrf_score=0.5, rrf_rank=1)


def _make_settings(min_entities: int = 2, top_k: int = 10) -> VerificationSettings:
    return VerificationSettings(min_entities_for_search=min_entities, counterevidence_top_k=top_k)


def test_search_all_sparse_returns_not_searched() -> None:
    settings = _make_settings(min_entities=2)
    nli = MagicMock()
    searcher = CounterEvidenceSearcher(
        bm25_retrieve=MagicMock(return_value=[]),
        chunk_texts={},
        nli_verifier=nli,
        settings=settings,
    )
    claims = [_make_claim(["one_entity"], "c1")]
    updated, candidates = searcher.search(claims, "2024-01-01")
    assert updated[0].verification_status == VerificationStatus.NOT_SEARCHED
    assert candidates == []


def test_search_entity_rich_claim_triggers_bm25() -> None:
    settings = _make_settings(min_entities=2)
    mock_bm25 = MagicMock(return_value=[_make_candidate("doc-ch-0000", "no contradiction here")])
    chunk_texts = {"doc-ch-0000": "no contradiction here"}
    nli = MagicMock()
    # Low contradiction probability (UNRESOLVED)
    nli.classify_batch.return_value = [{"entailment": 0.60, "contradiction": 0.10, "neutral": 0.30}]
    nli.apply_heuristic.return_value = VerificationStatus.UNRESOLVED

    searcher = CounterEvidenceSearcher(
        bm25_retrieve=mock_bm25,
        chunk_texts=chunk_texts,
        nli_verifier=nli,
        settings=settings,
    )
    claims = [_make_claim(["OSHA", "NFPA"], "c1")]
    updated, candidates = searcher.search(claims, "2024-01-01")
    mock_bm25.assert_called_once()
    assert len(candidates) == 1
    assert updated[0].claim_id == "c1"


def test_search_contradiction_updates_claim() -> None:
    settings = _make_settings(min_entities=2)
    cand = _make_candidate("doc-ch-0000", "contradicting text")
    mock_bm25 = MagicMock(return_value=[cand])
    chunk_texts = {"doc-ch-0000": "contradicting text"}
    nli = MagicMock()
    nli.classify_batch.return_value = [{"entailment": 0.05, "contradiction": 0.92, "neutral": 0.03}]
    nli.apply_heuristic.return_value = VerificationStatus.CONTRADICTED

    searcher = CounterEvidenceSearcher(
        bm25_retrieve=mock_bm25,
        chunk_texts=chunk_texts,
        nli_verifier=nli,
        settings=settings,
    )
    claims = [_make_claim(["OSHA", "NFPA"], "c1")]
    updated, candidates = searcher.search(claims, "2024-01-01")

    assert updated[0].verification_status == VerificationStatus.CONTRADICTED
    assert updated[0].requires_expert_review is True
    assert candidates[0].verification_status_assigned == VerificationStatus.CONTRADICTED
    assert "c1" in candidates[0].contradicts_claim_ids


def test_search_with_temporal_filter_applied() -> None:
    settings = _make_settings(min_entities=2)
    cand = _make_candidate("doc-ch-0000", "text")
    mock_bm25 = MagicMock(return_value=[cand])
    mock_filter = MagicMock(return_value=[])  # filter removes all
    chunk_texts = {"doc-ch-0000": "text"}
    nli = MagicMock()

    searcher = CounterEvidenceSearcher(
        bm25_retrieve=mock_bm25,
        chunk_texts=chunk_texts,
        nli_verifier=nli,
        temporal_filter_fn=mock_filter,
        settings=settings,
    )
    claims = [_make_claim(["OSHA", "NFPA"], "c1")]
    _, candidates = searcher.search(claims, "2024-01-01")
    mock_filter.assert_called_once()
    assert candidates == []  # all filtered out


def test_search_missing_chunk_text_skipped() -> None:
    settings = _make_settings(min_entities=2)
    cand = _make_candidate("doc-ch-0000", "text")
    mock_bm25 = MagicMock(return_value=[cand])
    chunk_texts: dict[str, str] = {}  # empty — no text available
    nli = MagicMock()

    searcher = CounterEvidenceSearcher(
        bm25_retrieve=mock_bm25,
        chunk_texts=chunk_texts,
        nli_verifier=nli,
        settings=settings,
    )
    claims = [_make_claim(["OSHA", "NFPA"], "c1")]
    _, candidates = searcher.search(claims, "2024-01-01")
    nli.classify_batch.assert_not_called()
    assert candidates == []


def test_search_preserves_claim_order() -> None:
    settings = _make_settings(min_entities=2, top_k=1)
    cand = _make_candidate("doc-ch-0000", "text")
    mock_bm25 = MagicMock(return_value=[cand])
    chunk_texts = {"doc-ch-0000": "text"}
    nli = MagicMock()
    nli.classify_batch.return_value = [
        {"entailment": 0.1, "contradiction": 0.5, "neutral": 0.4},
        {"entailment": 0.1, "contradiction": 0.5, "neutral": 0.4},
    ]
    nli.apply_heuristic.return_value = VerificationStatus.UNRESOLVED

    searcher = CounterEvidenceSearcher(
        bm25_retrieve=mock_bm25,
        chunk_texts=chunk_texts,
        nli_verifier=nli,
        settings=settings,
    )
    claims = [
        _make_claim(["OSHA", "NFPA"], "c1"),
        _make_claim(["one"], "sparse"),
    ]
    updated, _ = searcher.search(claims, "2024-01-01")
    assert [c.claim_id for c in updated] == ["c1", "sparse"]
