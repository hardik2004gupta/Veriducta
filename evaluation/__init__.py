"""Evaluation harness — dataset management, validation, annotation, and export.

Public surface for the evaluation package.  The evaluation runner (Phase 18)
and CLI scripts import from this module rather than from individual sub-modules.
"""

from evaluation.annotation import (
    ANNOTATION_SCHEMA,
    AnnotationExporter,
    AnnotationLoader,
    AnnotationStatistics,
    AnnotationValidator,
)
from evaluation.corruptions import CORRUPTIONS_SEED, CorruptionDatasetBuilder
from evaluation.dataset import DatasetManager
from evaluation.export import DatasetExporter
from evaluation.golden import GOLDEN_QA_SEED, GoldenDatasetBuilder
from evaluation.loader import DatasetLoader
from evaluation.schemas import (
    FAILURE_MODE_TO_ROOT_CAUSE,
    AnswerType,
    CitationRequirement,
    CorruptionSeverity,
    DatasetManifest,
    DatasetStats,
    Difficulty,
    EvaluationCorruptionCase,
    GoldenQAItem,
    HallucinationRisk,
    ReviewStatus,
    TemporalConstraintType,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationResult,
)
from evaluation.validation import DatasetValidator

__all__ = [
    "ANNOTATION_SCHEMA",
    "CORRUPTIONS_SEED",
    "FAILURE_MODE_TO_ROOT_CAUSE",
    "GOLDEN_QA_SEED",
    "AnnotationExporter",
    "AnnotationLoader",
    "AnnotationStatistics",
    "AnnotationValidator",
    "AnswerType",
    "CitationRequirement",
    "CorruptionDatasetBuilder",
    "CorruptionSeverity",
    "DatasetExporter",
    "DatasetLoader",
    "DatasetManager",
    "DatasetManifest",
    "DatasetStats",
    "DatasetValidator",
    "Difficulty",
    "EvaluationCorruptionCase",
    "GoldenDatasetBuilder",
    "GoldenQAItem",
    "HallucinationRisk",
    "ReviewStatus",
    "TemporalConstraintType",
    "ValidationIssue",
    "ValidationIssueSeverity",
    "ValidationResult",
]
