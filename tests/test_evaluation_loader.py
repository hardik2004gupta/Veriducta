"""Tests for evaluation/loader.py - DatasetLoader."""

import json
from pathlib import Path

import pytest

from core.exceptions import NotFoundError, ValidationError
from evaluation.loader import DatasetLoader
from evaluation.schemas import EvaluationCorruptionCase, GoldenQAItem


def _make_golden_item() -> dict:
    return {
        "question_id": "qa-001",
        "question": "What is the ceiling concentration for H2S?",
        "gold_answer": "The OSHA ceiling concentration for H2S is 20 ppm.",
        "supporting_chunk_ids": ["osha-resp-prot-ch-0012"],
        "expected_entities": ["H2S", "ppm"],
        "expected_citations": ["osha-resp-prot-ch-0012"],
        "difficulty": "easy",
        "domain": "safety",
        "answer_type": "numerical_threshold",
    }


def _make_corruption_case() -> dict:
    return {
        "case_id": "corr-retrieval-001",
        "question_id": "qa-001",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "severity": "high",
        "description": "Swap correct chunk with wrong chunk.",
        "expected_quality_delta": -0.40,
    }


class TestDatasetLoader:
    def test_load_golden_qa_from_jsonl(self, tmp_path: Path):
        jsonl_file = tmp_path / "golden_qa.jsonl"
        jsonl_file.write_text(json.dumps(_make_golden_item()) + "\n", encoding="utf-8")

        loader = DatasetLoader(dataset_dir=str(tmp_path))
        items = loader.load_golden_qa(path=str(jsonl_file))

        assert len(items) == 1
        assert isinstance(items[0], GoldenQAItem)
        assert items[0].question_id == "qa-001"

    def test_load_corruptions_from_jsonl(self, tmp_path: Path):
        jsonl_file = tmp_path / "corruptions.jsonl"
        jsonl_file.write_text(json.dumps(_make_corruption_case()) + "\n", encoding="utf-8")

        loader = DatasetLoader(dataset_dir=str(tmp_path))
        cases = loader.load_corruptions(path=str(jsonl_file))

        assert len(cases) == 1
        assert isinstance(cases[0], EvaluationCorruptionCase)
        assert cases[0].case_id == "corr-retrieval-001"

    def test_load_golden_qa_raises_not_found_error_when_file_missing(self, tmp_path: Path):
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        with pytest.raises(NotFoundError):
            loader.load_golden_qa(path=str(tmp_path / "missing.jsonl"))

    def test_load_corruptions_raises_not_found_error_when_file_missing(self, tmp_path: Path):
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        with pytest.raises(NotFoundError):
            loader.load_corruptions(path=str(tmp_path / "missing.jsonl"))

    def test_load_golden_qa_raises_validation_error_on_invalid_json(self, tmp_path: Path):
        bad_file = tmp_path / "bad.jsonl"
        bad_file.write_text('{"invalid": "record"}\n', encoding="utf-8")
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        with pytest.raises(ValidationError):
            loader.load_golden_qa(path=str(bad_file))

    def test_load_golden_qa_skips_blank_lines(self, tmp_path: Path):
        jsonl_file = tmp_path / "golden_qa.jsonl"
        jsonl_file.write_text(
            "\n" + json.dumps(_make_golden_item()) + "\n\n",
            encoding="utf-8",
        )
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        items = loader.load_golden_qa(path=str(jsonl_file))
        assert len(items) == 1

    def test_load_golden_qa_loads_multiple_records(self, tmp_path: Path):
        jsonl_file = tmp_path / "golden_qa.jsonl"
        item1 = _make_golden_item()
        item2 = {**_make_golden_item(), "question_id": "qa-002"}
        lines = json.dumps(item1) + "\n" + json.dumps(item2) + "\n"
        jsonl_file.write_text(lines, encoding="utf-8")

        loader = DatasetLoader(dataset_dir=str(tmp_path))
        items = loader.load_golden_qa(path=str(jsonl_file))
        assert len(items) == 2
        assert items[1].question_id == "qa-002"

    def test_load_annotation_schema_raises_not_found_when_missing(self, tmp_path: Path):
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        with pytest.raises(NotFoundError):
            loader.load_annotation_schema(path=str(tmp_path / "schema.json"))

    def test_load_annotation_schema_returns_dict(self, tmp_path: Path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"$schema": "test", "type": "object"}', encoding="utf-8")
        loader = DatasetLoader(dataset_dir=str(tmp_path))
        schema = loader.load_annotation_schema(path=str(schema_file))
        assert isinstance(schema, dict)
        assert schema["type"] == "object"

    def test_default_paths_use_dataset_dir(self, tmp_path: Path):
        golden_dir = tmp_path / "golden"
        golden_dir.mkdir()
        golden_file = golden_dir / "golden_qa.jsonl"
        golden_file.write_text(json.dumps(_make_golden_item()) + "\n", encoding="utf-8")

        loader = DatasetLoader(dataset_dir=str(tmp_path))
        items = loader.load_golden_qa()
        assert len(items) == 1
