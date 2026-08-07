"""NLI entailment checker using cross-encoder/nli-deberta-v3-base.

Implements the 3-class heuristic specified in the MVP:
- supported:             entailment_prob > 0.65
- contradicted:          contradiction_prob > 0.85 AND neutral_prob < 0.30
- ambiguous_conditional: neutral_prob > 0.40 AND contradiction_prob in (0.30, 0.70)
- unresolved:            none of the above

Label index mapping for cross-encoder/nli-deberta-v3-base (id2label from model config):
  Index 0 → contradiction
  Index 1 → entailment
  Index 2 → neutral
"""

from __future__ import annotations

import numpy as np
import structlog
from sentence_transformers import CrossEncoder

from config.settings import VerificationSettings, get_settings
from schemas.models import Claim, VerificationStatus

logger = structlog.get_logger(__name__)

# Label indices for cross-encoder/nli-deberta-v3-base
_IDX_CONTRADICTION = 0
_IDX_ENTAILMENT = 1
_IDX_NEUTRAL = 2

_nli_model: CrossEncoder | None = None  # module-level singleton


def get_nli_model(model_id: str = "cross-encoder/nli-deberta-v3-base") -> CrossEncoder:
    """Return the module-level NLI model singleton, loading on first call.

    Args:
        model_id: Hugging Face model identifier.

    Returns:
        Loaded :class:`~sentence_transformers.CrossEncoder`.
    """
    global _nli_model
    if _nli_model is None:
        logger.info("nli_model_loading", model_id=model_id)
        _nli_model = CrossEncoder(model_id)
        logger.info("nli_model_loaded", model_id=model_id)
    return _nli_model


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Numerically stable softmax over a 1-D array."""
    shifted = logits - np.max(logits)
    exp = np.exp(shifted)
    return exp / exp.sum()  # type: ignore[no-any-return]


class NLIEntailmentVerifier:
    """Runs batch NLI inference to classify claims against supporting chunks.

    Uses :func:`get_nli_model` internally — the model is a module singleton and
    is never reloaded per-request.

    Args:
        settings: :class:`~config.settings.VerificationSettings`.  If ``None``,
                  the global settings are used.
        model_id: Override the NLI model identifier.
    """

    def __init__(
        self,
        settings: VerificationSettings | None = None,
        model_id: str | None = None,
    ) -> None:
        self._settings = settings or get_settings().verification
        self._model_id = model_id or self._settings.nli_model_id

    def classify_pair(self, premise: str, hypothesis: str) -> dict[str, float]:
        """Run NLI inference for a single (premise, hypothesis) pair.

        Args:
            premise: Source chunk text (the evidence).
            hypothesis: Claim text to check.

        Returns:
            Dict with keys ``"entailment"``, ``"contradiction"``, ``"neutral"``.
        """
        model = get_nli_model(self._model_id)
        raw = model.predict([(premise, hypothesis)])
        probs = _softmax(np.array(raw[0]))
        return {
            "contradiction": float(probs[_IDX_CONTRADICTION]),
            "entailment": float(probs[_IDX_ENTAILMENT]),
            "neutral": float(probs[_IDX_NEUTRAL]),
        }

    def classify_batch(self, pairs: list[tuple[str, str]]) -> list[dict[str, float]]:
        """Run NLI inference for a batch of (premise, hypothesis) pairs.

        Args:
            pairs: List of ``(premise, hypothesis)`` tuples.

        Returns:
            List of probability dicts, one per input pair.
        """
        if not pairs:
            return []
        model = get_nli_model(self._model_id)
        raw: np.ndarray = model.predict(pairs)  # type: ignore[arg-type, assignment]
        results: list[dict[str, float]] = []
        for row in raw:
            probs = _softmax(np.array(row))
            results.append(
                {
                    "contradiction": float(probs[_IDX_CONTRADICTION]),
                    "entailment": float(probs[_IDX_ENTAILMENT]),
                    "neutral": float(probs[_IDX_NEUTRAL]),
                }
            )
        return results

    def apply_heuristic(self, probs: dict[str, float]) -> VerificationStatus:
        """Map an NLI probability dict to a VerificationStatus.

        Thresholds from the MVP spec:
        - supported:             entailment > 0.65
        - contradicted:          contradiction > 0.85 AND neutral < 0.30
        - ambiguous_conditional: neutral > 0.40 AND contradiction in (0.30, 0.70)
        - unresolved:            none of the above

        Args:
            probs: Dict with keys ``"entailment"``, ``"contradiction"``, ``"neutral"``.

        Returns:
            :class:`~schemas.models.VerificationStatus` label.
        """
        e = probs["entailment"]
        c = probs["contradiction"]
        n = probs["neutral"]
        s = self._settings

        if e > s.entailment_threshold:
            return VerificationStatus.SUPPORTED
        if c > s.contradiction_threshold and n < s.contradiction_neutral_max:
            return VerificationStatus.CONTRADICTED
        if (
            n > s.ambiguous_neutral_min
            and s.ambiguous_contradiction_min < c < s.ambiguous_contradiction_max
        ):
            return VerificationStatus.AMBIGUOUS_CONDITIONAL
        return VerificationStatus.UNRESOLVED

    def verify_claims(self, claims: list[Claim], chunk_texts: dict[str, str]) -> list[Claim]:
        """Verify a list of claims against their cited chunk texts.

        Claims whose ``citation_chunk_id`` is absent from *chunk_texts* receive
        ``verification_status=UNRESOLVED``.  NLI probabilities are stored on
        each returned claim.

        Args:
            claims: Claims to verify.
            chunk_texts: Mapping of chunk_id → chunk text.

        Returns:
            New list of :class:`~schemas.models.Claim` with updated NLI fields.
        """
        pairs: list[tuple[str, str]] = []
        pair_indices: list[int] = []  # which claim index each pair belongs to

        for i, claim in enumerate(claims):
            text = chunk_texts.get(claim.citation_chunk_id)
            if text:
                pairs.append((text, claim.text))
                pair_indices.append(i)

        probs_list = self.classify_batch(pairs)

        verified: list[Claim] = []
        result_iter = iter(zip(pair_indices, probs_list, strict=False))
        next_pair = next(result_iter, None)

        for i, claim in enumerate(claims):
            if next_pair is not None and next_pair[0] == i:
                _idx_pr, probs = next_pair
                status = self.apply_heuristic(probs)
                updated = claim.model_copy(
                    update={
                        "verification_status": status,
                        "nli_entailment_probability": probs["entailment"],
                        "nli_contradiction_probability": probs["contradiction"],
                        "nli_neutral_probability": probs["neutral"],
                        "requires_expert_review": status
                        in (
                            VerificationStatus.CONTRADICTED,
                            VerificationStatus.AMBIGUOUS_CONDITIONAL,
                        ),
                    }
                )
                verified.append(updated)
                next_pair = next(result_iter, None)
            else:
                verified.append(claim)

        return verified

    @property
    def model_id(self) -> str:
        """The NLI model identifier used by this verifier."""
        return self._model_id
