# Architecture

## Eight-Layer Architecture

```
┌───────────────────────────────────────────────────────────┐
│  Layer 8 - API (api/)                                     │
│  FastAPI application factory, routing, middleware, DI     │
├───────────────────────────────────────────────────────────┤
│  Layer 7 - Evaluation (evaluation/)                       │
│  Runner, metrics, RAGAS baseline, CI regression gate      │
├───────────────────────────────────────────────────────────┤
│  Layer 6 - Causal Replay (replay/)                        │
│  Four-stage gold ablation, corruption runner              │
├───────────────────────────────────────────────────────────┤
│  Layer 5 - Verification (verification/)                   │
│  Claim integrity orchestration, VerificationReport        │
├───────────────────────────────────────────────────────────┤
│  Layer 4 - Generation (generation/)                       │
│  Claude structured output, NLI, counterevidence           │
├───────────────────────────────────────────────────────────┤
│  Layer 3 - Retrieval (retrieval/)                         │
│  BM25 + dense, RRF, temporal filter, reranker, expander   │
├───────────────────────────────────────────────────────────┤
│  Layer 2 - Ingestion (ingestion/)                         │
│  PDF parsing, chunking, embedding, Qdrant upsert, BM25    │
├───────────────────────────────────────────────────────────┤
│  Layer 1 - Foundation                                     │
│  config · core · schemas · utils · storage                │
│  observability · models                                   │
└───────────────────────────────────────────────────────────┘
```

Data flows strictly downward. No layer may import from a layer above it.
`observability` is a cross-cutting concern importable by any layer.

---

## Diagram 1 - Overall System Architecture

```mermaid
graph TD
    subgraph Client["Client Layer"]
        FE["Next.js 15 Frontend\n(port 3000)"]
        CLI["CLI Scripts\nscripts/"]
    end

    subgraph API["API Layer - FastAPI (port 8000)"]
        APP["app.py\nLifespan · CORS · Request-ID middleware"]
        HEALTH["GET /health\nGET /version"]
        QUERY["POST /query\nPOST /replay"]
    end

    subgraph Pipeline["Pipeline Layers"]
        RET["retrieval/\nVeriductaRetriever"]
        GEN["generation/\nVeriductaGenerator"]
        VER["verification/\nVeriductaVerifier"]
    end

    subgraph Foundation["Foundation"]
        CONF["config/\nSettings (lru_cache)"]
        CORE["core/\nExceptions · Interfaces"]
        SCH["schemas/\nPydantic models"]
        UTIL["utils/\nhashing · ids · serialization"]
        OBS["observability/\nPrometheus · OTel · Evidence log"]
    end

    subgraph Storage["Storage Backends"]
        QD["Qdrant\nDense vectors"]
        MN["MinIO\nPDF objects"]
        SQ["SQLite\nTrace index"]
        FS["Filesystem\nBM25 · JSONL logs"]
    end

    FE -->|HTTP| APP
    CLI -->|import| Pipeline

    APP --> HEALTH
    APP --> QUERY
    QUERY --> RET
    RET --> GEN
    GEN --> VER
    VER -->|VerificationReport| QUERY

    Pipeline --> Foundation
    Pipeline --> Storage
    OBS -->|metrics scrape| PROM["Prometheus\n(port 9090)"]
    PROM --> GRAF["Grafana\n(port 3001)"]
```

---

## Diagram 2 - Retrieval Pipeline

```mermaid
flowchart LR
    Q["Query\n+ query_date"] --> BM25["BM25Retriever\ntop-100 candidates"]
    Q --> DENSE["DenseRetriever\nBGE-large-en-v1.5\ntop-100 candidates"]

    BM25 --> RRF["RRF Fusion\nk = 60\n1 / (60 + rank)"]
    DENSE --> RRF

    RRF --> TF["TemporalFilter\nrejects: not_yet_effective\nor superseded"]
    TF -->|version graph| VG["networkx DiGraph\nversion_graph.json"]

    TF --> CE["CrossEncoderReranker\nms-marco-MiniLM-L-12-v2\ntop-40 → top-8"]
    CE -->|pre_rerank_top40 stored| EL["Evidence Log\nJSONL + SQLite index"]

    CE --> EXP["ParentChildExpander\nfetches parent section\nfrom Qdrant"]
    EXP --> RR["RetrievalResult\ntop-8 candidates\n+ full trace"]

    style EL fill:#1e3a5f,color:#93c5fd
    style VG fill:#1e3a5f,color:#93c5fd
```

---

## Diagram 3 - Generation & Verification Pipeline

```mermaid
flowchart TD
    RR["RetrievalResult\n(top-8 chunks + trace)"] --> GEN

    subgraph GEN["VeriductaGenerator"]
        SP["System Prompt\nprompts.py"]
        LLM["Claude Sonnet 4.6\nmax_tokens = 2048"]
        VAL["JSON Schema\nValidation\n≤ 2 retries"]
        SP --> LLM --> VAL
    end

    VAL --> ANS["StructuredAnswer\n(claims + citations)"]

    ANS --> VER

    subgraph VER["VeriductaVerifier"]
        NLI["NLI Entailment\nnli-deberta-v3-base\nentailment / contradiction / neutral"]
        CE["CounterevidenceRetriever\n5-step contrastive BM25\ntop-10 candidates"]
        REPORT["VerificationReport\nassembly"]
        NLI --> REPORT
        CE --> REPORT
    end

    VER --> VR["VerificationReport\n(per-claim status\n+ expert_review flag)"]

    subgraph NLI_THRESH["3-Class Heuristic"]
        S["supported\nentailment > 0.65"]
        C["contradicted\ncontradiction > 0.85\nneutral < 0.30"]
        AC["ambiguous_conditional\nneutral > 0.40"]
        UR["unresolved\n(none of the above)"]
    end

    NLI -.->|applies| NLI_THRESH
```

---

## Diagram 4 - Causal Replay Engine (Four-Stage Ablation)

```mermaid
flowchart TD
    FAIL["Failed / Low-Quality Answer\n(trace_id + question_id)"] --> AE

    subgraph AE["VeriductaReplayEngine"]

        S1["Stage 1 - Chunking\nreplay_with_config(boundary_aware=True)\ncompute Recall@5 delta\n↓ if delta > threshold → root cause = chunking"]

        S2["Stage 2 - Retrieval\nreplay_with_context(gold_chunks)\ncompute quality delta\n↓ if delta > threshold → root cause = retrieval"]

        S3["Stage 3 - Reranker\nload pre_rerank_top40 from trace\ntest top-1/3/5/8 cutoffs\ncompute quality deltas\n↓ if delta > threshold → root cause = reranking"]

        S4["Stage 4 - Generation\nreplay_with_context(historical context)\nbaseline prompt\ncompute quality delta\n↓ if delta > threshold → root cause = generation"]

        S1 --> S2 --> S3 --> S4
    end

    AE --> RR["ReplayReport\nstage_attributions: dict[str, float]\nprimary_root_cause: RootCauseStage"]

    subgraph EL["Evidence Log (read-only)"]
        TL["RetrievalTrace\npre_rerank_top40\nBM25/dense/RRF scores"]
        GL["GenerationTrace\nretrieval_trace_id link\ninput/output tokens"]
    end

    AE -->|reads via O(1) SQLite lookup| EL

    style S1 fill:#7c3aed,color:#f3e8ff
    style S2 fill:#0e7490,color:#e0f7fa
    style S3 fill:#b45309,color:#fef3c7
    style S4 fill:#15803d,color:#dcfce7
```

---

## Diagram 5 - Evaluation Pipeline

```mermaid
flowchart TD
    subgraph DATA["Input Data"]
        GQ["data/golden_qa.jsonl\n40 annotated questions"]
        CC["data/synthetic_corruptions/\ncorruptions.jsonl\n60 corruption cases"]
    end

    GQ --> ER["EvaluationRunner\nruns full pipeline\nper question"]
    CC --> CR["CorruptionRunner\nruns ablation\nper corruption case"]

    ER --> MC["MetricsComputer"]
    CR --> MC

    subgraph MC["MetricsComputer"]
        RM["RetrievalMetrics\nRecall@5 · Precision@5\ntemporal_precision"]
        AQ["AnswerQualityMetrics\ncitation_entailment_rate\nomission_rate\ncontradiction_ack_rate"]
        CA["CausalAttributionMetrics\nroot_cause_localization_accuracy\nstage_attribution_deltas"]
        OP["OperationalMetrics\np50 / p95 / p99 latency\ntoken costs"]
    end

    MC --> RW["ReportWriter\nJSON · Markdown · CSV · HTML"]
    MC --> RG["RegressionEngine\ncheck vs ci_baseline.json"]

    subgraph GATES["5 Blocking Regression Conditions"]
        G1["faithfulness drop > 2%"]
        G2["Recall@5 drop > 3%"]
        G3["p95 latency increase > 20%"]
        G4["root-cause accuracy drop > 5%"]
        G5["unauthorised evidence exposure > 0%"]
    end

    RG -->|fails on any| GATES
    GATES -->|exit 1| CI["CI / GitHub Actions"]
    RW --> RPT["evaluation_report_{ts}.json\nevaluation_summary_{ts}.txt"]
    RW --> RAGAS["ragas_comparison_{ts}.json\n(optional RAGAS baseline)"]
```

---

## Diagram 6 - Deployment Architecture

```mermaid
graph TD
    subgraph DEV["Developer Machine (docker compose up)"]

        subgraph APP_TIER["Application Tier"]
            API["veriducta-api\nuvicorn · port 8000\nFastAPI + pipeline"]
            FE["veriducta-frontend\nNext.js 15 · port 3000"]
        end

        subgraph STORAGE_TIER["Storage Tier"]
            QD["qdrant\nport 6333 (HTTP)\nport 6334 (gRPC)"]
            MN["minio\nport 9000 (S3 API)\nport 9001 (Console)"]
        end

        subgraph OBS_TIER["Observability Tier"]
            PROM["prometheus\nport 9090\nscrapes :8000/metrics"]
            GRAF["grafana\nport 3001\ndashboard UI"]
            OTLP["otelcol\nOTLP gRPC :4317\nOTLP HTTP :4318"]
            JAEGER["jaeger\nport 16686 (UI)"]
        end

        subgraph FS_TIER["Filesystem Volumes"]
            CORPUS["./data/corpus/\nPDFs + sidecars"]
            LOGS["./evidence_logs/\nJSONL + SQLite index"]
            SNAPS["./config/chunking_snapshots/\n{hash}.json"]
            BM25["./corpus/bm25_index.pkl"]
        end

    end

    subgraph CLOUD["External (API call)"]
        ANT["Anthropic API\nclaude-sonnet-4-6"]
    end

    API -->|embed + rerank| QD
    API -->|object store| MN
    API -->|spans| OTLP
    API -->|generate| ANT
    OTLP --> JAEGER
    PROM -->|scrape| API
    PROM --> GRAF
    FE -->|HTTP| API
    API -->|read/write| FS_TIER
```

---

## Evaluation Framework

The `evaluation/` package implements the complete Phase 18 evaluation harness.

| Component | Class | Purpose |
|---|---|---|
| `runner.py` | `EvaluationRunner` | Executes queries through the full pipeline; captures per-query latency and errors |
| `metrics.py` | `MetricsComputer` | Computes all four metric groups from `EvaluationRunResults` |
| `regression.py` | `RegressionEngine` | Checks five blocking conditions against a stored baseline |
| `comparison.py` | `RunComparator` | Produces per-metric deltas across two evaluation runs |
| `baseline.py` | `BaselineRunner` | Runs alternative pipeline configurations (dense-only, BM25-only, etc.) |
| `report.py` | `ReportWriter` | Serialises results to JSON, Markdown, CSV, and HTML |
| `benchmark.py` | `BenchmarkRunner` | Top-level orchestrator that wires all components together |
| `ragas_adapter.py` | `RAGASAdapter` | Optional RAGAS integration; gracefully skipped when unavailable |

**Dependency injection**: All `EvaluationRunner` constructor arguments are optional (`None`).
Tests run without any live ML models or services.

---

## Storage Layer

| Backend    | Purpose                                       |
|------------|-----------------------------------------------|
| Qdrant     | Dense vector store for chunk embeddings       |
| MinIO      | Object storage for corpus PDFs and artifacts  |
| SQLite     | Evidence log index (O(1) trace lookup)        |
| Filesystem | BM25 index pickle, config snapshots, logs     |

---

## Observability Stack

| Component      | Role                                      |
|----------------|-------------------------------------------|
| structlog      | JSON structured application logs          |
| OpenTelemetry  | Distributed tracing across pipeline spans |
| Prometheus     | Metrics scrape endpoint (`:8000/metrics`) |
| Grafana        | Dashboard over Prometheus data            |
| OTLP Collector | Span aggregation and metric forwarding    |
| Jaeger         | Distributed trace UI                      |

---

## Interface Boundaries

All pipeline components implement abstract interfaces defined in `core/interfaces.py`.
This allows the causal replay engine to swap configurations without re-running expensive
components - for example, substituting a stored pre-reranking trace (40 candidates with
scores) instead of re-running cross-encoder inference for Stage 3 ablation.

---

## Dependency Graph

```
schemas ─────────────────────────────────────────────┐
utils   ─────────────────────────────────────────────┤
config  ───────────────────────────────────────────┐ │
                                                   │ │
core    ──(imports config)─────────────────────────┤ │
storage ──(imports core) ──────────────────────────┤ │
                                                   ▼ ▼
models  ──────────────────────────────────────► ingestion
                                                      │
observability ────────────────────────────────────────┤
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

---

## OTel Span Hierarchy

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

Every span carries: `config_snapshot_hash`, `input_hash`, `output_hash`, `latency_ms`.
