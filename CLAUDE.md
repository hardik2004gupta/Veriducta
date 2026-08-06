# CLAUDE.md — Veriducta Engineering Specification

**Authoritative reference for all Claude Code sessions working on this repository.**

Every session MUST read this file in full before making any changes.

---

## 1. Project Overview

### What Veriducta Is

Veriducta is a RAG pipeline observability tool that answers one question no existing tool can:
**given a failed answer, which pipeline stage caused the failure, and by how much?**

It builds a production-quality RAG pipeline over a corpus of 30–50 public engineering and
geoscience documents, instruments every stage with full causal traceability, and implements a
four-stage gold ablation engine capable of attributing answer degradation to a specific pipeline
stage (chunking, retrieval, reranking, or generation).

### MVP Objective

Demonstrate three things simultaneously:

1. The full pipeline runs end-to-end over a real document corpus and produces structured,
   claim-level answers with per-claim citation and NLI entailment verification.
2. The causal replay engine correctly identifies the root-cause stage on a 60-case synthetic
   corruption benchmark with ≥ 0.70 overall accuracy and ≥ 0.65 on realistic boundary-error cases.
3. Every metric in the reliability scorecard is computed, reproducible, and compared against a
   RAGAS baseline — including four metrics RAGAS cannot compute.

### Core Innovation

Veriducta stores a **complete, replayable trace** of every retrieval decision — BM25 scores,
dense scores, RRF ranks, the full pre-reranking top-40 candidate list with scores, temporal filter
decisions — so the replay engine can test counterfactuals without re-running expensive inference.
This is what makes causal attribution possible without an oracle.

### Success Criteria (from spec)

- Root-cause localization accuracy ≥ 0.70 overall, ≥ 0.65 on realistic boundary-error subset.
- At least one chunking corruption case correctly attributed to chunking by Stage 1 ablation.
- Evaluation scorecard shows ≥ 4 metrics RAGAS does not compute:
  omission rate, causal attribution accuracy, temporal-valid retrieval rate,
  contradiction acknowledgment rate.
- CI regression gate passes on final codebase and fails when a deliberate regression is injected.
- Technical blog post contains a worked example with a real attribution report showing a chunking
  failure that scored above 0.80 on RAGAS faithfulness but was correctly identified as materially
  incomplete by Veriducta.

---

## 2. High-Level Architecture

```
┌───────────────────────────────────────────────────────────┐
│  Layer 8 — API (api/)                                     │
│  FastAPI application factory, HTTP routing, middleware     │
├───────────────────────────────────────────────────────────┤
│  Layer 7 — Evaluation (evaluation/)                       │
│  Evaluation runner, metrics computation, RAGAS baseline,  │
│  regression gate, evaluation report writer                │
├───────────────────────────────────────────────────────────┤
│  Layer 6 — Causal Replay (replay/)                        │
│  Four-stage gold ablation, heuristic span attribution,    │
│  synthetic corruption runner                              │
├───────────────────────────────────────────────────────────┤
│  Layer 5 — Verification (verification/)                   │
│  Claim-level NLI entailment checking, counterevidence     │
│  retrieval, VerificationReport assembly                   │
├───────────────────────────────────────────────────────────┤
│  Layer 4 — Generation (generation/)                       │
│  Claude Sonnet 4.6 structured generation, JSON schema     │
│  enforcement, generation trace logging                    │
├───────────────────────────────────────────────────────────┤
│  Layer 3 — Retrieval (retrieval/)                         │
│  BM25 + dense hybrid retrieval, RRF fusion, temporal      │
│  filtering, cross-encoder reranking, parent-child          │
│  expansion, TraceableRetriever                            │
├───────────────────────────────────────────────────────────┤
│  Layer 2 — Ingestion (ingestion/)                         │
│  PDF parsing, hierarchical chunking, embedding,           │
│  Qdrant upsert, version graph, BM25 index                 │
├───────────────────────────────────────────────────────────┤
│  Layer 1 — Foundation                                     │
│  config/ · core/ · schemas/ · utils/ · storage/           │
│  observability/ · models/                                 │
└───────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

**Foundation (`config/`, `core/`, `schemas/`, `utils/`, `storage/`, `observability/`, `models/`)**
Typed configuration, exception hierarchy, abstract interfaces, shared Pydantic schemas,
stateless utilities, storage abstractions, Prometheus metric definitions, OpenTelemetry setup.
No business logic. No pipeline logic. Pure infrastructure.

**Ingestion (`ingestion/`)**
Owns document lifecycle from raw PDF to indexed chunk. Responsible for: PDF text extraction
(PyMuPDF + pdfplumber), hierarchical parent-child chunking with configurable section boundary
detection, stable chunk ID assignment, metadata sidecar validation, dense embedding via
BAAI/bge-large-en-v1.5, Qdrant collection upsert, BM25 index construction (rank-bm25),
version graph construction (networkx), chunking configuration snapshot serialisation.

**Retrieval (`retrieval/`)**
Owns candidate selection from the indexed corpus. Responsible for: BM25 retrieval (top-100),
dense retrieval with Qdrant (top-100), RRF fusion, temporal validity filtering against the version
graph, cross-encoder reranking (cross-encoder/ms-marco-MiniLM-L-12-v2, top-40 input → top-8),
parent-child context expansion, complete retrieval trace logging to the evidence log.

**Generation (`generation/`)**
Owns structured answer production. Responsible for: Claude Sonnet 4.6 API calls, system prompt
management, JSON output schema enforcement with up to 2 retries, per-claim citation validation,
input/output token logging, generation trace linking to retrieval trace.

**Verification (`verification/`)**
Owns claim integrity checking. Responsible for: NLI entailment checking via
cross-encoder/nli-deberta-v3-base (3-class heuristic: supported/contradicted/ambiguous-conditional),
5-step counterevidence retrieval using entity-expanded contrastive BM25 queries,
VerificationReport assembly, expert-review flagging.

**Causal Replay (`replay/`)**
Owns root-cause attribution. Responsible for: four-stage gold ablation (Stage 1 chunking,
Stage 2 retrieval, Stage 3 reranker, Stage 4 generation), heuristic span attribution signals,
synthetic corruption runner over the 60-case benchmark.

**Evaluation (`evaluation/`)**
Owns metric computation and regression gating. Responsible for: running all 40 gold questions
through the pipeline, running all 60 corruption cases through the replay engine, computing the
complete reliability scorecard, RAGAS baseline comparison, evaluation report JSON/text output,
CI regression gate execution.

**Observability (`observability/`)**
Owns instrumentation. Responsible for: Prometheus metric definitions (module-level singletons),
OpenTelemetry tracer configuration, evidence log JSONL writer with gzip rotation, SQLite index
for O(1) trace lookup, structlog configuration.

**API (`api/`)**
Owns HTTP surface. Responsible for: FastAPI application factory, lifespan management,
middleware registration (CORS, request-ID stamping), global exception handlers,
health and version endpoints, dependency injection wiring. No business logic in route handlers.

---

## 3. Repository Structure

```
veriducta/
├── api/                 HTTP entry point
├── config/              Typed settings
├── core/                Domain core (exceptions, interfaces, logging)
├── storage/             Storage abstractions
├── schemas/             Shared Pydantic models
├── models/              ML model wrappers (Phase 5+)
├── utils/               Stateless utilities
├── ingestion/           Phase 1–6 pipeline
├── retrieval/           Phase 7–10 pipeline
├── generation/          Phase 11–13 pipeline
├── verification/        Phase 11–13 pipeline
├── replay/              Phase 17 pipeline
├── evaluation/          Phase 18 pipeline
├── observability/       Metrics, tracing, evidence log
├── scripts/             CLI entry points
├── tests/               pytest test suite
├── docs/                Skeleton documentation
├── docker/              Infrastructure configs
├── .github/workflows/   GitHub Actions CI
└── data/                Corpus data (Phase 1+, git-ignored)
```

### Per-Directory Rules

#### `api/`

| Field | Value |
|---|---|
| **Purpose** | HTTP interface — routing, middleware, DI, exception mapping |
| **Phase created** | 0 |
| **Owner** | Stable across all phases |
| **Allowed imports** | `config`, `core`, `schemas`, `observability` (cross-cutting) |
| **Forbidden imports** | `ingestion`, `retrieval`, `generation`, `verification`, `replay`, `evaluation` |
| **Rule** | Route handlers must be thin. All business logic lives in pipeline packages. |

#### `config/`

| Field | Value |
|---|---|
| **Purpose** | Typed, immutable application configuration via Pydantic Settings |
| **Phase created** | 0 |
| **Allowed imports** | `pydantic`, `pydantic_settings` only |
| **Forbidden imports** | All application packages |
| **Rule** | Settings are loaded once at startup (`get_settings()` is `lru_cache`d). Never mutate settings at runtime. |

#### `core/`

| Field | Value |
|---|---|
| **Purpose** | Domain primitives: exception hierarchy, abstract interfaces, logging setup |
| **Phase created** | 0 |
| **Allowed imports** | `config` (logging only) |
| **Forbidden imports** | All other application packages |
| **Rule** | No concrete implementations. No business logic. `interfaces.py` uses `Any` for return types until Phase 1 defines concrete types. |

#### `schemas/`

| Field | Value |
|---|---|
| **Purpose** | Shared Pydantic data-transfer objects and domain value types |
| **Phase created** | 0 |
| **Allowed imports** | `pydantic`, stdlib only |
| **Forbidden imports** | All application packages |
| **Rule** | No business logic in schemas. No methods beyond Pydantic validators. |

#### `utils/`

| Field | Value |
|---|---|
| **Purpose** | Pure stateless helper functions |
| **Phase created** | 0 |
| **Modules** | `hashing`, `ids`, `timers`, `filesystem`, `serialization`, `datetime_utils`, `retry` |
| **Allowed imports** | stdlib, `orjson`, `tenacity`, `pydantic` (serialization only) |
| **Forbidden imports** | All application packages |
| **Rule** | Every function must be pure (no side effects) except `filesystem.py` and `retry.py`. |

#### `storage/`

| Field | Value |
|---|---|
| **Purpose** | Storage backend abstractions; re-exports `BaseStorage` |
| **Phase created** | 0 |
| **Allowed imports** | `core` (for `BaseStorage`) |
| **Concrete implementations** | Qdrant client (Phase 5), MinIO client (Phase 5), SQLite evidence log (Phase 14) |

#### `models/`

| Field | Value |
|---|---|
| **Purpose** | ML model wrappers (embedding, NLI cross-encoder) |
| **Phase created** | 5 (embedding), 12 (NLI) |
| **Allowed imports** | `schemas`, `utils`, `core`, `config`, `sentence_transformers` |
| **Rule** | Each model is loaded once at module level (or via singleton pattern). No model loading inside request handlers. |

#### `observability/`

| Field | Value |
|---|---|
| **Purpose** | Prometheus metrics, OpenTelemetry tracing, evidence log |
| **Phase created** | 0 (metric definitions), 14 (evidence log wiring) |
| **Allowed imports** | `prometheus_client`, `opentelemetry`, `config`, `schemas`, `utils` |
| **Forbidden imports** | `ingestion`, `retrieval`, `generation`, `replay`, `evaluation` |
| **Rule** | Observability must be non-invasive. Pipeline code calls observability; observability never calls pipeline code. |

#### `ingestion/`

| Field | Value |
|---|---|
| **Purpose** | Document parsing, chunking, embedding, version graph, BM25 index, Qdrant upsert |
| **Phase created** | 1–6 |
| **Allowed imports** | `schemas`, `utils`, `core`, `config`, `models`, `storage`, `observability` |
| **Forbidden imports** | `retrieval`, `generation`, `verification`, `replay`, `evaluation`, `api` |

#### `retrieval/`

| Field | Value |
|---|---|
| **Purpose** | BM25 + dense hybrid retrieval, RRF, temporal filter, reranker, expander |
| **Phase created** | 7–10 |
| **Allowed imports** | `schemas`, `utils`, `core`, `config`, `models`, `storage`, `observability` |
| **Forbidden imports** | `ingestion`, `generation`, `verification`, `replay`, `evaluation`, `api` |
| **Rule** | Retrieval is read-only. It never writes to Qdrant. |

#### `generation/`

| Field | Value |
|---|---|
| **Purpose** | LLM call, schema enforcement, NLI verification, counterevidence scan |
| **Phase created** | 11–13 |
| **Allowed imports** | `schemas`, `utils`, `core`, `config`, `models`, `retrieval` (for counterevidence BM25), `observability` |
| **Forbidden imports** | `ingestion`, `replay`, `evaluation`, `api` |

#### `verification/`

| Field | Value |
|---|---|
| **Purpose** | Claim verification orchestration (delegates to `generation/entailment.py`) |
| **Phase created** | 11–13 |
| **Allowed imports** | `schemas`, `utils`, `core`, `generation` |
| **Forbidden imports** | `ingestion`, `retrieval`, `replay`, `evaluation`, `api` |

#### `replay/`

| Field | Value |
|---|---|
| **Purpose** | Four-stage ablation engine and synthetic corruption runner |
| **Phase created** | 17 |
| **Allowed imports** | `schemas`, `utils`, `core`, `retrieval`, `generation`, `observability` |
| **Forbidden imports** | `ingestion`, `evaluation`, `api` |
| **Rule** | Replay reads historical traces from the evidence log. It never re-ingests documents. |

#### `evaluation/`

| Field | Value |
|---|---|
| **Purpose** | Evaluation runner, metric computation, RAGAS baseline, regression gate |
| **Phase created** | 18 |
| **Allowed imports** | `schemas`, `utils`, `core`, `retrieval`, `generation`, `verification`, `replay`, `observability` |
| **Forbidden imports** | `ingestion`, `api` |

#### `scripts/`

| Field | Value |
|---|---|
| **Purpose** | CLI entry points that orchestrate pipeline operations |
| **Phase created** | 1+ |
| **Allowed imports** | All application packages |
| **Rule** | Scripts are thin wrappers. Logic lives in pipeline packages. |

---

## 4. Engineering Principles

### SOLID

- **Single Responsibility**: Each module and class has exactly one reason to change.
  `ingestion/chunker.py` only chunks. `ingestion/embedder.py` only embeds.
- **Open/Closed**: Extend via new implementations of abstract interfaces, not by modifying
  existing pipeline code.
- **Liskov Substitution**: All concrete implementations of `BaseRetriever`, `BaseGenerator`,
  etc. must be interchangeable without breaking callers.
- **Interface Segregation**: `BaseParser` is separate from `BaseChunker`. No fat interfaces.
- **Dependency Inversion**: High-level modules (API, orchestrators) depend on abstractions
  (`BaseRetriever`, `BaseGenerator`). Concrete implementations are injected.

### Composition Over Inheritance

Prefer composing small single-purpose objects. The `VeriductaRetriever` composes
`BM25Retriever`, `DenseRetriever`, `RRFusion`, `TemporalFilter`, `CrossEncoderReranker`,
and `ParentChildExpander` — it does not inherit from any of them.

### Dependency Injection

Pipeline components receive their collaborators as constructor arguments. FastAPI route
handlers receive settings and clients via `Depends()`. Nothing reaches for global singletons
inside business logic (exception: `get_settings()` in infrastructure code, `observability/metrics.py`
module-level Prometheus singletons).

### Immutable Configuration

`Settings` is constructed once at startup via `get_settings()` (`lru_cache(maxsize=1)`).
Pipeline steps receive configuration as `ConfigurationSnapshot` objects — immutable, hashable,
serialisable. Configuration snapshots are hashed at creation time. Never pass mutable config dicts
through pipeline boundaries.

### Pure Functions

All functions in `utils/` are pure unless otherwise noted (`filesystem.py`, `retry.py`).
Hashing, ID generation, serialisation, and datetime operations have no side effects.

### Typed APIs

All public functions and class methods have complete type annotations.
`mypy --strict` must pass at all times. `Any` is permitted only in serialisation utilities,
abstract interfaces (where concrete types are undefined in the current phase), and
JSON helpers.

### Small, Cohesive Modules

Each `.py` file owns one concept. A 200-line file is a sign of good design. A 600-line file
is a warning to split. No omnibus utility files.

### No Hidden Global State

Module-level state is permitted only for:
- Prometheus metric singletons (`observability/metrics.py`)
- `lru_cache`d settings (`config/settings.py`)
- Loaded ML models (one per model class, never re-loaded)

Everything else is explicit.

### Explicit Interfaces

Every abstract interface is in `core/interfaces.py`. Every concrete implementation declares its
interface in its class signature (e.g., `class VeriductaRetriever(BaseRetriever)`).
Duck typing is not used for cross-module boundaries.

---

## 5. Coding Standards

### Type Hints

```python
# Always use built-in generics (Python 3.12+)
def process(items: list[str]) -> dict[str, int]: ...


# Use | for unions
def find(id: str) -> Chunk | None: ...


# Use from __future__ import annotations in schema files only
```

### Docstrings

Every **public** class and function requires a docstring.
Format:
```python
def embed(self, texts: list[str]) -> list[list[float]]:
    """Return dense vector embeddings for a batch of texts.

    Args:
        texts: Non-empty list of strings to embed.

    Returns:
        List of float vectors, one per input text, in the same order.

    Raises:
        VectorStoreError: If the embedding model is unavailable.
    """
```

Private helpers (`_`) and test functions do not require docstrings.

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Module | `snake_case` | `bm25_retriever.py` |
| Class | `PascalCase` | `VeriductaRetriever` |
| Function/method | `snake_case` | `retrieve_candidates()` |
| Constant | `UPPER_SNAKE` | `RETRIEVAL_LATENCY` |
| Private method | `_snake_case` | `_apply_temporal_filter()` |
| TypeVar | Short uppercase | `F`, `T` |

### File Organisation

Standard module layout:
```
"""Module docstring."""

# stdlib imports
# third-party imports
# first-party imports (alphabetical, separated by blank line per group)

# Constants / module-level singletons

# Classes (interfaces first, concrete second)

# Module-level functions

# Private helpers
```

### Import Ordering

Enforced by `ruff --select I`. Groups (separated by blank lines):
1. `__future__`
2. stdlib
3. third-party
4. first-party (application packages)

Within groups: alphabetical.

### Logging

**Never use `print()`.** All output goes through structlog:

```python
import structlog

logger = structlog.get_logger(__name__)

# Bind context for the duration of an operation
logger.info("retrieval_started", query_hash=query_hash, top_k=top_k)
logger.warning("temporal_filter_rejected", chunk_id=chunk_id, reason=reason)
logger.error("generation_failed", trace_id=trace_id, attempts=retries)
```

Use lowercase snake_case event names. Attach structured key-value pairs. Never format
strings into the event name.

### Error Handling

Raise specific exceptions from `core/exceptions.py`. Never raise bare `Exception`.
Never swallow exceptions silently. If an exception must be caught and re-raised, always
re-raise the original or wrap it:

```python
try:
    result = qdrant_client.upsert(...)
except QdrantException as exc:
    raise VectorStoreError(f"Upsert failed for {collection}") from exc
```

### Testing

- Test file naming: `tests/test_{module_name}.py`
- Test function naming: `test_{what}_{condition}_{expected_outcome}()`
- One assertion per logical outcome (multiple `assert` statements are fine for the same scenario)
- Use `pytest.raises` for exception testing
- No `try/except` in tests
- Coverage target: 80% minimum (abstract interfaces, OTel, and Prometheus metric definitions
  are excluded from the coverage report)

### Formatting

Line length: 100 characters. Enforced by `ruff` and `black` (both configured in `pyproject.toml`).
Run `make format` before every commit.

---

## 6. Dependency Rules

### Dependency Graph

```
schemas ──────────────────────────────────────────────┐
utils  ──────────────────────────────────────────────┐│
config ────────────────────────────────────────────┐ ││
                                                   │ ││
core ───(imports config) ──────────────────────────┤ ││
storage ──(imports core) ──────────────────────────┤ ││
                                                   ▼ ▼▼
models ─────────────────────────────────────────► ingestion
                                                       │
observability ─────────────────────────────────────────┤
                                                       ▼
                                                  retrieval
                                                       │
                                                       ▼
                                                  generation
                                                       │
                                                       ▼
                                               verification
                                                       │
                                                       ▼
                                                    replay
                                                       │
                                                       ▼
                                                  evaluation
                                                       │
                                                       ▼
                                                      api
```

### Strict Rules

1. `schemas` and `utils` have **zero** imports from any application package.
2. `config` has **zero** imports from any application package.
3. `core` imports only `config`.
4. Data flows **downward** only. No layer may import from a layer above it.
5. `api` may import from any layer but contains no business logic.
6. `observability` is a cross-cutting concern — any layer may import it, but it never
   imports pipeline packages.
7. Circular imports are a build error (enforced by `ruff --select I`).

### Circular Import Prevention

- Never import at module level from a sibling that also imports you.
- Use `TYPE_CHECKING` guards for type-only imports if needed:
  ```python
  from __future__ import annotations
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from ingestion.parser import ParsedDocument
  ```

---

## 7. Interface Contracts

All abstract interfaces are defined in `core/interfaces.py`. Concrete implementations
in pipeline packages subclass these.

### `BaseParser`

**Purpose**: Parse a raw PDF into a structured representation.
**Implemented by**: `ingestion.parser.PyMuPDFParser` (Phase 2)
**Methods**:
- `parse(source: str) -> ParsedDocument` — receives absolute file path; returns `ParsedDocument`
  dataclass containing per-page text blocks, linearised tables as Markdown, and page metadata.
- `supports(mime_type: str) -> bool` — returns True for `"application/pdf"`.
**Lifecycle**: Instantiated once per ingestion run. Stateless.

### `BaseChunker`

**Purpose**: Split a `ParsedDocument` into hierarchical `Chunk` objects.
**Implemented by**: `ingestion.chunker.HierarchicalChunker` (Phase 3)
**Methods**:
- `chunk(document: ParsedDocument, config: ChunkingConfig) -> list[Chunk]` — returns ordered
  list of child chunks. Each child carries a `parent_chunk_id` pointing to its parent chunk.
  When `boundary_aware=True`, the chunker never splits a child chunk across a detected section
  boundary. Chunk IDs follow the format `{document_id}-ch-{zero_padded_index}`.
  Parent IDs follow `{document_id}-par-{zero_padded_index}`.
- `snapshot() -> ConfigurationSnapshot` — returns a serialisable, hashed config snapshot.
  Snapshots are stored at `config/chunking_snapshots/{hash}.json`.
**Lifecycle**: Instantiated with a `ChunkingConfig`. Call `snapshot()` before calling `chunk()`.

### `BaseEmbeddingModel`

**Purpose**: Produce dense vector embeddings for text batches.
**Implemented by**: `models.embedding.BGELargeEmbedding` (Phase 5)
**Model**: `BAAI/bge-large-en-v1.5` (dimension: 1024)
**Methods**:
- `embed(texts: list[str]) -> list[list[float]]` — batch size of 32 is the default.
  Query embedding uses the recommended prefix: `"Represent this sentence for searching relevant passages: "`.
- `dimension: int` — property returning 1024.
- `model_id: str` — property returning `"BAAI/bge-large-en-v1.5"`.
**Lifecycle**: Load once at module level. Never reload per-request.

### `BaseRetriever`

**Purpose**: Execute hybrid retrieval and return a fully traced `RetrievalResult`.
**Implemented by**: `retrieval.retriever.VeriductaRetriever` (Phase 10)
**Methods**:
- `retrieve(query, query_date, top_k=8) -> RetrievalResult` — runs BM25 (top-100) + dense
  (top-100) → RRF fusion → temporal filter → cross-encoder reranking (top-40 input, top-8 output)
  → parent-child expansion. Emits OpenTelemetry spans. Writes `RetrievalTrace` to evidence log.
- `get_trace(trace_id: str) -> RetrievalTrace` — O(1) lookup via SQLite index.
- `replay_with_config(trace_id, config_override) -> RetrievalResult` — re-runs retrieval for a
  historical query using an alternative `ConfigurationSnapshot`. Used by Stage 1 and Stage 3
  of the ablation engine.
**Lifecycle**: Instantiated once per application process. Holds references to all sub-components.

### `BaseGenerator`

**Purpose**: Produce a structured, citation-grounded answer from a retrieval context.
**Implemented by**: `generation.generator.VeriductaGenerator` (Phase 11/13)
**Methods**:
- `generate(query, context) -> StructuredAnswer` — calls Claude Sonnet 4.6 (`claude-sonnet-4-6`)
  with `max_tokens=2048`. Validates JSON response against output schema. Retries up to 2 times
  on schema validation failure. Logs tokens, cost, and latency.
- `replay_with_context(query, context_override, config_override) -> StructuredAnswer` — re-runs
  generation with substitute context or configuration. Used by Stage 2 and Stage 4 ablation.
**Lifecycle**: Instantiated once per application process.

### `BaseVerifier`

**Purpose**: Verify all claims in a `StructuredAnswer` and produce a `VerificationReport`.
**Implemented by**: `generation.verifier.VeriductaVerifier` (Phase 13)
**Methods**:
- `verify(answer, retrieval_result) -> VerificationReport` — runs NLI entailment checking on all
  claims, then runs the 5-step counterevidence scan for claims with ≥ 2 key entities.
  Claims with < 2 entities receive `verification_status="not_searched"` with reason
  `"insufficient_entity_signal"`.
**Lifecycle**: Instantiated once per application process.

### `BaseReplayEngine`

**Purpose**: Execute four-stage causal ablation to attribute answer failures.
**Implemented by**: `replay.ablation.VeriductaReplayEngine` (Phase 17)
**Methods**:
- `run_ablation(trace_id, question_id) -> ReplayReport` — executes all four ablation stages
  sequentially. Returns a `ReplayReport` with per-stage quality deltas and a primary root-cause
  label.
- `run_corruption(corruption_case) -> ReplayReport` — executes ablation on a single case from
  `data/synthetic_corruptions/corruptions.jsonl`.
**Lifecycle**: Instantiated once per evaluation run.

### `BaseStorage`

**Purpose**: Generic key-value / object store for arbitrary byte payloads.
**Implemented by**: `storage.minio_storage.MinIOStorage` (Phase 5)
**Methods**:
- `put(key, value, *, content_type)` — store bytes under key.
- `get(key) -> bytes` — retrieve bytes; raises `NotFoundError` if absent.
- `delete(key)` — delete object.
- `exists(key) -> bool` — check existence without fetching payload.
**Lifecycle**: Instantiated once; client connection is pooled.

---

## 8. Shared Models

All shared schemas live in `schemas/models.py`. They are Pydantic `BaseModel` subclasses.
They carry no business logic — only field declarations and Pydantic validators.

### Enumerations

| Enum | Values | Used By |
|---|---|---|
| `VerificationStatus` | `supported`, `contradicted`, `ambiguous_conditional`, `not_searched`, `unresolved` | `Claim`, NLI entailment |
| `ConfidenceTag` | `high`, `medium`, `low`, `uncertain` | `Claim`, generator output |
| `TemporalValidityTag` | `valid`, `superseded`, `not_yet_effective`, `unknown` | `Claim`, temporal filter |
| `FailureMode` | `chunking_boundary`, `retrieval_miss`, `omission`, `temporal_confusion`, `hallucination`, `contradiction`, `none` | Golden QA dataset, corruption benchmark |
| `RootCauseStage` | `chunking`, `retrieval`, `reranking`, `generation`, `unknown` | Replay engine output |

### `DocumentMetadata`

The validated sidecar for a corpus document. Every field has a counterpart in the JSON sidecar
file. The `version_hash` field is the SHA-256 of the raw PDF bytes (use `utils.hashing.sha256_file`).
Required fields: `document_id`, `title`, `source`, `document_type`, `effective_date`,
`version_hash`, `filename`, `page_count`.

### `Document`

Aggregates `DocumentMetadata` with extracted text (`raw_text`) and per-page text list
(`page_texts`). Populated by `BaseParser.parse()` in Phase 2.

### `Chunk`

A single text chunk with:
- `chunk_id`: `{document_id}-ch-{zero_padded_index}` (4-digit zero-padding)
- `parent_chunk_id`: `{document_id}-par-{zero_padded_index}` or `None` for parent chunks
- `token_count`: pre-computed; target 200–400 tokens for child chunks, 1400–1600 for parents
- `is_table`: True for chunks derived from pdfplumber table extraction
- `effective_date` / `expiry_date`: propagated from `DocumentMetadata` for temporal filtering

### `Citation`

Links a claim to its supporting chunk. Contains `chunk_id`, `document_id`, `excerpt`
(verbatim ≤ 50 token snippet), and optional `page_number`.

### `Claim`

A single verifiable assertion. Key fields:
- `citation_chunk_id`: required — points to the primary supporting chunk
- `key_entities`: list of ≥ 2 specific technical terms (required for counterevidence scan)
- `nli_*_probability`: populated by `entailment.py` — never populated by the generator
- `requires_expert_review`: set to `True` if any claim is `contradicted` or
  `ambiguous_conditional`

### `RetrievalCandidate`

Carries all scores through the retrieval pipeline. Score fields may be `None` if the candidate
was absent from a particular retrieval list (e.g., absent from BM25 results but present in dense).

### `RetrievalResult`

The final output of `BaseRetriever.retrieve()`. Contains `candidates` (top-k after reranking),
`pre_rerank_top40` (full pre-reranking list — essential for Stage 3 replay), and
`temporal_rejections` (for audit).

### `RetrievalTrace` / `GenerationTrace`

Evidence log entries. `GenerationTrace.retrieval_trace_id` links the generation trace to its
parent retrieval trace. Both are written to `evidence_logs/YYYY-MM-DD.jsonl` and indexed
in SQLite.

### `ConfigurationSnapshot`

Immutable, hashable record of pipeline parameters at execution time. The `hash` field is the
SHA-256 of the canonical JSON serialisation (`utils.hashing.sha256_json`). Stored at
`config/{stage}_snapshots/{hash}.json`.

### `EvaluationMetrics`

Aggregates all four metric groups: `RetrievalMetrics`, `AnswerQualityMetrics`,
`CausalAttributionMetrics`, `OperationalMetrics`. Populated by `evaluation/metrics.py` in Phase 18.

---

## 9. Configuration System

### Settings Class Hierarchy

```
Settings                          (env prefix: VERIDUCTA_)
├── APISettings                   (env prefix: API_)
├── AnthropicSettings             (env prefix: ANTHROPIC_)
├── QdrantSettings                (env prefix: QDRANT_)
├── MinIOSettings                 (env prefix: MINIO_)
├── ObservabilitySettings         (env prefix: OTLP_)
└── LoggingSettings               (env prefix: LOG_)
```

### Access Pattern

```python
from config.settings import get_settings

settings = get_settings()  # lru_cache — same object every call
settings.qdrant.host  # "localhost"
settings.anthropic.model  # "claude-sonnet-4-6"
settings.is_testing  # bool property
```

### Environment Variable Precedence (highest to lowest)

1. Shell environment variables (`export ANTHROPIC_API_KEY=sk-ant-...`)
2. `.env` file (loaded by `pydantic-settings`)
3. Default values defined in field declarations

### Nested Variable Syntax

Use double-underscore for nested overrides:
```bash
VERIDUCTA__QDRANT__HOST=qdrant-prod
```

### Environment Selector

```bash
VERIDUCTA_ENV=development   # Default; console logs allowed, docs enabled
VERIDUCTA_ENV=testing       # Used by pytest; OTel disabled, JSON logs
VERIDUCTA_ENV=production    # JSON logs only; docs disabled
```

### Secrets

`ANTHROPIC_API_KEY` is the only secret in Phase 0. Never log it. Never commit it.
Store in `.env` (git-ignored) locally. In CI, use GitHub Secrets → environment variable.

### Testing Overrides

In `tests/conftest.py`:
```python
os.environ.setdefault("VERIDUCTA_ENV", "testing")
```

The `settings.is_testing` property gates OTel export (no-op in testing).

---

## 10. Logging & Observability

### Structured Logging (structlog)

Every module obtains a logger via:
```python
import structlog

logger = structlog.get_logger(__name__)
```

Or via the helper:
```python
from core.logging import get_logger

logger = get_logger(__name__)
```

**Output format**:
- `VERIDUCTA_ENV=development` + `LOG_FORMAT!=json` → human-readable ConsoleRenderer
- All other environments → JSON Lines to stdout

**Standard context keys injected automatically**:
- `service` (from `ObservabilitySettings.service_name`)
- `version` (from `ObservabilitySettings.service_version`)
- `env` (from `Settings.env`)
- `timestamp` (ISO-8601)
- `filename`, `lineno` (when `LOG_INCLUDE_CALLER=true`)

**Request-scoped context keys** (injected by `RequestContextMiddleware`):
- `request_id` (UUID4 per request)
- `trace_id` (from `X-Trace-Id` header or new UUID4)
- `method`, `path`

### OpenTelemetry (Phases 8+)

Configured in `observability/tracing.py`. `configure_tracing()` is called at startup lifespan.
In testing mode, the no-op provider is used (no export overhead).

Span hierarchy (defined in Phase 14):
```
veriducta.query
  ├── veriducta.retrieval
  │   ├── veriducta.retrieval.bm25
  │   ├── veriducta.retrieval.dense
  │   ├── veriducta.retrieval.rrf
  │   ├── veriducta.retrieval.temporal_filter
  │   └── veriducta.retrieval.reranker
  ├── veriducta.generation
  └── veriducta.verification
      ├── veriducta.verification.entailment
      └── veriducta.verification.counterevidence
```

Every span must carry: `config_snapshot_hash`, `input_hash`, `output_hash`, `latency_ms`.

### Prometheus Metrics

Defined as module-level singletons in `observability/metrics.py`. Exposed at `:8000/metrics`
by `prometheus_client` (multi-process mode for production).

Key metric families:
- `veriducta_documents_ingested_total` (counter, label: `document_type`)
- `veriducta_chunks_created_total` (counter, label: `chunking_variant`)
- `veriducta_retrieval_latency_ms` (histogram)
- `veriducta_temporal_filter_rejections_total` (counter, label: `rejection_reason`)
- `veriducta_generation_latency_ms` (histogram)
- `veriducta_generation_tokens_input_total` / `_output_total` (counters)
- `veriducta_generation_cost_usd_total` (counter)
- `veriducta_claims_verified_total` (counter, label: `verification_status`)
- `veriducta_replay_ablations_total` (counter, label: `stage`)
- `veriducta_root_cause_attributed_total` (counter, label: `root_cause_stage`)
- `veriducta_pipeline_up` (gauge)

### Evidence Log

Implemented in Phase 14 at `observability/evidence_log.py`.

Structure:
- Active file: `evidence_logs/YYYY-MM-DD.jsonl` — one JSON Lines entry per query
- Compressed files: `evidence_logs/YYYY-MM-DD.jsonl.gz` after 24 hours
- SQLite index: `evidence_logs/index.db` with schema:
  `(trace_id, log_file, byte_offset, query_hash, created_at, quality_score, flagged_as_failure)`

Retrieval is O(1): read byte offset from SQLite, seek to position in JSONL file.

### Correlation IDs

Every log line and OTel span carries both `request_id` and `trace_id`. The `trace_id` propagates
across the full pipeline so retrieval, generation, and verification spans are linked.
`GenerationTrace.retrieval_trace_id` explicitly links the generation record to its retrieval record.

---

## 11. Error Handling Strategy

### Exception Hierarchy

```
Exception
└── BaseError                     (code, message, details dict)
    ├── ConfigurationError        CONFIGURATION_ERROR
    ├── ValidationError           VALIDATION_ERROR  (+ field)
    ├── NotFoundError             NOT_FOUND  (+ resource, identifier)
    ├── PipelineError             PIPELINE_ERROR  (+ stage, trace_id)
    │   ├── IngestionError        INGESTION_ERROR
    │   ├── RetrievalError        RETRIEVAL_ERROR
    │   ├── GenerationError       GENERATION_ERROR
    │   ├── VerificationError     VERIFICATION_ERROR
    │   └── ReplayError           REPLAY_ERROR
    └── StorageError              STORAGE_ERROR  (+ backend)
        ├── VectorStoreError      VECTOR_STORE_ERROR  (backend=qdrant)
        └── ObjectStoreError      OBJECT_STORE_ERROR  (backend=minio)
```

### Error Propagation Rules

1. Pipeline code raises specific exceptions (`IngestionError`, `RetrievalError`, etc.).
2. Exceptions always include `details` with enough context to diagnose the failure without
   additional lookups.
3. Always use `raise XxxError(...) from original_exc` to preserve the traceback chain.
4. Never catch-all `except Exception` in pipeline code. Catch specific types.
5. The API layer catches `BaseError` subclasses and maps them to HTTP responses.

### HTTP Status Mapping (registered in `api/app.py`)

| Exception | HTTP Status |
|---|---|
| `NotFoundError` | 404 |
| `ValidationError` | 422 |
| Any other `BaseError` | 500 |
| `Exception` (unhandled) | 500 |

### Logging Expectations

- `INFO`: successful operations, pipeline milestones
- `WARNING`: recoverable issues (temporal filter rejections, schema validation retries)
- `ERROR`: non-fatal failures (generation failed after retries, NLI model unavailable)
- `EXCEPTION`: unexpected errors with full traceback (caught by generic handler only)

---

## 12. Testing Strategy

### Test Layout

```
tests/
├── conftest.py            Session-scoped app + TestClient fixtures
├── test_health.py         API endpoint smoke tests
├── test_exceptions.py     Exception hierarchy correctness
├── test_schemas.py        Schema validation and field rules
├── test_utils.py          Core utilities (hashing, IDs, timers, serialisation, datetime)
└── test_utils_extended.py Extended utility coverage
```

### Fixture Strategy

```python
# conftest.py sets VERIDUCTA_ENV=testing before any import
os.environ.setdefault("VERIDUCTA_ENV", "testing")


@pytest.fixture(scope="session")
def app() -> FastAPI: ...  # one app per test session


@pytest.fixture(scope="session")
def client(app) -> TestClient: ...  # synchronous test client
```

Phase-specific fixtures (Qdrant, MinIO, BM25 index) are added to `conftest.py` when
the corresponding phase is implemented. Use `pytest-asyncio` for async tests.

### Mocking Policy

- **Never mock the core pipeline logic** — integration tests must use real pipeline code.
- **Mock external services** (Anthropic API, Qdrant, MinIO) only when testing failure paths
  that cannot be triggered with real services in CI.
- **Use `pytest-mock` or `unittest.mock.patch`** for external API calls in unit tests.
- **Qdrant in tests**: Use the real `qdrant-client` against a local Qdrant instance started
  by Docker Compose. Never use in-memory mocks for Qdrant.

### Coverage Requirements

- Minimum: **80%** (configured in `pyproject.toml`)
- Excluded from coverage:
  - `core/interfaces.py` (abstract — no executable lines)
  - `observability/tracing.py` (requires live OTLP)
  - `observability/metrics.py` (Prometheus singletons — registration-only)

### Test Naming

```python
def test_{what}_{condition}_{expected}() -> None:
    # test_retrieve_superseded_document_returns_empty_candidates
    # test_chunker_boundary_aware_never_splits_across_section
    # test_nli_entailment_contradiction_above_threshold_flags_review
```

### Integration vs. Unit Tests

| Type | Location | Characteristics |
|---|---|---|
| Unit | `tests/test_*.py` | No live services; test a single function or class |
| Integration | `tests/integration/test_*.py` (Phase 1+) | Live Qdrant/MinIO; test full pipeline slice |
| End-to-end | `tests/e2e/test_pipeline.py` (Phase 3+) | Full query → answer → verification |

---

## 13. Git Workflow

### Branch Strategy

```
main                    ← stable; every merge has passing CI
├── phase/1-ingestion   ← one branch per phase
├── phase/2-retrieval
├── feat/description    ← short features off the current phase branch
└── fix/description     ← bug fixes
```

### Commit Style

```
type(scope): short description in imperative mood

Examples:
feat(ingestion): implement boundary-aware hierarchical chunker
fix(retrieval): handle empty BM25 candidate set on sparse queries
test(replay): add ablation accuracy test for chunking corruptions
docs(api): update health endpoint response schema
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

### Merge Requirements

1. CI must pass: ruff, black, mypy, pytest (all green).
2. Coverage must not drop below 80%.
3. Phase exit conditions (from spec / `Veriducta MVP.pdf`) must be documented in the PR.
4. No merge without a passing health check on the feature branch.

### Phase Tagging

After merging each phase branch: `git tag phase-N-complete`

---

## 14. Development Workflow

### Per-Session Claude Code Instructions

Every Claude Code session working on this repository MUST:

1. **Read `CLAUDE.md` in full** before making any changes.
2. **Run `git status`** to understand the current working tree state.
3. **Identify the target phase** from the Phase Roadmap (Section 15).
4. **Read only files relevant to the current task** — do not read the entire repository.
5. **Inspect the existing implementation** before adding anything new.
6. **Never rewrite a working module** — extend it or add a new module.
7. **Never regenerate Phase 0 infrastructure** — the foundation is complete.
8. **Implement only the current phase** — do not skip ahead.

### Before Finishing Any Session

Every session must end by running and verifying all four checks pass:

```bash
make lint       # ruff check .
make format     # ruff format . && black .
make type-check # mypy .
make test       # pytest (must show 60+ tests passing)
```

If any check fails, fix it before stopping. Do not leave the repository in a broken state.

### End-of-Session Report

Every session ends with:
1. **Summary**: what was built or changed (2–3 sentences)
2. **Files changed**: exhaustive list of modified/created files
3. **Tests run**: `X passed, Y failed` from pytest output
4. **Remaining work**: what is next in the Phase Roadmap

---

## 15. Phase Roadmap

**Phase 0** (complete): Engineering foundation — repository structure, FastAPI skeleton,
configuration, interfaces, schemas, utilities, Docker, CI.

---

### Phase 1 — Document Metadata & Sidecar Schema

**Objective**: Define and validate the JSON sidecar format for every corpus document.

**Primary modules**:
- `ingestion/sidecar.py` — sidecar schema, `validate_sidecar()`, file I/O
- `schemas/models.py` — extend `DocumentMetadata` with JSON schema validator

**Expected outputs**:
- `corpus/sidecars/{document_id}.json` for each screened document
- `scripts/validate_sidecars.py` — CLI that validates all sidecars and reports failures
- Unit tests: malformed sidecars rejected, all required fields validated

**Dependencies**: Phase 0

---

### Phase 2 — PDF Parser

**Objective**: Extract structured text and table content from PDF files.

**Primary modules**:
- `ingestion/parser.py` — `PyMuPDFParser(BaseParser)` using `fitz.open()`
- `models/parsed_document.py` — `ParsedDocument` dataclass (page text blocks + linearised tables + metadata)

**Expected outputs**:
- Per-page text extraction preserving page number metadata
- pdfplumber table detection and Markdown linearisation
- Unit tests: text extraction quality on 3 representative corpus documents

**Dependencies**: Phase 1
**New deps**: `PyMuPDF` (`fitz`), `pdfplumber`

---

### Phase 3 — Hierarchical Chunker

**Objective**: Implement boundary-aware parent-child chunking with configuration snapshot.

**Primary modules**:
- `ingestion/chunker.py` — `HierarchicalChunker(BaseChunker)`

**Key specification** (from `Veriducta MVP.pdf`):
- Parent chunks: 1400–1600 tokens assembled at section boundaries
- Child chunks: 200–400 tokens with 50-token overlap
- `boundary_aware=True`: child chunks never split across detected section boundaries
  (if a window would cross a `section_boundary_markers` regex match, it terminates at the boundary)
- Chunk IDs: `{document_id}-ch-{zero_padded_4digit_index}`
- Parent IDs: `{document_id}-par-{zero_padded_4digit_index}`
- Config snapshots: `config/chunking_snapshots/{hash}.json`

**Expected outputs**:
- Chunking failure corpus: 10–15 documents where boundary-aware vs. boundary-naive
  configurations produce different splits at critical clauses
- `corpus/chunking_variants/{document_id}_boundary_map.json` for each failure document
- Unit tests: boundary-aware and boundary-naive produce different splits on controlled input

**Dependencies**: Phase 2

---

### Phase 4 — Version Graph

**Objective**: Build a temporal validity graph over the corpus.

**Primary modules**:
- `ingestion/version_graph.py` — networkx DiGraph

**Key specification**:
- `build_version_graph(sidecar_dir) -> nx.DiGraph`
- `get_valid_documents(query_date: str) -> list[str]`
- `get_superseded_documents(query_date: str) -> list[str]`
- `get_supersession_chain(document_id: str) -> list[str]`
- Serialised to `corpus/version_graph.json` using `networkx.node_link_data()`

**Expected outputs**:
- `corpus/version_graph.json`
- Unit tests: correct `get_valid_documents` output for 3 manually chosen test dates

**Dependencies**: Phase 1
**New deps**: `networkx`

---

### Phase 5 — Embedding Pipeline & Qdrant Upsert

**Objective**: Embed all child chunks and upsert to Qdrant.

**Primary modules**:
- `models/embedding.py` — `BGELargeEmbedding(BaseEmbeddingModel)` wrapping `BAAI/bge-large-en-v1.5`
- `ingestion/embedder.py` — batch embedding (size 32) + Qdrant upsert

**Key specification**:
- Qdrant collection: `veriducta_chunks`, cosine distance, dimension 1024
- Payload schema per chunk: `chunk_id`, `document_id`, `text`, `parent_chunk_id`, `token_count`,
  `is_table`, `effective_date`, `expiry_date`, `chunk_index`, `page_number`
- Spot-check: after upsert, verify 3 known chunks are retrievable by vector similarity

**New deps**: `sentence-transformers`, `qdrant-client`

**Dependencies**: Phases 3, 4

---

### Phase 6 — BM25 Index & Ingestion Orchestrator

**Objective**: Build BM25 index and wire the complete ingestion pipeline.

**Primary modules**:
- `ingestion/bm25_indexer.py` — `rank_bm25.BM25Okapi` over all child chunk texts
- `ingestion/ingestor.py` — orchestrates parse → chunk → embed → upsert → version graph → BM25
- `scripts/ingest_corpus.py` — CLI entry point

**Key specification**:
- BM25 index serialised to `corpus/bm25_index.pkl`
- Ingestion must be idempotent: re-running does not duplicate chunks
- `scripts/ingest_corpus.py` completes without errors on the full corpus

**New deps**: `rank-bm25`
**Dependencies**: Phases 2–5

---

### Phase 7 — BM25 & Dense Retrieval Modules

**Objective**: Implement the two base retrieval components.

**Primary modules**:
- `retrieval/bm25_retriever.py` — loads `corpus/bm25_index.pkl`, tokenises query, returns top-100
  as `list[(chunk_id, bm25_score, bm25_rank)]`
- `retrieval/dense_retriever.py` — loads `BGELargeEmbedding`, implements LRU cache (TTL 1 hour)
  keyed on query hash, queries Qdrant with `limit=100`

**Key specification**:
- BM25 tokeniser must match the tokeniser used at index time (same `rank_bm25` instance)
- Dense query prefix: `"Represent this sentence for searching relevant passages: "`

**Dependencies**: Phases 5, 6

---

### Phase 8 — RRF Fusion & Temporal Filter

**Objective**: Implement score fusion and temporal validity filtering.

**Primary modules**:
- `retrieval/fusion.py` — RRF with `k=60`, formula: `1/(60 + rank)`, implicit rank 101 for absent candidates
- `retrieval/temporal_filter.py` — standalone utility; rejects chunks where `effective_date > query_date`
  or document has a superseding document with `effective_date ≤ query_date`

**Key specification**:
- Rejection reasons: `"not_yet_effective"` or `"superseded"` — must be logged in `RetrievalCandidate.rejection_reason`
- Temporal filter must use the version graph (Phase 4)

**Dependencies**: Phases 4, 7

---

### Phase 9 — Cross-Encoder Reranker & Parent-Child Expander

**Objective**: Implement reranking and context expansion.

**Primary modules**:
- `retrieval/reranker.py` — `cross-encoder/ms-marco-MiniLM-L-12-v2`; batch inference over top-40 RRF candidates
- `retrieval/expander.py` — fetches parent chunk from Qdrant for each of top-8 post-rerank chunks;
  constructs context as `child_chunk_text\n\n[SECTION]\nparent_section_text`

**Key specification**:
- Full pre-reranking top-40 list (with scores) MUST be stored in `RetrievalTrace.pre_rerank_top40`
  — this is what allows Stage 3 ablation without re-running inference
- Reranker returns all 40 with scores and `post_rerank_rank`

**New deps**: `sentence-transformers` (cross-encoder)
**Dependencies**: Phase 8

---

### Phase 10 — TraceableRetriever & Integration Tests

**Objective**: Assemble the complete retrieval pipeline and verify with 5 queries.

**Primary modules**:
- `retrieval/retriever.py` — `VeriductaRetriever(BaseRetriever)` orchestrating all sub-components
- Emit OTel spans for each sub-stage
- Write `RetrievalTrace` to the evidence log (stub in Phase 10; full implementation in Phase 14)
- Implement `replay_with_config()` for counterfactual retrieval

**Expected outputs**:
- 5 integration tests covering: temporal filter exclusion, BM25 exact terminology match,
  dense paraphrase match, reranker re-ordering, trace completeness

**Dependencies**: Phase 9

---

### Phase 11 — Structured Generator & System Prompt

**Objective**: Implement LLM generation with JSON schema enforcement.

**Primary modules**:
- `generation/generator.py` — `VeriductaGenerator(BaseGenerator)`
- `generation/prompts.py` — system prompt (tested on 10 representative contexts; must achieve
  ≥ 9/10 first-try schema compliance before Phase 12 begins)

**Key specification**:
- `max_tokens=2048`, model `claude-sonnet-4-6`
- Retry up to 2 times on schema validation failure with correction instruction appended
- Log: `input_tokens`, `output_tokens`, `estimated_cost_usd`, `generation_latency_ms`
- `schema_validation_attempts` counter (1 = first try succeeded)

**New deps**: `anthropic` SDK
**Dependencies**: Phase 10

---

### Phase 12 — NLI Entailment Checker

**Objective**: Implement the 3-class NLI heuristic for claim verification.

**Primary modules**:
- `generation/entailment.py` — `cross-encoder/nli-deberta-v3-base`, batch inference

**3-class heuristic** (exact thresholds from spec):
- `supported`: entailment probability > 0.65
- `contradicted`: contradiction probability > 0.85 AND neutral < 0.30
- `ambiguous_conditional`: neutral > 0.40 AND contradiction between 0.30 and 0.70
- `unresolved`: none of the above

**Expected outputs**:
- `requires_expert_review=True` on any answer with ≥ 1 contradicted or ambiguous_conditional claim

**Dependencies**: Phase 11

---

### Phase 13 — Counterevidence Retrieval & TraceableGenerator

**Objective**: Implement the 5-step counterevidence scan and assemble the full verifier.

**Primary modules**:
- `generation/counterevidence.py` — 5-step algorithm (exact implementation below)
- `generation/verifier.py` — `VeriductaVerifier(BaseVerifier)`, `VeriductaGenerator` wired

**5-step counterevidence algorithm** (from spec):
1. Extract `key_entities` from all claims; flatten, deduplicate, remove domain stopwords.
2. Construct contrastive query: `{entities} exception OR limitation OR superseded OR contraindicated OR contradicts OR "shall not" OR "not applicable" OR warning OR caution` (max 10 entities).
3. BM25-only retrieval with temporal filtering, top-10 candidates.
4. NLI batch inference: score all 10 candidates against all claims.
5. Classify each candidate-claim pair; update `verification_status` and attach chunk IDs.

Entity-sparse case: claims with < 2 `key_entities` → `verification_status="not_searched"`,
reason `"insufficient_entity_signal"`.

**Expected outputs**:
- End-to-end test: 10 pilot queries complete without unhandled errors; all answers schema-valid

**Dependencies**: Phases 10, 12

---

### Phase 14 — OpenTelemetry Instrumentation & Evidence Log

**Objective**: Full OTel span hierarchy and evidence log with SQLite index.

**Primary modules**:
- `observability/evidence_log.py` — JSONL writer, gzip rotation, SQLite index reader/writer
- Wire OTel spans into `retrieval/retriever.py`, `generation/generator.py`, `generation/verifier.py`

**Evidence log spec**:
- Active: `evidence_logs/YYYY-MM-DD.jsonl`
- Compressed: gzip after 24 hours
- SQLite: `(trace_id TEXT PK, log_file TEXT, byte_offset INTEGER, query_hash TEXT, created_at TEXT, quality_score REAL, flagged_as_failure INTEGER)`
- Reader: seek to `byte_offset` for O(1) lookup

**Dependencies**: Phase 13

---

### Phase 15 — Prometheus Metrics & Grafana Dashboard

**Objective**: Wire all metric definitions into pipeline stages; verify Grafana dashboard.

**Primary modules**:
- Wire `observability/metrics.py` counters and histograms into ingestion, retrieval, and generation
- `docker/grafana/provisioning/dashboards/veriducta.json` — Grafana dashboard JSON

**Expected outputs**:
- `http://localhost:8000/metrics` returns all defined metric families after a pipeline run
- Grafana at `http://localhost:3000` shows data from the first evaluation run

**Dependencies**: Phase 14

---

### Phase 16 — Golden QA Dataset & Synthetic Corruption Benchmark

**Objective**: Complete the annotation dataset and build all 60 corruption cases.

**Primary modules / data files**:
- `data/golden_qa.jsonl` — 40 questions with supporting chunk IDs, counterevidence chunk IDs,
  temporal validity tag, difficulty label, failure mode label, domain tag, annotator notes
- `data/synthetic_corruptions/corruptions.jsonl` — 60 cases:
  - 20 retrieval corruptions (swap, supersession removal, BM25 zeroing, top-k reduction)
  - 15 chunking corruptions (boundary-naive collection activation)
  - 15 reranker corruptions (top-1 forcing, cross-encoder bypass, score inversion)
  - 10 generation corruptions (unstructured prompt, contradictory injection, token truncation)
- Each corruption case includes: `ground_truth_root_cause`, `is_realistic_boundary_error`

**Dependencies**: Phase 15

---

### Phase 17 — Causal Replay Engine

**Objective**: Implement the four-stage ablation engine and synthetic corruption runner.

**Primary modules**:
- `replay/ablation.py` — `VeriductaReplayEngine(BaseReplayEngine)`
- `replay/heuristic.py` — `HeuristicSignalReport` with 3 signals + disclaimer language
- `replay/corruption.py` — iterates `corruptions.jsonl`, runs ablation, records attributed stage

**Four-stage ablation** (from spec):
- Stage 1 (chunking): if document in chunking failure corpus, `replay_with_config()` with boundary-aware collection; compute Recall@5 delta
- Stage 2 (retrieval): load gold `supporting_chunk_ids`; `replay_with_context()` with gold chunks; compute quality delta
- Stage 3 (reranker): load `pre_rerank_top40` from trace; reconstruct contexts at top-1/3/5/8 cutoffs; compute quality deltas
- Stage 4 (generation): `replay_with_context()` with historical retrieval context and baseline prompt

**Expected outputs**:
- `ReplayReport` dataclass with `stage_attributions: dict[str, float]` and `primary_root_cause: RootCauseStage`
- Root-cause localization accuracy ≥ 0.70 on 60-case benchmark

**Dependencies**: Phases 14, 16

---

### Phase 18 — Evaluation Harness, RAGAS Baseline & CI Regression Gate

**Objective**: Complete evaluation pipeline, RAGAS comparison, and regression gate.

**Primary modules**:
- `evaluation/runner.py` — runs all 40 gold questions + 60 corruption cases
- `evaluation/metrics.py` — computes full `EvaluationMetrics` (all four groups)
- `evaluation/report.py` — writes `evaluation_report_{timestamp}.json` and
  `evaluation_summary_{timestamp}.txt`
- `scripts/check_regression_gate.py` — reads current report vs. `ci_baseline.json`;
  exits 1 on blocking regressions (faithfulness drop, Recall@5 drop, p95 latency increase,
  root-cause accuracy drop, unauthorised evidence exposure)
- `.github/workflows/regression_gate.yml` — CI workflow

**Five blocking regression conditions**:
1. Faithfulness (citation entailment rate) drops > 2% from baseline
2. Recall@5 drops > 3% from baseline
3. p95 latency increases > 20% from baseline
4. Root-cause localization accuracy drops > 5% from baseline
5. Unauthorised evidence exposure rate > 0%

**Additional deliverables**:
- `ci_baseline.json` — first complete evaluation run stored as regression reference
- Complete `README.md` with actual evaluation numbers, RAGAS comparison table, known limitations
- Technical blog post (`docs/blog_post.md`)

**Dependencies**: Phases 15, 16, 17

---

## 16. Architecture Constraints

These rules must never be violated in any phase.

1. **Retrieval cannot call FastAPI.** `retrieval/` has no dependency on `api/` or FastAPI.
2. **API contains no business logic.** Route handlers delegate immediately to pipeline components.
3. **Replay cannot ingest documents.** The replay engine reads historical traces from the evidence
   log. It never calls `ingestion/` components.
4. **Configuration is immutable after startup.** `get_settings()` returns a cached singleton.
   No runtime mutations. Pipeline steps receive `ConfigurationSnapshot` objects, never mutable dicts.
5. **No business logic in schemas.** `schemas/models.py` contains only field declarations and
   Pydantic validators. No pipeline methods on schema classes.
6. **Observability is non-invasive.** Importing `observability/` must not trigger side effects.
   Metric increment calls must never raise exceptions that propagate to pipeline callers.
7. **Evidence log is append-only.** The JSONL evidence log is never modified after writing.
   Corrections go to a separate correction log.
8. **Temporal filtering is mandatory.** Every retrieval path (BM25 and dense) applies temporal
   filtering. There is no way to call retrieval with temporal filtering disabled in production.
9. **ConfigurationSnapshots must be hashed before use.** Any pipeline step that records a
   configuration must call `sha256_json(parameters)` and store the hash. Unhashed snapshots
   must not be written to the evidence log.
10. **No `print()` statements.** All output is structured logging via structlog.
11. **Generation traces must link to retrieval traces.** `GenerationTrace.retrieval_trace_id`
    must reference a real `RetrievalTrace.trace_id`. Orphan generation traces are a bug.
12. **Pre-reranking top-40 is sacred.** The full pre-reranking candidate list with scores must
    always be stored in the evidence log. Without it, Stage 3 ablation is impossible.

---

## 17. Performance Goals

### End-to-End Query Latency

| Percentile | Target |
|---|---|
| p50 | < 4 seconds |
| p95 | < 10 seconds |
| p99 | < 15 seconds |

The two largest latency contributors are dense embedding inference and cross-encoder reranking,
both running on CPU. Mitigation options (apply in order if p95 > 10s):
1. Enable query embedding LRU cache (TTL 1 hour, keyed on query hash)
2. Use BM25-only retrieval for the counterevidence scan (already specified)
3. Reduce reranker input from 40 to 20 candidates

### Memory

- Embedding model (`BAAI/bge-large-en-v1.5`): ~1.3 GB
- NLI model (`cross-encoder/nli-deberta-v3-base`): ~350 MB
- Reranker model (`cross-encoder/ms-marco-MiniLM-L-12-v2`): ~90 MB
- BM25 index (50-document corpus): < 50 MB
- Total expected: < 2 GB

### Batch Sizes

| Operation | Batch Size |
|---|---|
| Embedding (ingestion) | 32 child chunks |
| Reranker inference (retrieval) | 40 query-chunk pairs (single batch call) |
| NLI entailment (verification) | All claims in single batch |
| NLI counterevidence (verification) | All 10 candidates × all claims |

### Caching Strategy

- Query embeddings: LRU cache (max 1000 entries, TTL 1 hour) in `dense_retriever.py`
- BM25 index: loaded once at startup, held in memory
- ML models: loaded once at module level, never reloaded
- Settings: `lru_cache(maxsize=1)`

### Concurrency Assumptions

The MVP runs with `uvicorn` in single-worker mode (`API_WORKERS=1`).
ML models are not thread-safe for write operations; they are read-only after loading.
No async inference: LLM calls, embedding, and cross-encoder inference are synchronous
(run in thread pool executor in production FastAPI if needed).

---

## 18. Security Guidelines

### Environment Variables & Secrets

- `ANTHROPIC_API_KEY` is the only secret. Never log it. Never include it in error messages.
- Store secrets in `.env` locally (git-ignored). In CI: GitHub Secrets.
- `.env.example` contains placeholder values only. Keep it updated when new secrets are added.

### Input Validation

- All user-facing input (query text, `query_date`) must be validated via Pydantic before
  entering the pipeline.
- `query_date` must parse via `utils.datetime_utils.parse_iso_date()` — reject malformed dates.
- Query text: strip, enforce non-empty, enforce max 2000 characters.

### Serialisation Safety

- Use `utils.serialization.to_json()` (orjson) for all outbound serialisation.
  Never use `json.dumps()` with default `=str` in pipeline code.
- Never deserialise arbitrary Python objects (no `pickle.loads()` from external sources).
  The BM25 index (`corpus/bm25_index.pkl`) is internal and trusted.
- Pydantic `model_validate()` is the gateway for all inbound data from external sources.

### API Safety

- CORS is configured via `APISettings.cors_origins`. Default is `["*"]` for development only.
  Production must set `API_CORS_ORIGINS` to the specific allowed origin.
- No authentication in the MVP. Authentication is explicitly out of scope.
- Exception handlers never expose internal tracebacks to HTTP responses.
  The generic handler returns only `{"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."}`.

### Data Privacy

- Corpus documents are public-domain (USGS, NIST, OSHA). No PII in corpus.
- Evidence logs may contain query text. Do not expose evidence logs over HTTP without access control.

---

## 19. Documentation Standards

### Per-Module Docstring (required)

Every `.py` file must begin with a module docstring:
```python
"""One-line summary of what this module does.

Optional paragraph explaining key design decisions or constraints that are
not obvious from reading the code.
"""
```

### Per-Class Docstring (required for public classes)

```python
class HierarchicalChunker(BaseChunker):
    """Boundary-aware parent-child chunker for technical documents.

    Implements the hierarchical chunking strategy specified in the MVP:
    parent chunks at 1400–1600 tokens, child chunks at 200–400 tokens with
    50-token overlap. When ``boundary_aware=True``, child windows never cross
    detected section boundaries.
    """
```

### Per-Function Docstring (required for public functions)

Use Google style with Args/Returns/Raises sections.

### Comment Policy

Write comments only when the WHY is non-obvious: a hidden constraint, a subtle invariant,
a known quirk of a third-party library, a spec-mandated threshold.

```python
# RRF constant k=60 is the standard value from Cormack et al. (2009).
# Changing it requires re-benchmarking retrieval quality.
rrf_score = 1.0 / (60 + rank)
```

Do NOT write comments explaining what the code does. Do NOT write comments referencing
the current task, issue number, or phase.

### README Updates

`README.md` must be updated when:
- Architecture changes significantly
- A new external dependency is added
- The evaluation scorecard has real numbers (Phase 18)

### Architecture Documentation

`docs/ARCHITECTURE.md` must be updated when a new pipeline component is added.
The five-layer diagram must remain accurate.

---

## 20. Claude Code Instructions

### Mandatory Pre-Work (every session)

```
1. Read CLAUDE.md fully.
2. git status — understand working tree state.
3. Identify which Phase is being implemented.
4. Read only files relevant to the current task.
5. Check if interfaces relevant to the phase are already defined in core/interfaces.py.
6. Check if schemas relevant to the phase are already defined in schemas/models.py.
```

### What Claude Must NEVER Do

- **Never regenerate the repository** — Phase 0 infrastructure is complete and correct.
- **Never rewrite a completed phase** — extend it, or add alongside it.
- **Never skip a phase** — phases have dependencies; out-of-order implementation breaks the spec.
- **Never commit without running all four checks** (ruff, black, mypy, pytest).
- **Never add `# type: ignore` without a comment explaining why** it is necessary.
- **Never use `print()`** — use structlog.
- **Never add TODO comments** — implement it or don't; incomplete stubs are worse than nothing.
- **Never mock Qdrant in integration tests** — use a real Qdrant instance.
- **Never hardcode file paths** — use `utils.filesystem.project_root()` or configured paths.
- **Never mutate a `ConfigurationSnapshot`** after creation.

### What Claude Should Always Do

- **Prefer extension over replacement**: add new functions/classes rather than modifying
  existing ones when the existing ones are working.
- **Keep commits atomic**: one logical change per commit.
- **Preserve interface contracts**: if `core/interfaces.py` defines a signature, concrete
  implementations must honour it exactly.
- **Maintain backwards compatibility within a phase**: don't rename functions that tests already call.
- **Add tests for every new behaviour**: no new function ships without a test.
- **Update `schemas/models.py`** when new data types are needed by the current phase —
  but only add fields, never remove or rename existing ones.

### End-of-Session Required Output

Every session ends with this exact structure:

```
## Summary
[2–3 sentences describing what was built or changed]

## Files Changed
- path/to/file.py — [one-line description of change]
- ...

## Tests Run
pytest: X passed, Y failed
ruff: [pass / N errors]
black: [pass / N files would reformat]
mypy: [pass / N errors]

## Remaining Work
[Next phase or task from the Phase Roadmap]
```

---

*End of CLAUDE.md — Veriducta Engineering Specification*
*Generated after Phase 0 completion. Update this document when architecture changes.*
