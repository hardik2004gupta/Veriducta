"""BGE-Large-EN-v1.5 embedding model wrapper.

Loaded once at module level via the singleton accessor :func:`get_embedding_model`.
Never reloaded per-request.  The query prefix required by BGE for retrieval tasks
is applied automatically when ``is_query=True``.
"""

import structlog
from sentence_transformers import SentenceTransformer

from core.exceptions import IngestionError
from core.interfaces import BaseEmbeddingModel

logger = structlog.get_logger(__name__)

_MODEL_ID = "BAAI/bge-large-en-v1.5"
_DIMENSION = 1024
_ENCODE_BATCH_SIZE = 32
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# Module-level singleton — loaded once, held for the process lifetime.
_model_instance: "BGELargeEmbedding | None" = None


class BGELargeEmbedding(BaseEmbeddingModel):
    """Dense embedding model wrapping ``BAAI/bge-large-en-v1.5``.

    Batch size defaults to 32.  Uses GPU if available, CPU otherwise.
    Query embedding automatically prepends the BGE retrieval prefix so
    callers do not need to manage it.

    Lifecycle: instantiated once via :func:`get_embedding_model`; never
    reloaded per-request.
    """

    def __init__(self, model_id: str = _MODEL_ID) -> None:
        logger.info("embedding_model_loading", model_id=model_id)
        try:
            self._model = SentenceTransformer(model_id)
        except Exception as exc:
            raise IngestionError(
                f"Failed to load embedding model: {model_id}",
                details={"model_id": model_id, "error": str(exc)},
            ) from exc
        logger.info("embedding_model_loaded", model_id=model_id, dimension=_DIMENSION)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return dense vectors for a batch of passage texts.

        Args:
            texts: Non-empty list of passage strings (not query strings).
                   For query embedding use :meth:`embed_query`.

        Returns:
            List of 1024-dimensional float vectors, one per input text.

        Raises:
            IngestionError: If the texts list is empty or encoding fails.
        """
        if not texts:
            raise IngestionError(
                "embed() called with empty text list",
                details={"count": 0},
            )
        try:
            vectors = self._model.encode(
                texts,
                batch_size=_ENCODE_BATCH_SIZE,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return [v.tolist() for v in vectors]
        except Exception as exc:
            raise IngestionError(
                "Embedding batch failed",
                details={"count": len(texts), "error": str(exc)},
            ) from exc

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string with the BGE retrieval prefix.

        Args:
            query: Natural-language query text.

        Returns:
            1024-dimensional float vector.
        """
        prefixed = _QUERY_PREFIX + query
        return self.embed([prefixed])[0]

    @property
    def dimension(self) -> int:
        """Embedding dimensionality: 1024."""
        return _DIMENSION

    @property
    def model_id(self) -> str:
        """Canonical HuggingFace model ID."""
        return _MODEL_ID


def get_embedding_model() -> BGELargeEmbedding:
    """Return the process-level singleton :class:`BGELargeEmbedding`.

    Loads the model on the first call; subsequent calls return the cached
    instance.

    Returns:
        The singleton :class:`BGELargeEmbedding` instance.
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = BGELargeEmbedding()
    return _model_instance
