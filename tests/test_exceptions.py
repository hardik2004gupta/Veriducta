"""Tests for the exception hierarchy."""

from core.exceptions import (
    BaseError,
    ConfigurationError,
    GenerationError,
    IngestionError,
    NotFoundError,
    ObjectStoreError,
    PipelineError,
    ReplayError,
    RetrievalError,
    StorageError,
    ValidationError,
    VectorStoreError,
    VerificationError,
)


def test_base_error_attributes() -> None:
    err = BaseError("something failed", code="TEST_CODE", details={"key": "val"})
    assert str(err) == "something failed"
    assert err.code == "TEST_CODE"
    assert err.details == {"key": "val"}


def test_configuration_error_is_base_error() -> None:
    err = ConfigurationError("bad config")
    assert isinstance(err, BaseError)
    assert err.code == "CONFIGURATION_ERROR"


def test_validation_error_captures_field() -> None:
    err = ValidationError("invalid value", field="chunk_size")
    assert err.details["field"] == "chunk_size"
    assert err.code == "VALIDATION_ERROR"


def test_pipeline_error_captures_stage() -> None:
    err = PipelineError("pipeline failed", stage="retrieval")
    assert err.details["stage"] == "retrieval"


def test_ingestion_error_is_pipeline_error() -> None:
    err = IngestionError("parse failed")
    assert isinstance(err, PipelineError)
    assert err.code == "INGESTION_ERROR"


def test_retrieval_error() -> None:
    err = RetrievalError("no candidates")
    assert isinstance(err, PipelineError)
    assert err.code == "RETRIEVAL_ERROR"


def test_generation_error() -> None:
    err = GenerationError("schema mismatch")
    assert isinstance(err, PipelineError)
    assert err.code == "GENERATION_ERROR"


def test_verification_error() -> None:
    err = VerificationError("nli failed")
    assert isinstance(err, PipelineError)


def test_replay_error() -> None:
    err = ReplayError("ablation crashed")
    assert isinstance(err, PipelineError)


def test_storage_error_is_base_error() -> None:
    err = StorageError("disk full", backend="qdrant")
    assert isinstance(err, BaseError)
    assert err.details["backend"] == "qdrant"


def test_vector_store_error() -> None:
    err = VectorStoreError("upsert failed")
    assert isinstance(err, StorageError)
    assert err.code == "VECTOR_STORE_ERROR"


def test_object_store_error() -> None:
    err = ObjectStoreError("bucket missing")
    assert isinstance(err, StorageError)
    assert err.code == "OBJECT_STORE_ERROR"


def test_not_found_error() -> None:
    err = NotFoundError("Document", "usgs-2021-001")
    assert isinstance(err, BaseError)
    assert err.code == "NOT_FOUND"
    assert "usgs-2021-001" in str(err)
    assert err.details["resource"] == "Document"
