"""Optional RAGAS adapter for external baseline comparison.

This module gracefully degrades when the ``ragas`` package is not installed.
Callers should always check :meth:`RAGASAdapter.is_available` before calling
:meth:`RAGASAdapter.compute`.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_RAGAS_AVAILABLE = False
try:
    import ragas  # noqa: F401

    _RAGAS_AVAILABLE = True
except ImportError:
    pass


class RAGASAdapter:
    """Compute RAGAS metrics for external comparison with Veriducta's own evaluation.

    When ``ragas`` is not installed all methods return empty results and log a
    warning rather than raising.
    """

    def is_available(self) -> bool:
        """Return True if the ``ragas`` library is installed and importable."""
        return _RAGAS_AVAILABLE

    def compute(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str],
    ) -> dict[str, float]:
        """Compute RAGAS evaluation metrics.

        Computes: ``faithfulness``, ``answer_relevancy``, ``context_recall``,
        ``context_precision``.  Returns an empty dict if ragas is unavailable or
        computation fails.

        Args:
            questions: Natural-language question strings.
            answers: Generated answer strings matching each question.
            contexts: Per-question lists of retrieved chunk texts.
            ground_truths: Reference (gold) answers for each question.

        Returns:
            Dict mapping metric name to float value.  Empty on failure.
        """
        if not _RAGAS_AVAILABLE:
            logger.warning("ragas_not_available", hint="pip install ragas datasets")
            return {}

        if not questions:
            logger.warning("ragas_empty_input")
            return {}

        try:
            return self._compute_ragas(questions, answers, contexts, ground_truths)
        except Exception as exc:
            logger.error("ragas_computation_failed", error=str(exc))
            return {}

    def _compute_ragas(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str],
    ) -> dict[str, float]:
        """Internal: run ragas evaluation pipeline."""
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        dataset = Dataset.from_dict(
            {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
            }
        )
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )
        return {str(k): float(v) for k, v in result.items()}
