"""Tests for evaluation/annotation.py - AnnotationLoader, AnnotationValidator,
AnnotationStatistics, and AnnotationExporter."""

import json
from pathlib import Path

import pytest

from evaluation.annotation import (
    ANNOTATION_SCHEMA,
    AnnotationExporter,
    AnnotationLoader,
    AnnotationStatistics,
    AnnotationValidator,
)
from evaluation.schemas import GoldenQAItem, ValidationIssueSeverity


def _golden_item(**overrides) -> GoldenQAItem:
    base = {
        "question_id": "qa-001",
        "question": "What is the OSHA PEL for hydrogen sulfide?",
        "gold_answer": "The OSHA PEL for hydrogen sulfide is 20 ppm ceiling concentration.",
        "supporting_chunk_ids": ["osha-resp-prot-ch-0012"],
        "expected_entities": ["H2S", "ppm", "ceiling"],
        "expected_citations": ["osha-resp-prot-ch-0012"],
        "difficulty": "easy",
        "domain": "safety",
        "answer_type": "numerical_threshold",
    }
    base.update(overrides)
    return GoldenQAItem.model_validate(base)


class TestAnnotationSchema:
    def test_annotation_schema_is_dict(self):
        assert isinstance(ANNOTATION_SCHEMA, dict)

    def test_annotation_schema_has_required_fields_key(self):
        assert "required" in ANNOTATION_SCHEMA

    def test_annotation_schema_includes_question_id_pattern(self):
        props = ANNOTATION_SCHEMA["properties"]
        assert "pattern" in props["question_id"]

    def test_annotation_schema_has_correct_schema_version(self):
        assert ANNOTATION_SCHEMA["$schema"] == "http://json-schema.org/draft-07/schema#"


class TestAnnotationLoader:
    def test_load_without_path_returns_embedded_schema(self):
        loader = AnnotationLoader()
        schema = loader.load()
        assert isinstance(schema, dict)
        assert schema["title"] == "GoldenQAAnnotationSchema"

    def test_load_returns_copy_not_original(self):
        loader = AnnotationLoader()
        schema1 = loader.load()
        schema2 = loader.load()
        schema1["modified"] = True
        assert "modified" not in schema2

    def test_load_from_file_returns_parsed_schema(self, tmp_path: Path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps({"type": "object", "title": "Test"}), encoding="utf-8")
        loader = AnnotationLoader(schema_path=str(schema_file))
        schema = loader.load()
        assert schema["title"] == "Test"

    def test_load_from_missing_file_raises_error(self, tmp_path: Path):
        loader = AnnotationLoader(schema_path=str(tmp_path / "missing.json"))
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_write_creates_file_with_annotation_schema(self, tmp_path: Path):
        loader = AnnotationLoader()
        dest = tmp_path / "annotation_schema.json"
        loader.write(dest)
        assert dest.exists()
        written = json.loads(dest.read_text(encoding="utf-8"))
        assert written["title"] == "GoldenQAAnnotationSchema"


class TestAnnotationValidator:
    def test_valid_items_produce_no_errors(self):
        validator = AnnotationValidator()
        result = validator.validate([_golden_item()])
        assert result.errors_count == 0

    def test_draft_items_produce_warning(self):
        validator = AnnotationValidator()
        result = validator.validate([_golden_item(review_status="draft")])
        warnings = [i for i in result.issues if i.issue_type == "draft_item"]
        assert len(warnings) == 1
        assert warnings[0].severity == ValidationIssueSeverity.WARNING

    def test_approved_items_produce_no_draft_warning(self):
        validator = AnnotationValidator()
        result = validator.validate([_golden_item(review_status="approved")])
        warnings = [i for i in result.issues if i.issue_type == "draft_item"]
        assert len(warnings) == 0

    def test_hallucination_mode_with_low_risk_produces_warning(self):
        validator = AnnotationValidator()
        item = _golden_item(failure_mode="hallucination", hallucination_risk="low")
        result = validator.validate([item])
        warnings = [i for i in result.issues if i.issue_type == "hallucination_risk_inconsistency"]
        assert len(warnings) == 1

    def test_hallucination_mode_with_high_risk_passes(self):
        validator = AnnotationValidator()
        item = _golden_item(failure_mode="hallucination", hallucination_risk="high")
        result = validator.validate([item])
        warnings = [i for i in result.issues if i.issue_type == "hallucination_risk_inconsistency"]
        assert len(warnings) == 0

    def test_temporal_confusion_without_constraint_produces_warning(self):
        validator = AnnotationValidator()
        item = _golden_item(failure_mode="temporal_confusion", temporal_constraints="none")
        result = validator.validate([item])
        warnings = [i for i in result.issues if i.issue_type == "temporal_constraint_missing"]
        assert len(warnings) == 1

    def test_temporal_confusion_with_constraint_passes(self):
        validator = AnnotationValidator()
        item = _golden_item(
            failure_mode="temporal_confusion", temporal_constraints="version_dependent"
        )
        result = validator.validate([item])
        warnings = [i for i in result.issues if i.issue_type == "temporal_constraint_missing"]
        assert len(warnings) == 0

    def test_empty_expected_failure_modes_produces_warning(self):
        validator = AnnotationValidator()
        item = _golden_item(expected_failure_modes=[])
        result = validator.validate([item])
        warnings = [i for i in result.issues if i.issue_type == "empty_expected_failure_modes"]
        assert len(warnings) == 1


class TestAnnotationStatistics:
    def test_empty_items_returns_total_zero(self):
        stats = AnnotationStatistics()
        result = stats.compute([])
        assert result["total"] == 0

    def test_total_matches_item_count(self):
        stats = AnnotationStatistics()
        items = [_golden_item(question_id=f"qa-{i:03d}") for i in range(1, 4)]
        result = stats.compute(items)
        assert result["total"] == 3

    def test_difficulty_distribution_is_computed(self):
        stats = AnnotationStatistics()
        items = [_golden_item(question_id=f"qa-{i:03d}") for i in range(1, 4)]
        result = stats.compute(items)
        assert "difficulty" in result
        assert isinstance(result["difficulty"], dict)

    def test_avg_supporting_chunks_is_correct(self):
        stats = AnnotationStatistics()
        item1 = _golden_item(question_id="qa-001", supporting_chunk_ids=["a-ch-0001", "a-ch-0002"])
        item2 = _golden_item(question_id="qa-002", supporting_chunk_ids=["b-ch-0001"])
        result = stats.compute([item1, item2])
        assert result["avg_supporting_chunks"] == 1.5

    def test_verification_required_count_is_correct(self):
        stats = AnnotationStatistics()
        item1 = _golden_item(question_id="qa-001", verification_required=True)
        item2 = _golden_item(question_id="qa-002", verification_required=False)
        result = stats.compute([item1, item2])
        assert result["verification_required_count"] == 1


class TestAnnotationExporter:
    def test_to_markdown_table_includes_header(self):
        exporter = AnnotationExporter()
        items = [_golden_item()]
        md = exporter.to_markdown_table(items)
        assert "| ID |" in md
        assert "qa-001" in md

    def test_to_review_markdown_includes_question(self):
        exporter = AnnotationExporter()
        items = [_golden_item()]
        md = exporter.to_review_markdown(items)
        assert "What is the OSHA PEL" in md
        assert "qa-001" in md

    def test_to_csv_includes_header_row(self):
        exporter = AnnotationExporter()
        items = [_golden_item()]
        csv = exporter.to_csv(items)
        first_line = csv.splitlines()[0]
        assert "question_id" in first_line

    def test_to_csv_includes_item_data(self):
        exporter = AnnotationExporter()
        items = [_golden_item()]
        csv = exporter.to_csv(items)
        assert "qa-001" in csv
        assert "easy" in csv
        assert "safety" in csv
