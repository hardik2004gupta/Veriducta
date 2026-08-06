"""Cross-encoder reranker using ms-marco-MiniLM-L-12-v2.

Runs a single batch inference pass over the top-40 RRF candidates.  The
complete reranked list (all 40 with scores and ``post_rerank_rank``) is
returned so the replay engine can test reranker cutoff counterfactuals
without re-running inference.
"""

import structlog
from sentence_transformers import CrossEncoder

from core.exceptions import RetrievalError
from observability.metrics import RERANKER_LATENCY
from schemas.models import RetrievalCandidate
from utils.timers import timer

logger = structlog.get_logger(__name__)

_RERANKER_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-12-v2"

_reranker_instance: "CrossEncoderReranker | None" = None


class CrossEncoderReranker:
    """ms-marco-MiniLM-L-12-v2 cross-encoder reranker.

    Takes up to ``reranker_input_top_k`` candidates, runs batch inference,
    and returns all candidates with ``reranker_score`` and ``post_rerank_rank``
    set.  Candidates without chunk text receive score ``-inf`` and sort last.

    Args:
        model_id: HuggingFace model identifier.
    """

    def __init__(self, model_id: str = _RERANKER_MODEL_ID) -> None:
        logger.info("reranker_loading", model_id=model_id)
        try:
            self._model: CrossEncoder = CrossEncoder(model_id)
        except Exception as exc:
            raise RetrievalError(
                f"Failed to load reranker model: {model_id}",
                details={"model_id": model_id, "error": str(exc)},
            ) from exc
        self._model_id = model_id
        logger.info("reranker_loaded", model_id=model_id)

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        """Rerank *candidates* by relevance to *query*.

        Args:
            query: Natural-language query string.
            candidates: Up to 40 candidates; those with ``chunk.text``
                        are scored; the rest receive score ``-inf``.

        Returns:
            All input candidates sorted by descending reranker score, with
            ``reranker_score`` and ``post_rerank_rank`` populated.

        Raises:
            RetrievalError: If batch inference fails.
        """
        if not candidates:
            return []

        # Separate candidates that have chunk text from those that don't.
        scoreable = [(i, c) for i, c in enumerate(candidates) if c.chunk and c.chunk.text]

        if not scoreable:
            logger.warning("reranker_no_chunk_text", candidate_count=len(candidates))
            return [
                c.model_copy(update={"reranker_score": float("-inf"), "post_rerank_rank": rank})
                for rank, c in enumerate(candidates, start=1)
            ]

        pairs = [(query, c.chunk.text) for _, c in scoreable]  # type: ignore[union-attr]

        with timer("reranker") as t:
            try:
                raw_scores = self._model.predict(pairs)
            except Exception as exc:
                raise RetrievalError(
                    "Reranker batch inference failed",
                    details={"model_id": self._model_id, "error": str(exc)},
                ) from exc

        RERANKER_LATENCY.observe(t.elapsed_ms)
        logger.debug(
            "reranker_inference_done",
            latency_ms=t.elapsed_ms,
            scored_count=len(scoreable),
        )

        # Map original index → score
        score_map: dict[int, float] = {
            orig_idx: float(s) for (orig_idx, _), s in zip(scoreable, raw_scores, strict=False)
        }

        scored = [
            c.model_copy(update={"reranker_score": score_map.get(i, float("-inf"))})
            for i, c in enumerate(candidates)
        ]

        sorted_cands = sorted(
            scored,
            key=lambda c: c.reranker_score if c.reranker_score is not None else float("-inf"),
            reverse=True,
        )

        result: list[RetrievalCandidate] = [
            c.model_copy(update={"post_rerank_rank": rank})
            for rank, c in enumerate(sorted_cands, start=1)
        ]

        logger.info(
            "reranker_done",
            input_count=len(candidates),
            latency_ms=t.elapsed_ms,
        )
        return result

    @property
    def model_id(self) -> str:
        """Reranker model HuggingFace identifier."""
        return self._model_id


def get_reranker(model_id: str = _RERANKER_MODEL_ID) -> CrossEncoderReranker:
    """Return the process-level singleton :class:`CrossEncoderReranker`.

    Loads the model on first call; subsequent calls return the cached instance.

    Args:
        model_id: Model to load on first call; ignored on subsequent calls.

    Returns:
        The singleton :class:`CrossEncoderReranker`.
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker(model_id)
    return _reranker_instance
