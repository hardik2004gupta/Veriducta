"""Tests for ingestion/ingestor.py — orchestrator (with mocked embedder)."""

import json
from pathlib import Path

import fitz
import pytest

from config.settings import IngestionSettings
from ingestion.ingestor import Ingestor, IngestResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HASH = "a" * 64


def _make_pdf(path: Path, text: str = "Test document content. " * 50) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


def _make_sidecar(path: Path, doc_id: str, pdf_name: str) -> Path:
    data: dict[str, object] = {
        "document_id": doc_id,
        "title": f"Title {doc_id}",
        "source": "https://example.com",
        "document_type": "technical_report",
        "effective_date": "2023-01-01",
        "expiry_date": None,
        "supersedes": [],
        "superseded_by": [],
        "version_hash": _HASH,
        "filename": pdf_name,
        "page_count": 1,
        "has_tables": False,
        "has_figures": False,
        "primary_entities": [],
        "chunking_variant": "boundary_aware",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_settings(tmp_path: Path) -> IngestionSettings:
    return IngestionSettings(
        corpus_dir=str(tmp_path / "corpus"),
        sidecar_dir=str(tmp_path / "corpus" / "sidecars"),
        bm25_index_path=str(tmp_path / "corpus" / "bm25_index.pkl"),
        version_graph_path=str(tmp_path / "corpus" / "version_graph.json"),
        chunking_snapshot_dir=str(tmp_path / "config" / "chunking_snapshots"),
        parent_size_tokens=200,
        child_size_tokens=50,
        child_overlap_tokens=10,
        boundary_aware=True,
    )


# ---------------------------------------------------------------------------
# Ingestor.ingest_document — no embedder (test mode)
# ---------------------------------------------------------------------------


def test_ingest_document_success_no_embedder(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    pdf = _make_pdf(corpus / "doc-001.pdf")
    sidecar = _make_sidecar(sidecars / "doc-001.json", "doc-001", "doc-001.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    result = ingestor.ingest_document(str(pdf), str(sidecar))

    assert isinstance(result, IngestResult)
    assert result.success is True
    assert result.document_id == "doc-001"
    assert result.chunk_count > 0
    assert result.child_count == 0  # no embedder


def test_ingest_document_missing_pdf_returns_failure(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    sidecar = _make_sidecar(sidecars / "doc-001.json", "doc-001", "doc-001.pdf")
    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    result = ingestor.ingest_document(str(corpus / "missing.pdf"), str(sidecar))

    assert result.success is False
    assert "doc-001" in result.document_id


def test_ingest_document_missing_sidecar_returns_failure(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    pdf = _make_pdf(corpus / "doc-001.pdf")
    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    result = ingestor.ingest_document(str(pdf), str(corpus / "missing.json"))

    assert result.success is False


def test_ingest_document_propagates_dates_to_chunks(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    pdf = _make_pdf(corpus / "doc-001.pdf")
    _make_sidecar(sidecars / "doc-001.json", "doc-001", "doc-001.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    ingestor.ingest_document(str(pdf), str(sidecars / "doc-001.json"))

    for chunk in ingestor.all_chunks:
        assert chunk.effective_date == "2023-01-01"


def test_ingest_document_adds_to_version_graph(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    pdf = _make_pdf(corpus / "doc-001.pdf")
    _make_sidecar(sidecars / "doc-001.json", "doc-001", "doc-001.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    ingestor.ingest_document(str(pdf), str(sidecars / "doc-001.json"))

    assert "doc-001" in ingestor.version_graph.graph.nodes


# ---------------------------------------------------------------------------
# Ingestor.ingest_corpus
# ---------------------------------------------------------------------------


def test_ingest_corpus_processes_all_pdfs(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    for i in range(3):
        _make_pdf(corpus / f"doc-{i:03d}.pdf")
        _make_sidecar(sidecars / f"doc-{i:03d}.json", f"doc-{i:03d}", f"doc-{i:03d}.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    results = ingestor.ingest_corpus(str(corpus))

    assert len(results) == 3
    assert all(r.success for r in results)


def test_ingest_corpus_missing_sidecar_marks_failure(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "sidecars").mkdir()

    _make_pdf(corpus / "no-sidecar.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    results = ingestor.ingest_corpus(str(corpus))

    assert len(results) == 1
    assert results[0].success is False


# ---------------------------------------------------------------------------
# Ingestor.build_and_save_indexes
# ---------------------------------------------------------------------------


def test_build_and_save_indexes_writes_files(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    sidecars = corpus / "sidecars"
    sidecars.mkdir()

    _make_pdf(corpus / "doc-001.pdf")
    _make_sidecar(sidecars / "doc-001.json", "doc-001", "doc-001.pdf")

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    ingestor.ingest_corpus(str(corpus))
    ingestor.build_and_save_indexes()

    assert Path(settings.bm25_index_path).exists()
    assert Path(settings.version_graph_path).exists()


def test_build_and_save_indexes_no_chunks_raises(tmp_path: Path) -> None:
    from core.exceptions import IngestionError

    settings = _make_settings(tmp_path)
    ingestor = Ingestor(settings=settings, embedder=None)
    with pytest.raises(IngestionError):
        ingestor.build_and_save_indexes()
