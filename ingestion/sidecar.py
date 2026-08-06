"""Sidecar metadata schema, validation, and file I/O.

Every corpus document must have a companion JSON sidecar that captures its
identity, temporal validity, and version provenance.  The sidecar is the
single source of truth for ``document_id``, ``effective_date``, and the
supersession chain — all of which drive temporal filtering during retrieval.

Sidecars are stored at ``corpus/sidecars/{document_id}.json``.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import structlog

from core.exceptions import ValidationError
from schemas.models import DocumentMetadata
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# JSON Schema
# ---------------------------------------------------------------------------

SIDECAR_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "document_id",
        "title",
        "source",
        "document_type",
        "effective_date",
        "version_hash",
        "filename",
        "page_count",
    ],
    "properties": {
        "document_id": {"type": "string", "minLength": 1},
        "title": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "document_type": {"type": "string", "minLength": 1},
        "effective_date": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
        },
        "expiry_date": {
            "oneOf": [
                {"type": "null"},
                {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
            ]
        },
        "supersedes": {"type": "array", "items": {"type": "string"}},
        "superseded_by": {"type": "array", "items": {"type": "string"}},
        "version_hash": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": r"^[0-9a-f]{64}$",
        },
        "filename": {"type": "string", "minLength": 1},
        "page_count": {"type": "integer", "minimum": 1},
        "has_tables": {"type": "boolean"},
        "has_figures": {"type": "boolean"},
        "primary_entities": {"type": "array", "items": {"type": "string"}},
        "chunking_variant": {"type": "string"},
    },
    "additionalProperties": True,
}

_VALIDATOR = jsonschema.Draft7Validator(SIDECAR_JSON_SCHEMA)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_sidecar(data: dict[str, Any]) -> DocumentMetadata:
    """Validate a raw dict against the sidecar JSON Schema and Pydantic rules.

    Args:
        data: Dictionary decoded from a sidecar JSON file.

    Returns:
        Validated :class:`~schemas.models.DocumentMetadata` instance.

    Raises:
        ValidationError: If JSON Schema or Pydantic validation fails.
    """
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        field_path = ".".join(str(p) for p in first.path) if first.path else None
        raise ValidationError(
            f"Sidecar schema validation failed: {first.message}",
            field=field_path,
            details={
                "error_count": len(errors),
                "first_path": list(first.path),
                "validator": first.validator,
            },
        )
    try:
        return DocumentMetadata.model_validate(data)
    except Exception as exc:
        raise ValidationError(
            f"Sidecar Pydantic validation failed: {exc}",
            details={"pydantic_error": str(exc)},
        ) from exc


def load_sidecar(path: str | Path) -> DocumentMetadata:
    """Load and validate a sidecar JSON file from disk.

    Args:
        path: Path to the sidecar ``.json`` file.

    Returns:
        Validated :class:`~schemas.models.DocumentMetadata` instance.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValidationError: If the sidecar fails validation.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Sidecar file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    metadata = validate_sidecar(data)
    logger.debug("sidecar_loaded", document_id=metadata.document_id, path=str(path))
    return metadata


def save_sidecar(metadata: DocumentMetadata, path: str | Path) -> None:
    """Serialise :class:`~schemas.models.DocumentMetadata` to a JSON sidecar file.

    Creates parent directories as needed.

    Args:
        metadata: Validated document metadata to write.
        path: Destination ``.json`` file path.
    """
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(metadata.model_dump_json(indent=2))
    logger.debug("sidecar_saved", document_id=metadata.document_id, path=str(path))


def load_all_sidecars(sidecar_dir: str | Path) -> list[DocumentMetadata]:
    """Load and validate every ``.json`` file in *sidecar_dir*.

    Files that fail validation are skipped with a WARNING log; they do not
    raise an exception.

    Args:
        sidecar_dir: Directory containing sidecar JSON files.

    Returns:
        Validated metadata objects in filename order.
    """
    sidecar_dir = Path(sidecar_dir)
    results: list[DocumentMetadata] = []

    for path in sorted(sidecar_dir.glob("*.json")):
        try:
            results.append(load_sidecar(path))
        except (ValidationError, json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("sidecar_load_failed", path=str(path), error=str(exc))

    logger.info("sidecars_loaded", count=len(results), directory=str(sidecar_dir))
    return results
