"""BM25 index over all child chunks.

The index is built from child chunk texts using ``rank_bm25.BM25Okapi`` and
serialised to ``corpus/bm25_index.pkl``.  Loading and searching are O(n) in the
number of indexed chunks but fast enough for corpuses of 30-50 documents.

The tokeniser used here (whitespace split + lowercase) must match exactly
at index time and at query time to produce correct BM25 scores.
"""

import pickle
from pathlib import Path
from typing import Any

import structlog
from rank_bm25 import BM25Okapi

from core.exceptions import IngestionError, NotFoundError
from schemas.models import Chunk
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


def _tokenise(text: str) -> list[str]:
    """Shared tokeniser: lowercase whitespace split.

    Must be used identically at index build time and query time.

    Args:
        text: Input string.

    Returns:
        List of lowercase tokens.
    """
    return text.lower().split()


class BM25Index:
    """BM25Okapi index over child chunk texts.

    Args:
        None.  Use :meth:`build` to populate, :meth:`save`/:meth:`load` to
        persist.

    Usage::

        idx = BM25Index()
        idx.build(child_chunks)
        idx.save("corpus/bm25_index.pkl")
        results = idx.search("maximum permissible exposure", top_k=10)
    """

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []
        self._texts: list[str] = []

    def build(self, chunks: list[Chunk]) -> None:
        """Build the BM25 index from a list of child chunks.

        Only child chunks (``parent_chunk_id is not None``) are indexed.

        Args:
            chunks: Mixed list of parent and child chunks.  Parents are
                    silently skipped.

        Raises:
            IngestionError: If no child chunks are found.
        """
        children = [c for c in chunks if c.parent_chunk_id is not None]
        if not children:
            raise IngestionError(
                "BM25 index build failed: no child chunks provided",
                details={"total_input": len(chunks)},
            )

        self._chunk_ids = [c.chunk_id for c in children]
        self._texts = [c.text for c in children]
        tokenised = [_tokenise(t) for t in self._texts]
        self._bm25 = BM25Okapi(tokenised)

        logger.info("bm25_index_built", chunk_count=len(children))

    def save(self, path: str | Path) -> None:
        """Serialise the index to *path* using pickle.

        Args:
            path: Destination ``.pkl`` file path.

        Raises:
            IngestionError: If the index has not been built yet.
        """
        if self._bm25 is None:
            raise IngestionError(
                "Cannot save an empty BM25 index - call build() first.",
                details={},
            )
        path = Path(path)
        ensure_dir(path.parent)
        payload: dict[str, Any] = {
            "bm25": self._bm25,
            "chunk_ids": self._chunk_ids,
            "texts": self._texts,
        }
        with path.open("wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info("bm25_index_saved", path=str(path), chunk_count=len(self._chunk_ids))

    def load(self, path: str | Path) -> None:
        """Restore the index from a pickle file produced by :meth:`save`.

        Args:
            path: Path to the ``.pkl`` file.

        Raises:
            NotFoundError: If the file does not exist.
        """
        path = Path(path)
        if not path.exists():
            raise NotFoundError("bm25_index", str(path))
        with path.open("rb") as fh:
            payload: dict[str, Any] = pickle.load(fh)  # noqa: S301
        self._bm25 = payload["bm25"]
        self._chunk_ids = payload["chunk_ids"]
        self._texts = payload["texts"]
        logger.info("bm25_index_loaded", path=str(path), chunk_count=len(self._chunk_ids))

    def search(self, query: str, top_k: int = 100) -> list[tuple[str, float, int]]:
        """Search the index and return top-*k* results.

        Args:
            query: Natural-language query string.
            top_k: Maximum number of results to return.

        Returns:
            List of ``(chunk_id, bm25_score, bm25_rank)`` tuples sorted by
            descending score.  Rank is 1-based.

        Raises:
            IngestionError: If the index has not been built or loaded.
        """
        if self._bm25 is None:
            raise IngestionError(
                "BM25 index not loaded - call build() or load() first.",
                details={},
            )
        tokens = _tokenise(query)
        scores = self._bm25.get_scores(tokens)

        # Pair each score with its index, sort descending
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[tuple[str, float, int]] = []
        for rank, (idx, score) in enumerate(indexed[:top_k], start=1):
            results.append((self._chunk_ids[idx], float(score), rank))
        return results

    @property
    def chunk_count(self) -> int:
        """Number of chunks in the index."""
        return len(self._chunk_ids)

    @property
    def is_built(self) -> bool:
        """True if the index has been built or loaded."""
        return self._bm25 is not None
