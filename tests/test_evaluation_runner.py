"""Tests for evaluation/runner.py."""

from unittest.mock import MagicMock

import pytest

from evaluation.runner import (
    CorruptionEvaluationResult,
    EvaluationRunner,
    QueryEvaluationResult,
)
from evaluation.schemas import (
    AnswerType,
    CorruptionSeverity,
    Difficulty,
    EvaluationCorruptionCase,
    GoldenQAItem,
)
from schemas.models import RootCauseStage


def _make_golden(question_id="qa-001", supporting=None):
    return GoldenQAItem(
        question_id=question_id,
        question="What is the safe load capacity of beam type A?",
        gold_answer="The safe load capacity is 500 kg.",
        supporting_chunk_ids=supporting or ["doc-001-ch-0001"],
        expected_entities=["beam type A", "load capacity"],
        expected_citations=["doc-001-ch-0001"],
        difficulty=Difficulty.EASY,
        domain="structural_engineering",
        answer_type=AnswerType.NUMERICAL_THRESHOLD,
    )


def _make_corruption(case_id="corr-retrieval-001", q_id="qa-001"):
    return EvaluationCorruptionCase(
        case_id=case_id,
        question_id=q_id,
        corruption_type="retrieval_swap",
        ground_truth_root_cause=RootCauseStage.RETRIEVAL,
        severity=CorruptionSeverity.MEDIUM,
        description="Swap top retrieval chunk.",
        expected_quality_delta=-0.3,
    )


class TestEvaluationRunner:
    def test_run_golden_qa_no_components_returns_results(self):
        runner = EvaluationRunner()
        items = [_make_golden("qa-001"), _make_golden("qa-002")]
        results = runner.run_golden_qa(items)
        assert len(results) == 2
        assert results[0].question_id == "qa-001"
        assert results[1].question_id == "qa-002"

    def test_run_golden_qa_no_components_skips_pipeline(self):
        runner = EvaluationRunner()
        results = runner.run_golden_qa([_make_golden()])
        r = results[0]
        assert r.retrieval_result is None
        assert r.structured_answer is None
        assert r.verification_report is None
        assert r.error is None

    def test_run_golden_qa_total_latency_nonnegative(self):
        runner = EvaluationRunner()
        results = runner.run_golden_qa([_make_golden()])
        assert results[0].total_latency_ms >= 0.0

    def test_run_golden_qa_with_retriever_calls_retrieve(self):
        mock_retriever = MagicMock()
        mock_result = MagicMock()
        mock_result.candidates = []
        mock_retriever.retrieve.return_value = mock_result

        runner = EvaluationRunner(retriever=mock_retriever)
        results = runner.run_golden_qa([_make_golden()], top_k=5)

        mock_retriever.retrieve.assert_called_once()
        call_args = mock_retriever.retrieve.call_args
        assert call_args[0][2] == 5  # top_k
        assert results[0].retrieval_result is mock_result

    def test_run_golden_qa_generator_not_called_without_retrieval(self):
        mock_generator = MagicMock()
        runner = EvaluationRunner(generator=mock_generator)
        runner.run_golden_qa([_make_golden()])
        mock_generator.generate.assert_not_called()

    def test_run_golden_qa_generator_called_with_retrieval(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = MagicMock()
        mock_generator = MagicMock()
        mock_generator.generate.return_value = MagicMock()

        runner = EvaluationRunner(retriever=mock_retriever, generator=mock_generator)
        runner.run_golden_qa([_make_golden()])
        mock_generator.generate.assert_called_once()

    def test_run_golden_qa_error_captured_not_raised(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.side_effect = RuntimeError("boom")

        runner = EvaluationRunner(retriever=mock_retriever)
        results = runner.run_golden_qa([_make_golden()])
        assert results[0].error == "boom"
        assert results[0].retrieval_result is None

    def test_run_corruption_benchmark_no_controller(self):
        runner = EvaluationRunner()
        cases = [_make_corruption()]
        results = runner.run_corruption_benchmark(cases)
        assert len(results) == 1
        assert results[0].case_id == "corr-retrieval-001"
        assert results[0].replay_report is None
        assert results[0].attributed_root_cause == "unknown"
        assert not results[0].is_correct

    def test_run_corruption_benchmark_with_controller(self):
        mock_controller = MagicMock()
        mock_report = MagicMock()
        mock_report.primary_root_cause = RootCauseStage.RETRIEVAL
        mock_controller.run_corruption.return_value = mock_report

        runner = EvaluationRunner(replay_controller=mock_controller)
        results = runner.run_corruption_benchmark([_make_corruption()])

        assert results[0].is_correct
        assert results[0].attributed_root_cause == "retrieval"

    def test_run_corruption_benchmark_error_captured(self):
        mock_controller = MagicMock()
        mock_controller.run_corruption.side_effect = RuntimeError("replay failure")

        runner = EvaluationRunner(replay_controller=mock_controller)
        results = runner.run_corruption_benchmark([_make_corruption()])

        assert results[0].error == "replay failure"
        assert not results[0].is_correct

    def test_build_run_results_aggregates_latency(self):
        runner = EvaluationRunner()
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=None,
            structured_answer=None,
            verification_report=None,
            retrieval_latency_ms=10.0,
            generation_latency_ms=20.0,
            verification_latency_ms=5.0,
            total_latency_ms=35.0,
        )
        cr = CorruptionEvaluationResult(
            case_id="corr-retrieval-001",
            ground_truth_root_cause="retrieval",
            attributed_root_cause="retrieval",
            is_correct=True,
            is_realistic_boundary_error=False,
            replay_report=None,
            latency_ms=15.0,
        )
        run_results = runner.build_run_results([qr], [cr])
        assert run_results.total_latency_ms == pytest.approx(50.0)
        assert len(run_results.query_results) == 1
        assert len(run_results.corruption_results) == 1

    def test_build_run_results_new_run_id(self):
        runner = EvaluationRunner()
        r1 = runner.build_run_results([], [])
        r2 = runner.build_run_results([], [])
        assert r1.run_id != r2.run_id

    def test_query_date_propagated_to_retriever(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = MagicMock()

        runner = EvaluationRunner(retriever=mock_retriever, query_date="2023-06-15")
        runner.run_golden_qa([_make_golden()])

        call_args = mock_retriever.retrieve.call_args
        assert call_args[0][1] == "2023-06-15"
