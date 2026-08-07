"""Chunk embedding and Qdrant upsert.

Takes child chunks from the chunker, embeds them in batches of 32 using
``BAAI/bge-large-en-v1.5``, and upserts each vector with its full payload
to the ``veriducta_chunks`` Qdrant collection.

Collection creation is idempotent: calling :meth:`ChunkEmbedder.ensure_collection`
on an existing collection is a no-op.
"""

from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from core.exceptions import IngestionError, VectorStoreError
from models.embedding import BGELargeEmbedding
from observability.metrics import CHUNKS_CREATED
from schemas.models import Chunk
from utils.hashing import stable_point_id

logger = structlog.get_logger(__name__)

_COLLECTION = "veriducta_chunks"
_DIMENSION = 1024
_DEFAULT_BATCH = 32


class ChunkEmbedder:
    """Embeds child chunks and upserts them to Qdrant.

    Args:
        model: :class:`~models.embedding.BGELargeEmbedding` instance.
        client: Qdrant client instance.
        batch_size: Number of chunks to embed and upsert per batch.
        collection_name: Qdrant collection to write to.
    """

    def __init__(
        self,
        model: BGELargeEmbedding,
        client: QdrantClient,
        batch_size: int = _DEFAULT_BATCH,
        collection_name: str = _COLLECTION,
    ) -> None:
        self._model = model
        self._client = client
        self._batch_size = batch_size
        self._collection = collection_name

    def ensure_collection(self) -> None:
        """Create the Qdrant collection if it does not already exist.

        The collection uses cosine distance and dimension 1024.  Calling this
        on an existing collection is a safe no-op.

        Raises:
            VectorStoreError: If collection creation fails.
        """
        try:
            existing = [c.name for c in self._client.get_collections().collections]
            if self._collection in existing:
                logger.debug("qdrant_collection_exists", collection=self._collection)
                return
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("qdrant_collection_created", collection=self._collection)
        except Exception as exc:
            raise VectorStoreError(
                f"Failed to ensure Qdrant collection '{self._collection}'",
                details={"collection": self._collection, "error": str(exc)},
            ) from exc

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        """Embed *chunks* and upsert them to Qdrant.

        Only child chunks (``parent_chunk_id is not None``) are upserted;
        parent chunks are stored in the BM25 index and used for context
        expansion but are not directly searchable by vector.

        Args:
            chunks: List of :class:`~schemas.models.Chunk` objects from the
                    chunker.  Mixed parent + child lists are accepted; parents
                    are silently filtered out.

        Returns:
            Number of child chunks successfully upserted.

        Raises:
            VectorStoreError: If Qdrant upsert fails.
            IngestionError: If embedding fails.
        """
        children = [c for c in chunks if c.parent_chunk_id is not None]
        if not children:
            logger.warning("embedder_no_children", total_chunks=len(chunks))
            return 0

        upserted = 0
        for i in range(0, len(children), self._batch_size):
            batch = children[i : i + self._batch_size]
            texts = [c.text for c in batch]
            try:
                vectors = self._model.embed(texts)
            except IngestionError:
                raise
            except Exception as exc:
                raise IngestionError(
                    "Embedding batch failed",
                    details={"batch_start": i, "batch_size": len(batch), "error": str(exc)},
                ) from exc

            points = [
                PointStruct(
                    id=_stable_point_id(chunk.chunk_id),
                    vector=vector,
                    payload=_chunk_payload(chunk),
                )
                for chunk, vector in zip(batch, vectors, strict=False)
            ]
            try:
                self._client.upsert(
                    collection_name=self._collection,
                    points=points,
                    wait=True,
                )
            except Exception as exc:
                raise VectorStoreError(
                    f"Qdrant upsert failed for batch at index {i}",
                    details={"collection": self._collection, "error": str(exc)},
                ) from exc

            upserted += len(batch)
            logger.debug(
                "embedder_batch_upserted",
                batch_start=i,
                batch_size=len(batch),
                total_so_far=upserted,
            )

        chunking_variant = children[0].metadata.get("chunking_variant", "boundary_aware")
        CHUNKS_CREATED.labels(chunking_variant=chunking_variant).inc(upserted)
        logger.info(
            "embedder_completed",
            collection=self._collection,
            upserted=upserted,
        )
        return upserted

    def verify_chunks(self, chunk_ids: list[str]) -> list[str]:
        """Return the subset of *chunk_ids* that are present in Qdrant.

        Args:
            chunk_ids: Child chunk IDs to verify.

        Returns:
            IDs that were found in the collection.
        """
        found: list[str] = []
        for chunk_id in chunk_ids:
            pts = self._client.retrieve(
                collection_name=self._collection,
                ids=[_stable_point_id(chunk_id)],
                with_payload=False,
            )
            if pts:
                found.append(chunk_id)
        return found


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _stable_point_id(chunk_id: str) -> int:
    """Delegate to :func:`~utils.hashing.stable_point_id`."""
    return stable_point_id(chunk_id)


def _chunk_payload(chunk: Chunk) -> dict[str, Any]:
    """Build the Qdrant point payload from a :class:`~schemas.models.Chunk`.

    Args:
        chunk: Child chunk to serialise.

    Returns:
        Dict with all fields required by the retrieval and replay engines.
    """
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "text": chunk.text,
        "parent_chunk_id": chunk.parent_chunk_id,
        "token_count": chunk.token_count,
        "is_table": chunk.is_table,
        "effective_date": chunk.effective_date,
        "expiry_date": chunk.expiry_date,
        "chunk_index": chunk.chunk_index,
        "page_number": chunk.page_number,
    }
