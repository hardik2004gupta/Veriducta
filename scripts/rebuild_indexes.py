"""CLI: rebuild the BM25 index and version graph from an existing Qdrant collection.

Useful when the BM25 index or version graph files are lost or corrupted without
needing to re-run the full embedding pipeline.

Usage::

    python -m scripts.rebuild_indexes [--corpus-dir corpus]
"""

import argparse
import sys
from pathlib import Path

import structlog
from qdrant_client import QdrantClient

from config.settings import get_settings
from core.logging import configure_logging
from ingestion.bm25_indexer import BM25Index
from ingestion.sidecar import load_all_sidecars
from ingestion.version_graph import build_version_graph
from schemas.models import Chunk
from utils.filesystem import ensure_dir, project_root

logger = structlog.get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild BM25 index and version graph from Qdrant payloads."
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(project_root() / "corpus"),
        help="Root corpus directory (default: corpus/).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Rebuild indexes and return an exit code.

    Args:
        argv: Command-line arguments; uses ``sys.argv`` when ``None``.

    Returns:
        0 on success, 1 on failure.
    """
    configure_logging()
    args = _parse_args(argv)
    settings = get_settings()
    corpus_path = Path(args.corpus_dir)

    logger.info("rebuild_indexes_started", corpus_dir=str(corpus_path))

    # 1. Rebuild version graph from sidecars
    sidecar_dir = corpus_path / "sidecars"
    if not sidecar_dir.exists():
        logger.error("sidecar_dir_missing", path=str(sidecar_dir))
        return 1

    sidecars = load_all_sidecars(sidecar_dir)
    if not sidecars:
        logger.error("no_sidecars_found", directory=str(sidecar_dir))
        return 1

    vg = build_version_graph(sidecars)
    vg_path = Path(settings.ingestion.version_graph_path)
    ensure_dir(vg_path.parent)
    vg.save(vg_path)
    logger.info("version_graph_rebuilt", path=str(vg_path), nodes=len(sidecars))

    # 2. Rebuild BM25 index by scrolling Qdrant payloads
    try:
        client = QdrantClient(
            host=settings.qdrant.host,
            port=settings.qdrant.port,
            prefer_grpc=settings.qdrant.prefer_grpc,
        )
        collection = settings.qdrant.collection_name
        existing = [c.name for c in client.get_collections().collections]
        if collection not in existing:
            logger.error("qdrant_collection_missing", collection=collection)
            return 1

        chunks: list[Chunk] = []
        offset = None
        while True:
            result = client.scroll(
                collection_name=collection,
                scroll_filter=None,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            batch, next_offset = result
            for point in batch:
                if point.payload:
                    p = point.payload
                    chunks.append(
                        Chunk(
                            chunk_id=p["chunk_id"],
                            parent_chunk_id=p.get("parent_chunk_id"),
                            document_id=p["document_id"],
                            text=p["text"],
                            token_count=p.get("token_count", 0),
                            chunk_index=p.get("chunk_index", 0),
                            is_table=p.get("is_table", False),
                            effective_date=p.get("effective_date"),
                            expiry_date=p.get("expiry_date"),
                            page_number=p.get("page_number"),
                        )
                    )
            offset = next_offset
            if offset is None:
                break

        if not chunks:
            logger.error("no_chunks_in_qdrant", collection=collection)
            return 1

        bm25 = BM25Index()
        bm25.build(chunks)
        bm25_path = Path(settings.ingestion.bm25_index_path)
        bm25.save(bm25_path)
        logger.info("bm25_rebuilt", path=str(bm25_path), chunks=bm25.chunk_count)

    except Exception as exc:
        logger.error("rebuild_bm25_failed", error=str(exc))
        return 1

    print(
        f"Rebuild complete: version graph ({len(sidecars)} docs), BM25 ({bm25.chunk_count} chunks)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
