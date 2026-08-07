# Veriducta — Project Summary

## One-Line Description

A RAG pipeline observability tool that identifies *which pipeline stage* (chunking, retrieval, reranking, or generation) caused a specific answer failure — with 73.3% attribution accuracy on a 60-case benchmark.

---

## The Problem It Solves

Existing RAG evaluation tools (RAGAS, TruLens, DeepEval) measure answer quality but cannot explain *why* quality is low or which pipeline component to fix. A developer receiving a faithfulness score of 0.82 on a bad answer has no actionable signal.

Veriducta closes this gap with a four-stage causal ablation engine that replays historical queries against counterfactual pipeline configurations.

---

## Technical Scope

### Core Stack
- **Language**: Python 3.12 (strict mypy, ruff, black)
- **API**: FastAPI with full OpenTelemetry instrumentation
- **Vector DB**: Qdrant (cosine distance, 1024-dim BGE-large embeddings)
- **LLM**: Claude Sonnet 4.6 (Anthropic SDK, JSON schema enforcement)
- **Frontend**: Next.js 15, TypeScript strict, TailwindCSS, Recharts, Framer Motion
- **Infrastructure**: Docker Compose (Qdrant, MinIO, OTel Collector, Prometheus, Grafana)

### Models Used
| Model | Purpose | Size |
|---|---|---|
| BAAI/bge-large-en-v1.5 | Dense embedding | ~1.3 GB |
| cross-encoder/ms-marco-MiniLM-L-12-v2 | Reranking | ~90 MB |
| cross-encoder/nli-deberta-v3-base | NLI claim verification | ~350 MB |
| Claude Sonnet 4.6 | Structured generation | API |

### Scale
- 30–50 document corpus (public engineering/regulatory documents)
- ~10,000 indexed chunks
- 40-question gold QA dataset
- 60-case synthetic corruption benchmark
- 801 automated tests, 92.81% coverage

---

## Key Technical Innovations

### 1. Replayable Retrieval Traces
Every query stores the full pre-reranking top-40 candidate list with cross-encoder scores in an append-only JSONL evidence log, indexed by SQLite byte offset for O(1) lookup. This makes Stage 3 ablation possible without re-running inference.

### 2. Four-Stage Causal Ablation
- **Stage 1**: Replay with boundary-aware chunking; measure Recall@5 delta
- **Stage 2**: Inject gold supporting chunks; measure quality delta (oracle-required)
- **Stage 3**: Load stored top-40; test cutoff variants; no additional inference
- **Stage 4**: Replay with historical context and baseline prompt

### 3. Boundary-Aware Hierarchical Chunking
Parent chunks (1400–1600 tokens) assembled at section boundaries. Child chunks (200–400 tokens) never split across detected section boundary markers. Configuration snapshots are SHA-256 hashed and immutable — enabling comparison between historical runs with different chunking configs.

### 4. Four Metrics RAGAS Cannot Compute
- Omission rate (8.2%)
- Causal attribution accuracy (73.3%)
- Temporal-valid retrieval rate (94.1%)
- Contradiction acknowledgment rate (91.7%)

---

## Results

| Metric | Value | Target |
|---|---|---|
| Root-cause accuracy | **73.3%** | ≥ 70% ✓ |
| Boundary-error accuracy | **68.8%** | ≥ 65% ✓ |
| p50 latency | **2.8 s** | < 4 s ✓ |
| p95 latency | **7.4 s** | < 10 s ✓ |
| Test coverage | **92.81%** | ≥ 80% ✓ |

---

## Architecture Complexity

8-layer strict dependency graph (no circular imports enforced at CI level):
```
schemas/utils/config → core → storage/models → ingestion
→ retrieval → generation → verification → replay → evaluation → api
```

Each layer is independently testable. The replay engine can substitute any layer with a counterfactual configuration without touching surrounding layers.

---

## What This Demonstrates

- Designing and building a production-quality ML-backed API from scratch under strict architectural constraints
- Cross-domain implementation: information retrieval, NLP, LLM integration, observability, frontend
- Causal reasoning about system failures — moving beyond measurement to attribution
- End-to-end engineering: Docker infrastructure, CI/CD, type safety, 80%+ test coverage
- Technical communication: architecture diagrams, blog post, benchmark methodology

---

*Repository: github.com/hardik-gupta/veriducta · License: MIT*
