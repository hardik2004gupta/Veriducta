"""CLI: run the full ingestion pipeline over the corpus directory.

Usage::

    python -m scripts.ingest_corpus [--corpus-dir corpus]

Exit code 0 = all documents ingested successfully.
Exit code 1 = one or more documents failed ingestion.
"""

import argparse
import sys

import structlog
from qdrant_client import QdrantClient

from config.settings import get_settings
from core.logging import configure_logging
from ingestion.embedder import ChunkEmbedder
from ingestion.ingestor import Ingestor
from models.embedding import get_embedding_model
from utils.filesystem import project_root

logger = structlog.get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest all PDF + sidecar pairs in a corpus directory."
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(project_root() / "corpus"),
        help="Root corpus directory (default: corpus/).",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Skip embedding and Qdrant upsert (BM25 and version graph only).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run corpus ingestion and return an exit code.

    Args:
        argv: Command-line arguments; uses ``sys.argv`` when ``None``.

    Returns:
        0 if all documents ingested successfully, 1 if any failed.
    """
    configure_logging()
    args = _parse_args(argv)
    settings = get_settings()

    logger.info(
        "ingest_corpus_started",
        corpus_dir=args.corpus_dir,
        skip_embedding=args.skip_embedding,
    )

    embedder: ChunkEmbedder | None = None
    if not args.skip_embedding:
        client = QdrantClient(
            host=settings.qdrant.host,
            port=settings.qdrant.port,
            prefer_grpc=settings.qdrant.prefer_grpc,
        )
        model = get_embedding_model()
        embedder = ChunkEmbedder(
            model=model,
            client=client,
            batch_size=settings.ingestion.embedding_batch_size,
            collection_name=settings.qdrant.collection_name,
        )

    ingestor = Ingestor(settings=settings.ingestion, embedder=embedder)
    results = ingestor.ingest_corpus(args.corpus_dir)

    try:
        ingestor.build_and_save_indexes()
    except Exception as exc:
        logger.error("index_build_failed", error=str(exc))
        return 1

    failed = [r for r in results if not r.success]
    if failed:
        for r in failed:
            print(f"  FAILED: {r.document_id} — {r.error}", file=sys.stderr)
        total = len(results)
        print(f"\nIngestion: {total - len(failed)}/{total} succeeded.", file=sys.stderr)
        return 1

    print(f"Ingestion complete: {len(results)}/{len(results)} documents succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
