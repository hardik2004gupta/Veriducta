"""Tests for evaluation/schemas.py - enumerations, models, and field rules."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from evaluation.schemas import (
    FAILURE_MODE_TO_ROOT_CAUSE,
    AnswerType,
    CitationRequirement,
    CorruptionSeverity,
    Difficulty,
    EvaluationCorruptionCase,
    GoldenQAItem,
    HallucinationRisk,
    ReviewStatus,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationResult,
)
from schemas.models import FailureMode, RootCauseStage, TemporalValidityTag


class TestEnumerations:
    def test_difficulty_values_are_lowercase_strings(self):
        assert Difficulty.EASY == "easy"
        assert Difficulty.MEDIUM == "medium"
        assert Difficulty.HARD == "hard"

    def test_answer_type_values_are_lowercase_strings(self):
        assert AnswerType.FACTUAL == "factual"
        assert AnswerType.NUMERICAL_THRESHOLD == "numerical_threshold"
        assert AnswerType.PROCEDURAL == "procedural"
        assert AnswerType.COMPARATIVE == "comparative"
        assert AnswerType.TEMPORAL == "temporal"

    def test_hallucination_risk_values(self):
        assert HallucinationRisk.LOW == "low"
        assert HallucinationRisk.HIGH == "high"

    def test_corruption_severity_has_four_levels(self):
        assert len(CorruptionSeverity) == 4
        assert CorruptionSeverity.CRITICAL == "critical"

    def test_validation_issue_severity_has_two_levels(self):
        assert ValidationIssueSeverity.ERROR == "error"
        assert ValidationIssueSeverity.WARNING == "warning"


class TestFailureModeToRootCause:
    def test_chunking_boundary_maps_to_chunking(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.CHUNKING_BOUNDARY] == RootCauseStage.CHUNKING

    def test_retrieval_miss_maps_to_retrieval(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.RETRIEVAL_MISS] == RootCauseStage.RETRIEVAL

    def test_omission_maps_to_retrieval(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.OMISSION] == RootCauseStage.RETRIEVAL

    def test_temporal_confusion_maps_to_retrieval(self):
        assert (
            FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.TEMPORAL_CONFUSION] == RootCauseStage.RETRIEVAL
        )

    def test_hallucination_maps_to_generation(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.HALLUCINATION] == RootCauseStage.GENERATION

    def test_contradiction_maps_to_generation(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.CONTRADICTION] == RootCauseStage.GENERATION

    def test_none_maps_to_unknown(self):
        assert FAILURE_MODE_TO_ROOT_CAUSE[FailureMode.NONE] == RootCauseStage.UNKNOWN

    def test_all_failure_modes_are_covered(self):
        for mode in FailureMode:
            assert mode in FAILURE_MODE_TO_ROOT_CAUSE


class TestGoldenQAItem:
    def _valid_item(self, **overrides) -> dict:
        base = {
            "question_id": "qa-001",
            "question": "What is the minimum safe temperature?",
            "gold_answer": (
                "The minimum safe temperature is 20 degrees Celsius per standard safety protocol."
            ),
            "supporting_chunk_ids": ["osha-resp-prot-ch-0012"],
            "expected_entities": ["temperature", "safety protocol"],
            "expected_citations": ["osha-resp-prot-ch-0012"],
            "difficulty": "easy",
            "domain": "safety",
            "answer_type": "numerical_threshold",
        }
        base.update(overrides)
        return base

    def test_valid_item_parses_correctly(self):
        item = GoldenQAItem.model_validate(self._valid_item())
        assert item.question_id == "qa-001"
        assert item.difficulty == Difficulty.EASY
        assert item.citation_requirement == CitationRequirement.REQUIRED

    def test_question_id_pattern_enforced(self):
        with pytest.raises(PydanticValidationError):
            GoldenQAItem.model_validate(self._valid_item(question_id="question-1"))

    def test_question_id_pattern_requires_three_digits(self):
        with pytest.raises(PydanticValidationError):
            GoldenQAItem.model_validate(self._valid_item(question_id="qa-1"))

    def test_expected_root_cause_property_returns_correct_stage(self):
        item = GoldenQAItem.model_validate(self._valid_item(failure_mode="chunking_boundary"))
        assert item.expected_root_cause == RootCauseStage.CHUNKING

    def test_expected_root_cause_for_none_failure_mode(self):
        item = GoldenQAItem.model_validate(self._valid_item())
        assert item.expected_root_cause == RootCauseStage.UNKNOWN

    def test_defaults_are_populated(self):
        item = GoldenQAItem.model_validate(self._valid_item())
        assert item.counterevidence_chunk_ids == []
        assert item.verification_required is False
        assert item.failure_mode == FailureMode.NONE
        assert item.review_status == ReviewStatus.APPROVED

    def test_temporal_validity_default_is_valid(self):
        item = GoldenQAItem.model_validate(self._valid_item())
        assert item.temporal_validity == TemporalValidityTag.VALID

    def test_model_dump_json_roundtrip(self):
        item = GoldenQAItem.model_validate(self._valid_item())
        serialised = item.model_dump_json()
        restored = GoldenQAItem.model_validate_json(serialised)
        assert restored.question_id == item.question_id


class TestEvaluationCorruptionCase:
    def _valid_case(self, **overrides) -> dict:
        base = {
            "case_id": "corr-retrieval-001",
            "question_id": "qa-001",
            "corruption_type": "retrieval_swap",
            "ground_truth_root_cause": "retrieval",
            "severity": "high",
            "description": "Replace correct chunk with wrong chunk.",
            "expected_quality_delta": -0.40,
        }
        base.update(overrides)
        return base

    def test_valid_case_parses_correctly(self):
        case = EvaluationCorruptionCase.model_validate(self._valid_case())
        assert case.case_id == "corr-retrieval-001"
        assert case.ground_truth_root_cause == RootCauseStage.RETRIEVAL

    def test_case_id_pattern_enforced(self):
        with pytest.raises(PydanticValidationError):
            EvaluationCorruptionCase.model_validate(self._valid_case(case_id="case-001"))

    def test_question_id_pattern_enforced(self):
        with pytest.raises(PydanticValidationError):
            EvaluationCorruptionCase.model_validate(self._valid_case(question_id="q-1"))

    def test_defaults_are_populated(self):
        case = EvaluationCorruptionCase.model_validate(self._valid_case())
        assert case.is_realistic_boundary_error is False
        assert case.pipeline_trace_id == ""
        assert case.corruption_parameters == {}
        assert case.notes == ""

    def test_model_dump_json_roundtrip(self):
        case = EvaluationCorruptionCase.model_validate(self._valid_case())
        restored = EvaluationCorruptionCase.model_validate_json(case.model_dump_json())
        assert restored.case_id == case.case_id


class TestValidationResult:
    def test_is_valid_true_when_no_errors(self):
        result = ValidationResult(is_valid=True, errors_count=0, warnings_count=2)
        assert result.is_valid is True

    def test_issues_default_to_empty_list(self):
        result = ValidationResult(is_valid=True)
        assert result.issues == []

    def test_validation_issue_has_required_fields(self):
        issue = ValidationIssue(
            severity=ValidationIssueSeverity.ERROR,
            issue_type="duplicate_id",
            item_id="qa-001",
            message="duplicate ID",
        )
        assert issue.severity == ValidationIssueSeverity.ERROR
