"""Tests for ingestion/embedder.py — embedding and Qdrant upsert (mocked)."""

from unittest.mock import MagicMock

import pytest

from core.exceptions import IngestionError, VectorStoreError
from ingestion.embedder import ChunkEmbedder, _chunk_payload, _stable_point_id
from schemas.models import Chunk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_child_chunk(i: int) -> Chunk:
    return Chunk(
        chunk_id=f"doc-001-ch-{i:04d}",
        parent_chunk_id="doc-001-par-0000",
        document_id="doc-001",
        text=f"Child chunk number {i} with some content.",
        token_count=10,
        chunk_index=i,
    )


def _make_parent_chunk() -> Chunk:
    return Chunk(
        chunk_id="doc-001-par-0000",
        parent_chunk_id=None,
        document_id="doc-001",
        text="Parent chunk text.",
        token_count=5,
        chunk_index=0,
    )


def _mock_model(dim: int = 4) -> MagicMock:
    model = MagicMock()
    model.embed.side_effect = lambda texts: [[0.1] * dim for _ in texts]
    return model


def _mock_client(collection_exists: bool = True) -> MagicMock:
    client = MagicMock()
    coll = MagicMock()
    coll.name = "veriducta_chunks"
    if collection_exists:
        client.get_collections.return_value.collections = [coll]
    else:
        client.get_collections.return_value.collections = []
    return client


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------


def test_ensure_collection_creates_when_missing() -> None:
    client = _mock_client(collection_exists=False)
    embedder = ChunkEmbedder(model=_mock_model(), client=client)
    embedder.ensure_collection()
    client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_exists() -> None:
    client = _mock_client(collection_exists=True)
    embedder = ChunkEmbedder(model=_mock_model(), client=client)
    embedder.ensure_collection()
    client.create_collection.assert_not_called()


def test_ensure_collection_raises_on_client_error() -> None:
    client = MagicMock()
    client.get_collections.side_effect = RuntimeError("connection refused")
    embedder = ChunkEmbedder(model=_mock_model(), client=client)
    with pytest.raises(VectorStoreError):
        embedder.ensure_collection()


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------


def test_upsert_chunks_returns_count() -> None:
    chunks = [_make_child_chunk(i) for i in range(5)]
    embedder = ChunkEmbedder(model=_mock_model(), client=_mock_client())
    count = embedder.upsert_chunks(chunks)
    assert count == 5


def test_upsert_chunks_filters_parent_chunks() -> None:
    chunks = [_make_child_chunk(i) for i in range(3)] + [_make_parent_chunk()]
    embedder = ChunkEmbedder(model=_mock_model(), client=_mock_client())
    count = embedder.upsert_chunks(chunks)
    assert count == 3


def test_upsert_chunks_empty_list_returns_zero() -> None:
    embedder = ChunkEmbedder(model=_mock_model(), client=_mock_client())
    count = embedder.upsert_chunks([])
    assert count == 0


def test_upsert_chunks_only_parents_returns_zero() -> None:
    embedder = ChunkEmbedder(model=_mock_model(), client=_mock_client())
    count = embedder.upsert_chunks([_make_parent_chunk()])
    assert count == 0


def test_upsert_chunks_raises_vector_store_error_on_qdrant_failure() -> None:
    client = _mock_client()
    client.upsert.side_effect = RuntimeError("upsert failed")
    embedder = ChunkEmbedder(model=_mock_model(), client=client)
    with pytest.raises(VectorStoreError):
        embedder.upsert_chunks([_make_child_chunk(0)])


def test_upsert_chunks_raises_ingestion_error_on_embed_failure() -> None:
    model = MagicMock()
    model.embed.side_effect = IngestionError("embed failed", details={})
    embedder = ChunkEmbedder(model=model, client=_mock_client())
    with pytest.raises(IngestionError):
        embedder.upsert_chunks([_make_child_chunk(0)])


def test_upsert_chunks_batches_correctly() -> None:
    chunks = [_make_child_chunk(i) for i in range(10)]
    model = _mock_model()
    embedder = ChunkEmbedder(model=model, client=_mock_client(), batch_size=3)
    embedder.upsert_chunks(chunks)
    # 10 chunks / batch_size 3 = 4 embed calls
    assert model.embed.call_count == 4


# ---------------------------------------------------------------------------
# _stable_point_id
# ---------------------------------------------------------------------------


def test_stable_point_id_is_deterministic() -> None:
    assert _stable_point_id("doc-001-ch-0000") == _stable_point_id("doc-001-ch-0000")


def test_stable_point_id_different_for_different_ids() -> None:
    assert _stable_point_id("doc-001-ch-0000") != _stable_point_id("doc-001-ch-0001")


def test_stable_point_id_is_non_negative() -> None:
    assert _stable_point_id("any-chunk-id") >= 0


# ---------------------------------------------------------------------------
# _chunk_payload
# ---------------------------------------------------------------------------


def test_chunk_payload_contains_required_fields() -> None:
    chunk = _make_child_chunk(0)
    payload = _chunk_payload(chunk)
    required = {
        "chunk_id",
        "document_id",
        "text",
        "parent_chunk_id",
        "token_count",
        "is_table",
        "effective_date",
        "expiry_date",
        "chunk_index",
        "page_number",
    }
    assert required.issubset(payload.keys())


def test_chunk_payload_values_match_chunk() -> None:
    chunk = _make_child_chunk(42)
    payload = _chunk_payload(chunk)
    assert payload["chunk_id"] == chunk.chunk_id
    assert payload["document_id"] == chunk.document_id
    assert payload["text"] == chunk.text
    assert payload["chunk_index"] == 42
