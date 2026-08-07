"""Tests for ingestion/sidecar.py - schema validation and file I/O."""

import json
from pathlib import Path

import pytest

from core.exceptions import ValidationError
from ingestion.sidecar import (
    load_all_sidecars,
    load_sidecar,
    save_sidecar,
    validate_sidecar,
)
from schemas.models import DocumentMetadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SIDECAR: dict[str, object] = {
    "document_id": "test-doc-001",
    "title": "Test Document",
    "source": "https://example.com/test.pdf",
    "document_type": "technical_report",
    "effective_date": "2023-01-01",
    "expiry_date": None,
    "supersedes": [],
    "superseded_by": [],
    "version_hash": "a" * 64,
    "filename": "test-doc-001.pdf",
    "page_count": 10,
    "has_tables": True,
    "has_figures": False,
    "primary_entities": ["entity_a", "entity_b"],
    "chunking_variant": "boundary_aware",
}


# ---------------------------------------------------------------------------
# validate_sidecar
# ---------------------------------------------------------------------------


def test_validate_sidecar_valid_data_returns_metadata() -> None:
    meta = validate_sidecar(VALID_SIDECAR)
    assert isinstance(meta, DocumentMetadata)
    assert meta.document_id == "test-doc-001"
    assert meta.page_count == 10


def test_validate_sidecar_missing_required_field_raises() -> None:
    data = {k: v for k, v in VALID_SIDECAR.items() if k != "document_id"}
    with pytest.raises(ValidationError) as exc_info:
        validate_sidecar(data)
    assert "document_id" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


def test_validate_sidecar_bad_effective_date_format_raises() -> None:
    data = {**VALID_SIDECAR, "effective_date": "01/01/2023"}
    with pytest.raises(ValidationError):
        validate_sidecar(data)


def test_validate_sidecar_bad_version_hash_raises() -> None:
    data = {**VALID_SIDECAR, "version_hash": "short"}
    with pytest.raises(ValidationError):
        validate_sidecar(data)


def test_validate_sidecar_negative_page_count_raises() -> None:
    data = {**VALID_SIDECAR, "page_count": 0}
    with pytest.raises(ValidationError):
        validate_sidecar(data)


def test_validate_sidecar_non_hex_version_hash_raises() -> None:
    data = {**VALID_SIDECAR, "version_hash": "z" * 64}
    with pytest.raises(ValidationError):
        validate_sidecar(data)


def test_validate_sidecar_extra_fields_allowed() -> None:
    data = {**VALID_SIDECAR, "custom_field": "value"}
    meta = validate_sidecar(data)
    assert meta.document_id == "test-doc-001"


def test_validate_sidecar_supersedes_list() -> None:
    data = {**VALID_SIDECAR, "supersedes": ["old-doc-001", "old-doc-002"]}
    meta = validate_sidecar(data)
    assert meta.supersedes == ["old-doc-001", "old-doc-002"]


def test_validate_sidecar_expiry_date_valid_format() -> None:
    data = {**VALID_SIDECAR, "expiry_date": "2025-12-31"}
    meta = validate_sidecar(data)
    assert meta.expiry_date == "2025-12-31"


def test_validate_sidecar_expiry_date_bad_format_raises() -> None:
    data = {**VALID_SIDECAR, "expiry_date": "2025/12/31"}
    with pytest.raises(ValidationError):
        validate_sidecar(data)


# ---------------------------------------------------------------------------
# load_sidecar / save_sidecar
# ---------------------------------------------------------------------------


def test_save_and_load_sidecar_roundtrip(tmp_path: Path) -> None:
    meta = validate_sidecar(VALID_SIDECAR)
    path = tmp_path / "test-doc-001.json"
    save_sidecar(meta, path)
    loaded = load_sidecar(path)
    assert loaded.document_id == meta.document_id
    assert loaded.version_hash == meta.version_hash
    assert loaded.page_count == meta.page_count


def test_load_sidecar_file_not_found_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_sidecar(tmp_path / "nonexistent.json")


def test_load_sidecar_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_sidecar(bad)


def test_save_sidecar_creates_parent_dirs(tmp_path: Path) -> None:
    meta = validate_sidecar(VALID_SIDECAR)
    path = tmp_path / "deep" / "nested" / "sidecar.json"
    save_sidecar(meta, path)
    assert path.exists()


# ---------------------------------------------------------------------------
# load_all_sidecars
# ---------------------------------------------------------------------------


def test_load_all_sidecars_returns_all_valid(tmp_path: Path) -> None:
    for i in range(3):
        data = {**VALID_SIDECAR, "document_id": f"doc-{i:03d}", "filename": f"doc-{i:03d}.pdf"}
        path = tmp_path / f"doc-{i:03d}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
    results = load_all_sidecars(tmp_path)
    assert len(results) == 3
    ids = {m.document_id for m in results}
    assert ids == {"doc-000", "doc-001", "doc-002"}


def test_load_all_sidecars_skips_invalid_files(tmp_path: Path) -> None:
    (tmp_path / "valid.json").write_text(json.dumps(VALID_SIDECAR), encoding="utf-8")
    (tmp_path / "invalid.json").write_text('{"document_id": "only-id"}', encoding="utf-8")
    results = load_all_sidecars(tmp_path)
    assert len(results) == 1
    assert results[0].document_id == "test-doc-001"


def test_load_all_sidecars_empty_dir_returns_empty(tmp_path: Path) -> None:
    results = load_all_sidecars(tmp_path)
    assert results == []
