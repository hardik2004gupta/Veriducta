"""High-level dataset manager - single entry point for the evaluation harness.

:class:`DatasetManager` orchestrates loading, validation, annotation
statistics, and export.  The evaluation runner and CLI scripts use this
class rather than interacting with individual sub-modules directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from evaluation.annotation import (
    AnnotationLoader,
    AnnotationStatistics,
    AnnotationValidator,
)
from evaluation.corruptions import CorruptionDatasetBuilder
from evaluation.export import DatasetExporter
from evaluation.golden import GoldenDatasetBuilder
from evaluation.loader import DatasetLoader
from evaluation.schemas import (
    DatasetManifest,
    DatasetStats,
    EvaluationCorruptionCase,
    GoldenQAItem,
    ValidationResult,
)
from evaluation.validation import DatasetValidator
from replay.models import CorruptionCase

logger = structlog.get_logger(__name__)


class DatasetManager:
    """Orchestrate loading, validation, and export of the evaluation dataset.

    Args:
        dataset_dir: Root directory containing ``golden/``, ``synthetic/``,
                     ``annotations/``, and ``exports/`` subdirectories.
    """

    def __init__(self, dataset_dir: str | Path = "data") -> None:
        self._root = Path(dataset_dir)
        self._loader = DatasetLoader(dataset_dir)
        self._golden_builder = GoldenDatasetBuilder()
        self._corruption_builder = CorruptionDatasetBuilder()
        self._dataset_validator = DatasetValidator()
        self._annotation_validator = AnnotationValidator()
        self._annotation_stats = AnnotationStatistics()
        self._annotation_loader = AnnotationLoader()

        self._golden_items: list[GoldenQAItem] = []
        self._corruption_cases: list[EvaluationCorruptionCase] = []

    # ------------------------------------------------------------------
    # Loading - from seed (no disk I/O)
    # ------------------------------------------------------------------

    def load_from_seed(self) -> None:
        """Populate the manager from the embedded Python seed data.

        Call this when JSONL files have not yet been generated, e.g. in tests
        or on first run before :meth:`build_and_write` is called.
        """
        self._golden_items = self._golden_builder.load_from_seed()
        self._corruption_cases = self._corruption_builder.load_from_seed()
        logger.info(
            "dataset_loaded_from_seed",
            golden=len(self._golden_items),
            corruptions=len(self._corruption_cases),
        )

    # ------------------------------------------------------------------
    # Loading - from JSONL files
    # ------------------------------------------------------------------

    def load_from_files(
        self,
        golden_path: str | Path | None = None,
        corruptions_path: str | Path | None = None,
    ) -> None:
        """Load the dataset from JSONL files on disk.

        Args:
            golden_path: Override for the golden QA JSONL path.
            corruptions_path: Override for the corruptions JSONL path.

        Raises:
            NotFoundError: If either file does not exist.
            ValidationError: If any JSONL line fails Pydantic validation.
        """
        self._golden_items = self._loader.load_golden_qa(golden_path)
        self._corruption_cases = self._loader.load_corruptions(corruptions_path)
        logger.info(
            "dataset_loaded_from_files",
            golden=len(self._golden_items),
            corruptions=len(self._corruption_cases),
        )

    # ------------------------------------------------------------------
    # Build + write (seed → JSONL)
    # ------------------------------------------------------------------

    def build_and_write(
        self,
        golden_path: str | Path | None = None,
        corruptions_path: str | Path | None = None,
        annotation_schema_path: str | Path | None = None,
    ) -> None:
        """Generate JSONL files from seed data and write them to disk.

        Also writes the annotation schema JSON.  Idempotent: re-running
        overwrites the files with identical content.

        Args:
            golden_path: Destination for golden QA JSONL.
                         Defaults to ``{dataset_dir}/golden/golden_qa.jsonl``.
            corruptions_path: Destination for corruptions JSONL.
                              Defaults to ``{dataset_dir}/synthetic/corruptions.jsonl``.
            annotation_schema_path: Destination for annotation schema JSON.
                                    Defaults to
                                    ``{dataset_dir}/annotations/annotation_schema.json``.
        """
        if not self._golden_items:
            self._golden_items = self._golden_builder.load_from_seed()
        if not self._corruption_cases:
            self._corruption_cases = self._corruption_builder.load_from_seed()

        golden_dest = (
            Path(golden_path) if golden_path else self._root / "golden" / "golden_qa.jsonl"
        )
        corruptions_dest = (
            Path(corruptions_path)
            if corruptions_path
            else self._root / "synthetic" / "corruptions.jsonl"
        )
        schema_dest = (
            Path(annotation_schema_path)
            if annotation_schema_path
            else self._root / "annotations" / "annotation_schema.json"
        )

        self._golden_builder.write_to_file(golden_dest, self._golden_items)
        self._corruption_builder.write_to_file(corruptions_dest, self._corruption_cases)
        self._annotation_loader.write(schema_dest)
        logger.info(
            "dataset_built_and_written",
            golden_path=str(golden_dest),
            corruptions_path=str(corruptions_dest),
            schema_path=str(schema_dest),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> dict[str, ValidationResult]:
        """Run all dataset validation checks.

        Returns:
            Dict with keys ``"golden_qa"``, ``"corruptions"``,
            ``"cross_reference"``, ``"annotations"`` mapping to their
            respective :class:`~evaluation.schemas.ValidationResult`.
        """
        results = {
            "golden_qa": self._dataset_validator.validate_golden_qa(self._golden_items),
            "corruptions": self._dataset_validator.validate_corruptions(self._corruption_cases),
            "cross_reference": self._dataset_validator.validate_cross_reference(
                self._golden_items, self._corruption_cases
            ),
            "annotations": self._annotation_validator.validate(self._golden_items),
        }
        all_valid = all(r.is_valid for r in results.values())
        logger.info("dataset_validation_summary", all_valid=all_valid)
        return results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def compute_stats(self) -> DatasetStats:
        """Compute aggregate statistics for the loaded dataset.

        Returns:
            :class:`~evaluation.schemas.DatasetStats` with counts and distributions.
        """
        from collections import Counter

        golden = self._golden_items
        corruptions = self._corruption_cases

        difficulty_dist = Counter(str(i.difficulty) for i in golden)
        domain_dist = Counter(str(i.domain) for i in golden)
        failure_dist = Counter(str(i.failure_mode) for i in golden)
        answer_type_dist = Counter(str(i.answer_type) for i in golden)
        temporal_dist = Counter(str(i.temporal_validity) for i in golden)
        review_dist = Counter(str(i.review_status) for i in golden)
        corruption_type_dist = Counter(str(c.corruption_type) for c in corruptions)
        root_cause_dist = Counter(str(c.ground_truth_root_cause) for c in corruptions)
        realistic_count = sum(1 for c in corruptions if c.is_realistic_boundary_error)
        total_supporting = sum(len(i.supporting_chunk_ids) for i in golden)
        mean_supporting = total_supporting / len(golden) if golden else 0.0

        return DatasetStats(
            total_questions=len(golden),
            difficulty_distribution=dict(difficulty_dist),
            domain_distribution=dict(domain_dist),
            failure_mode_distribution=dict(failure_dist),
            answer_type_distribution=dict(answer_type_dist),
            temporal_validity_distribution=dict(temporal_dist),
            review_status_distribution=dict(review_dist),
            total_corruptions=len(corruptions),
            corruption_type_distribution=dict(corruption_type_dist),
            root_cause_distribution=dict(root_cause_dist),
            realistic_boundary_error_count=realistic_count,
            total_supporting_chunks=total_supporting,
            mean_supporting_chunks=round(mean_supporting, 2),
        )

    def compute_annotation_statistics(self) -> dict[str, Any]:
        """Compute annotation-level statistics for golden QA items.

        Returns:
            Dict from :class:`~evaluation.annotation.AnnotationStatistics.compute`.
        """
        return self._annotation_stats.compute(self._golden_items)

    def get_manifest(self) -> DatasetManifest:
        """Build a :class:`~evaluation.schemas.DatasetManifest` for the loaded dataset.

        Returns:
            Manifest with item counts and an empty checksum (populated by build script).
        """
        return DatasetManifest(
            golden_qa_count=len(self._golden_items),
            corruptions_count=len(self._corruption_cases),
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(
        self,
        formats: list[str] | None = None,
        export_dir: str | Path | None = None,
    ) -> dict[str, Path]:
        """Export the dataset to one or more formats.

        Args:
            formats: List of format names to export.  Supported values:
                     ``"jsonl"``, ``"csv"``, ``"markdown"``.
                     Defaults to all three.
            export_dir: Override export directory.  Defaults to
                        ``{dataset_dir}/exports``.

        Returns:
            Dict mapping ``"{dataset}_{format}"`` to the written :class:`~pathlib.Path`.
        """
        requested = set(formats or ["jsonl", "csv", "markdown"])
        dest_dir = Path(export_dir) if export_dir else self._root / "exports"
        exporter = DatasetExporter(
            golden_items=self._golden_items,
            corruption_cases=self._corruption_cases,
            export_dir=dest_dir,
        )
        written: dict[str, Path] = {}

        if "jsonl" in requested:
            written["golden_jsonl"] = exporter.write_golden_jsonl()
            written["corruptions_jsonl"] = exporter.write_corruptions_jsonl()
        if "csv" in requested:
            written["golden_csv"] = exporter.write_golden_csv()
            written["corruptions_csv"] = exporter.write_corruptions_csv()
        if "markdown" in requested:
            written["golden_markdown"] = exporter.write_golden_markdown()
            written["corruptions_markdown"] = exporter.write_corruptions_markdown()

        logger.info("dataset_exported", formats=list(requested), file_count=len(written))
        return written

    # ------------------------------------------------------------------
    # Replay integration
    # ------------------------------------------------------------------

    def to_replay_cases(self) -> list[CorruptionCase]:
        """Convert all corruption cases to replay engine format.

        Returns:
            List of :class:`~replay.models.CorruptionCase` for the ablation engine.
        """
        return self._corruption_builder.to_replay_cases(self._corruption_cases)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def golden_items(self) -> list[GoldenQAItem]:
        """Currently loaded golden QA items."""
        return list(self._golden_items)

    @property
    def corruption_cases(self) -> list[EvaluationCorruptionCase]:
        """Currently loaded corruption cases."""
        return list(self._corruption_cases)
