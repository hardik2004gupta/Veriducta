"""Tests for retrieval/expander.py."""

from unittest.mock import MagicMock

import pytest

from core.exceptions import VectorStoreError
from retrieval.expander import ExpansionLogEntry, ParentChildExpander, build_generation_context
from schemas.models import Chunk, RetrievalCandidate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str, text: str = "child text", parent_id: str | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-a",
        text=text,
        token_count=5,
        chunk_index=0,
        parent_chunk_id=parent_id,
    )


def _make_candidate(
    chunk_id: str, text: str = "child text", parent_id: str | None = None
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        chunk=_make_chunk(chunk_id, text, parent_id),
        rrf_score=0.5,
        rrf_rank=1,
    )


def _parent_point(parent_id: str, parent_text: str = "parent text") -> MagicMock:
    """Fake Qdrant ScoredPoint for parent retrieval."""
    pt = MagicMock()
    pt.payload = {
        "chunk_id": parent_id,
        "document_id": "doc-a",
        "text": parent_text,
        "parent_chunk_id": None,
        "token_count": 20,
        "chunk_index": 0,
        "is_table": False,
        "effective_date": None,
        "expiry_date": None,
        "page_number": None,
    }
    return pt


def _make_expander(parent_points: list[MagicMock] | None = None) -> ParentChildExpander:
    client = MagicMock()
    client.retrieve.return_value = parent_points or []
    return ParentChildExpander(qdrant_client=client)


# ---------------------------------------------------------------------------
# expand: basic behaviour
# ---------------------------------------------------------------------------


def test_expand_empty_candidates() -> None:
    expander = _make_expander()
    expanded, log = expander.expand([])
    assert expanded == []
    assert log == []


def test_expand_no_parent_id_not_expanded() -> None:
    cand = _make_candidate("doc-a-ch-0000", parent_id=None)
    expander = _make_expander()
    expanded, log = expander.expand([cand])
    assert len(expanded) == 1
    assert expanded[0].parent_chunk is None
    assert log[0].expanded is False
    assert log[0].parent_chunk_id is None


def test_expand_with_parent_id_sets_parent_chunk() -> None:
    cand = _make_candidate("doc-a-ch-0000", parent_id="doc-a-par-0000")
    parent_pt = _parent_point("doc-a-par-0000", "Parent section text")
    expander = _make_expander([parent_pt])
    expanded, log = expander.expand([cand])
    assert expanded[0].parent_chunk is not None
    assert expanded[0].parent_chunk.text == "Parent section text"


def test_expand_log_records_expansion_success() -> None:
    cand = _make_candidate("doc-a-ch-0000", parent_id="doc-a-par-0000")
    parent_pt = _parent_point("doc-a-par-0000")
    expander = _make_expander([parent_pt])
    _, log = expander.expand([cand])
    assert log[0].expanded is True
    assert log[0].parent_chunk_id == "doc-a-par-0000"
    assert log[0].child_chunk_id == "doc-a-ch-0000"


def test_expand_parent_not_found_still_returns_candidate() -> None:
    cand = _make_candidate("doc-a-ch-0000", parent_id="doc-a-par-0000")
    expander = _make_expander([])  # no points found
    expanded, log = expander.expand([cand])
    assert len(expanded) == 1
    assert expanded[0].parent_chunk is None
    assert log[0].expanded is False


def test_expand_qdrant_error_raises_vector_store_error() -> None:
    cand = _make_candidate("doc-a-ch-0000", parent_id="doc-a-par-0000")
    client = MagicMock()
    client.retrieve.side_effect = RuntimeError("Qdrant unavailable")
    expander = ParentChildExpander(qdrant_client=client)
    with pytest.raises(VectorStoreError):
        expander.expand([cand])


def test_expand_candidate_without_chunk_skipped() -> None:
    cand = RetrievalCandidate(chunk_id="orphan-ch-0000", rrf_score=0.3, rrf_rank=1)
    expander = _make_expander()
    expanded, log = expander.expand([cand])
    assert len(expanded) == 1
    assert log[0].expanded is False


def test_expand_log_entry_type() -> None:
    expander = _make_expander()
    cand = _make_candidate("doc-a-ch-0000")
    _, log = expander.expand([cand])
    assert isinstance(log[0], ExpansionLogEntry)


# ---------------------------------------------------------------------------
# build_generation_context
# ---------------------------------------------------------------------------


def test_build_generation_context_child_only() -> None:
    cand = _make_candidate("a", text="child text")
    context = build_generation_context([cand])
    assert "child text" in context
    assert "[SECTION]" not in context


def test_build_generation_context_with_parent() -> None:
    cand = _make_candidate("a", text="child text", parent_id="a-par")
    parent = _make_chunk("a-par", text="parent section", parent_id=None)
    cand = cand.model_copy(update={"parent_chunk": parent})
    context = build_generation_context([cand])
    assert "child text" in context
    assert "[SECTION]" in context
    assert "parent section" in context


def test_build_generation_context_multiple_candidates_joined() -> None:
    c1 = _make_candidate("a", text="first")
    c2 = _make_candidate("b", text="second")
    context = build_generation_context([c1, c2])
    assert "first" in context
    assert "second" in context


def test_build_generation_context_skips_candidate_without_chunk() -> None:
    cand = RetrievalCandidate(chunk_id="no-chunk", rrf_score=0.5, rrf_rank=1)
    context = build_generation_context([cand])
    assert context == ""
