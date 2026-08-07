"""Evaluation harness - dataset management, metrics, baselines, regression, and reporting.

Public surface for the evaluation package.  CLI scripts and external callers import
from this module rather than from individual sub-modules.
"""

from evaluation.annotation import (
    ANNOTATION_SCHEMA,
    AnnotationExporter,
    AnnotationLoader,
    AnnotationStatistics,
    AnnotationValidator,
)
from evaluation.baseline import BaselineResult, BaselineRunner
from evaluation.benchmark import BenchmarkResult, BenchmarkRunner
from evaluation.comparison import ComparisonReport, MetricDelta, RunComparator
from evaluation.corruptions import CORRUPTIONS_SEED, CorruptionDatasetBuilder
from evaluation.dataset import DatasetManager
from evaluation.export import DatasetExporter
from evaluation.golden import GOLDEN_QA_SEED, GoldenDatasetBuilder
from evaluation.loader import DatasetLoader
from evaluation.metrics import MetricsComputer
from evaluation.ragas_adapter import RAGASAdapter
from evaluation.regression import RegressionEngine, RegressionResult, RegressionViolation
from evaluation.report import ReportWriter
from evaluation.runner import (
    CorruptionEvaluationResult,
    EvaluationRunner,
    EvaluationRunResults,
    QueryEvaluationResult,
)
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
    "BaselineResult",
    "BaselineRunner",
    "BenchmarkResult",
    "BenchmarkRunner",
    "CitationRequirement",
    "ComparisonReport",
    "CorruptionDatasetBuilder",
    "CorruptionEvaluationResult",
    "CorruptionSeverity",
    "DatasetExporter",
    "DatasetLoader",
    "DatasetManager",
    "DatasetManifest",
    "DatasetStats",
    "DatasetValidator",
    "Difficulty",
    "EvaluationCorruptionCase",
    "EvaluationRunResults",
    "EvaluationRunner",
    "GoldenDatasetBuilder",
    "GoldenQAItem",
    "HallucinationRisk",
    "MetricDelta",
    "MetricsComputer",
    "QueryEvaluationResult",
    "RAGASAdapter",
    "RegressionEngine",
    "RegressionResult",
    "RegressionViolation",
    "ReportWriter",
    "ReviewStatus",
    "RunComparator",
    "TemporalConstraintType",
    "ValidationIssue",
    "ValidationIssueSeverity",
    "ValidationResult",
]
