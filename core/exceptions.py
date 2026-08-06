"""Application-wide exception hierarchy."""

from typing import Any


class BaseError(Exception):
    """Root exception for all Veriducta errors.

    Every raised exception should subclass this so callers can catch the full
    hierarchy with a single ``except BaseError`` clause when needed.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "VERIDUCTA_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details: dict[str, Any] = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigurationError(BaseError):
    """Raised when the application configuration is invalid or incomplete."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class ValidationError(BaseError):
    """Raised when input data fails schema or business-rule validation."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details or {})
        if field:
            self.details["field"] = field


# ---------------------------------------------------------------------------
# Pipeline errors
# ---------------------------------------------------------------------------


class PipelineError(BaseError):
    """Base class for errors that occur during RAG pipeline execution."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        trace_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="PIPELINE_ERROR", details=details or {})
        if stage:
            self.details["stage"] = stage
        if trace_id:
            self.details["trace_id"] = trace_id


class IngestionError(PipelineError):
    """Raised when the ingestion pipeline fails to parse or store a document."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, stage="ingestion", details=details)
        self.code = "INGESTION_ERROR"


class RetrievalError(PipelineError):
    """Raised when retrieval cannot produce a valid candidate set."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, stage="retrieval", details=details)
        self.code = "RETRIEVAL_ERROR"


class GenerationError(PipelineError):
    """Raised when the generator fails to produce a valid structured answer."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, stage="generation", details=details)
        self.code = "GENERATION_ERROR"


class VerificationError(PipelineError):
    """Raised when the verification stage encounters an unrecoverable error."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, stage="verification", details=details)
        self.code = "VERIFICATION_ERROR"


class ReplayError(PipelineError):
    """Raised when the causal replay engine cannot execute an ablation."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, stage="replay", details=details)
        self.code = "REPLAY_ERROR"


# ---------------------------------------------------------------------------
# Storage errors
# ---------------------------------------------------------------------------


class StorageError(BaseError):
    """Base class for errors from any storage backend."""

    def __init__(
        self,
        message: str,
        *,
        backend: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="STORAGE_ERROR", details=details or {})
        if backend:
            self.details["backend"] = backend


class VectorStoreError(StorageError):
    """Raised when Qdrant operations fail."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, backend="qdrant", details=details)
        self.code = "VECTOR_STORE_ERROR"


class ObjectStoreError(StorageError):
    """Raised when MinIO / S3 operations fail."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, backend="minio", details=details)
        self.code = "OBJECT_STORE_ERROR"


# ---------------------------------------------------------------------------
# Not-found helpers
# ---------------------------------------------------------------------------


class NotFoundError(BaseError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        resource: str,
        identifier: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"{resource} not found: {identifier!r}",
            code="NOT_FOUND",
            details=details or {},
        )
        self.details["resource"] = resource
        self.details["identifier"] = identifier
