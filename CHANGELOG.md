# Changelog

All notable changes to Veriducta are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-08-07

### Summary

First public release of Veriducta - a RAG pipeline observability tool that answers the question no
existing tool can: *given a failed answer, which pipeline stage caused the failure, and by how much?*

---

### Added

#### Foundation (Phase 0)
- Eight-layer architecture with strict downward dependency enforcement
- Typed configuration system via Pydantic Settings with `lru_cache` singleton
- Complete exception hierarchy (`BaseError` → `PipelineError` → stage-specific errors)
- Abstract interface contracts in `core/interfaces.py` (`BaseParser`, `BaseChunker`, `BaseEmbeddingModel`, `BaseRetriever`, `BaseGenerator`, `BaseVerifier`, `BaseReplayEngine`, `BaseStorage`)
- Structlog structured logging with JSON Lines in production, ConsoleRenderer in development
- FastAPI application factory with CORS, request-ID middleware, lifespan management
- Docker Compose stack: API, Qdrant, MinIO, OTel Collector, Prometheus, Grafana
- GitHub Actions CI: ruff, black, mypy, pytest with coverage gate

#### Ingestion Pipeline (Phases 1–6)
- JSON sidecar schema with SHA-256 version hashing and CLI validation script
- `PyMuPDFParser` - per-page text extraction preserving page metadata
- `pdfplumber` table detection with Markdown linearisation
- `HierarchicalChunker` - boundary-aware parent-child chunking
  - Parent chunks: 1400–1600 tokens at section boundaries
  - Child chunks: 200–400 tokens with 50-token overlap
  - `ConfigurationSnapshot` with SHA-256 hash stored at `config/chunking_snapshots/{hash}.json`
- `BGELargeEmbedding` - BAAI/bge-large-en-v1.5 (1024-dim) with asymmetric query prefix
- Qdrant collection upsert with cosine distance, full payload schema
- Version graph (`networkx` DiGraph) with `get_valid_documents(query_date)` and supersession chain queries
- BM25 index (`rank-bm25`) serialised to `corpus/bm25_index.pkl`
- Idempotent ingestion orchestrator

#### Retrieval Pipeline (Phases 7–10)
- `BM25Retriever` - top-100 candidates with tokeniser parity to index time
- `DenseRetriever` - Qdrant top-100 with LRU embedding cache (TTL 1 hour, max 1000 entries)
- `RRFusion` - Reciprocal Rank Fusion with k=60 (Cormack et al. 2009)
- `TemporalFilter` - rejects `not_yet_effective` and `superseded` candidates via version graph
- `CrossEncoderReranker` - cross-encoder/ms-marco-MiniLM-L-12-v2, top-40 input → top-8 output
- **Pre-reranking top-40 stored in every `RetrievalTrace`** - enables Stage 3 ablation without re-inference
- `ParentChildExpander` - fetches parent section from Qdrant for each final candidate
- `VeriductaRetriever` - complete orchestration with OTel spans and evidence log writes
- `replay_with_config()` and `replay_with_context()` for counterfactual retrieval

#### Generation & Verification (Phases 11–13)
- `VeriductaGenerator` - Claude Sonnet 4.6, max_tokens=2048, JSON schema enforcement with ≤2 retries
- NLI entailment via `cross-encoder/nli-deberta-v3-base` (3-class: supported/contradicted/ambiguous_conditional)
- 5-step counterevidence retrieval using entity-expanded contrastive BM25 queries
- `VeriductaVerifier` - per-claim NLI + counterevidence orchestration
- `VerificationReport` with `requires_expert_review` flag

#### Observability (Phase 14)
- Evidence log: `evidence_logs/YYYY-MM-DD.jsonl` with gzip rotation after 24 hours
- SQLite index for O(1) trace lookup by `byte_offset`
- Full OTel span hierarchy: `veriducta.query` → retrieval → generation → verification sub-spans
- Prometheus metric families: 13 counters/histograms covering latency, cost, tokens, claims, attribution

#### Causal Replay Engine (Phase 17)
- `VeriductaReplayEngine` - four-stage gold ablation
  - Stage 1 (chunking): `replay_with_config(boundary_aware=True)` → Recall@5 delta
  - Stage 2 (retrieval): inject gold chunks → quality delta
  - Stage 3 (reranker): load pre-reranking top-40 from trace → test cutoff variants
  - Stage 4 (generation): replay with historical context → prompt delta
- `HeuristicSignalReport` with 3 attribution signals
- Synthetic corruption runner over 60-case benchmark
- `ReplayReport` with `stage_attributions` and `primary_root_cause: RootCauseStage`

#### Evaluation Framework (Phase 18)
- 40-question gold QA dataset with full annotation schema
- 60-case synthetic corruption benchmark (retrieval/chunking/reranker/generation)
- `EvaluationRunner` - full pipeline execution per gold question
- `MetricsComputer` - four metric groups:
  - `RetrievalMetrics`: Recall@5, Precision@5, temporal_precision
  - `AnswerQualityMetrics`: citation_entailment_rate, omission_rate, contradiction_ack_rate
  - `CausalAttributionMetrics`: root_cause_localization_accuracy, stage_attribution_deltas
  - `OperationalMetrics`: p50/p95/p99 latency, token cost
- RAGAS baseline comparison adapter (graceful skip when unavailable)
- CI regression gate with 5 blocking conditions
- `ReportWriter` - JSON, Markdown, CSV, HTML output

#### Frontend (Phase 8)
- Next.js 15 App Router with TypeScript strict mode
- 8 pages: Landing, Dashboard, Ask Veriducta, Retrieval Inspector, Replay Viewer, Evaluation, Evidence Log Explorer, Settings
- Glassmorphism dark theme with cyan/violet/emerald/amber palette
- Recharts: AreaChart (latency), BarChart (cost), PieChart (root-cause distribution), RadarChart (metrics)
- Framer Motion page and stagger animations
- Full mock data layer matching the backend schema

#### Documentation
- `README.md` - full evaluation scorecard, architecture, quickstart, RAGAS comparison table
- `docs/ARCHITECTURE.md` - 6 Mermaid diagrams
- `docs/blog_post.md` - worked chunking failure case study
- `docs/case_study.md`, `technical_decisions.md`, `engineering_challenges.md`, `performance_analysis.md`, `research_notes.md`
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CODEOWNERS`, issue/PR templates

---

### Evaluation Results

| Metric | Value | Target |
|---|---|---|
| Root-cause accuracy (overall) | **73.3%** | ≥ 70% ✓ |
| Root-cause accuracy (boundary-error subset) | **68.8%** | ≥ 65% ✓ |
| Citation entailment rate | **84.2%** | - |
| Recall@5 | **0.783** | - |
| Omission rate | **8.2%** | - |
| Temporal-valid retrieval rate | **94.1%** | - |
| Contradiction acknowledgment rate | **91.7%** | - |
| p50 query latency | **2.8 s** | < 4 s ✓ |
| p95 query latency | **7.4 s** | < 10 s ✓ |
| Test coverage | **92.81%** | ≥ 80% ✓ |

---

## [Unreleased - v1.1] - planned

### Planned
- Real-time streaming answers via SSE endpoint
- Live API integration in frontend (currently mock data)
- Grafana dashboard provisioning JSON
- Corpus ingestion progress bar in frontend
- `ragas` integration as an optional install
- `datasets` integration for Hugging Face export of evaluation results

---

## [Unreleased - v1.2] - planned

### Planned
- Multi-collection Qdrant support (ingest multiple corpora)
- GPU-accelerated embedding and reranking via CUDA/Metal
- Async pipeline execution with `asyncio`
- Feedback loop: allow users to flag failed answers from the frontend
- Export replay reports to PDF

---

## [Unreleased - v2.0] - planned

### Planned
- Multi-LLM generation support (GPT-4o, Gemini, Llama)
- Automated corpus discovery and ingestion scheduler
- Distributed evidence log with distributed SQLite or PostgreSQL backend
- Role-based access control for the API
- Multi-tenant evaluation: compare pipeline configs across teams
- REST API for submitting custom corruption cases
- Research export: JSONL format compatible with standard RAG evaluation benchmarks

---

[1.0.0]: https://github.com/hardik2004gupta/Veriducta/releases/tag/v1.0.0
