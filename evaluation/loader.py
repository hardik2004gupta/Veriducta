"""Low-level dataset file I/O for the evaluation harness.

:class:`DatasetLoader` reads JSONL and JSON files from disk and deserialises
them into typed Pydantic models.  It does not perform semantic validation —
use :class:`~evaluation.validation.DatasetValidator` for that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from core.exceptions import NotFoundError, ValidationError
from evaluation.schemas import EvaluationCorruptionCase, GoldenQAItem

logger = structlog.get_logger(__name__)

_M = TypeVar("_M", bound=BaseModel)


class DatasetLoader:
    """Load golden QA and corruption datasets from JSONL files.

    Args:
        dataset_dir: Root directory containing ``golden/``, ``synthetic/``,
                     and ``annotations/`` subdirectories.
    """

    def __init__(self, dataset_dir: str | Path = "data") -> None:
        self._root = Path(dataset_dir)

    # ------------------------------------------------------------------
    # Golden QA
    # ------------------------------------------------------------------

    def load_golden_qa(self, path: str | Path | None = None) -> list[GoldenQAItem]:
        """Load and deserialise all golden QA items from JSONL.

        Args:
            path: Override path. Defaults to ``{dataset_dir}/golden/golden_qa.jsonl``.

        Returns:
            List of :class:`~evaluation.schemas.GoldenQAItem` in file order.

        Raises:
            NotFoundError: If the file does not exist.
            ValidationError: If any JSONL line fails Pydantic validation.
        """
        resolved = Path(path) if path else self._root / "golden" / "golden_qa.jsonl"
        return self._load_jsonl(resolved, GoldenQAItem, "golden_qa")

    # ------------------------------------------------------------------
    # Corruption cases
    # ------------------------------------------------------------------

    def load_corruptions(self, path: str | Path | None = None) -> list[EvaluationCorruptionCase]:
        """Load and deserialise all corruption cases from JSONL.

        Args:
            path: Override path. Defaults to ``{dataset_dir}/synthetic/corruptions.jsonl``.

        Returns:
            List of :class:`~evaluation.schemas.EvaluationCorruptionCase` in file order.

        Raises:
            NotFoundError: If the file does not exist.
            ValidationError: If any JSONL line fails Pydantic validation.
        """
        resolved = Path(path) if path else self._root / "synthetic" / "corruptions.jsonl"
        return self._load_jsonl(resolved, EvaluationCorruptionCase, "corruptions")

    # ------------------------------------------------------------------
    # Annotation schema
    # ------------------------------------------------------------------

    def load_annotation_schema(self, path: str | Path | None = None) -> dict[str, Any]:
        """Load the annotation JSON Schema from disk.

        Args:
            path: Override path. Defaults to
                  ``{dataset_dir}/annotations/annotation_schema.json``.

        Returns:
            Parsed JSON schema as a dict.

        Raises:
            NotFoundError: If the file does not exist.
        """
        resolved = Path(path) if path else self._root / "annotations" / "annotation_schema.json"
        if not resolved.exists():
            raise NotFoundError(
                resource="annotation_schema",
                identifier=str(resolved),
            )
        with resolved.open(encoding="utf-8") as fh:
            schema: dict[str, Any] = json.load(fh)
        logger.info("annotation_schema_loaded", path=str(resolved))
        return schema

    # ------------------------------------------------------------------
    # Generic JSONL helper
    # ------------------------------------------------------------------

    def _load_jsonl(
        self,
        path: Path,
        model_cls: type[_M],
        dataset_name: str,
    ) -> list[_M]:
        """Deserialise every non-empty line in a JSONL file into ``model_cls``.

        Args:
            path: Absolute or relative path to the JSONL file.
            model_cls: Pydantic model class for each record.
            dataset_name: Human-readable name for error messages.

        Returns:
            List of deserialised model instances.

        Raises:
            NotFoundError: If the file does not exist.
            ValidationError: If any line fails validation.
        """
        if not path.exists():
            raise NotFoundError(
                resource=dataset_name,
                identifier=str(path),
            )

        items: list[_M] = []
        with path.open(encoding="utf-8") as fh:
            for line_num, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    record: dict[str, Any] = json.loads(stripped)
                    items.append(model_cls.model_validate(record))
                except (json.JSONDecodeError, Exception) as exc:
                    raise ValidationError(
                        message=f"{dataset_name}: invalid record at line {line_num}",
                        field=f"line_{line_num}",
                        details={"path": str(path), "error": str(exc)},
                    ) from exc

        logger.info(
            "dataset_loaded",
            dataset=dataset_name,
            path=str(path),
            count=len(items),
        )
        return items
