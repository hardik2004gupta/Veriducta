"""Tests for ingestion/chunker.py - hierarchical parent-child chunking."""

from pathlib import Path

import pytest

from core.exceptions import IngestionError
from ingestion.chunker import (
    ChunkingConfig,
    HierarchicalChunker,
    _build_children,
    _group_into_parents,
)
from models.parsed_document import ParsedDocument, TextBlock
from schemas.models import Chunk, ConfigurationSnapshot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_doc(text: str, document_id: str = "doc-001") -> ParsedDocument:
    blocks = [TextBlock(text=text, page_number=1)]
    return ParsedDocument(
        document_id=document_id,
        filename=f"{document_id}.pdf",
        page_count=1,
        text_blocks=blocks,
        raw_text=text,
        page_texts=[text],
    )


def _make_long_doc(n_sections: int = 5) -> ParsedDocument:
    sections = []
    for i in range(n_sections):
        sections.append(f"\n1.{i} Section {i}\n" + "This is section content. " * 80)
    full = "\n".join(sections)
    return ParsedDocument(
        document_id="long-doc",
        filename="long-doc.pdf",
        page_count=1,
        text_blocks=[TextBlock(text=full, page_number=1)],
        raw_text=full,
        page_texts=[full],
    )


# ---------------------------------------------------------------------------
# ChunkingConfig
# ---------------------------------------------------------------------------


def test_chunking_config_defaults() -> None:
    cfg = ChunkingConfig()
    assert cfg.parent_size_tokens == 1500
    assert cfg.child_size_tokens == 300
    assert cfg.child_overlap_tokens == 50
    assert cfg.boundary_aware is True


def test_chunking_config_to_dict() -> None:
    cfg = ChunkingConfig(parent_size_tokens=1000, boundary_aware=False)
    d = cfg.to_dict()
    assert d["parent_size_tokens"] == 1000
    assert d["boundary_aware"] is False


# ---------------------------------------------------------------------------
# HierarchicalChunker.snapshot
# ---------------------------------------------------------------------------


def test_snapshot_returns_configuration_snapshot() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    snap = chunker.snapshot()
    assert isinstance(snap, ConfigurationSnapshot)
    assert snap.stage == "chunking"
    assert len(snap.hash) == 64


def test_snapshot_hash_is_deterministic() -> None:
    cfg = ChunkingConfig(parent_size_tokens=1000)
    h1 = HierarchicalChunker(cfg).snapshot().hash
    h2 = HierarchicalChunker(cfg).snapshot().hash
    assert h1 == h2


def test_snapshot_hash_changes_with_config() -> None:
    h1 = HierarchicalChunker(ChunkingConfig(boundary_aware=True)).snapshot().hash
    h2 = HierarchicalChunker(ChunkingConfig(boundary_aware=False)).snapshot().hash
    assert h1 != h2


def test_snapshot_save_writes_file(tmp_path: Path) -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    snap = chunker.save_snapshot(tmp_path)
    assert isinstance(snap, ConfigurationSnapshot)
    written = Path(tmp_path) / f"{snap.hash}.json"
    assert written.exists()
    assert written.suffix == ".json"


# ---------------------------------------------------------------------------
# HierarchicalChunker.chunk - basic
# ---------------------------------------------------------------------------


def test_chunk_returns_list_of_chunks() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_doc("Hello world. " * 50)
    chunks = chunker.chunk(doc, cfg)
    assert isinstance(chunks, list)
    assert all(isinstance(c, Chunk) for c in chunks)
    assert len(chunks) > 0


def test_chunk_empty_document_raises() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_doc("")
    with pytest.raises(IngestionError):
        chunker.chunk(doc, cfg)


def test_chunk_produces_parent_and_child_chunks() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(5)
    chunks = chunker.chunk(doc, cfg)
    parents = [c for c in chunks if c.parent_chunk_id is None]
    children = [c for c in chunks if c.parent_chunk_id is not None]
    assert len(parents) >= 1
    assert len(children) >= 1


def test_chunk_ids_follow_spec() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(3)
    chunks = chunker.chunk(doc, cfg)
    parents = [c for c in chunks if c.parent_chunk_id is None]
    children = [c for c in chunks if c.parent_chunk_id is not None]
    for parent in parents:
        assert "-par-" in parent.chunk_id
    for child in children:
        assert "-ch-" in child.chunk_id


def test_chunk_ids_use_document_id() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(2)
    doc.document_id = "my-doc-xyz"
    chunks = chunker.chunk(doc, cfg)
    for c in chunks:
        assert c.chunk_id.startswith("my-doc-xyz-")


def test_child_chunk_parent_ids_point_to_real_parents() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(3)
    chunks = chunker.chunk(doc, cfg)
    parent_ids = {c.chunk_id for c in chunks if c.parent_chunk_id is None}
    for child in (c for c in chunks if c.parent_chunk_id is not None):
        assert child.parent_chunk_id in parent_ids


def test_chunk_token_counts_are_positive() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(2)
    chunks = chunker.chunk(doc, cfg)
    for c in chunks:
        assert c.token_count > 0


def test_chunk_effective_date_is_none_before_propagation() -> None:
    cfg = ChunkingConfig()
    chunker = HierarchicalChunker(cfg)
    doc = _make_long_doc(2)
    chunks = chunker.chunk(doc, cfg)
    for c in chunks:
        assert c.effective_date is None


# ---------------------------------------------------------------------------
# Boundary-aware vs. boundary-naive
# ---------------------------------------------------------------------------


def test_boundary_aware_and_naive_produce_different_chunks() -> None:
    boundary_text = (
        "Introduction\n"
        "Content before boundary. " * 40 + "\n1.1 New Section\n" + "Content after boundary. " * 40
    )
    doc = _make_doc(boundary_text)

    aware_cfg = ChunkingConfig(boundary_aware=True)
    naive_cfg = ChunkingConfig(boundary_aware=False)
    chunker = HierarchicalChunker(aware_cfg)

    aware_chunks = chunker.chunk(doc, aware_cfg)
    naive_chunks = chunker.chunk(doc, naive_cfg)

    aware_texts = {c.text for c in aware_chunks if c.parent_chunk_id is not None}
    naive_texts = {c.text for c in naive_chunks if c.parent_chunk_id is not None}
    # The two strategies should produce at least some different splits
    assert aware_texts != naive_texts or len(aware_chunks) != len(naive_chunks)


# ---------------------------------------------------------------------------
# _group_into_parents helper
# ---------------------------------------------------------------------------


def test_group_into_parents_single_section() -> None:
    groups = _group_into_parents(["short text"], parent_size=1000)
    assert len(groups) == 1
    assert groups[0] == ["short text"]


def test_group_into_parents_splits_at_budget() -> None:
    # Each section is ~400 chars = ~100 tokens; budget is 150 tokens → 2 per group
    sections = ["A" * 400] * 6
    groups = _group_into_parents(sections, parent_size=150)
    assert len(groups) >= 2


def test_group_into_parents_empty_input() -> None:
    groups = _group_into_parents([], parent_size=1000)
    assert groups == []


# ---------------------------------------------------------------------------
# _build_children helper
# ---------------------------------------------------------------------------


def test_build_children_produces_children() -> None:
    text = "Word " * 200
    children = _build_children(
        parent_text=text,
        parent_id="doc-par-0000",
        document_id="doc",
        start_index=0,
        child_size=100,
        overlap=20,
        boundary_markers=[],
    )
    assert len(children) >= 1
    for c in children:
        assert c.parent_chunk_id == "doc-par-0000"


def test_build_children_empty_text_returns_empty() -> None:
    children = _build_children(
        parent_text="   ",
        parent_id="doc-par-0000",
        document_id="doc",
        start_index=0,
        child_size=100,
        overlap=20,
        boundary_markers=[],
    )
    assert children == []


def test_build_children_index_increments() -> None:
    text = "Content " * 300
    children = _build_children(
        parent_text=text,
        parent_id="doc-par-0000",
        document_id="doc",
        start_index=5,
        child_size=100,
        overlap=20,
        boundary_markers=[],
    )
    indices = [c.chunk_index for c in children]
    assert indices[0] == 5
    assert indices == list(range(5, 5 + len(children)))
