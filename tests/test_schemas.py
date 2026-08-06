"""Tests for shared Pydantic schemas."""

from schemas.models import (
    Chunk,
    Claim,
    ConfigurationSnapshot,
    DocumentMetadata,
    EvaluationMetrics,
    VerificationStatus,
)
from utils.hashing import sha256_str
from utils.ids import chunk_id, parent_chunk_id


def test_document_metadata_roundtrip() -> None:
    """DocumentMetadata serialises and deserialises cleanly."""
    meta = DocumentMetadata(
        document_id="usgs-2021-001",
        title="Test Document",
        source="https://example.com/doc.pdf",
        document_type="technical_report",
        effective_date="2021-01-15",
        version_hash=sha256_str("fake-content"),
        filename="test.pdf",
        page_count=10,
    )
    data = meta.model_dump()
    restored = DocumentMetadata.model_validate(data)
    assert restored.document_id == meta.document_id
    assert restored.effective_date == "2021-01-15"


def test_chunk_id_format() -> None:
    """chunk_id and parent_chunk_id follow the required naming convention."""
    assert chunk_id("usgs-2021-001", 0) == "usgs-2021-001-ch-0000"
    assert chunk_id("usgs-2021-001", 99) == "usgs-2021-001-ch-0099"
    assert parent_chunk_id("usgs-2021-001", 3) == "usgs-2021-001-par-0003"


def test_chunk_requires_chunk_id() -> None:
    """Chunk must accept a valid chunk_id."""
    c = Chunk(
        chunk_id="usgs-2021-001-ch-0000",
        document_id="usgs-2021-001",
        text="Some text content.",
        token_count=4,
        chunk_index=0,
    )
    assert c.chunk_id == "usgs-2021-001-ch-0000"


def test_claim_defaults() -> None:
    """Claim default verification status is UNRESOLVED."""
    claim = Claim(
        text="The document states X.",
        citation_chunk_id="usgs-2021-001-ch-0001",
    )
    assert claim.verification_status == VerificationStatus.UNRESOLVED
    assert claim.requires_expert_review is False


def test_configuration_snapshot_has_hash() -> None:
    """ConfigurationSnapshot must carry a non-empty hash string."""
    snap = ConfigurationSnapshot(
        stage="chunking",
        parameters={"boundary_aware": True, "max_tokens": 400},
        hash=sha256_str("{}"),
    )
    assert len(snap.hash) == 64


def test_evaluation_metrics_defaults_are_zero() -> None:
    """EvaluationMetrics must initialise all numeric fields to zero."""
    metrics = EvaluationMetrics()
    assert metrics.retrieval.recall_at_5 == 0.0
    assert metrics.causal_attribution.root_cause_localization_accuracy == 0.0
    assert metrics.operational.p95_latency_ms == 0.0
