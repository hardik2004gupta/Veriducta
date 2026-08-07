"""Tests for evaluation/golden.py — GOLDEN_QA_SEED and GoldenDatasetBuilder."""

from pathlib import Path

import pytest

from evaluation.golden import GOLDEN_QA_SEED, GoldenDatasetBuilder
from evaluation.schemas import Difficulty, GoldenQAItem
from schemas.models import FailureMode


class TestGoldenQASeed:
    def test_seed_has_forty_items(self):
        assert len(GOLDEN_QA_SEED) == 40

    def test_all_question_ids_are_unique(self):
        ids = [d["question_id"] for d in GOLDEN_QA_SEED]
        assert len(ids) == len(set(ids))

    def test_question_ids_follow_pattern(self):
        import re

        pattern = re.compile(r"^qa-\d{3}$")
        for d in GOLDEN_QA_SEED:
            assert pattern.match(d["question_id"]), d["question_id"]

    def test_question_ids_are_sequential(self):
        ids = sorted([d["question_id"] for d in GOLDEN_QA_SEED])
        for i, qid in enumerate(ids, start=1):
            assert qid == f"qa-{i:03d}", f"Expected qa-{i:03d}, got {qid}"

    def test_difficulty_distribution_is_correct(self):
        difficulties = [d["difficulty"] for d in GOLDEN_QA_SEED]
        assert difficulties.count("easy") == 10
        assert difficulties.count("medium") == 20
        assert difficulties.count("hard") == 10

    def test_all_items_have_required_fields(self):
        required = {
            "question_id",
            "question",
            "gold_answer",
            "supporting_chunk_ids",
            "expected_entities",
            "expected_citations",
            "difficulty",
            "domain",
            "answer_type",
        }
        for d in GOLDEN_QA_SEED:
            missing = required - d.keys()
            assert not missing, f"{d['question_id']} missing: {missing}"

    def test_all_items_are_pydantic_valid(self):
        for d in GOLDEN_QA_SEED:
            item = GoldenQAItem.model_validate(d)
            assert item.question_id.startswith("qa-")

    def test_failure_modes_include_all_expected_types(self):
        modes = {d["failure_mode"] for d in GOLDEN_QA_SEED}
        assert "none" in modes
        assert "chunking_boundary" in modes
        assert "retrieval_miss" in modes
        assert "omission" in modes
        assert "temporal_confusion" in modes
        assert "hallucination" in modes
        assert "contradiction" in modes

    def test_domains_include_all_four_domains(self):
        domains = {d["domain"] for d in GOLDEN_QA_SEED}
        assert domains == {"safety", "geology", "engineering", "regulatory"}

    def test_hallucination_cases_have_empty_supporting_chunks(self):
        hallucination_items = [d for d in GOLDEN_QA_SEED if d["failure_mode"] == "hallucination"]
        for d in hallucination_items:
            assert d["expected_entities"], f"{d['question_id']} has no expected_entities"


class TestGoldenDatasetBuilder:
    def test_load_from_seed_returns_forty_items(self):
        builder = GoldenDatasetBuilder()
        items = builder.load_from_seed()
        assert len(items) == 40

    def test_load_from_seed_returns_golden_qa_items(self):
        builder = GoldenDatasetBuilder()
        items = builder.load_from_seed()
        assert all(isinstance(i, GoldenQAItem) for i in items)

    def test_items_property_returns_list(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        assert isinstance(builder.items, list)
        assert len(builder.items) == 40

    def test_get_by_id_returns_correct_item(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        item = builder.get_by_id("qa-001")
        assert item is not None
        assert item.question_id == "qa-001"

    def test_get_by_id_returns_none_for_missing_id(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        assert builder.get_by_id("qa-999") is None

    def test_get_by_failure_mode_filters_correctly(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        chunking_items = builder.get_by_failure_mode("chunking_boundary")
        assert len(chunking_items) > 0
        assert all(i.failure_mode == FailureMode.CHUNKING_BOUNDARY for i in chunking_items)

    def test_get_by_difficulty_filters_correctly(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        easy_items = builder.get_by_difficulty("easy")
        assert len(easy_items) == 10
        assert all(i.difficulty == Difficulty.EASY for i in easy_items)

    def test_get_by_domain_filters_correctly(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        safety_items = builder.get_by_domain("safety")
        assert len(safety_items) == 12
        assert all(i.domain == "safety" for i in safety_items)

    def test_get_hallucination_cases_returns_items_with_hallucination_mode(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        hallucination_items = builder.get_hallucination_cases()
        assert len(hallucination_items) > 0
        assert all(i.failure_mode == FailureMode.HALLUCINATION for i in hallucination_items)

    def test_get_temporal_cases_returns_temporal_confusion_items(self):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        temporal_items = builder.get_temporal_cases()
        assert len(temporal_items) > 0
        assert all(i.failure_mode == FailureMode.TEMPORAL_CONFUSION for i in temporal_items)

    def test_write_to_file_and_reload(self, tmp_path: Path):
        builder = GoldenDatasetBuilder()
        builder.load_from_seed()
        dest = tmp_path / "golden_qa.jsonl"
        builder.write_to_file(dest)

        assert dest.exists()
        lines = [ln for ln in dest.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 40

    def test_load_from_file_produces_same_items_as_seed(self, tmp_path: Path):
        builder = GoldenDatasetBuilder()
        seed_items = builder.load_from_seed()
        dest = tmp_path / "golden_qa.jsonl"
        builder.write_to_file(dest)

        file_items = builder.load_from_file(dest)
        assert len(file_items) == len(seed_items)
        assert file_items[0].question_id == seed_items[0].question_id

    def test_load_from_file_raises_when_file_missing(self):
        builder = GoldenDatasetBuilder()
        with pytest.raises(FileNotFoundError):
            builder.load_from_file("/nonexistent/path.jsonl")
