"""Tests for evaluation/corruptions.py — CORRUPTIONS_SEED and CorruptionDatasetBuilder."""

from pathlib import Path

import pytest

from evaluation.corruptions import CORRUPTIONS_SEED, CorruptionDatasetBuilder
from evaluation.schemas import EvaluationCorruptionCase
from replay.models import CorruptionCase
from schemas.models import RootCauseStage


class TestCorruptionsSeed:
    def test_seed_has_sixty_cases(self):
        assert len(CORRUPTIONS_SEED) == 60

    def test_all_case_ids_are_unique(self):
        ids = [d["case_id"] for d in CORRUPTIONS_SEED]
        assert len(ids) == len(set(ids))

    def test_retrieval_cases_count_is_twenty(self):
        retrieval = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "retrieval"]
        assert len(retrieval) == 20

    def test_chunking_cases_count_is_fifteen(self):
        chunking = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "chunking"]
        assert len(chunking) == 15

    def test_reranker_cases_count_is_fifteen(self):
        reranker = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "reranking"]
        assert len(reranker) == 15

    def test_generation_cases_count_is_ten(self):
        generation = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "generation"]
        assert len(generation) == 10

    def test_chunking_realistic_boundary_errors_count_is_ten(self):
        realistic = [
            d
            for d in CORRUPTIONS_SEED
            if d["ground_truth_root_cause"] == "chunking"
            and d.get("is_realistic_boundary_error", False)
        ]
        assert len(realistic) == 10

    def test_chunking_non_realistic_boundary_errors_count_is_five(self):
        non_realistic = [
            d
            for d in CORRUPTIONS_SEED
            if d["ground_truth_root_cause"] == "chunking"
            and not d.get("is_realistic_boundary_error", False)
        ]
        assert len(non_realistic) == 5

    def test_all_expected_quality_deltas_are_negative(self):
        for d in CORRUPTIONS_SEED:
            msg = f"{d['case_id']} expected_quality_delta={d['expected_quality_delta']}"
            assert d["expected_quality_delta"] < 0, msg

    def test_all_cases_are_pydantic_valid(self):
        for d in CORRUPTIONS_SEED:
            case = EvaluationCorruptionCase.model_validate(d)
            assert case.case_id.startswith("corr-")

    def test_retrieval_corruption_types_are_correct(self):
        retrieval = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "retrieval"]
        types = {d["corruption_type"] for d in retrieval}
        assert "retrieval_swap" in types
        assert "retrieval_supersession_removal" in types
        assert "retrieval_bm25_zeroing" in types
        assert "retrieval_top_k_reduction" in types

    def test_generation_corruption_types_are_correct(self):
        generation = [d for d in CORRUPTIONS_SEED if d["ground_truth_root_cause"] == "generation"]
        types = {d["corruption_type"] for d in generation}
        assert "generation_unstructured_prompt" in types
        assert "generation_contradictory_injection" in types
        assert "generation_token_truncation" in types

    def test_all_cases_have_required_fields(self):
        required = {
            "case_id",
            "question_id",
            "corruption_type",
            "ground_truth_root_cause",
            "severity",
            "description",
            "expected_quality_delta",
        }
        for d in CORRUPTIONS_SEED:
            missing = required - d.keys()
            assert not missing, f"{d['case_id']} missing: {missing}"


class TestCorruptionDatasetBuilder:
    def test_load_from_seed_returns_sixty_cases(self):
        builder = CorruptionDatasetBuilder()
        cases = builder.load_from_seed()
        assert len(cases) == 60

    def test_load_from_seed_returns_typed_models(self):
        builder = CorruptionDatasetBuilder()
        cases = builder.load_from_seed()
        assert all(isinstance(c, EvaluationCorruptionCase) for c in cases)

    def test_cases_property_returns_list(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        assert isinstance(builder.cases, list)
        assert len(builder.cases) == 60

    def test_get_by_id_returns_correct_case(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        case = builder.get_by_id("corr-retrieval-001")
        assert case is not None
        assert case.case_id == "corr-retrieval-001"

    def test_get_by_id_returns_none_for_missing(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        assert builder.get_by_id("corr-unknown-999") is None

    def test_get_by_root_cause_filters_retrieval(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        retrieval = builder.get_by_root_cause("retrieval")
        assert len(retrieval) == 20
        assert all(c.ground_truth_root_cause == RootCauseStage.RETRIEVAL for c in retrieval)

    def test_get_realistic_boundary_errors_returns_ten(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        realistic = builder.get_realistic_boundary_errors()
        assert len(realistic) == 10
        assert all(c.is_realistic_boundary_error for c in realistic)

    def test_get_by_question_returns_matching_cases(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        cases = builder.get_by_question("qa-001")
        assert len(cases) > 0
        assert all(c.question_id == "qa-001" for c in cases)

    def test_to_replay_case_converts_correctly(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        eval_case = builder.get_by_id("corr-retrieval-001")
        assert eval_case is not None
        replay_case = builder.to_replay_case(eval_case)
        assert isinstance(replay_case, CorruptionCase)
        assert replay_case.case_id == eval_case.case_id
        assert replay_case.corruption_type == eval_case.corruption_type
        assert replay_case.ground_truth_root_cause == eval_case.ground_truth_root_cause

    def test_to_replay_cases_converts_all_loaded_cases(self):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        replay_cases = builder.to_replay_cases()
        assert len(replay_cases) == 60
        assert all(isinstance(c, CorruptionCase) for c in replay_cases)

    def test_write_to_file_and_reload(self, tmp_path: Path):
        builder = CorruptionDatasetBuilder()
        builder.load_from_seed()
        dest = tmp_path / "corruptions.jsonl"
        builder.write_to_file(dest)
        assert dest.exists()
        lines = [ln for ln in dest.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 60

    def test_load_from_file_raises_when_missing(self):
        builder = CorruptionDatasetBuilder()
        with pytest.raises(FileNotFoundError):
            builder.load_from_file("/nonexistent/path.jsonl")
