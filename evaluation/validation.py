"""Dataset-level validation for golden QA and corruption benchmark files.

:class:`DatasetValidator` checks structural and semantic integrity — duplicate
IDs, missing citations, invalid labels, broken cross-references — and returns
a typed :class:`~evaluation.schemas.ValidationResult` rather than raising.
"""

from __future__ import annotations

import re

import structlog

from evaluation.schemas import (
    EvaluationCorruptionCase,
    GoldenQAItem,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationResult,
)

logger = structlog.get_logger(__name__)

_CHUNK_ID_PATTERN = re.compile(r"^[a-z0-9-]+-ch-\d{4}$")


class DatasetValidator:
    """Validate golden QA items and corruption cases.

    All check methods return :class:`~evaluation.schemas.ValidationResult`
    rather than raising so callers can choose whether to abort or continue.
    """

    # ------------------------------------------------------------------
    # Golden QA validation
    # ------------------------------------------------------------------

    def validate_golden_qa(self, items: list[GoldenQAItem]) -> ValidationResult:
        """Run all checks on a list of golden QA items.

        Args:
            items: Loaded :class:`~evaluation.schemas.GoldenQAItem` records.

        Returns:
            :class:`~evaluation.schemas.ValidationResult` with all issues.
        """
        issues: list[ValidationIssue] = []
        issues.extend(self._check_duplicate_ids([i.question_id for i in items], "qa"))
        issues.extend(self._check_duplicate_questions([i.question for i in items]))
        issues.extend(self._check_missing_citations(items))
        issues.extend(self._check_chunk_id_format(items))
        issues.extend(self._check_empty_entities(items))
        return self._build_result(issues)

    # ------------------------------------------------------------------
    # Corruption case validation
    # ------------------------------------------------------------------

    def validate_corruptions(self, cases: list[EvaluationCorruptionCase]) -> ValidationResult:
        """Run all checks on a list of corruption cases.

        Args:
            cases: Loaded :class:`~evaluation.schemas.EvaluationCorruptionCase` records.

        Returns:
            :class:`~evaluation.schemas.ValidationResult` with all issues.
        """
        issues: list[ValidationIssue] = []
        issues.extend(self._check_duplicate_ids([c.case_id for c in cases], "corruption"))
        issues.extend(self._check_corruption_type_distribution(cases))
        issues.extend(self._check_quality_delta_sign(cases))
        return self._build_result(issues)

    # ------------------------------------------------------------------
    # Cross-reference validation
    # ------------------------------------------------------------------

    def validate_cross_reference(
        self,
        items: list[GoldenQAItem],
        cases: list[EvaluationCorruptionCase],
    ) -> ValidationResult:
        """Check that every corruption case references a valid question_id.

        Args:
            items: Golden QA items (source of truth for question IDs).
            cases: Corruption cases to validate.

        Returns:
            :class:`~evaluation.schemas.ValidationResult` with broken-reference issues.
        """
        known_ids = {i.question_id for i in items}
        issues: list[ValidationIssue] = []
        for case in cases:
            if case.question_id and case.question_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        issue_type="broken_question_reference",
                        item_id=case.case_id,
                        message=(
                            f"corruption case {case.case_id!r} references "
                            f"unknown question_id {case.question_id!r}"
                        ),
                    )
                )
        return self._build_result(issues)

    # ------------------------------------------------------------------
    # Private checks — golden QA
    # ------------------------------------------------------------------

    def _check_duplicate_ids(self, ids: list[str], kind: str) -> list[ValidationIssue]:
        seen: set[str] = set()
        issues: list[ValidationIssue] = []
        for item_id in ids:
            if item_id in seen:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        issue_type="duplicate_id",
                        item_id=item_id,
                        message=f"duplicate {kind} ID: {item_id!r}",
                    )
                )
            seen.add(item_id)
        return issues

    def _check_duplicate_questions(self, questions: list[str]) -> list[ValidationIssue]:
        seen: dict[str, int] = {}
        issues: list[ValidationIssue] = []
        for idx, q in enumerate(questions):
            normalised = q.strip().lower()
            if normalised in seen:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="duplicate_question",
                        item_id=f"index_{idx}",
                        message=(
                            f"question text appears more than once "
                            f"(first at index {seen[normalised]})"
                        ),
                    )
                )
            else:
                seen[normalised] = idx
        return issues

    def _check_missing_citations(self, items: list[GoldenQAItem]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in items:
            if item.citation_requirement.value == "required" and not item.supporting_chunk_ids:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        issue_type="missing_citations",
                        item_id=item.question_id,
                        message=(
                            f"{item.question_id!r} has citation_requirement=required "
                            "but supporting_chunk_ids is empty"
                        ),
                    )
                )
        return issues

    def _check_chunk_id_format(self, items: list[GoldenQAItem]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in items:
            for chunk_id in item.supporting_chunk_ids + item.counterevidence_chunk_ids:
                if not _CHUNK_ID_PATTERN.match(chunk_id):
                    issues.append(
                        ValidationIssue(
                            severity=ValidationIssueSeverity.WARNING,
                            issue_type="invalid_chunk_id_format",
                            item_id=item.question_id,
                            message=(
                                f"chunk_id {chunk_id!r} does not match "
                                r"'{doc_id}-ch-{NNNN}' pattern"
                            ),
                        )
                    )
        return issues

    def _check_empty_entities(self, items: list[GoldenQAItem]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in items:
            if len(item.expected_entities) < 2:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="insufficient_entities",
                        item_id=item.question_id,
                        message=(
                            f"{item.question_id!r} has fewer than 2 expected_entities "
                            "(counterevidence scan requires at least 2)"
                        ),
                    )
                )
        return issues

    # ------------------------------------------------------------------
    # Private checks — corruptions
    # ------------------------------------------------------------------

    def _check_corruption_type_distribution(
        self, cases: list[EvaluationCorruptionCase]
    ) -> list[ValidationIssue]:
        from schemas.models import RootCauseStage

        stage_counts: dict[str, int] = {}
        for case in cases:
            stage_counts[case.ground_truth_root_cause] = (
                stage_counts.get(case.ground_truth_root_cause, 0) + 1
            )
        issues: list[ValidationIssue] = []
        expected: dict[str, int] = {
            RootCauseStage.RETRIEVAL: 20,
            RootCauseStage.CHUNKING: 15,
            RootCauseStage.RERANKING: 15,
            RootCauseStage.GENERATION: 10,
        }
        for stage, expected_count in expected.items():
            actual = stage_counts.get(stage, 0)
            if actual != expected_count:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="unexpected_corruption_distribution",
                        item_id="dataset",
                        message=(
                            f"expected {expected_count} {stage!r} corruption cases, found {actual}"
                        ),
                    )
                )
        return issues

    def _check_quality_delta_sign(
        self, cases: list[EvaluationCorruptionCase]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for case in cases:
            if case.expected_quality_delta > 0:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="positive_expected_quality_delta",
                        item_id=case.case_id,
                        message=(
                            f"{case.case_id!r} has positive expected_quality_delta "
                            f"({case.expected_quality_delta:.2f}); "
                            "corruptions should degrade quality"
                        ),
                    )
                )
        return issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(issues: list[ValidationIssue]) -> ValidationResult:
        """Aggregate issues into a ValidationResult."""
        errors = sum(1 for i in issues if i.severity == ValidationIssueSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == ValidationIssueSeverity.WARNING)
        result = ValidationResult(
            is_valid=errors == 0,
            issues=issues,
            errors_count=errors,
            warnings_count=warnings,
        )
        logger.info(
            "dataset_validation_complete",
            is_valid=result.is_valid,
            errors=errors,
            warnings=warnings,
        )
        return result
