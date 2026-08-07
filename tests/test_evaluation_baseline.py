"""Tests for evaluation/baseline.py."""

from unittest.mock import MagicMock

from evaluation.baseline import BaselineRunner
from evaluation.runner import EvaluationRunner
from evaluation.schemas import AnswerType, Difficulty, GoldenQAItem


def _make_golden(question_id="qa-001"):
    return GoldenQAItem(
        question_id=question_id,
        question="What is the limit?",
        gold_answer="The limit is 100.",
        supporting_chunk_ids=["doc-001-ch-0001"],
        expected_entities=["limit"],
        expected_citations=["doc-001-ch-0001"],
        difficulty=Difficulty.EASY,
        domain="engineering",
        answer_type=AnswerType.FACTUAL,
    )


class TestBaselineRunner:
    def test_empty_runner_returns_empty_list(self):
        runner = BaselineRunner()
        results = runner.run_all([_make_golden()])
        assert results == []

    def test_registered_labels_returned(self):
        runner = BaselineRunner()
        runner.register("dense_only", EvaluationRunner())
        runner.register("bm25_only", EvaluationRunner())
        labels = runner.registered_labels()
        assert sorted(labels) == ["bm25_only", "dense_only"]

    def test_run_all_returns_one_result_per_label(self):
        runner = BaselineRunner()
        runner.register("dense_only", EvaluationRunner())
        runner.register("bm25_only", EvaluationRunner())
        results = runner.run_all([_make_golden()])
        assert len(results) == 2
        labels = {r.label for r in results}
        assert labels == {"dense_only", "bm25_only"}

    def test_run_all_no_components_no_error(self):
        runner = BaselineRunner()
        runner.register("no_pipeline", EvaluationRunner())
        results = runner.run_all([_make_golden()])
        assert len(results) == 1
        assert results[0].error is None

    def test_run_all_captures_exception(self):
        bad_runner = MagicMock(spec=EvaluationRunner)
        bad_runner.run_golden_qa.side_effect = RuntimeError("broken runner")

        baseline_runner = BaselineRunner()
        baseline_runner.register("broken", bad_runner)
        results = baseline_runner.run_all([_make_golden()])

        assert len(results) == 1
        assert results[0].error is not None
        assert "broken runner" in results[0].error

    def test_run_results_has_run_id(self):
        runner = BaselineRunner()
        runner.register("test", EvaluationRunner())
        results = runner.run_all([_make_golden()])
        assert results[0].run_results.run_id != ""

    def test_empty_golden_items_still_runs(self):
        runner = BaselineRunner()
        runner.register("empty_run", EvaluationRunner())
        results = runner.run_all([])
        assert len(results) == 1
        assert results[0].error is None

    def test_register_overrides_existing_label(self):
        runner = BaselineRunner()
        runner1 = EvaluationRunner()
        runner2 = EvaluationRunner()
        runner.register("variant", runner1)
        runner.register("variant", runner2)  # override
        assert len(runner.registered_labels()) == 1
