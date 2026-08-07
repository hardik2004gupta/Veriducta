"""Tests for evaluation/export.py - DatasetExporter."""

import json
from pathlib import Path

from evaluation.export import DatasetExporter
from evaluation.schemas import EvaluationCorruptionCase, GoldenQAItem


def _golden_item(qid: str = "qa-001") -> GoldenQAItem:
    return GoldenQAItem.model_validate(
        {
            "question_id": qid,
            "question": "What is the minimum safe temperature for X?",
            "gold_answer": "The minimum safe temperature is 20 degrees per safety code.",
            "supporting_chunk_ids": ["osha-resp-prot-ch-0012"],
            "expected_entities": ["temperature", "safety code"],
            "expected_citations": ["osha-resp-prot-ch-0012"],
            "difficulty": "easy",
            "domain": "safety",
            "answer_type": "numerical_threshold",
        }
    )


def _corruption_case(cid: str = "corr-retrieval-001") -> EvaluationCorruptionCase:
    return EvaluationCorruptionCase.model_validate(
        {
            "case_id": cid,
            "question_id": "qa-001",
            "corruption_type": "retrieval_swap",
            "ground_truth_root_cause": "retrieval",
            "severity": "high",
            "description": "Swap correct chunk with wrong chunk.",
            "expected_quality_delta": -0.40,
        }
    )


class TestDatasetExporter:
    def test_write_golden_jsonl_creates_file(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_jsonl()
        assert path.exists()
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1

    def test_write_golden_jsonl_content_is_valid_json(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_jsonl()
        line = path.read_text(encoding="utf-8").strip()
        parsed = json.loads(line)
        assert parsed["question_id"] == "qa-001"

    def test_write_corruptions_jsonl_creates_file(self, tmp_path: Path):
        exporter = DatasetExporter(
            corruption_cases=[_corruption_case()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_corruptions_jsonl()
        assert path.exists()
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1

    def test_write_golden_csv_has_header(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_csv()
        content = path.read_text(encoding="utf-8")
        assert "question_id" in content.splitlines()[0]

    def test_write_golden_csv_has_data_row(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_csv()
        content = path.read_text(encoding="utf-8")
        assert "qa-001" in content

    def test_write_corruptions_csv_has_header(self, tmp_path: Path):
        exporter = DatasetExporter(
            corruption_cases=[_corruption_case()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_corruptions_csv()
        content = path.read_text(encoding="utf-8")
        assert "case_id" in content.splitlines()[0]

    def test_write_golden_markdown_contains_question(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_markdown()
        content = path.read_text(encoding="utf-8")
        assert "qa-001" in content
        assert "What is the minimum safe temperature" in content

    def test_write_corruptions_markdown_contains_case_id(self, tmp_path: Path):
        exporter = DatasetExporter(
            corruption_cases=[_corruption_case()],
            export_dir=str(tmp_path),
        )
        path = exporter.write_corruptions_markdown()
        content = path.read_text(encoding="utf-8")
        assert "corr-retrieval-001" in content

    def test_write_stats_json_creates_file(self, tmp_path: Path):
        exporter = DatasetExporter(export_dir=str(tmp_path))
        stats = {"total": 40, "difficulty": {"easy": 10}}
        path = exporter.write_stats_json(stats)
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["total"] == 40

    def test_write_golden_jsonl_accepts_path_override(self, tmp_path: Path):
        exporter = DatasetExporter(
            golden_items=[_golden_item()],
            export_dir=str(tmp_path),
        )
        custom = tmp_path / "custom" / "output.jsonl"
        path = exporter.write_golden_jsonl(path=str(custom))
        assert path == custom
        assert path.exists()

    def test_write_multiple_items(self, tmp_path: Path):
        items = [_golden_item(f"qa-{i:03d}") for i in range(1, 6)]
        exporter = DatasetExporter(
            golden_items=items,
            export_dir=str(tmp_path),
        )
        path = exporter.write_golden_jsonl()
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 5
