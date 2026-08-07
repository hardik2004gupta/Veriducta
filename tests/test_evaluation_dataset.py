"""Tests for evaluation/dataset.py — DatasetManager."""

import json
from pathlib import Path

from evaluation.dataset import DatasetManager
from evaluation.schemas import (
    DatasetStats,
    EvaluationCorruptionCase,
    GoldenQAItem,
    ValidationResult,
)
from replay.models import CorruptionCase


class TestDatasetManagerFromSeed:
    def test_load_from_seed_populates_golden_items(self):
        manager = DatasetManager()
        manager.load_from_seed()
        assert len(manager.golden_items) == 40

    def test_load_from_seed_populates_corruption_cases(self):
        manager = DatasetManager()
        manager.load_from_seed()
        assert len(manager.corruption_cases) == 60

    def test_golden_items_are_typed(self):
        manager = DatasetManager()
        manager.load_from_seed()
        assert all(isinstance(i, GoldenQAItem) for i in manager.golden_items)

    def test_corruption_cases_are_typed(self):
        manager = DatasetManager()
        manager.load_from_seed()
        assert all(isinstance(c, EvaluationCorruptionCase) for c in manager.corruption_cases)


class TestDatasetManagerValidation:
    def test_validate_passes_on_seed_data(self):
        manager = DatasetManager()
        manager.load_from_seed()
        results = manager.validate()
        assert "golden_qa" in results
        assert "corruptions" in results
        assert "cross_reference" in results
        assert "annotations" in results

    def test_validate_returns_validation_results(self):
        manager = DatasetManager()
        manager.load_from_seed()
        results = manager.validate()
        assert all(isinstance(v, ValidationResult) for v in results.values())

    def test_validate_golden_qa_passes(self):
        manager = DatasetManager()
        manager.load_from_seed()
        results = manager.validate()
        assert results["golden_qa"].is_valid is True

    def test_validate_corruptions_passes(self):
        manager = DatasetManager()
        manager.load_from_seed()
        results = manager.validate()
        assert results["corruptions"].is_valid is True

    def test_validate_cross_reference_passes(self):
        manager = DatasetManager()
        manager.load_from_seed()
        results = manager.validate()
        assert results["cross_reference"].is_valid is True


class TestDatasetManagerStats:
    def test_compute_stats_returns_dataset_stats(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert isinstance(stats, DatasetStats)

    def test_stats_total_questions_is_forty(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert stats.total_questions == 40

    def test_stats_total_corruptions_is_sixty(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert stats.total_corruptions == 60

    def test_stats_difficulty_distribution_sums_to_forty(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert sum(stats.difficulty_distribution.values()) == 40

    def test_stats_domain_distribution_has_four_domains(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert len(stats.domain_distribution) == 4

    def test_stats_realistic_boundary_error_count_is_ten(self):
        manager = DatasetManager()
        manager.load_from_seed()
        stats = manager.compute_stats()
        assert stats.realistic_boundary_error_count == 10

    def test_compute_annotation_statistics_returns_dict(self):
        manager = DatasetManager()
        manager.load_from_seed()
        ann_stats = manager.compute_annotation_statistics()
        assert isinstance(ann_stats, dict)
        assert ann_stats["total"] == 40


class TestDatasetManagerBuildAndWrite:
    def test_build_and_write_creates_golden_jsonl(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.build_and_write()
        golden_path = tmp_path / "golden" / "golden_qa.jsonl"
        assert golden_path.exists()
        lines = [ln for ln in golden_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 40

    def test_build_and_write_creates_corruptions_jsonl(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.build_and_write()
        corruptions_path = tmp_path / "synthetic" / "corruptions.jsonl"
        assert corruptions_path.exists()
        lines = [
            ln for ln in corruptions_path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]
        assert len(lines) == 60

    def test_build_and_write_creates_annotation_schema(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.build_and_write()
        schema_path = tmp_path / "annotations" / "annotation_schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["title"] == "GoldenQAAnnotationSchema"

    def test_build_and_write_is_idempotent(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.build_and_write()
        manager.build_and_write()
        golden_path = tmp_path / "golden" / "golden_qa.jsonl"
        lines = [ln for ln in golden_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 40


class TestDatasetManagerLoadFromFiles:
    def test_load_from_files_after_build(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.build_and_write()
        manager.load_from_files()
        assert len(manager.golden_items) == 40
        assert len(manager.corruption_cases) == 60


class TestDatasetManagerExport:
    def test_export_jsonl_writes_files(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.load_from_seed()
        written = manager.export(formats=["jsonl"], export_dir=str(tmp_path / "exports"))
        assert "golden_jsonl" in written
        assert "corruptions_jsonl" in written
        assert written["golden_jsonl"].exists()

    def test_export_all_formats(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.load_from_seed()
        written = manager.export(
            formats=["jsonl", "csv", "markdown"],
            export_dir=str(tmp_path / "exports"),
        )
        assert len(written) == 6

    def test_export_returns_existing_paths(self, tmp_path: Path):
        manager = DatasetManager(dataset_dir=str(tmp_path))
        manager.load_from_seed()
        written = manager.export(formats=["csv"], export_dir=str(tmp_path / "exports"))
        for path in written.values():
            assert path.exists()


class TestDatasetManagerReplayIntegration:
    def test_to_replay_cases_returns_sixty_cases(self):
        manager = DatasetManager()
        manager.load_from_seed()
        cases = manager.to_replay_cases()
        assert len(cases) == 60

    def test_to_replay_cases_returns_typed_models(self):
        manager = DatasetManager()
        manager.load_from_seed()
        cases = manager.to_replay_cases()
        assert all(isinstance(c, CorruptionCase) for c in cases)

    def test_manifest_has_correct_counts(self):
        manager = DatasetManager()
        manager.load_from_seed()
        manifest = manager.get_manifest()
        assert manifest.golden_qa_count == 40
        assert manifest.corruptions_count == 60
