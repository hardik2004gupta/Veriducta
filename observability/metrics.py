"""Prometheus metric definitions for all pipeline stages.

Metric instances are module-level singletons; they must be registered once
at process startup. Concrete collectors are wired up in Phase 4.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Ingestion metrics
# ---------------------------------------------------------------------------

DOCUMENTS_INGESTED = Counter(
    "veriducta_documents_ingested_total",
    "Total number of documents successfully ingested.",
    ["document_type"],
)

CHUNKS_CREATED = Counter(
    "veriducta_chunks_created_total",
    "Total number of chunks created during ingestion.",
    ["chunking_variant"],
)

INGESTION_ERRORS = Counter(
    "veriducta_ingestion_errors_total",
    "Total number of ingestion errors.",
    ["error_type"],
)

# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------

RETRIEVAL_LATENCY = Histogram(
    "veriducta_retrieval_latency_ms",
    "End-to-end retrieval latency in milliseconds.",
    buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

BM25_RETRIEVAL_LATENCY = Histogram(
    "veriducta_bm25_retrieval_latency_ms",
    "BM25 retrieval latency in milliseconds.",
    buckets=[5, 10, 25, 50, 100, 250, 500],
)

DENSE_RETRIEVAL_LATENCY = Histogram(
    "veriducta_dense_retrieval_latency_ms",
    "Dense (vector) retrieval latency in milliseconds.",
    buckets=[50, 100, 250, 500, 1000, 2500],
)

RERANKER_LATENCY = Histogram(
    "veriducta_reranker_latency_ms",
    "Cross-encoder reranker latency in milliseconds.",
    buckets=[100, 250, 500, 1000, 2500, 5000],
)

EMBEDDING_CACHE_HITS = Counter(
    "veriducta_embedding_cache_hits_total",
    "Query embedding cache hits.",
)

EMBEDDING_CACHE_MISSES = Counter(
    "veriducta_embedding_cache_misses_total",
    "Query embedding cache misses.",
)

TEMPORAL_FILTER_REJECTIONS = Counter(
    "veriducta_temporal_filter_rejections_total",
    "Chunks rejected by the temporal validity filter.",
    ["rejection_reason"],
)

# ---------------------------------------------------------------------------
# Generation metrics
# ---------------------------------------------------------------------------

GENERATION_LATENCY = Histogram(
    "veriducta_generation_latency_ms",
    "LLM generation latency in milliseconds.",
    buckets=[500, 1000, 2000, 4000, 8000, 16000],
)

GENERATION_TOKENS_INPUT = Counter(
    "veriducta_generation_tokens_input_total",
    "Total input tokens consumed by the generator.",
)

GENERATION_TOKENS_OUTPUT = Counter(
    "veriducta_generation_tokens_output_total",
    "Total output tokens produced by the generator.",
)

GENERATION_COST_USD = Counter(
    "veriducta_generation_cost_usd_total",
    "Cumulative estimated generation cost in USD.",
)

SCHEMA_VALIDATION_RETRIES = Counter(
    "veriducta_schema_validation_retries_total",
    "Number of schema validation retries required.",
)

GENERATION_FAILURES = Counter(
    "veriducta_generation_failures_total",
    "Queries that failed generation after all retries.",
)

# ---------------------------------------------------------------------------
# Verification metrics
# ---------------------------------------------------------------------------

CLAIMS_VERIFIED = Counter(
    "veriducta_claims_verified_total",
    "Total claims processed by the NLI entailment checker.",
    ["verification_status"],
)

EXPERT_REVIEW_FLAGS = Counter(
    "veriducta_expert_review_flags_total",
    "Answers flagged for expert review.",
)

# ---------------------------------------------------------------------------
# Replay metrics
# ---------------------------------------------------------------------------

REPLAY_ABLATIONS_RUN = Counter(
    "veriducta_replay_ablations_total",
    "Total ablation runs executed by the replay engine.",
    ["stage"],
)

ROOT_CAUSE_ATTRIBUTED = Counter(
    "veriducta_root_cause_attributed_total",
    "Root causes attributed by the replay engine.",
    ["root_cause_stage"],
)

# ---------------------------------------------------------------------------
# Pipeline health
# ---------------------------------------------------------------------------

ACTIVE_REQUESTS = Gauge(
    "veriducta_active_requests",
    "Number of requests currently being processed.",
)

PIPELINE_UP = Gauge(
    "veriducta_pipeline_up",
    "1 if all pipeline components are healthy, 0 otherwise.",
)
