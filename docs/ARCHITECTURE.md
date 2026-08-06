# Architecture

## Eight-Layer Architecture

```
┌───────────────────────────────────────────────────────────┐
│  Layer 8 — API (api/)                                     │
│  FastAPI application factory, routing, middleware, DI     │
├───────────────────────────────────────────────────────────┤
│  Layer 7 — Evaluation (evaluation/)                       │
│  Runner, metrics, RAGAS baseline, CI regression gate      │
├───────────────────────────────────────────────────────────┤
│  Layer 6 — Causal Replay (replay/)                        │
│  Four-stage gold ablation, corruption runner              │
├───────────────────────────────────────────────────────────┤
│  Layer 5 — Verification (verification/)                   │
│  Claim integrity orchestration, VerificationReport        │
├───────────────────────────────────────────────────────────┤
│  Layer 4 — Generation (generation/)                       │
│  Claude structured output, NLI, counterevidence           │
├───────────────────────────────────────────────────────────┤
│  Layer 3 — Retrieval (retrieval/)                         │
│  BM25 + dense, RRF, temporal filter, reranker, expander   │
├───────────────────────────────────────────────────────────┤
│  Layer 2 — Ingestion (ingestion/) ✓ Phase 1 complete      │
│  PDF parsing, chunking, embedding, Qdrant upsert, BM25    │
├───────────────────────────────────────────────────────────┤
│  Layer 1 — Foundation                                     │
│  config · core · schemas · utils · storage                │
│  observability · models                                   │
└───────────────────────────────────────────────────────────┘
```

Data flows strictly downward. No layer may import from a layer above it.
`observability` is a cross-cutting concern importable by any layer.

## Storage Layer

| Backend    | Purpose                                       |
|------------|-----------------------------------------------|
| Qdrant     | Dense vector store for chunk embeddings       |
| MinIO      | Object storage for corpus PDFs and artifacts  |
| SQLite     | Evidence log index (O(1) trace lookup)        |
| Filesystem | BM25 index pickle, config snapshots, logs     |

## Observability Stack

| Component      | Role                                      |
|----------------|-------------------------------------------|
| structlog      | JSON structured application logs          |
| OpenTelemetry  | Distributed tracing across pipeline spans |
| Prometheus     | Metrics scrape endpoint (`:8000/metrics`) |
| Grafana        | Dashboard over Prometheus data            |
| OTLP Collector | Span aggregation and metric forwarding    |

## Interface Boundaries

All pipeline components implement abstract interfaces defined in `core/interfaces.py`.
This allows the causal replay engine to swap configurations without re-running expensive
components — for example, substituting a stored pre-reranking trace (40 candidates with
scores) instead of re-running cross-encoder inference for Stage 3 ablation.

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
