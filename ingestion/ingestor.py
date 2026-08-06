"""Ingestion orchestrator: PDF → chunks → embeddings → Qdrant + BM25 + version graph.

The :class:`Ingestor` runs the complete ingestion pipeline for a single document
and exposes a corpus-level method that processes every document in a directory.
It is idempotent: re-ingesting a document with the same ``version_hash`` is a
no-op at the Qdrant level (upsert semantics).
"""

from dataclasses import dataclass
from pathlib import Path

import structlog

from config.settings import IngestionSettings, get_settings
from core.exceptions import IngestionError
from ingestion.bm25_indexer import BM25Index
from ingestion.chunker import ChunkingConfig, HierarchicalChunker
from ingestion.embedder import ChunkEmbedder
from ingestion.parser import PyMuPDFParser
from ingestion.sidecar import load_sidecar
from ingestion.version_graph import VersionGraph
from observability.metrics import DOCUMENTS_INGESTED, INGESTION_ERRORS
from schemas.models import Chunk, DocumentMetadata

logger = structlog.get_logger(__name__)


@dataclass
class IngestResult:
    """Summary of a single document ingestion run.

    Args:
        document_id: Identifier of the ingested document.
        success: True if ingestion completed without error.
        chunk_count: Total number of chunks (parents + children) produced.
        child_count: Number of child chunks upserted to Qdrant.
        error: Error message if ``success`` is False.
    """

    document_id: str
    success: bool
    chunk_count: int = 0
    child_count: int = 0
    error: str = ""


class Ingestor:
    """Orchestrates the full ingestion pipeline for the Veriducta corpus.

    The pipeline for each document:
    1. Load and validate the sidecar (``document_id``, dates, version hash).
    2. Parse the PDF into a :class:`~models.parsed_document.ParsedDocument`.
    3. Chunk the document into parent + child :class:`~schemas.models.Chunk` objects.
    4. Propagate temporal metadata (``effective_date``, ``expiry_date``) onto chunks.
    5. Embed child chunks and upsert to Qdrant.
    6. Register the document in the in-memory version graph.

    After all documents are ingested, call :meth:`build_and_save_indexes` to
    serialise the BM25 index and version graph.

    Args:
        settings: Ingestion configuration.  Defaults to ``get_settings().ingestion``.
        embedder: Pre-wired :class:`~ingestion.embedder.ChunkEmbedder`.
        chunker: :class:`~ingestion.chunker.HierarchicalChunker` instance.
        version_graph: In-memory :class:`~ingestion.version_graph.VersionGraph`.
    """

    def __init__(
        self,
        settings: IngestionSettings | None = None,
        embedder: ChunkEmbedder | None = None,
        chunker: HierarchicalChunker | None = None,
        version_graph: VersionGraph | None = None,
    ) -> None:
        cfg = settings or get_settings().ingestion
        self._settings = cfg
        self._chunking_config = ChunkingConfig(
            parent_size_tokens=cfg.parent_size_tokens,
            child_size_tokens=cfg.child_size_tokens,
            child_overlap_tokens=cfg.child_overlap_tokens,
            boundary_aware=cfg.boundary_aware,
        )
        self._parser = PyMuPDFParser()
        self._chunker = chunker or HierarchicalChunker(self._chunking_config)
        self._embedder = embedder
        self._version_graph = version_graph or VersionGraph()
        self._all_chunks: list[Chunk] = []

    def ingest_document(self, pdf_path: str, sidecar_path: str) -> IngestResult:
        """Ingest a single PDF document.

        Args:
            pdf_path: Absolute path to the PDF file.
            sidecar_path: Absolute path to the companion sidecar JSON file.

        Returns:
            :class:`IngestResult` summarising success or failure.
        """
        metadata: DocumentMetadata | None = None
        try:
            metadata = load_sidecar(sidecar_path)
            doc_id = metadata.document_id
            logger.info("ingestor_document_started", document_id=doc_id)

            # Parse
            parsed = self._parser.parse(pdf_path)
            parsed.document_id = doc_id  # override stem with authoritative ID

            # Chunk
            chunks = self._chunker.chunk(parsed, self._chunking_config)

            # Propagate temporal metadata onto every chunk
            for chunk in chunks:
                chunk.effective_date = metadata.effective_date
                chunk.expiry_date = metadata.expiry_date
                chunk.metadata["document_type"] = metadata.document_type
                chunk.metadata["chunking_variant"] = metadata.chunking_variant

            # Embed + upsert to Qdrant (skipped if no embedder — test mode)
            child_count = 0
            if self._embedder is not None:
                self._embedder.ensure_collection()
                child_count = self._embedder.upsert_chunks(chunks)

            # Accumulate chunks for BM25 index
            self._all_chunks.extend(chunks)

            # Register in version graph
            self._version_graph.add_document(metadata)

            DOCUMENTS_INGESTED.labels(document_type=metadata.document_type).inc()

            logger.info(
                "ingestor_document_completed",
                document_id=doc_id,
                total_chunks=len(chunks),
                child_count=child_count,
            )
            return IngestResult(
                document_id=doc_id,
                success=True,
                chunk_count=len(chunks),
                child_count=child_count,
            )

        except Exception as exc:
            doc_id = metadata.document_id if metadata else Path(pdf_path).stem
            INGESTION_ERRORS.labels(error_type=type(exc).__name__).inc()
            logger.error(
                "ingestor_document_failed",
                document_id=doc_id,
                error=str(exc),
            )
            return IngestResult(
                document_id=doc_id,
                success=False,
                error=str(exc),
            )

    def ingest_corpus(self, corpus_dir: str) -> list[IngestResult]:
        """Ingest all paired PDF + sidecar files in *corpus_dir*.

        Expects the following layout inside *corpus_dir*::

            corpus/
            ├── document-id.pdf
            └── sidecars/
                └── document-id.json

        Args:
            corpus_dir: Root corpus directory.

        Returns:
            One :class:`IngestResult` per PDF found in *corpus_dir*.
        """
        corpus_path = Path(corpus_dir)
        sidecar_dir = corpus_path / "sidecars"
        results: list[IngestResult] = []

        pdf_files = sorted(corpus_path.glob("*.pdf"))
        logger.info("ingestor_corpus_started", pdf_count=len(pdf_files))

        for pdf_path in pdf_files:
            sidecar_path = sidecar_dir / f"{pdf_path.stem}.json"
            if not sidecar_path.exists():
                logger.warning(
                    "ingestor_sidecar_missing",
                    pdf=str(pdf_path),
                    expected_sidecar=str(sidecar_path),
                )
                results.append(
                    IngestResult(
                        document_id=pdf_path.stem,
                        success=False,
                        error=f"Sidecar not found: {sidecar_path}",
                    )
                )
                continue
            results.append(self.ingest_document(str(pdf_path), str(sidecar_path)))

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            "ingestor_corpus_completed",
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
        )
        return results

    def build_and_save_indexes(self) -> None:
        """Serialise the BM25 index and version graph to disk.

        Call this once after all documents have been ingested via
        :meth:`ingest_document` or :meth:`ingest_corpus`.

        Raises:
            IngestionError: If no chunks have been ingested yet.
        """
        if not self._all_chunks:
            raise IngestionError(
                "No chunks to index — ingest at least one document first.",
                details={},
            )

        # BM25 index
        bm25 = BM25Index()
        bm25.build(self._all_chunks)
        bm25.save(self._settings.bm25_index_path)

        # Version graph
        self._version_graph.save(self._settings.version_graph_path)

        # Chunking config snapshot
        snap = self._chunker.save_snapshot(Path(self._settings.chunking_snapshot_dir))

        logger.info(
            "ingestor_indexes_saved",
            bm25_path=self._settings.bm25_index_path,
            graph_path=self._settings.version_graph_path,
            snapshot_hash=snap.hash,
        )

    @property
    def version_graph(self) -> VersionGraph:
        """The in-memory version graph populated during ingestion."""
        return self._version_graph

    @property
    def all_chunks(self) -> list[Chunk]:
        """All chunks produced across all ingested documents."""
        return list(self._all_chunks)
