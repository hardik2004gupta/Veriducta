"""Tests for generation/entailment.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from config.settings import VerificationSettings
from generation.entailment import NLIEntailmentVerifier, _softmax, get_nli_model
from schemas.models import Claim, ConfidenceTag, TemporalValidityTag, VerificationStatus

# ---------------------------------------------------------------------------
# _softmax
# ---------------------------------------------------------------------------


def test_softmax_sums_to_one() -> None:
    logits = np.array([1.0, 2.0, 0.5])
    result = _softmax(logits)
    assert abs(result.sum() - 1.0) < 1e-6


def test_softmax_higher_logit_higher_probability() -> None:
    logits = np.array([0.0, 10.0, 0.0])
    result = _softmax(logits)
    assert result[1] > 0.99


def test_softmax_numerically_stable_large_values() -> None:
    logits = np.array([1000.0, 1000.0, 1000.0])
    result = _softmax(logits)
    assert not np.any(np.isnan(result))
    assert abs(result.sum() - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# NLIEntailmentVerifier.apply_heuristic
# ---------------------------------------------------------------------------


def _make_settings(
    entailment_threshold: float = 0.65,
    contradiction_threshold: float = 0.85,
    contradiction_neutral_max: float = 0.30,
    ambiguous_neutral_min: float = 0.40,
    ambiguous_contradiction_min: float = 0.30,
    ambiguous_contradiction_max: float = 0.70,
) -> VerificationSettings:
    return VerificationSettings(
        entailment_threshold=entailment_threshold,
        contradiction_threshold=contradiction_threshold,
        contradiction_neutral_max=contradiction_neutral_max,
        ambiguous_neutral_min=ambiguous_neutral_min,
        ambiguous_contradiction_min=ambiguous_contradiction_min,
        ambiguous_contradiction_max=ambiguous_contradiction_max,
    )


def test_apply_heuristic_supported_above_threshold() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    probs = {"entailment": 0.80, "contradiction": 0.10, "neutral": 0.10}
    assert verifier.apply_heuristic(probs) == VerificationStatus.SUPPORTED


def test_apply_heuristic_supported_at_exact_threshold_is_not_supported() -> None:
    settings = _make_settings(entailment_threshold=0.65)
    verifier = NLIEntailmentVerifier(settings=settings)
    probs = {"entailment": 0.65, "contradiction": 0.20, "neutral": 0.15}
    # 0.65 is NOT > 0.65 (strict greater)
    assert verifier.apply_heuristic(probs) != VerificationStatus.SUPPORTED


def test_apply_heuristic_contradicted() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    probs = {"entailment": 0.05, "contradiction": 0.90, "neutral": 0.05}
    assert verifier.apply_heuristic(probs) == VerificationStatus.CONTRADICTED


def test_apply_heuristic_contradicted_neutral_too_high_returns_unresolved() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    # contradiction > 0.85 but neutral >= 0.30
    probs = {"entailment": 0.05, "contradiction": 0.90, "neutral": 0.35}
    result = verifier.apply_heuristic(probs)
    assert result != VerificationStatus.CONTRADICTED


def test_apply_heuristic_ambiguous_conditional() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    # neutral > 0.40 AND contradiction in (0.30, 0.70)
    probs = {"entailment": 0.10, "contradiction": 0.45, "neutral": 0.45}
    assert verifier.apply_heuristic(probs) == VerificationStatus.AMBIGUOUS_CONDITIONAL


def test_apply_heuristic_unresolved_mixed() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    probs = {"entailment": 0.35, "contradiction": 0.35, "neutral": 0.30}
    assert verifier.apply_heuristic(probs) == VerificationStatus.UNRESOLVED


# ---------------------------------------------------------------------------
# NLIEntailmentVerifier.classify_batch
# ---------------------------------------------------------------------------


def test_classify_batch_empty_returns_empty() -> None:
    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings)
    result = verifier.classify_batch([])
    assert result == []


@patch("generation.entailment.get_nli_model")
def test_classify_batch_returns_probability_dicts(mock_get: MagicMock) -> None:
    mock_model = MagicMock()
    # Return logits for contradiction, entailment, neutral
    mock_model.predict.return_value = np.array([[0.1, 2.0, 0.3]])
    mock_get.return_value = mock_model

    settings = _make_settings()
    verifier = NLIEntailmentVerifier(settings=settings, model_id="test-model")
    result = verifier.classify_batch([("premise text", "hypothesis text")])

    assert len(result) == 1
    probs = result[0]
    assert set(probs.keys()) == {"contradiction", "entailment", "neutral"}
    assert abs(sum(probs.values()) - 1.0) < 1e-5


@patch("generation.entailment.get_nli_model")
def test_classify_batch_multiple_pairs(mock_get: MagicMock) -> None:
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([[0.1, 2.0, 0.3], [2.0, 0.1, 0.3]])
    mock_get.return_value = mock_model

    verifier = NLIEntailmentVerifier(model_id="test")
    result = verifier.classify_batch([("p1", "h1"), ("p2", "h2")])
    assert len(result) == 2


# ---------------------------------------------------------------------------
# NLIEntailmentVerifier.verify_claims
# ---------------------------------------------------------------------------


def _make_claim(
    claim_id: str = "c1",
    text: str = "the sky is blue",
    citation_chunk_id: str = "chunk-0001",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        text=text,
        citation_chunk_id=citation_chunk_id,
        confidence=ConfidenceTag.HIGH,
        temporal_validity=TemporalValidityTag.VALID,
    )


@patch("generation.entailment.get_nli_model")
def test_verify_claims_supported_sets_status(mock_get: MagicMock) -> None:
    mock_model = MagicMock()
    # High entailment (index 1)
    mock_model.predict.return_value = np.array([[0.05, 3.0, 0.05]])
    mock_get.return_value = mock_model

    verifier = NLIEntailmentVerifier(settings=_make_settings(), model_id="test")
    claim = _make_claim()
    chunk_texts = {"chunk-0001": "blue sky evidence"}

    result = verifier.verify_claims([claim], chunk_texts)
    assert len(result) == 1
    assert result[0].verification_status == VerificationStatus.SUPPORTED
    assert result[0].nli_entailment_probability is not None
    assert result[0].requires_expert_review is False


@patch("generation.entailment.get_nli_model")
def test_verify_claims_contradicted_flags_review(mock_get: MagicMock) -> None:
    mock_model = MagicMock()
    # High contradiction (index 0), low neutral (index 2)
    mock_model.predict.return_value = np.array([[3.0, 0.05, 0.05]])
    mock_get.return_value = mock_model

    verifier = NLIEntailmentVerifier(settings=_make_settings(), model_id="test")
    claim = _make_claim()
    result = verifier.verify_claims([claim], {"chunk-0001": "evidence"})
    assert result[0].verification_status == VerificationStatus.CONTRADICTED
    assert result[0].requires_expert_review is True


@patch("generation.entailment.get_nli_model")
def test_verify_claims_missing_chunk_id_left_unresolved(mock_get: MagicMock) -> None:
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([[0.0, 3.0, 0.0]])
    mock_get.return_value = mock_model

    verifier = NLIEntailmentVerifier(settings=_make_settings(), model_id="test")
    claim = _make_claim(citation_chunk_id="missing-chunk")
    result = verifier.verify_claims([claim], {"other-chunk": "text"})
    # Claim is returned unchanged (no chunk found)
    assert result[0].claim_id == claim.claim_id
    assert result[0].verification_status == claim.verification_status


def test_verify_claims_empty_list() -> None:
    verifier = NLIEntailmentVerifier(settings=_make_settings(), model_id="test")
    result = verifier.verify_claims([], {})
    assert result == []


def test_model_id_property() -> None:
    verifier = NLIEntailmentVerifier(model_id="my-model")
    assert verifier.model_id == "my-model"


@patch("generation.entailment._nli_model", None)
@patch("generation.entailment.CrossEncoder")
def test_get_nli_model_loads_on_first_call(mock_ce: MagicMock) -> None:
    mock_ce.return_value = MagicMock()
    model = get_nli_model("dummy-model")
    mock_ce.assert_called_once_with("dummy-model")
    assert model is not None
