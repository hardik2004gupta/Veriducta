"""Typed application configuration via Pydantic Settings."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment identifier."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class APISettings(BaseSettings):
    """FastAPI server configuration."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    reload: bool = Field(default=False)
    cors_origins: list[str] = Field(default=["*"])

    model_config = SettingsConfigDict(env_prefix="API_")


class AnthropicSettings(BaseSettings):
    """Anthropic API configuration."""

    api_key: str = Field(default="")
    model: str = Field(default="claude-sonnet-4-6")
    max_tokens: int = Field(default=2048, ge=1)
    max_retries: int = Field(default=2, ge=0)

    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_")


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""

    host: str = Field(default="localhost")
    port: int = Field(default=6333, ge=1, le=65535)
    collection_name: str = Field(default="veriducta_chunks")
    grpc_port: int = Field(default=6334)
    prefer_grpc: bool = Field(default=False)

    model_config = SettingsConfigDict(env_prefix="QDRANT_")


class MinIOSettings(BaseSettings):
    """MinIO / S3-compatible object storage configuration."""

    endpoint: str = Field(default="localhost:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    bucket: str = Field(default="veriducta")
    secure: bool = Field(default=False)

    model_config = SettingsConfigDict(env_prefix="MINIO_")


class IngestionSettings(BaseSettings):
    """Ingestion pipeline configuration."""

    corpus_dir: str = Field(default="corpus")
    sidecar_dir: str = Field(default="corpus/sidecars")
    bm25_index_path: str = Field(default="corpus/bm25_index.pkl")
    version_graph_path: str = Field(default="corpus/version_graph.json")
    chunking_snapshot_dir: str = Field(default="config/chunking_snapshots")
    embedding_batch_size: int = Field(default=32, ge=1)
    parent_size_tokens: int = Field(default=1500, ge=100)
    child_size_tokens: int = Field(default=300, ge=50)
    child_overlap_tokens: int = Field(default=50, ge=0)
    boundary_aware: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="INGESTION_")


class RetrievalSettings(BaseSettings):
    """Retrieval pipeline configuration."""

    bm25_top_k: int = Field(default=100, ge=1)
    dense_top_k: int = Field(default=100, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    reranker_model_id: str = Field(default="cross-encoder/ms-marco-MiniLM-L-12-v2")
    reranker_input_top_k: int = Field(default=40, ge=1)
    reranker_output_top_k: int = Field(default=8, ge=1)
    embedding_cache_size: int = Field(default=1000, ge=0)
    embedding_cache_ttl_seconds: int = Field(default=3600, ge=1)
    temporal_filtering_enabled: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_")


class GenerationSettings(BaseSettings):
    """Structured generation configuration."""

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    prompt_version: str = Field(default="v1")

    model_config = SettingsConfigDict(env_prefix="GENERATION_")


class VerificationSettings(BaseSettings):
    """NLI entailment and counterevidence configuration."""

    nli_model_id: str = Field(default="cross-encoder/nli-deberta-v3-base")
    counterevidence_top_k: int = Field(default=10, ge=1)
    entailment_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    contradiction_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    contradiction_neutral_max: float = Field(default=0.30, ge=0.0, le=1.0)
    ambiguous_neutral_min: float = Field(default=0.40, ge=0.0, le=1.0)
    ambiguous_contradiction_min: float = Field(default=0.30, ge=0.0, le=1.0)
    ambiguous_contradiction_max: float = Field(default=0.70, ge=0.0, le=1.0)
    min_entities_for_search: int = Field(default=2, ge=1)

    model_config = SettingsConfigDict(env_prefix="VERIFICATION_")


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry, Prometheus, and evidence log configuration."""

    otlp_endpoint: str = Field(default="http://localhost:4317")
    prometheus_port: int = Field(default=8000, ge=1, le=65535)
    service_name: str = Field(default="veriducta")
    service_version: str = Field(default="1.0.0")
    evidence_log_dir: str = Field(default="evidence_logs")
    sqlite_index_path: str = Field(default="evidence_logs/index.db")
    rotation_size_mb: float = Field(default=0.0, ge=0.0, description="0 disables size rotation.")
    retention_days: int = Field(default=30, ge=1)
    sampling_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(env_prefix="OTLP_", extra="ignore")


class LoggingSettings(BaseSettings):
    """Structured logging configuration."""

    level: str = Field(default="INFO")
    format: str = Field(default="json")
    include_caller: bool = Field(default=True)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"Log level must be one of {valid}, got {v!r}")
        return upper

    model_config = SettingsConfigDict(env_prefix="LOG_")


class ReplaySettings(BaseSettings):
    """Causal replay engine configuration."""

    golden_qa_path: str = Field(default="data/golden/golden_qa.jsonl")
    corruptions_path: str = Field(default="data/synthetic/corruptions.jsonl")
    chunking_failure_corpus_dir: str = Field(default="corpus/chunking_variants")
    quality_delta_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    reranker_cutoffs: list[int] = Field(default=[1, 3, 5, 8])
    max_concurrent_replays: int = Field(default=1, ge=1)
    cache_enabled: bool = Field(default=True)
    cache_max_size: int = Field(default=100, ge=0)

    model_config = SettingsConfigDict(env_prefix="REPLAY_")


class DatasetSettings(BaseSettings):
    """Dataset build and validation configuration."""

    dataset_dir: str = Field(default="data")
    golden_qa_path: str = Field(default="data/golden/golden_qa.jsonl")
    corruptions_path: str = Field(default="data/synthetic/corruptions.jsonl")
    annotation_schema_path: str = Field(default="data/annotations/annotation_schema.json")
    export_dir: str = Field(default="data/exports")
    expected_golden_count: int = Field(default=40, ge=1)
    expected_corruptions_count: int = Field(default=60, ge=1)

    model_config = SettingsConfigDict(env_prefix="DATASET_")


class EvaluationSettings(BaseSettings):
    """Evaluation harness configuration - parallelism, thresholds, output paths."""

    report_dir: str = Field(default="evaluation_reports")
    baseline_metrics_path: str = Field(default="ci_baseline.json")
    top_k: int = Field(default=8, ge=1)
    batch_size: int = Field(default=4, ge=1)
    parallelism: int = Field(default=1, ge=1)
    cache_enabled: bool = Field(default=True)

    # Regression thresholds (CLAUDE.md Phase 18 - five blocking conditions)
    faithfulness_drop_max: float = Field(default=0.02, ge=0.0, le=1.0)
    recall5_drop_max: float = Field(default=0.03, ge=0.0, le=1.0)
    p95_latency_increase_max: float = Field(default=0.20, ge=0.0)
    root_cause_drop_max: float = Field(default=0.05, ge=0.0, le=1.0)
    evidence_exposure_max: float = Field(default=0.0, ge=0.0, le=1.0)

    # Metric quality thresholds from spec
    min_root_cause_accuracy: float = Field(default=0.70, ge=0.0, le=1.0)
    min_realistic_boundary_accuracy: float = Field(default=0.65, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(env_prefix="EVALUATION_")


class Settings(BaseSettings):
    """Root application settings aggregating all sub-configurations."""

    env: Environment = Field(default=Environment.DEVELOPMENT)

    api: APISettings = Field(default_factory=APISettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    replay: ReplaySettings = Field(default_factory=ReplaySettings)
    dataset: DatasetSettings = Field(default_factory=DatasetSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)

    model_config = SettingsConfigDict(
        env_prefix="VERIDUCTA_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_development(self) -> bool:
        """True when running in development mode."""
        return self.env == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """True when running under the test suite."""
        return self.env == Environment.TESTING

    @property
    def is_production(self) -> bool:
        """True when running in production."""
        return self.env == Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
