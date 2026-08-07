"""Tests for evaluation/validation.py — DatasetValidator."""

from evaluation.schemas import (
    EvaluationCorruptionCase,
    GoldenQAItem,
    ValidationIssueSeverity,
)
from evaluation.validation import DatasetValidator


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


def _corruption_case(**overrides) -> EvaluationCorruptionCase:
    base = {
        "case_id": "corr-retrieval-001",
        "question_id": "qa-001",
        "corruption_type": "retrieval_swap",
        "ground_truth_root_cause": "retrieval",
        "severity": "high",
        "description": "Swap correct chunk with wrong chunk.",
        "expected_quality_delta": -0.40,
    }
    base.update(overrides)
    return EvaluationCorruptionCase.model_validate(base)


class TestValidateGoldenQA:
    def test_valid_items_pass_with_no_errors(self):
        validator = DatasetValidator()
        result = validator.validate_golden_qa([_golden_item()])
        assert result.is_valid is True
        assert result.errors_count == 0

    def test_duplicate_ids_produce_error(self):
        validator = DatasetValidator()
        items = [_golden_item(), _golden_item()]
        result = validator.validate_golden_qa(items)
        errors = [i for i in result.issues if i.issue_type == "duplicate_id"]
        assert len(errors) == 1
        assert errors[0].severity == ValidationIssueSeverity.ERROR

    def test_duplicate_questions_produce_warning(self):
        validator = DatasetValidator()
        items = [
            _golden_item(question_id="qa-001"),
            _golden_item(
                question_id="qa-002",
                question="What is the OSHA PEL for hydrogen sulfide?",
            ),
        ]
        result = validator.validate_golden_qa(items)
        warnings = [i for i in result.issues if i.issue_type == "duplicate_question"]
        assert len(warnings) == 1
        assert warnings[0].severity == ValidationIssueSeverity.WARNING

    def test_missing_citations_produce_error_when_required(self):
        validator = DatasetValidator()
        item = _golden_item(supporting_chunk_ids=[], citation_requirement="required")
        result = validator.validate_golden_qa([item])
        errors = [i for i in result.issues if i.issue_type == "missing_citations"]
        assert len(errors) == 1

    def test_missing_citations_ok_when_citation_not_required(self):
        validator = DatasetValidator()
        item = _golden_item(supporting_chunk_ids=[], citation_requirement="none")
        result = validator.validate_golden_qa([item])
        errors = [i for i in result.issues if i.issue_type == "missing_citations"]
        assert len(errors) == 0

    def test_invalid_chunk_id_format_produces_warning(self):
        validator = DatasetValidator()
        item = _golden_item(supporting_chunk_ids=["bad-chunk-id"])
        result = validator.validate_golden_qa([item])
        warnings = [i for i in result.issues if i.issue_type == "invalid_chunk_id_format"]
        assert len(warnings) == 1
        assert warnings[0].severity == ValidationIssueSeverity.WARNING

    def test_valid_chunk_id_format_passes(self):
        validator = DatasetValidator()
        item = _golden_item(supporting_chunk_ids=["osha-resp-prot-ch-0012"])
        result = validator.validate_golden_qa([item])
        format_issues = [i for i in result.issues if i.issue_type == "invalid_chunk_id_format"]
        assert len(format_issues) == 0

    def test_insufficient_entities_produces_warning(self):
        validator = DatasetValidator()
        item = _golden_item(expected_entities=["single-entity"])
        result = validator.validate_golden_qa([item])
        warnings = [i for i in result.issues if i.issue_type == "insufficient_entities"]
        assert len(warnings) == 1

    def test_two_entities_passes_entity_check(self):
        validator = DatasetValidator()
        item = _golden_item(expected_entities=["entity-one", "entity-two"])
        result = validator.validate_golden_qa([item])
        entity_issues = [i for i in result.issues if i.issue_type == "insufficient_entities"]
        assert len(entity_issues) == 0


class TestValidateCorruptions:
    def _make_distribution(self) -> list[EvaluationCorruptionCase]:
        cases = []
        for i in range(20):
            cases.append(
                _corruption_case(
                    case_id=f"corr-retrieval-{i+1:03d}",
                    ground_truth_root_cause="retrieval",
                )
            )
        for i in range(15):
            cases.append(
                _corruption_case(
                    case_id=f"corr-chunking-{i+1:03d}",
                    ground_truth_root_cause="chunking",
                    corruption_type="chunking_boundary_naive",
                )
            )
        for i in range(15):
            cases.append(
                _corruption_case(
                    case_id=f"corr-reranker-{i+1:03d}",
                    ground_truth_root_cause="reranking",
                    corruption_type="reranker_score_inversion",
                )
            )
        for i in range(10):
            cases.append(
                _corruption_case(
                    case_id=f"corr-generation-{i+1:03d}",
                    ground_truth_root_cause="generation",
                    corruption_type="generation_unstructured_prompt",
                )
            )
        return cases

    def test_correct_distribution_passes(self):
        validator = DatasetValidator()
        result = validator.validate_corruptions(self._make_distribution())
        dist_issues = [
            i for i in result.issues if i.issue_type == "unexpected_corruption_distribution"
        ]
        assert len(dist_issues) == 0

    def test_wrong_distribution_produces_warnings(self):
        validator = DatasetValidator()
        cases = [_corruption_case(ground_truth_root_cause="retrieval") for _ in range(5)]
        result = validator.validate_corruptions(cases)
        dist_issues = [
            i for i in result.issues if i.issue_type == "unexpected_corruption_distribution"
        ]
        assert len(dist_issues) > 0

    def test_positive_quality_delta_produces_warning(self):
        validator = DatasetValidator()
        case = _corruption_case(expected_quality_delta=0.10)
        result = validator.validate_corruptions([case])
        warnings = [i for i in result.issues if i.issue_type == "positive_expected_quality_delta"]
        assert len(warnings) == 1

    def test_negative_quality_delta_passes(self):
        validator = DatasetValidator()
        case = _corruption_case(expected_quality_delta=-0.30)
        result = validator.validate_corruptions([case])
        warnings = [i for i in result.issues if i.issue_type == "positive_expected_quality_delta"]
        assert len(warnings) == 0

    def test_duplicate_case_ids_produce_error(self):
        validator = DatasetValidator()
        cases = [_corruption_case(), _corruption_case()]
        result = validator.validate_corruptions(cases)
        errors = [i for i in result.issues if i.issue_type == "duplicate_id"]
        assert len(errors) == 1


class TestValidateCrossReference:
    def test_valid_references_pass(self):
        validator = DatasetValidator()
        items = [_golden_item(question_id="qa-001")]
        cases = [_corruption_case(question_id="qa-001")]
        result = validator.validate_cross_reference(items, cases)
        assert result.is_valid is True

    def test_broken_reference_produces_error(self):
        validator = DatasetValidator()
        items = [_golden_item(question_id="qa-001")]
        cases = [_corruption_case(question_id="qa-099")]
        result = validator.validate_cross_reference(items, cases)
        errors = [i for i in result.issues if i.issue_type == "broken_question_reference"]
        assert len(errors) == 1
        assert result.is_valid is False

    def test_empty_question_id_skips_reference_check(self):
        validator = DatasetValidator()
        items = [_golden_item(question_id="qa-001")]
        case_data = {
            "case_id": "corr-retrieval-001",
            "question_id": "qa-001",
            "corruption_type": "retrieval_swap",
            "ground_truth_root_cause": "retrieval",
            "severity": "high",
            "description": "test",
            "expected_quality_delta": -0.30,
        }
        cases = [EvaluationCorruptionCase.model_validate(case_data)]
        result = validator.validate_cross_reference(items, cases)
        assert result.is_valid is True
