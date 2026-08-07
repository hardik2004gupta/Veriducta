"""Evaluation runner — executes golden QA and corruption benchmark queries.

:class:`EvaluationRunner` drives the retrieval → generation → verification pipeline
for each golden QA item and collects per-query results.  It also wraps the replay
engine for the 60-case corruption benchmark.  All components are injected as
constructor arguments so the runner is fully testable without live services.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

import structlog

from core.interfaces import BaseGenerator, BaseRetriever, BaseVerifier
from evaluation.schemas import EvaluationCorruptionCase, GoldenQAItem
from generation.schemas import StructuredAnswer, VerificationReport
from replay.controller import ReplayController
from replay.models import CorruptionCase, ReplayReport
from schemas.models import RetrievalResult

logger = structlog.get_logger(__name__)


@dataclass
class QueryEvaluationResult:
    """Result of evaluating one golden QA item through the full pipeline."""

    question_id: str
    question: str
    retrieval_result: RetrievalResult | None
    structured_answer: StructuredAnswer | None
    verification_report: VerificationReport | None
    retrieval_latency_ms: float
    generation_latency_ms: float
    verification_latency_ms: float
    total_latency_ms: float
    error: str | None = None


@dataclass
class CorruptionEvaluationResult:
    """Result of running the replay engine on one corruption case."""

    case_id: str
    ground_truth_root_cause: str
    attributed_root_cause: str
    is_correct: bool
    is_realistic_boundary_error: bool
    replay_report: ReplayReport | None
    latency_ms: float
    error: str | None = None


@dataclass
class EvaluationRunResults:
    """Aggregated results for a complete evaluation run."""

    run_id: str
    query_results: list[QueryEvaluationResult] = field(default_factory=list)
    corruption_results: list[CorruptionEvaluationResult] = field(default_factory=list)
    total_latency_ms: float = 0.0


class EvaluationRunner:
    """Execute golden QA and corruption benchmark evaluation.

    Args:
        retriever: Hybrid retrieval component.  When ``None`` retrieval is skipped.
        generator: Structured generation component.  Skipped when ``None``.
        verifier: Claim verification component.  Skipped when ``None``.
        replay_controller: Replay engine controller for corruption benchmark.
        query_date: ISO-8601 date injected into every retrieval call.
    """

    def __init__(
        self,
        retriever: BaseRetriever | None = None,
        generator: BaseGenerator | None = None,
        verifier: BaseVerifier | None = None,
        replay_controller: ReplayController | None = None,
        query_date: str = "2024-01-01",
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._verifier = verifier
        self._replay_controller = replay_controller
        self._query_date = query_date

    def run_golden_qa(
        self,
        items: list[GoldenQAItem],
        top_k: int = 8,
    ) -> list[QueryEvaluationResult]:
        """Evaluate all golden QA items through the retrieval → generation → verification pipeline.

        Args:
            items: List of annotated golden QA items.
            top_k: Retrieval top-k passed to the retriever.

        Returns:
            Per-item :class:`QueryEvaluationResult` list, one entry per input item.
        """
        results: list[QueryEvaluationResult] = []
        for item in items:
            result = self._evaluate_query(item, top_k)
            results.append(result)
            logger.info(
                "query_evaluation_complete",
                question_id=item.question_id,
                has_answer=result.structured_answer is not None,
                error=result.error,
            )
        return results

    def run_corruption_benchmark(
        self,
        cases: list[EvaluationCorruptionCase],
    ) -> list[CorruptionEvaluationResult]:
        """Run all corruption cases through the replay engine.

        Args:
            cases: List of corruption cases from the benchmark dataset.

        Returns:
            Per-case :class:`CorruptionEvaluationResult` list.
        """
        results: list[CorruptionEvaluationResult] = []
        for case in cases:
            result = self._evaluate_corruption(case)
            results.append(result)
            logger.info(
                "corruption_evaluation_complete",
                case_id=case.case_id,
                is_correct=result.is_correct,
                error=result.error,
            )
        return results

    def build_run_results(
        self,
        query_results: list[QueryEvaluationResult],
        corruption_results: list[CorruptionEvaluationResult],
    ) -> EvaluationRunResults:
        """Assemble query and corruption results into an :class:`EvaluationRunResults`.

        Args:
            query_results: Results from :meth:`run_golden_qa`.
            corruption_results: Results from :meth:`run_corruption_benchmark`.

        Returns:
            :class:`EvaluationRunResults` with a fresh run ID and summed latency.
        """
        total_latency_ms = sum(r.total_latency_ms for r in query_results) + sum(
            r.latency_ms for r in corruption_results
        )
        return EvaluationRunResults(
            run_id=str(uuid4()),
            query_results=query_results,
            corruption_results=corruption_results,
            total_latency_ms=total_latency_ms,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate_query(self, item: GoldenQAItem, top_k: int) -> QueryEvaluationResult:
        """Run one golden QA item through all available pipeline stages."""
        retrieval_result: RetrievalResult | None = None
        structured_answer: StructuredAnswer | None = None
        verification_report: VerificationReport | None = None
        retrieval_latency_ms = 0.0
        generation_latency_ms = 0.0
        verification_latency_ms = 0.0
        error: str | None = None

        t_start = time.perf_counter()

        try:
            if self._retriever is not None:
                t0 = time.perf_counter()
                retrieval_result = self._retriever.retrieve(item.question, self._query_date, top_k)
                retrieval_latency_ms = (time.perf_counter() - t0) * 1000.0

            if self._generator is not None and retrieval_result is not None:
                t0 = time.perf_counter()
                structured_answer = self._generator.generate(item.question, retrieval_result)
                generation_latency_ms = (time.perf_counter() - t0) * 1000.0

            if (
                self._verifier is not None
                and structured_answer is not None
                and retrieval_result is not None
            ):
                t0 = time.perf_counter()
                verification_report = self._verifier.verify(structured_answer, retrieval_result)
                verification_latency_ms = (time.perf_counter() - t0) * 1000.0

        except Exception as exc:
            error = str(exc)
            logger.error(
                "query_evaluation_failed",
                question_id=item.question_id,
                error=error,
            )

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        return QueryEvaluationResult(
            question_id=item.question_id,
            question=item.question,
            retrieval_result=retrieval_result,
            structured_answer=structured_answer,
            verification_report=verification_report,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
            verification_latency_ms=verification_latency_ms,
            total_latency_ms=total_latency_ms,
            error=error,
        )

    def _evaluate_corruption(self, case: EvaluationCorruptionCase) -> CorruptionEvaluationResult:
        """Run one corruption case through the replay engine."""
        replay_report: ReplayReport | None = None
        error: str | None = None
        attributed_root_cause = "unknown"
        is_correct = False

        t_start = time.perf_counter()

        try:
            if self._replay_controller is not None:
                corruption_case = CorruptionCase(
                    case_id=case.case_id,
                    corruption_type=case.corruption_type,
                    ground_truth_root_cause=case.ground_truth_root_cause,
                    is_realistic_boundary_error=case.is_realistic_boundary_error,
                    pipeline_trace_id=case.pipeline_trace_id,
                    question_id=case.question_id,
                    corruption_parameters=case.corruption_parameters,
                    notes=case.notes,
                )
                replay_report = self._replay_controller.run_corruption(corruption_case)
                attributed_root_cause = str(replay_report.primary_root_cause)
                is_correct = attributed_root_cause == str(case.ground_truth_root_cause)

        except Exception as exc:
            error = str(exc)
            logger.error(
                "corruption_evaluation_failed",
                case_id=case.case_id,
                error=error,
            )

        latency_ms = (time.perf_counter() - t_start) * 1000.0

        return CorruptionEvaluationResult(
            case_id=case.case_id,
            ground_truth_root_cause=str(case.ground_truth_root_cause),
            attributed_root_cause=attributed_root_cause,
            is_correct=is_correct,
            is_realistic_boundary_error=case.is_realistic_boundary_error,
            replay_report=replay_report,
            latency_ms=latency_ms,
            error=error,
        )
