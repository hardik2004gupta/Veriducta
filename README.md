# Veriducta — RAG Pipeline Observability

> **"Your RAG pipeline is failing. RAGAS gives it a 0.82 faithfulness score. Which stage caused the failure?"**
> Veriducta can tell you. RAGAS cannot.

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js 15](https://img.shields.io/badge/Next.js-15.3-black?logo=nextdotjs)](https://nextjs.org)
[![Claude Sonnet 4.6](https://img.shields.io/badge/Claude-Sonnet%204.6-orange?logo=anthropic)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Phase 7 Complete](https://img.shields.io/badge/Phase-7%20Complete-brightgreen)](docs/ARCHITECTURE.md)
[![Tests](https://img.shields.io/badge/Tests-801%20passing-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-92.8%25-brightgreen)](tests/)

---

## What Is Veriducta?

Veriducta is a production-quality **RAG pipeline observability tool** built around one idea that no existing tool supports:

**Given a failed answer, which pipeline stage caused the failure — and by how much?**

It achieves this through **four-stage causal ablation**: store a complete, replayable trace of every retrieval decision, then swap gold-standard inputs at each stage (chunking, retrieval, reranking, generation) and measure the quality delta. The stage with the largest delta is the root cause.

This is not heuristic attribution. It is counterfactual replay.

---

## Evaluation Scorecard

| Metric | Value | RAGAS Baseline | Exclusive to Veriducta |
|---|---|---|---|
| **Citation Faithfulness** | **87.1%** | 82.0% | — |
| **Recall@5** | **78.3%** | 74.0% | — |
| **Root-Cause Localization Accuracy** | **73.3%** | — | ✓ |
| **Omission Rate** | **8.2%** | — | ✓ |
| **Temporal-Valid Retrieval Rate** | **96.4%** | — | ✓ |
| **Contradiction Acknowledgment Rate** | **89.1%** | — | ✓ |
| **p50 / p95 Latency** | **2.8s / 7.2s** | — | — |
| **Mean Cost per Query** | **$0.0082** | — | — |

> 4 metrics RAGAS cannot compute. Root-cause accuracy ≥ 0.70 on the 60-case synthetic benchmark.

---

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│  API Layer          FastAPI · routing · DI · exception map │
├───────────────────────────────────────────────────────────┤
│  Evaluation         40 golden QA · 60-case benchmark       │
│                     · RAGAS baseline · CI regression gate  │
├───────────────────────────────────────────────────────────┤
│  Causal Replay      4-stage ablation · quality delta       │
│                     · root cause attribution               │
├───────────────────────────────────────────────────────────┤
│  Verification       NLI claim checking (deberta-v3-base)   │
│                     · counterevidence scan · expert flag   │
├───────────────────────────────────────────────────────────┤
│  Generation         Claude Sonnet 4.6 · JSON schema        │
│                     enforcement · token + cost logging     │
├───────────────────────────────────────────────────────────┤
│  Retrieval          BM25 + dense hybrid · RRF (k=60)       │
│                     · temporal filter · cross-encoder      │
│                     reranking · parent-child expansion     │
├───────────────────────────────────────────────────────────┤
│  Ingestion          PyMuPDF + pdfplumber · hierarchical    │
│                     chunking · BGE-large-en-v1.5 · Qdrant  │
├───────────────────────────────────────────────────────────┤
│  Foundation         config · core · schemas · utils        │
│                     · storage · observability · models     │
└───────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Why |
|---|---|
| **Store pre-reranking top-40** | Stage 3 ablation requires the full candidate list before reranking. Without it, counterfactual reranker inputs are impossible without re-inference. |
| **RRF k=60** | Standard value from Cormack et al. (2009); changing it requires re-benchmarking retrieval quality. |
| **BGE-large-en-v1.5** | 1024-dimensional embeddings outperform smaller models on domain-specific technical text. |
| **3-class NLI heuristic** | deberta-v3-base's three-class output (entailment/contradiction/neutral) catches conditionally valid claims that binary models miss. |
| **O(1) evidence log lookup** | SQLite byte-offset index means trace replay never requires full-file scans even at scale. |
| **Boundary-aware chunking** | Section boundaries are never split across child chunks — required for Stage 1 ablation to be meaningful. |

---

## The Four-Stage Ablation Engine

```
Query → Chunking → Retrieval → Reranking → Generation → Answer
           │           │            │            │
        Stage 1     Stage 2      Stage 3      Stage 4
        ablation    ablation     ablation     ablation
           └───────────┴────────────┴────────────┘
                    Quality Delta Attribution
```

**Stage 1 (Chunking)**: Swap boundary-naive collection for boundary-aware. Measure Recall@5 delta. If chunking cut a critical clause, gold chunks re-appear.

**Stage 2 (Retrieval)**: Inject gold `supporting_chunk_ids` from the annotation dataset. Measure quality delta with perfect retrieval. Large delta → retrieval is the bottleneck.

**Stage 3 (Reranker)**: Reconstruct retrieval context from the stored `pre_rerank_top40` at cutoffs top-1/3/5/8. No re-inference needed — the trace stores all scores. Large delta at one cutoff → reranker is burying the right evidence.

**Stage 4 (Generation)**: Replay with the historical retrieval context and baseline system prompt. Delta from original → generation contribution.

### Example Attribution Report

```json
{
  "question_id": "qa-031",
  "query": "What are the OSHA PELs for respirable crystalline silica?",
  "primary_root_cause": "retrieval",
  "stage_attributions": {
    "chunking":   -0.02,
    "retrieval":  -0.31,
    "reranking":  -0.08,
    "generation": -0.04
  },
  "heuristic_signals": [
    "Gold chunk osha-1926-1153-ch-0051 absent from pre-rerank top-40",
    "BM25 score for gold chunk below 5th percentile"
  ],
  "original_quality_score": 0.84,
  "ablated_quality_score":  0.49,
  "total_quality_delta":    -0.35
}
```

> RAGAS faithfulness scored this answer at **0.82**. Veriducta correctly identified the retrieval stage as the root cause — the gold chunk was never retrieved.

---

## Retrieval Pipeline

```
Query
  ├──► BM25 (rank-bm25, top-100) ─────────────────────┐
  └──► Dense (BGE-large-en-v1.5 + Qdrant, top-100) ──► RRF Fusion (k=60)
                                                         │
                                                   Temporal Filter
                                                   (version graph)
                                                         │
                                         Cross-Encoder Reranker
                                         ms-marco-MiniLM-L-12-v2
                                         top-40 input → top-8 output
                                                         │
                                          Parent-Child Expander
                                                         │
                                               RetrievalResult
                                          + RetrievalTrace (evidence log)
```

Every BM25 score, dense score, RRF rank, temporal filter decision, and the full pre-reranking top-40 list with scores are stored. The replay engine tests counterfactuals without re-running inference.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **LLM** | Claude Sonnet 4.6 |
| **Embedding** | `BAAI/bge-large-en-v1.5` — 1024-dimensional |
| **NLI** | `cross-encoder/nli-deberta-v3-base` — 3-class |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-12-v2` |
| **Vector DB** | Qdrant (cosine distance, 1024-dim) |
| **BM25** | `rank-bm25` (Okapi BM25) |
| **PDF parsing** | PyMuPDF + pdfplumber |
| **API** | FastAPI 0.115 + uvicorn |
| **Frontend** | Next.js 15 + TailwindCSS + Framer Motion + Recharts |
| **Metrics** | Prometheus |
| **Tracing** | OpenTelemetry |
| **Evidence log** | JSONL + SQLite index (O(1) byte-offset lookup) |
| **CI** | GitHub Actions |

---

## Installation

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose (for Qdrant, MinIO, Prometheus, Grafana)
- Anthropic API key

### 1. Clone and set up Python environment

```bash
git clone https://github.com/hardik-gupta/veriducta.git
cd veriducta
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Start infrastructure

```bash
docker compose up -d qdrant minio prometheus grafana
```

### 4. Run the API

```bash
uvicorn api.app:create_app --factory --reload --port 8080
```

### 5. Ingest the corpus

```bash
python scripts/ingest_corpus.py --corpus-dir data/corpus/
```

### 6. Start the frontend

```bash
cd frontend && npm install && npm run dev
# Open http://localhost:3000
```

---

## Running Evaluations

### Full evaluation harness (40 golden QA questions)

```bash
python scripts/run_evaluation.py --output evaluation_report.json
```

### Synthetic corruption benchmark (60 cases)

```bash
python scripts/run_benchmark.py --corruptions data/synthetic_corruptions/corruptions.jsonl
```

### CI regression gate

```bash
python scripts/check_regression_gate.py \
  --report evaluation_report.json \
  --baseline ci_baseline.json
# Exits 0 if all 5 conditions pass; exits 1 with details if any fail
```

### Five blocking regression conditions

| Condition | Threshold |
|---|---|
| Faithfulness drop | > 2% from baseline |
| Recall@5 drop | > 3% from baseline |
| p95 latency increase | > 20% from baseline |
| Root-cause accuracy drop | > 5% from baseline |
| Unauthorized evidence exposure | > 0% |

---

## Project Structure

```
veriducta/
├── api/               HTTP layer — routing, middleware, DI
├── config/            Pydantic settings (lru_cached)
├── core/              Exception hierarchy, abstract interfaces
├── schemas/           Shared Pydantic models
├── models/            ML model wrappers (BGE, NLI, reranker)
├── utils/             Pure stateless helpers
├── storage/           Qdrant + MinIO abstractions
├── observability/     Prometheus, OpenTelemetry, evidence log
├── ingestion/         PDF → chunks → embeddings → Qdrant
├── retrieval/         BM25 + dense + RRF + temporal + reranker
├── generation/        Claude generation + NLI verification
├── verification/      Claim-level verification orchestration
├── replay/            Four-stage causal ablation engine
├── evaluation/        Evaluation harness + RAGAS + regression gate
├── scripts/           CLI entry points
├── tests/             pytest suite (801 tests, 92.8% coverage)
├── frontend/          Next.js 15 dashboard
├── docs/              Architecture + portfolio docs
└── docker/            Qdrant, MinIO, Prometheus, Grafana configs
```

---

## The RAGAS Gap

RAGAS measures faithfulness and context recall but cannot answer: **"Which stage caused this failure?"**

| Capability | RAGAS | Veriducta |
|---|---|---|
| Faithfulness scoring | ✓ | ✓ |
| Context recall | ✓ | ✓ |
| Omission rate | — | ✓ |
| Causal root-cause attribution | — | ✓ |
| Temporal-valid retrieval rate | — | ✓ |
| Contradiction acknowledgment rate | — | ✓ |
| Replayable retrieval traces | — | ✓ |
| Stage-level quality delta | — | ✓ |

A high RAGAS faithfulness score does not mean the answer is complete. Veriducta found cases where RAGAS scored an answer ≥ 0.80 while it omitted a critical regulatory clause — because the gold chunk was never in the pre-rerank top-40.

---

## Testing

```bash
pytest                                    # 801 tests, ~92.8% coverage
pytest tests/integration/                 # live Qdrant/MinIO required
pytest -k "test_ablation"                 # causal replay tests only
make lint && make type-check              # ruff + mypy --strict
```

Current: **801 passed, 0 failed · 92.81% coverage**

---

## CI

```yaml
# .github/workflows/regression_gate.yml
on: [push, pull_request]
jobs:
  quality-gates:
    steps:
      - ruff check .           # linting
      - ruff format --check .  # formatting
      - mypy .                 # type checking (strict)
      - pytest --cov=. --cov-fail-under=80
      - python scripts/check_regression_gate.py
```

---

## Known Limitations

1. **CPU-only inference** — All three ML models run on CPU. p50 ~2.8s. GPU inference would reduce to sub-second.
2. **Single-worker API** — Thread-safe multi-worker deployment is not implemented.
3. **BM25 in memory** — Full BM25 index loaded at startup (~50 MB for a 50-document corpus).
4. **No authentication** — Evidence logs should not be exposed over HTTP without access control.
5. **BM25-only counterevidence** — Dense retrieval might surface additional contradictions.

---

## FAQ

**Why not just use LangSmith or Langfuse?**
They trace calls but cannot attribute failures to pipeline stages. Veriducta stores the complete retrieval state needed for counterfactual replay — pre-reranking candidates with scores, temporal filter decisions, RRF ranks — and uses it to run ablations without any additional inference.

**Why store the pre-reranking top-40?**
Stage 3 ablation reconstructs different retrieval contexts (top-1, top-3, top-5, top-8 cutoffs) from the stored candidates. Without the pre-reranking list, you would need to re-run dense retrieval and BM25 for every ablation — expensive and non-deterministic.

**Is this production-ready?**
The backend is production-quality (typed, tested, structured logging, metrics, CI-gated). The MVP runs single-worker. GPU inference, auth, and horizontal scaling are documented limitations.

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Case Study](docs/case_study.md)
- [Technical Decisions](docs/technical_decisions.md)
- [Engineering Challenges](docs/engineering_challenges.md)
- [Performance Analysis](docs/performance_analysis.md)
- [Research Notes](docs/research_notes.md)

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built with precision by Hardik Gupta*
