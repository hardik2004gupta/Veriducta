# Veriducta Roadmap

> Last updated: 2026-08-07 · v1.0.0

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Complete |
| 🔄 | In progress |
| 📋 | Planned |
| 💡 | Idea (not committed) |
| 🔬 | Research (speculative) |

---

## ✅ Completed - v1.0.0

### Core Pipeline
- ✅ Eight-layer architecture with strict dependency enforcement
- ✅ Boundary-aware hierarchical chunking (parent 1400–1600 tokens, child 200–400 tokens)
- ✅ Configuration snapshots with SHA-256 hashing
- ✅ BGE-large-en-v1.5 dense embedding (1024-dim)
- ✅ BM25 + dense hybrid retrieval with RRF (k=60)
- ✅ Temporal validity filtering via version graph
- ✅ Cross-encoder reranking (ms-marco-MiniLM-L-12-v2, top-40 → top-8)
- ✅ Parent-child context expansion
- ✅ Claude Sonnet 4.6 structured generation with JSON schema enforcement
- ✅ NLI entailment verification (nli-deberta-v3-base, 3-class heuristic)
- ✅ 5-step counterevidence retrieval
- ✅ Complete evidence log (JSONL + SQLite O(1) index)
- ✅ Full OTel span hierarchy across all pipeline stages

### Causal Replay Engine
- ✅ Four-stage gold ablation (chunking → retrieval → reranker → generation)
- ✅ Pre-reranking top-40 stored for Stage 3 replay without re-inference
- ✅ Synthetic corruption runner (60-case benchmark)
- ✅ 73.3% root-cause accuracy (target: ≥ 70%)
- ✅ 68.8% accuracy on boundary-error subset (target: ≥ 65%)

### Evaluation
- ✅ 40-question gold QA dataset
- ✅ 60-case corruption benchmark
- ✅ Full metric scorecard (retrieval + answer quality + causal + operational)
- ✅ CI regression gate with 5 blocking conditions
- ✅ RAGAS comparison adapter

### Observability
- ✅ 13 Prometheus metric families
- ✅ Grafana stack (Docker Compose)
- ✅ Structlog JSON + ConsoleRenderer

### Frontend
- ✅ Next.js 15 + TypeScript strict + TailwindCSS
- ✅ 8 pages (landing, dashboard, ask, retrieval, replay, evaluation, evidence, settings)
- ✅ Mock data layer matching backend schema

### Documentation
- ✅ README with evaluation scorecard and RAGAS comparison
- ✅ 6 Mermaid architecture diagrams
- ✅ 9 documentation pages (architecture, blog, case study, decisions, challenges, performance, research, deployment, portfolio)
- ✅ GitHub release assets: CHANGELOG, RELEASE_NOTES, ROADMAP, VERSION
- ✅ Open source: LICENSE (MIT), CODEOWNERS, issue/PR templates, CODE_OF_CONDUCT, SECURITY

---

## 📋 Planned - v1.1 (next 30 days)

### Frontend → Live
- 📋 Wire `frontend/lib/api.ts` to all 8 pages (remove mock data)
- 📋 Server-Sent Events for streaming generation progress
- 📋 Real-time sidebar status (live ping from `/api/v1/health`)
- 📋 Corpus upload UI (drag-and-drop PDF → trigger ingestion pipeline)

### Developer Experience
- 📋 One-command local setup script (`scripts/setup_local.sh`)
- 📋 Grafana dashboard JSON provisioning (ready-to-import)
- 📋 Makefile target: `make ingest-sample` (downloads 3 public-domain PDFs and ingests)

### Evaluation
- 📋 RAGAS as optional install (`pip install veriducta[ragas]`)
- 📋 HuggingFace Datasets export for gold QA and corruptions
- 📋 Evaluation HTML report (already written, needs CSS polish)

---

## 📋 Planned - v1.2 (next 90 days)

### Performance
- 📋 GPU-accelerated embedding via `sentence-transformers` CUDA backend
- 📋 GPU-accelerated cross-encoder reranking
- 📋 Parallel BM25 + dense retrieval (concurrent instead of sequential)
- 📋 Reduce reranker input from 40 → 20 candidates (if GPU unavailable)

### Corpus Management
- 📋 Multi-collection Qdrant support (separate collections per corpus)
- 📋 Incremental ingestion (delta updates without full re-index)
- 📋 Corpus version comparison UI
- 📋 Sidecar editor in frontend

### Quality
- 📋 User feedback loop: flag failed answers from the Ask page
- 📋 Active learning signal from flagged answers → re-annotation queue
- 📋 Export replay reports to PDF

---

## 📋 Planned - v2.0 (6+ months)

### Multi-LLM Support
- 📋 Generator abstraction supporting GPT-4o, Gemini 1.5, Llama 3.1 (via Ollama)
- 📋 Per-model cost tracking and comparison dashboard
- 📋 Cross-model faithfulness comparison in evaluation

### Architecture
- 📋 Async pipeline execution (`asyncio` + thread pool for ML models)
- 📋 Multi-worker uvicorn support with prometheus multiprocess mode
- 📋 Distributed evidence log (PostgreSQL or ClickHouse backend)
- 📋 REST API for submitting custom corruption cases

### Auth & Multi-Tenancy
- 📋 JWT authentication layer
- 📋 Per-user query history and cost attribution
- 📋 Organization-level pipeline configuration isolation

---

## 💡 Ideas (not committed)

- 💡 Browser extension that runs Veriducta attribution on any RAG chatbot output
- 💡 VS Code extension for inline RAG debugging
- 💡 Slack bot integration (ask questions, receive attributed answers)
- 💡 Automated corpus discovery from arXiv, OSHA, NIST, USGS RSS feeds
- 💡 Benchmark leaderboard: compare Veriducta attribution accuracy across corpora
- 💡 Fine-tuning pipeline: use attribution failures as negative examples
- 💡 Multimodal extension: tables, figures, and diagrams as first-class chunks

---

## 🔬 Long-Term Research

- 🔬 **Attribution without gold chunks**: eliminate the need for manually annotated supporting chunk IDs in Stage 2 ablation
- 🔬 **Continuous calibration**: automatically adjust attribution thresholds based on observed corpus drift
- 🔬 **Cross-pipeline attribution**: when two RAG systems answer the same query differently, identify whether the divergence originates in retrieval or generation
- 🔬 **Temporal drift detection**: automatically detect when a corpus document has been superseded and the version graph is stale
- 🔬 **NLI-free attribution**: replace the 3-class NLI heuristic with a learned quality scorer trained on human preference data
- 🔬 **Causal graphs**: replace the sequential four-stage ablation with a causal DAG that models interaction effects between stages

---

## 💡 Possible Enterprise Edition

| Feature | Description |
|---|---|
| SSO / SAML | Enterprise auth integration |
| Audit log | Immutable query-level compliance trail |
| Data residency | On-premises deployment with no cloud calls |
| SLA monitoring | Latency and cost SLA alerting |
| Corpus ACL | Per-document access control in retrieval |
| White-label | Custom branding for the frontend |
| Multi-region | Distributed ingestion and retrieval across regions |

---

*This roadmap is updated with each major release. Items in "Ideas" and "Research" sections are speculative and may not be implemented. Contributions welcome - see [CONTRIBUTING.md](docs/CONTRIBUTING.md).*
