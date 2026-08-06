"""Tests for ingestion/bm25_indexer.py — BM25 index build, serialisation, search."""

from pathlib import Path

import pytest

from core.exceptions import IngestionError, NotFoundError
from ingestion.bm25_indexer import BM25Index, _tokenise
from schemas.models import Chunk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, text: str, parent_id: str = "doc-par-0000") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_chunk_id=parent_id,
        document_id="doc-001",
        text=text,
        token_count=len(text.split()),
        chunk_index=int(chunk_id.split("-")[-1]),
    )


def _make_parent_chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        parent_chunk_id=None,
        document_id="doc-001",
        text="Parent section text.",
        token_count=5,
        chunk_index=0,
    )


SAMPLE_CHUNKS = [
    _make_chunk("doc-001-ch-0000", "The maximum permissible exposure limit is 50 mSv."),
    _make_chunk("doc-001-ch-0001", "Radiation safety requires monitoring of dose rates."),
    _make_chunk("doc-001-ch-0002", "Engineers must verify structural integrity annually."),
    _make_chunk("doc-001-ch-0003", "Temperature limits apply to electronic components."),
    _make_chunk("doc-001-ch-0004", "Safety procedures are documented in section 4."),
]


# ---------------------------------------------------------------------------
# _tokenise
# ---------------------------------------------------------------------------


def test_tokenise_lowercases() -> None:
    tokens = _tokenise("Hello World")
    assert tokens == ["hello", "world"]


def test_tokenise_splits_whitespace() -> None:
    tokens = _tokenise("a b  c")
    assert tokens == ["a", "b", "c"]


def test_tokenise_empty_string() -> None:
    tokens = _tokenise("")
    assert tokens == []


# ---------------------------------------------------------------------------
# BM25Index.build
# ---------------------------------------------------------------------------


def test_build_with_child_chunks_succeeds() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    assert idx.is_built
    assert idx.chunk_count == len(SAMPLE_CHUNKS)


def test_build_filters_parent_chunks() -> None:
    mixed = [*SAMPLE_CHUNKS, _make_parent_chunk("doc-001-par-0000")]
    idx = BM25Index()
    idx.build(mixed)
    assert idx.chunk_count == len(SAMPLE_CHUNKS)


def test_build_no_children_raises() -> None:
    idx = BM25Index()
    with pytest.raises(IngestionError):
        idx.build([_make_parent_chunk("doc-001-par-0000")])


def test_build_empty_list_raises() -> None:
    idx = BM25Index()
    with pytest.raises(IngestionError):
        idx.build([])


# ---------------------------------------------------------------------------
# BM25Index.search
# ---------------------------------------------------------------------------


def test_search_returns_list_of_tuples() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    results = idx.search("radiation exposure", top_k=3)
    assert isinstance(results, list)
    assert len(results) <= 3
    for chunk_id, score, rank in results:
        assert isinstance(chunk_id, str)
        assert isinstance(score, float)
        assert isinstance(rank, int)


def test_search_relevant_chunk_ranks_first() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    results = idx.search("maximum permissible exposure limit mSv", top_k=5)
    top_id = results[0][0]
    assert top_id == "doc-001-ch-0000"


def test_search_rank_is_1_based() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    results = idx.search("safety", top_k=5)
    ranks = [r[2] for r in results]
    assert ranks[0] == 1


def test_search_ranks_are_sequential() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    results = idx.search("safety procedures", top_k=5)
    ranks = [r[2] for r in results]
    assert ranks == list(range(1, len(ranks) + 1))


def test_search_unbuilt_index_raises() -> None:
    idx = BM25Index()
    with pytest.raises(IngestionError):
        idx.search("query")


def test_search_top_k_respected() -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    results = idx.search("safety", top_k=2)
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# BM25Index.save / load
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    path = tmp_path / "bm25_index.pkl"
    idx.save(path)

    idx2 = BM25Index()
    idx2.load(path)
    assert idx2.is_built
    assert idx2.chunk_count == idx.chunk_count


def test_loaded_index_produces_same_results(tmp_path: Path) -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    path = tmp_path / "bm25_index.pkl"
    idx.save(path)

    idx2 = BM25Index()
    idx2.load(path)

    r1 = idx.search("radiation safety", top_k=3)
    r2 = idx2.search("radiation safety", top_k=3)
    assert [t[0] for t in r1] == [t[0] for t in r2]


def test_save_unbuilt_index_raises() -> None:
    idx = BM25Index()
    with pytest.raises(IngestionError):
        idx.save("/tmp/should_not_exist.pkl")


def test_load_missing_file_raises(tmp_path: Path) -> None:
    idx = BM25Index()
    with pytest.raises(NotFoundError):
        idx.load(tmp_path / "nonexistent.pkl")


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    idx = BM25Index()
    idx.build(SAMPLE_CHUNKS)
    path = tmp_path / "deep" / "nested" / "index.pkl"
    idx.save(path)
    assert path.exists()
