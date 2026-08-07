"""Annotation utilities - loading, validation, export, and statistics.

Annotations are stored as a JSON Schema document that describes the expected
structure of each golden QA item field.  This module provides helpers to load
the schema, validate items against it, compute annotation statistics, and
export annotations in formats suitable for human review.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import structlog

from evaluation.schemas import (
    GoldenQAItem,
    HallucinationRisk,
    ReviewStatus,
    TemporalConstraintType,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationResult,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Annotation schema (embedded as Python dict for import-time availability)
# ---------------------------------------------------------------------------

ANNOTATION_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "GoldenQAAnnotationSchema",
    "version": "1.0",
    "description": (
        "Schema for a single annotated golden QA item in the Veriducta evaluation dataset."
    ),
    "type": "object",
    "required": [
        "question_id",
        "question",
        "gold_answer",
        "supporting_chunk_ids",
        "expected_entities",
        "expected_citations",
        "difficulty",
        "domain",
        "answer_type",
        "failure_mode",
    ],
    "properties": {
        "question_id": {
            "type": "string",
            "pattern": "^qa-\\d{3}$",
            "description": "Unique identifier in the form qa-NNN.",
        },
        "question": {"type": "string", "minLength": 10},
        "gold_answer": {"type": "string", "minLength": 20},
        "supporting_chunk_ids": {
            "type": "array",
            "items": {
                "type": "string",
                "pattern": "^[a-z0-9-]+-ch-\\d{4}$",
            },
            "description": "Chunk IDs that directly support the gold answer.",
        },
        "counterevidence_chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "expected_entities": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "description": "At least 2 key entities for counterevidence retrieval.",
        },
        "expected_citations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "temporal_validity": {
            "type": "string",
            "enum": ["valid", "superseded", "not_yet_effective", "unknown"],
        },
        "difficulty": {
            "type": "string",
            "enum": ["easy", "medium", "hard"],
        },
        "domain": {
            "type": "string",
            "enum": ["safety", "geology", "engineering", "regulatory"],
        },
        "answer_type": {
            "type": "string",
            "enum": ["factual", "numerical_threshold", "procedural", "comparative", "temporal"],
        },
        "verification_required": {"type": "boolean"},
        "failure_mode": {
            "type": "string",
            "enum": [
                "none",
                "chunking_boundary",
                "retrieval_miss",
                "omission",
                "temporal_confusion",
                "hallucination",
                "contradiction",
            ],
        },
        "expected_failure_modes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "hallucination_risk": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "citation_requirement": {
            "type": "string",
            "enum": ["required", "optional", "none"],
        },
        "temporal_constraints": {
            "type": "string",
            "enum": ["none", "date_specific", "version_dependent"],
        },
        "quality_notes": {"type": "string"},
        "annotator_notes": {"type": "string"},
        "review_status": {
            "type": "string",
            "enum": ["draft", "approved", "needs_review"],
        },
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# AnnotationLoader
# ---------------------------------------------------------------------------


class AnnotationLoader:
    """Load and return the annotation schema from disk or from the embedded default.

    Args:
        schema_path: Optional path to a JSON Schema file.  When ``None``,
                     :data:`ANNOTATION_SCHEMA` is returned without I/O.
    """

    def __init__(self, schema_path: str | Path | None = None) -> None:
        self._path = Path(schema_path) if schema_path else None

    def load(self) -> dict[str, Any]:
        """Return the annotation schema.

        Returns:
            Parsed JSON schema dict.

        Raises:
            FileNotFoundError: If a path was given but does not exist.
        """
        if self._path is None:
            logger.info("annotation_schema_loaded_from_embedded")
            return dict(ANNOTATION_SCHEMA)

        if not self._path.exists():
            raise FileNotFoundError(str(self._path))

        with self._path.open(encoding="utf-8") as fh:
            schema: dict[str, Any] = json.load(fh)
        logger.info("annotation_schema_loaded_from_file", path=str(self._path))
        return schema

    def write(self, path: str | Path) -> None:
        """Persist the embedded annotation schema to ``path``.

        Args:
            path: Destination path (parent directories will be created).
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            json.dump(ANNOTATION_SCHEMA, fh, indent=2)
        logger.info("annotation_schema_written", path=str(dest))


# ---------------------------------------------------------------------------
# AnnotationValidator
# ---------------------------------------------------------------------------


class AnnotationValidator:
    """Validate golden QA items against annotation quality rules.

    These checks are semantic (completeness, internal consistency) rather than
    structural (Pydantic handles structural validation).
    """

    def validate(self, items: list[GoldenQAItem]) -> ValidationResult:
        """Run all annotation quality checks.

        Args:
            items: Loaded :class:`~evaluation.schemas.GoldenQAItem` records.

        Returns:
            :class:`~evaluation.schemas.ValidationResult` with all issues found.
        """
        issues: list[ValidationIssue] = []
        issues.extend(self._check_draft_items(items))
        issues.extend(self._check_hallucination_risk_consistency(items))
        issues.extend(self._check_temporal_constraint_consistency(items))
        issues.extend(self._check_answer_length(items))
        issues.extend(self._check_expected_failure_modes_non_empty(items))
        errors = sum(1 for i in issues if i.severity == ValidationIssueSeverity.ERROR)
        warnings = sum(1 for i in issues if i.severity == ValidationIssueSeverity.WARNING)
        result = ValidationResult(
            is_valid=errors == 0,
            issues=issues,
            errors_count=errors,
            warnings_count=warnings,
        )
        logger.info(
            "annotation_validation_complete",
            is_valid=result.is_valid,
            errors=errors,
            warnings=warnings,
        )
        return result

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _check_draft_items(self, items: list[GoldenQAItem]) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                severity=ValidationIssueSeverity.WARNING,
                issue_type="draft_item",
                item_id=item.question_id,
                message=(
                    f"{item.question_id!r} has review_status='draft' "
                    "- not yet approved for evaluation"
                ),
            )
            for item in items
            if item.review_status == ReviewStatus.DRAFT
        ]

    def _check_hallucination_risk_consistency(
        self, items: list[GoldenQAItem]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in items:
            if (
                item.failure_mode == "hallucination"
                and item.hallucination_risk != HallucinationRisk.HIGH
            ):
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="hallucination_risk_inconsistency",
                        item_id=item.question_id,
                        message=(
                            f"{item.question_id!r}: failure_mode='hallucination' "
                            f"but hallucination_risk='{item.hallucination_risk}' (expected 'high')"
                        ),
                    )
                )
        return issues

    def _check_temporal_constraint_consistency(
        self, items: list[GoldenQAItem]
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        temporal_failure_modes = {"temporal_confusion"}
        for item in items:
            if (
                item.failure_mode in temporal_failure_modes
                and item.temporal_constraints == TemporalConstraintType.NONE
            ):
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="temporal_constraint_missing",
                        item_id=item.question_id,
                        message=(
                            f"{item.question_id!r}: failure_mode='temporal_confusion' "
                            "but temporal_constraints='none'"
                        ),
                    )
                )
        return issues

    def _check_answer_length(self, items: list[GoldenQAItem]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for item in items:
            word_count = len(item.gold_answer.split())
            if word_count < 10:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        issue_type="short_gold_answer",
                        item_id=item.question_id,
                        message=f"{item.question_id!r}: gold_answer has only {word_count} words",
                    )
                )
        return issues

    def _check_expected_failure_modes_non_empty(
        self, items: list[GoldenQAItem]
    ) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                severity=ValidationIssueSeverity.WARNING,
                issue_type="empty_expected_failure_modes",
                item_id=item.question_id,
                message=f"{item.question_id!r}: expected_failure_modes is empty",
            )
            for item in items
            if not item.expected_failure_modes
        ]


# ---------------------------------------------------------------------------
# AnnotationStatistics
# ---------------------------------------------------------------------------


class AnnotationStatistics:
    """Compute aggregate statistics over annotated golden QA items."""

    def compute(self, items: list[GoldenQAItem]) -> dict[str, Any]:
        """Return a statistics dict for a list of golden QA items.

        Args:
            items: Loaded :class:`~evaluation.schemas.GoldenQAItem` records.

        Returns:
            Dict with keys:
            ``total``, ``difficulty``, ``domain``, ``failure_mode``,
            ``answer_type``, ``review_status``, ``hallucination_risk``,
            ``temporal_constraints``, ``verification_required_count``,
            ``avg_supporting_chunks``, ``avg_counterevidence_chunks``,
            ``avg_expected_entities``.
        """
        if not items:
            return {"total": 0}

        difficulty_counts = Counter(i.difficulty for i in items)
        domain_counts = Counter(i.domain for i in items)
        failure_mode_counts = Counter(i.failure_mode for i in items)
        answer_type_counts = Counter(i.answer_type for i in items)
        review_status_counts = Counter(i.review_status for i in items)
        hallucination_risk_counts = Counter(i.hallucination_risk for i in items)
        temporal_constraint_counts = Counter(i.temporal_constraints for i in items)

        avg_supporting = sum(len(i.supporting_chunk_ids) for i in items) / len(items)
        avg_counter = sum(len(i.counterevidence_chunk_ids) for i in items) / len(items)
        avg_entities = sum(len(i.expected_entities) for i in items) / len(items)
        verification_required = sum(1 for i in items if i.verification_required)

        def _enum_dict(counter: Counter) -> dict:  # type: ignore[type-arg]
            return {k.value if hasattr(k, "value") else k: v for k, v in counter.items()}

        stats = {
            "total": len(items),
            "difficulty": _enum_dict(difficulty_counts),
            "domain": {str(k): v for k, v in domain_counts.items()},
            "failure_mode": _enum_dict(failure_mode_counts),
            "answer_type": _enum_dict(answer_type_counts),
            "review_status": _enum_dict(review_status_counts),
            "hallucination_risk": _enum_dict(hallucination_risk_counts),
            "temporal_constraints": _enum_dict(temporal_constraint_counts),
            "verification_required_count": verification_required,
            "avg_supporting_chunks": round(avg_supporting, 2),
            "avg_counterevidence_chunks": round(avg_counter, 2),
            "avg_expected_entities": round(avg_entities, 2),
        }
        logger.info("annotation_statistics_computed", total=len(items))
        return stats


# ---------------------------------------------------------------------------
# AnnotationExporter
# ---------------------------------------------------------------------------


class AnnotationExporter:
    """Export golden QA annotations to human-readable formats."""

    def to_markdown_table(self, items: list[GoldenQAItem]) -> str:
        """Render a Markdown summary table of all golden QA items.

        Args:
            items: Items to export.

        Returns:
            Markdown string with a table row per item.
        """
        header = (
            "| ID | Difficulty | Domain | Failure Mode | Review Status |\n|---|---|---|---|---|\n"
        )
        rows = [
            f"| {i.question_id} | {i.difficulty} | {i.domain}"
            f" | {i.failure_mode} | {i.review_status} |"
            for i in items
        ]
        return header + "\n".join(rows)

    def to_review_markdown(self, items: list[GoldenQAItem]) -> str:
        """Render a detailed Markdown review document for human annotators.

        Args:
            items: Items to include.

        Returns:
            Multi-section Markdown string.
        """
        sections: list[str] = ["# Veriducta Golden QA - Annotation Review\n"]
        for item in items:
            chunk_ids = ", ".join(item.supporting_chunk_ids) or "*(none)*"
            entities = ", ".join(item.expected_entities) or "*(none)*"
            sections.append(
                f"## {item.question_id} - {item.difficulty.upper()} - {item.domain}\n\n"
                f"**Question:** {item.question}\n\n"
                f"**Gold Answer:** {item.gold_answer}\n\n"
                f"**Supporting Chunks:** {chunk_ids}\n\n"
                f"**Expected Entities:** {entities}\n\n"
                f"**Failure Mode:** {item.failure_mode} | "
                f"**Hallucination Risk:** {item.hallucination_risk} | "
                f"**Review:** {item.review_status}\n\n"
                f"**Notes:** {item.annotator_notes or '*(none)*'}\n\n---\n"
            )
        return "\n".join(sections)

    def to_csv(self, items: list[GoldenQAItem]) -> str:
        """Export items as a CSV string.

        Args:
            items: Items to export.

        Returns:
            CSV string with header row.
        """
        header = (
            "question_id,difficulty,domain,answer_type,failure_mode,"
            "hallucination_risk,review_status,verification_required,"
            "supporting_chunk_count,expected_entity_count\n"
        )
        rows = [
            (
                f"{i.question_id},{i.difficulty},{i.domain},{i.answer_type},"
                f"{i.failure_mode},{i.hallucination_risk},{i.review_status},"
                f"{i.verification_required},{len(i.supporting_chunk_ids)},"
                f"{len(i.expected_entities)}"
            )
            for i in items
        ]
        return header + "\n".join(rows)
