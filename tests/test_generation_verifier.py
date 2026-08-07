"""Tests for generation/verifier.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.exceptions import VerificationError
from generation.schemas import StructuredAnswer, VerificationReport
from generation.verifier import VeriductaVerifier, _build_chunk_texts, _tally_statuses
from schemas.models import (
    Chunk,
    Claim,
    ConfidenceTag,
    RetrievalCandidate,
    RetrievalResult,
    TemporalValidityTag,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, text: str = "chunk text") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-a",
        text=text,
        token_count=10,
        chunk_index=0,
    )


def _make_candidate(chunk_id: str, text: str = "text") -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        chunk=_make_chunk(chunk_id, text),
        rrf_score=0.9,
        rrf_rank=1,
    )


def _make_retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        query="Q?",
        query_date="2024-01-01",
        top_k=8,
        candidates=[_make_candidate("doc-ch-0001", "evidence text")],
    )


def _make_claim(
    claim_id: str = "c1", status: VerificationStatus = VerificationStatus.UNRESOLVED
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text="assertion",
        citation_chunk_id="doc-ch-0001",
        confidence=ConfidenceTag.HIGH,
        temporal_validity=TemporalValidityTag.VALID,
        verification_status=status,
    )


def _make_answer(*claims: Claim) -> StructuredAnswer:
    return StructuredAnswer(answer="test answer", claims=list(claims))


# ---------------------------------------------------------------------------
# _build_chunk_texts
# ---------------------------------------------------------------------------


def test_build_chunk_texts_includes_child() -> None:
    rr = _make_retrieval_result()
    texts = _build_chunk_texts(rr)
    assert "doc-ch-0001" in texts
    assert texts["doc-ch-0001"] == "evidence text"


def test_build_chunk_texts_includes_parent() -> None:
    parent = _make_chunk("doc-par-0000", "parent text")
    cand = RetrievalCandidate(
        chunk_id="doc-ch-0001",
        chunk=_make_chunk("doc-ch-0001"),
        parent_chunk=parent,
        rrf_score=0.5,
        rrf_rank=1,
    )
    rr = RetrievalResult(query="q", query_date="2024-01-01", top_k=8, candidates=[cand])
    texts = _build_chunk_texts(rr)
    assert "doc-par-0000" in texts
    assert texts["doc-par-0000"] == "parent text"


def test_build_chunk_texts_empty_candidates() -> None:
    rr = RetrievalResult(query="q", query_date="2024-01-01", top_k=8, candidates=[])
    texts = _build_chunk_texts(rr)
    assert texts == {}


# ---------------------------------------------------------------------------
# _tally_statuses
# ---------------------------------------------------------------------------


def test_tally_statuses_counts_correctly() -> None:
    claims = [
        _make_claim("c1", VerificationStatus.SUPPORTED),
        _make_claim("c2", VerificationStatus.SUPPORTED),
        _make_claim("c3", VerificationStatus.CONTRADICTED),
        _make_claim("c4", VerificationStatus.UNRESOLVED),
    ]
    tallies = _tally_statuses(claims)
    assert tallies[VerificationStatus.SUPPORTED] == 2
    assert tallies[VerificationStatus.CONTRADICTED] == 1
    assert tallies[VerificationStatus.UNRESOLVED] == 1
    assert tallies[VerificationStatus.NOT_SEARCHED] == 0


# ---------------------------------------------------------------------------
# VeriductaVerifier.verify
# ---------------------------------------------------------------------------


def _make_verifier(
    nli_status: VerificationStatus = VerificationStatus.SUPPORTED,
    ce_searcher: MagicMock | None = None,
) -> VeriductaVerifier:
    nli = MagicMock()

    # verify_claims returns the same claims with updated status
    def mock_verify_claims(claims: list[Claim], chunk_texts: dict[str, str]) -> list[Claim]:
        return [c.model_copy(update={"verification_status": nli_status}) for c in claims]

    nli.verify_claims = mock_verify_claims
    nli.model_id = "test-nli-model"
    return VeriductaVerifier(nli_verifier=nli, counterevidence_searcher=ce_searcher)


def test_verify_returns_verification_report() -> None:
    verifier = _make_verifier()
    answer = _make_answer(_make_claim("c1"))
    report = verifier.verify(answer, _make_retrieval_result())
    assert isinstance(report, VerificationReport)
    assert report.answer_id == answer.answer_id


def test_verify_supported_claims_sets_count() -> None:
    verifier = _make_verifier(VerificationStatus.SUPPORTED)
    answer = _make_answer(_make_claim("c1"), _make_claim("c2"))
    report = verifier.verify(answer, _make_retrieval_result())
    assert report.supported_count == 2
    assert report.overall_requires_expert_review is False


def test_verify_contradicted_claim_flags_review() -> None:
    nli = MagicMock()
    nli.model_id = "test"

    def mock_verify(claims: list[Claim], chunk_texts: dict[str, str]) -> list[Claim]:
        return [
            c.model_copy(
                update={
                    "verification_status": VerificationStatus.CONTRADICTED,
                    "requires_expert_review": True,
                }
            )
            for c in claims
        ]

    nli.verify_claims = mock_verify
    verifier = VeriductaVerifier(nli_verifier=nli)
    answer = _make_answer(_make_claim("c1"))
    report = verifier.verify(answer, _make_retrieval_result())
    assert report.overall_requires_expert_review is True
    assert report.contradicted_count == 1


def test_verify_calls_counterevidence_when_provided() -> None:
    nli = MagicMock()
    nli.verify_claims.return_value = [_make_claim("c1")]
    nli.model_id = "test"

    from generation.schemas import CounterEvidenceCandidate

    mock_ce = MagicMock()
    mock_ce.search.return_value = (
        [_make_claim("c1")],
        [CounterEvidenceCandidate(chunk_id="x", document_id="d", text="t", contrastive_query="q")],
    )
    verifier = VeriductaVerifier(nli_verifier=nli, counterevidence_searcher=mock_ce)
    answer = _make_answer(_make_claim("c1"))
    report = verifier.verify(answer, _make_retrieval_result())
    mock_ce.search.assert_called_once()
    assert len(report.counterevidence_candidates) == 1


def test_verify_without_counterevidence_leaves_candidates_empty() -> None:
    verifier = _make_verifier()
    answer = _make_answer(_make_claim("c1"))
    report = verifier.verify(answer, _make_retrieval_result())
    assert report.counterevidence_candidates == []


def test_verify_nli_exception_raises_verification_error() -> None:
    nli = MagicMock()
    nli.verify_claims.side_effect = RuntimeError("NLI failure")
    nli.model_id = "test"
    verifier = VeriductaVerifier(nli_verifier=nli)
    with pytest.raises(VerificationError):
        verifier.verify(_make_answer(_make_claim("c1")), _make_retrieval_result())


def test_verify_already_verification_error_propagated() -> None:
    nli = MagicMock()
    nli.verify_claims.side_effect = VerificationError("already wrapped")
    nli.model_id = "test"
    verifier = VeriductaVerifier(nli_verifier=nli)
    with pytest.raises(VerificationError, match="already wrapped"):
        verifier.verify(_make_answer(_make_claim("c1")), _make_retrieval_result())


def test_verify_nli_model_id_in_report() -> None:
    verifier = _make_verifier()
    answer = _make_answer(_make_claim("c1"))
    report = verifier.verify(answer, _make_retrieval_result())
    assert report.nli_model_id == "test-nli-model"


def test_verify_empty_claims() -> None:
    verifier = _make_verifier()
    answer = _make_answer()
    report = verifier.verify(answer, _make_retrieval_result())
    assert report.verified_claims == []
    assert report.supported_count == 0
