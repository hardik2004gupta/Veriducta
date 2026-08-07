"""Tests for ingestion/version_graph.py — temporal validity graph."""

from pathlib import Path

import pytest

from ingestion.version_graph import VersionGraph, build_version_graph
from schemas.models import DocumentMetadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HASH = "a" * 64


def _meta(
    doc_id: str,
    effective: str,
    expiry: str | None = None,
    supersedes: list[str] | None = None,
    superseded_by: list[str] | None = None,
) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=doc_id,
        title=f"Title {doc_id}",
        source="https://example.com",
        document_type="standard",
        effective_date=effective,
        expiry_date=expiry,
        supersedes=supersedes or [],
        superseded_by=superseded_by or [],
        version_hash=_HASH,
        filename=f"{doc_id}.pdf",
        page_count=5,
    )


# ---------------------------------------------------------------------------
# VersionGraph.add_document / build_from_sidecars
# ---------------------------------------------------------------------------


def test_add_document_adds_node() -> None:
    vg = VersionGraph()
    vg.add_document(_meta("doc-001", "2023-01-01"))
    assert "doc-001" in vg.graph.nodes


def test_build_from_sidecars_adds_all_nodes() -> None:
    sidecars = [
        _meta("doc-001", "2022-01-01"),
        _meta("doc-002", "2023-01-01"),
    ]
    vg = VersionGraph()
    vg.build_from_sidecars(sidecars)
    assert vg.graph.number_of_nodes() == 2


def test_supersedes_creates_directed_edge() -> None:
    # doc-002 supersedes doc-001 → edge doc-001 → doc-002
    sidecars = [
        _meta("doc-001", "2022-01-01"),
        _meta("doc-002", "2023-01-01", supersedes=["doc-001"]),
    ]
    vg = build_version_graph(sidecars)
    assert vg.graph.has_edge("doc-001", "doc-002")


def test_superseded_by_creates_directed_edge() -> None:
    # doc-001 superseded_by doc-002 → edge doc-001 → doc-002
    sidecars = [
        _meta("doc-001", "2022-01-01", superseded_by=["doc-002"]),
        _meta("doc-002", "2023-01-01"),
    ]
    vg = build_version_graph(sidecars)
    assert vg.graph.has_edge("doc-001", "doc-002")


# ---------------------------------------------------------------------------
# get_valid_documents
# ---------------------------------------------------------------------------


def test_get_valid_documents_returns_active_docs() -> None:
    sidecars = [
        _meta("doc-001", "2022-01-01"),
        _meta("doc-002", "2024-01-01"),
    ]
    vg = build_version_graph(sidecars)
    valid = vg.get_valid_documents("2023-06-01")
    assert "doc-001" in valid
    assert "doc-002" not in valid  # not yet effective


def test_get_valid_documents_excludes_expired() -> None:
    sidecars = [_meta("doc-001", "2022-01-01", expiry="2023-01-01")]
    vg = build_version_graph(sidecars)
    valid = vg.get_valid_documents("2023-06-01")
    assert "doc-001" not in valid


def test_get_valid_documents_excludes_superseded() -> None:
    sidecars = [
        _meta("doc-001", "2020-01-01"),
        _meta("doc-002", "2022-01-01", supersedes=["doc-001"]),
    ]
    vg = build_version_graph(sidecars)
    valid = vg.get_valid_documents("2023-01-01")
    assert "doc-001" not in valid
    assert "doc-002" in valid


def test_get_valid_documents_includes_not_yet_superseded() -> None:
    # doc-002 becomes effective in 2025; before that, doc-001 is valid
    sidecars = [
        _meta("doc-001", "2020-01-01"),
        _meta("doc-002", "2025-01-01", supersedes=["doc-001"]),
    ]
    vg = build_version_graph(sidecars)
    valid = vg.get_valid_documents("2023-01-01")
    assert "doc-001" in valid
    assert "doc-002" not in valid


def test_get_valid_documents_three_test_dates() -> None:
    sidecars = [
        _meta("v1", "2020-01-01"),
        _meta("v2", "2022-01-01", supersedes=["v1"]),
        _meta("v3", "2024-01-01", supersedes=["v2"]),
    ]
    vg = build_version_graph(sidecars)

    # Before v2: only v1 valid
    assert vg.get_valid_documents("2021-06-01") == ["v1"]
    # Between v2 and v3: only v2 valid
    valid_2023 = vg.get_valid_documents("2023-01-01")
    assert "v2" in valid_2023
    assert "v1" not in valid_2023
    # After v3: only v3 valid
    valid_2025 = vg.get_valid_documents("2025-01-01")
    assert "v3" in valid_2025
    assert "v2" not in valid_2025


# ---------------------------------------------------------------------------
# get_superseded_documents
# ---------------------------------------------------------------------------


def test_get_superseded_documents_returns_superseded() -> None:
    sidecars = [
        _meta("doc-001", "2020-01-01"),
        _meta("doc-002", "2022-01-01", supersedes=["doc-001"]),
    ]
    vg = build_version_graph(sidecars)
    superseded = vg.get_superseded_documents("2023-01-01")
    assert "doc-001" in superseded
    assert "doc-002" not in superseded


# ---------------------------------------------------------------------------
# get_supersession_chain
# ---------------------------------------------------------------------------


def test_get_supersession_chain_single_hop() -> None:
    sidecars = [
        _meta("v1", "2020-01-01"),
        _meta("v2", "2022-01-01", supersedes=["v1"]),
    ]
    vg = build_version_graph(sidecars)
    chain = vg.get_supersession_chain("v1")
    assert chain == ["v1", "v2"]


def test_get_supersession_chain_multi_hop() -> None:
    sidecars = [
        _meta("v1", "2020-01-01"),
        _meta("v2", "2022-01-01", supersedes=["v1"]),
        _meta("v3", "2024-01-01", supersedes=["v2"]),
    ]
    vg = build_version_graph(sidecars)
    chain = vg.get_supersession_chain("v1")
    assert chain == ["v1", "v2", "v3"]


def test_get_supersession_chain_no_successor() -> None:
    vg = VersionGraph()
    vg.add_document(_meta("solo", "2023-01-01"))
    chain = vg.get_supersession_chain("solo")
    assert chain == ["solo"]


def test_get_supersession_chain_unknown_doc() -> None:
    vg = VersionGraph()
    chain = vg.get_supersession_chain("does-not-exist")
    assert chain == ["does-not-exist"]


# ---------------------------------------------------------------------------
# save / load
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    sidecars = [
        _meta("doc-001", "2022-01-01"),
        _meta("doc-002", "2023-01-01", supersedes=["doc-001"]),
    ]
    vg = build_version_graph(sidecars)
    path = tmp_path / "version_graph.json"
    vg.save(path)

    vg2 = VersionGraph()
    vg2.load(path)
    assert vg2.graph.number_of_nodes() == vg.graph.number_of_nodes()
    assert vg2.graph.has_edge("doc-001", "doc-002")


def test_load_nonexistent_file_raises(tmp_path: Path) -> None:
    vg = VersionGraph()
    with pytest.raises(FileNotFoundError):
        vg.load(tmp_path / "missing.json")


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    vg = VersionGraph()
    vg.add_document(_meta("doc-001", "2022-01-01"))
    path = tmp_path / "deep" / "graph.json"
    vg.save(path)
    assert path.exists()
