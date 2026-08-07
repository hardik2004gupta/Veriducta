"""Baseline runner for alternative pipeline configurations.

:class:`BaselineRunner` manages a registry of named :class:`~evaluation.runner.EvaluationRunner`
instances representing alternative pipeline variants (dense-only, BM25-only, hybrid without
reranker, etc.).  Callers construct the runners and register them; :meth:`BaselineRunner.run_all`
evaluates them all on the same golden QA set.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import structlog

from evaluation.runner import EvaluationRunner, EvaluationRunResults, QueryEvaluationResult
from evaluation.schemas import GoldenQAItem
from schemas.models import EvaluationMetrics

logger = structlog.get_logger(__name__)


@dataclass
class BaselineResult:
    """Results from a single named baseline configuration run."""

    label: str
    run_results: EvaluationRunResults
    metrics: EvaluationMetrics | None = None
    error: str | None = None


class BaselineRunner:
    """Run and collect results for alternative pipeline configurations.

    Standard baseline labels (all optional - register only what is needed):

    - ``dense_only``   - dense retrieval, no BM25
    - ``bm25_only``    - BM25 retrieval, no dense
    - ``hybrid``       - BM25 + dense RRF, no cross-encoder reranker
    - ``no_reranker``  - full hybrid, reranker disabled
    - ``no_replay``    - full pipeline without the causal replay step

    Callers register runners via :meth:`register` and then call :meth:`run_all`.
    """

    def __init__(self) -> None:
        self._runners: dict[str, EvaluationRunner] = {}

    def register(self, label: str, runner: EvaluationRunner) -> None:
        """Register a pre-configured :class:`~evaluation.runner.EvaluationRunner` under a label.

        Args:
            label: Short identifier (e.g. ``"dense_only"``).
            runner: Fully wired runner for this baseline variant.
        """
        self._runners[label] = runner
        logger.info("baseline_registered", label=label)

    def run_all(
        self,
        golden_items: list[GoldenQAItem],
        top_k: int = 8,
    ) -> list[BaselineResult]:
        """Run all registered baselines on the same golden QA set.

        Args:
            golden_items: Annotated golden QA items.
            top_k: Retrieval top-k for every baseline.

        Returns:
            List of :class:`BaselineResult`, one per registered runner.
        """
        results: list[BaselineResult] = []
        for label, runner in self._runners.items():
            logger.info("baseline_started", label=label)
            result = self._run_one(label, runner, golden_items, top_k)
            results.append(result)
            logger.info("baseline_complete", label=label, error=result.error)
        return results

    def registered_labels(self) -> list[str]:
        """Return labels of all currently registered baselines."""
        return list(self._runners.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_one(
        self,
        label: str,
        runner: EvaluationRunner,
        golden_items: list[GoldenQAItem],
        top_k: int,
    ) -> BaselineResult:
        try:
            query_results: list[QueryEvaluationResult] = runner.run_golden_qa(
                golden_items, top_k=top_k
            )
            run_results = runner.build_run_results(query_results, [])
            return BaselineResult(label=label, run_results=run_results)
        except Exception as exc:
            logger.error("baseline_run_failed", label=label, error=str(exc))
            return BaselineResult(
                label=label,
                run_results=EvaluationRunResults(run_id=str(uuid4())),
                error=str(exc),
            )
