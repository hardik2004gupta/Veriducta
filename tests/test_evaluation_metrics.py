"""Tests for evaluation/metrics.py."""

import pytest

from evaluation.metrics import MetricsComputer, _ndcg, _safe_mean
from evaluation.runner import (
    CorruptionEvaluationResult,
    EvaluationRunResults,
    QueryEvaluationResult,
)
from evaluation.schemas import AnswerType, Difficulty, GoldenQAItem
from schemas.models import (
    RetrievalCandidate,
    RetrievalResult,
)


def _make_golden(question_id="qa-001", supporting=None):
    return GoldenQAItem(
        question_id=question_id,
        question="What is the limit?",
        gold_answer="The limit is 100.",
        supporting_chunk_ids=supporting or ["doc-001-ch-0001"],
        expected_entities=["limit"],
        expected_citations=["doc-001-ch-0001"],
        difficulty=Difficulty.EASY,
        domain="engineering",
        answer_type=AnswerType.NUMERICAL_THRESHOLD,
    )


def _make_retrieval_result(chunk_ids, temporal_rejected=None):
    candidates = [
        RetrievalCandidate(chunk_id=cid, temporal_filter_rejected=False) for cid in chunk_ids
    ]
    rejections = [
        RetrievalCandidate(chunk_id=cid, temporal_filter_rejected=True)
        for cid in (temporal_rejected or [])
    ]
    return RetrievalResult(
        query="test",
        query_date="2024-01-01",
        top_k=len(candidates),
        candidates=candidates,
        temporal_rejections=rejections,
    )


def _make_query_result(question_id="qa-001", chunk_ids=None, answer=None, report=None):
    rr = _make_retrieval_result(chunk_ids or []) if chunk_ids is not None else None
    return QueryEvaluationResult(
        question_id=question_id,
        question="q",
        retrieval_result=rr,
        structured_answer=answer,
        verification_report=report,
        retrieval_latency_ms=100.0,
        generation_latency_ms=200.0,
        verification_latency_ms=50.0,
        total_latency_ms=350.0,
    )


def _make_run_results(query_results, corruption_results=None):
    return EvaluationRunResults(
        run_id="test-run-001",
        query_results=query_results,
        corruption_results=corruption_results or [],
    )


class TestSafeMean:
    def test_empty_list_returns_zero(self):
        assert _safe_mean([]) == 0.0

    def test_single_value(self):
        assert _safe_mean([0.7]) == pytest.approx(0.7)

    def test_multiple_values(self):
        assert _safe_mean([0.5, 0.9]) == pytest.approx(0.7)


class TestNdcg:
    def test_perfect_retrieval(self):
        # All relevant items at top k
        assert _ndcg([1, 1, 0, 0, 0], k=5) == pytest.approx(1.0)

    def test_no_relevant_items(self):
        assert _ndcg([0, 0, 0], k=3) == pytest.approx(0.0)

    def test_relevant_item_at_second_position(self):
        # Relevant at rank 2 vs ideal at rank 1
        score = _ndcg([0, 1, 0], k=3)
        assert 0.0 < score < 1.0

    def test_empty_relevance_list(self):
        assert _ndcg([], k=5) == pytest.approx(0.0)

    def test_k_cutoff_applied(self):
        # Relevant item at rank 4, k=3 — should not be counted
        assert _ndcg([0, 0, 0, 1], k=3) == pytest.approx(0.0)


class TestMetricsComputerRetrieval:
    def setup_method(self):
        self.computer = MetricsComputer()

    def test_recall_at_5_perfect(self):
        golden = _make_golden(supporting=["doc-001-ch-0001"])
        qr = _make_query_result(chunk_ids=["doc-001-ch-0001", "other-ch-0001"])
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.recall_at_5 == pytest.approx(1.0)

    def test_recall_at_5_miss(self):
        golden = _make_golden(supporting=["doc-001-ch-0001"])
        qr = _make_query_result(chunk_ids=["other-ch-0002", "other-ch-0003"])
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.recall_at_5 == pytest.approx(0.0)

    def test_mrr_first_rank(self):
        golden = _make_golden(supporting=["doc-001-ch-0001"])
        qr = _make_query_result(chunk_ids=["doc-001-ch-0001", "other-ch-0001"])
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.mrr == pytest.approx(1.0)

    def test_mrr_second_rank(self):
        golden = _make_golden(supporting=["doc-001-ch-0001"])
        qr = _make_query_result(chunk_ids=["other-ch-0001", "doc-001-ch-0001"])
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.mrr == pytest.approx(0.5)

    def test_temporal_valid_rate_all_valid(self):
        golden = _make_golden()
        rr = _make_retrieval_result(["doc-001-ch-0001"], temporal_rejected=[])
        qr = _make_query_result(chunk_ids=None)
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=rr,
            structured_answer=None,
            verification_report=None,
            retrieval_latency_ms=10.0,
            generation_latency_ms=0.0,
            verification_latency_ms=0.0,
            total_latency_ms=10.0,
        )
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.temporal_valid_retrieval_rate == pytest.approx(1.0)

    def test_no_retrieval_results_zero_metrics(self):
        golden = _make_golden()
        qr = _make_query_result(chunk_ids=None)
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.recall_at_5 == pytest.approx(0.0)
        assert metrics.retrieval.mrr == pytest.approx(0.0)

    def test_evidence_diversity_multiple_documents(self):
        golden = _make_golden()
        rr = _make_retrieval_result(["doc-001-ch-0001", "doc-002-ch-0001", "doc-003-ch-0001"])
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=rr,
            structured_answer=None,
            verification_report=None,
            retrieval_latency_ms=10.0,
            generation_latency_ms=0.0,
            verification_latency_ms=0.0,
            total_latency_ms=10.0,
        )
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.retrieval.evidence_diversity == pytest.approx(3.0)


class TestMetricsComputerAnswerQuality:
    def setup_method(self):
        self.computer = MetricsComputer()

    def test_faithfulness_all_supported(self):
        golden = _make_golden()
        mock_report = type(
            "R",
            (),
            {
                "supported_count": 3,
                "contradicted_count": 0,
                "ambiguous_count": 0,
                "not_searched_count": 0,
                "unresolved_count": 0,
                "verified_claims": [],
            },
        )()
        mock_answer = type(
            "A",
            (),
            {
                "claims": [],
                "citations": [],
                "estimated_cost_usd": 0.001,
            },
        )()
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=None,
            structured_answer=mock_answer,
            verification_report=mock_report,
            retrieval_latency_ms=0.0,
            generation_latency_ms=100.0,
            verification_latency_ms=50.0,
            total_latency_ms=150.0,
        )
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.answer_quality.citation_entailment_rate == pytest.approx(1.0)

    def test_faithfulness_partial(self):
        golden = _make_golden()
        mock_report = type(
            "R",
            (),
            {
                "supported_count": 2,
                "contradicted_count": 2,
                "ambiguous_count": 0,
                "not_searched_count": 0,
                "unresolved_count": 0,
                "verified_claims": [],
            },
        )()
        mock_answer = type(
            "A",
            (),
            {
                "claims": [],
                "citations": [],
                "estimated_cost_usd": 0.001,
            },
        )()
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=None,
            structured_answer=mock_answer,
            verification_report=mock_report,
            retrieval_latency_ms=0.0,
            generation_latency_ms=100.0,
            verification_latency_ms=50.0,
            total_latency_ms=150.0,
        )
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.answer_quality.citation_entailment_rate == pytest.approx(0.5)

    def test_no_verification_report_skipped(self):
        golden = _make_golden()
        qr = _make_query_result()
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [golden])
        assert metrics.answer_quality.citation_entailment_rate == pytest.approx(0.0)


class TestMetricsComputerCausalAttribution:
    def setup_method(self):
        self.computer = MetricsComputer()

    def test_empty_corruption_results(self):
        run = _make_run_results([])
        metrics = self.computer.compute(run, [])
        assert metrics.causal_attribution.root_cause_localization_accuracy == 0.0

    def test_all_correct(self):
        results = [
            CorruptionEvaluationResult(
                case_id=f"corr-retrieval-{i:03d}",
                ground_truth_root_cause="retrieval",
                attributed_root_cause="retrieval",
                is_correct=True,
                is_realistic_boundary_error=False,
                replay_report=MagicMock(stage_results={}),
                latency_ms=10.0,
            )
            for i in range(3)
        ]
        run = _make_run_results([], results)
        metrics = self.computer.compute(run, [])
        assert metrics.causal_attribution.root_cause_localization_accuracy == pytest.approx(1.0)

    def test_partial_correct(self):
        correct = CorruptionEvaluationResult(
            case_id="corr-retrieval-001",
            ground_truth_root_cause="retrieval",
            attributed_root_cause="retrieval",
            is_correct=True,
            is_realistic_boundary_error=False,
            replay_report=MagicMock(stage_results={}),
            latency_ms=10.0,
        )
        wrong = CorruptionEvaluationResult(
            case_id="corr-retrieval-002",
            ground_truth_root_cause="retrieval",
            attributed_root_cause="generation",
            is_correct=False,
            is_realistic_boundary_error=False,
            replay_report=MagicMock(stage_results={}),
            latency_ms=10.0,
        )
        run = _make_run_results([], [correct, wrong])
        metrics = self.computer.compute(run, [])
        assert metrics.causal_attribution.root_cause_localization_accuracy == pytest.approx(0.5)

    def test_no_replay_report_excluded(self):
        no_report = CorruptionEvaluationResult(
            case_id="corr-retrieval-001",
            ground_truth_root_cause="retrieval",
            attributed_root_cause="unknown",
            is_correct=False,
            is_realistic_boundary_error=False,
            replay_report=None,
            latency_ms=10.0,
        )
        run = _make_run_results([], [no_report])
        metrics = self.computer.compute(run, [])
        assert metrics.causal_attribution.root_cause_localization_accuracy == 0.0


class TestMetricsComputerOperational:
    def setup_method(self):
        self.computer = MetricsComputer()

    def test_latency_percentiles(self):
        latencies = [100.0, 200.0, 300.0, 400.0, 500.0, 1000.0]
        qrs = [
            QueryEvaluationResult(
                question_id=f"qa-{i:03d}",
                question="q",
                retrieval_result=None,
                structured_answer=None,
                verification_report=None,
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                verification_latency_ms=0.0,
                total_latency_ms=lat,
            )
            for i, lat in enumerate(latencies)
        ]
        run = _make_run_results(qrs)
        metrics = self.computer.compute(run, [])
        assert metrics.operational.p50_latency_ms > 0.0
        assert metrics.operational.p95_latency_ms >= metrics.operational.p50_latency_ms

    def test_no_latency_data_returns_zeros(self):
        run = _make_run_results([])
        metrics = self.computer.compute(run, [])
        assert metrics.operational.p50_latency_ms == 0.0
        assert metrics.operational.p95_latency_ms == 0.0

    def test_errored_queries_excluded_from_latency(self):
        err_qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=None,
            structured_answer=None,
            verification_report=None,
            retrieval_latency_ms=0.0,
            generation_latency_ms=0.0,
            verification_latency_ms=0.0,
            total_latency_ms=999.0,
            error="something broke",
        )
        ok_qr = QueryEvaluationResult(
            question_id="qa-002",
            question="q",
            retrieval_result=None,
            structured_answer=None,
            verification_report=None,
            retrieval_latency_ms=0.0,
            generation_latency_ms=0.0,
            verification_latency_ms=0.0,
            total_latency_ms=100.0,
        )
        run = _make_run_results([err_qr, ok_qr])
        metrics = self.computer.compute(run, [])
        # Only ok_qr (100ms) should be counted
        assert metrics.operational.p50_latency_ms == pytest.approx(100.0)

    def test_cost_computed_from_structured_answer(self):
        mock_answer = type(
            "A",
            (),
            {
                "estimated_cost_usd": 0.005,
                "claims": [],
                "citations": [],
            },
        )()
        qr = QueryEvaluationResult(
            question_id="qa-001",
            question="q",
            retrieval_result=None,
            structured_answer=mock_answer,
            verification_report=None,
            retrieval_latency_ms=0.0,
            generation_latency_ms=0.0,
            verification_latency_ms=0.0,
            total_latency_ms=100.0,
        )
        run = _make_run_results([qr])
        metrics = self.computer.compute(run, [])
        assert metrics.operational.mean_cost_per_query_usd == pytest.approx(0.005)


# Import MagicMock for use above (must be at module level for pytest collection)
from unittest.mock import MagicMock  # noqa: E402
