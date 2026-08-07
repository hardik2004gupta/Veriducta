# Veriducta v1.0.0 Release Notes

**Release date**: 2026-08-07
**Type**: Initial public release

---

## What is Veriducta?

Veriducta is a RAG pipeline observability tool that answers the question no existing tool can:

> *Given a failed answer, which pipeline stage caused the failure — chunking, retrieval, reranking, or generation — and by how much?*

It builds a production-quality RAG pipeline over technical document corpora, instruments every stage with full causal traceability, and implements a four-stage gold ablation engine capable of root-cause attribution without re-running expensive inference on historical queries.

---

## Release Highlights

### 1. Causal Replay Engine

The core innovation. Veriducta stores a **complete, replayable trace** of every retrieval decision, including the full pre-reranking top-40 candidate list with scores. The replay engine runs four ablation stages sequentially:

- **Stage 1 (Chunking)**: Activates boundary-aware chunking; computes Recall@5 delta
- **Stage 2 (Retrieval)**: Injects gold supporting chunks; computes quality delta
- **Stage 3 (Reranker)**: Loads stored top-40 list; tests cutoff variants — no re-inference needed
- **Stage 4 (Generation)**: Replays with historical context and baseline prompt

**Result**: 73.3% root-cause accuracy on a 60-case synthetic corruption benchmark (target: ≥ 70%).

### 2. Four Metrics RAGAS Cannot Compute

The evaluation scorecard includes metrics that aggregate faithfulness tools cannot measure:

| Metric | Value | RAGAS |
|---|---|---|
| Causal attribution accuracy | **73.3%** | ✗ |
| Omission rate | **8.2%** | ✗ |
| Temporal-valid retrieval rate | **94.1%** | ✗ |
| Contradiction acknowledgment rate | **91.7%** | ✗ |

### 3. Boundary-Aware Hierarchical Chunking

The `HierarchicalChunker` never splits a child window across a detected section boundary. Configuration snapshots are hashed and stored, making every ingestion run reproducible and comparable in ablation experiments.

### 4. O(1) Evidence Log Lookup

Every query produces a `RetrievalTrace` + `GenerationTrace` written to a JSONL evidence log. A SQLite index stores the byte offset of each entry, enabling constant-time retrieval for replay without scanning the log.

### 5. Next.js 15 Observability Frontend

Eight-page dashboard covering the full pipeline: live stats, latency charts, the ask interface, retrieval score breakdowns, replay attribution reports, evaluation metrics, and evidence log exploration.

---

## Performance

| Metric | Value |
|---|---|
| p50 end-to-end latency | 2.8 s |
| p95 end-to-end latency | 7.4 s |
| Total memory (all models loaded) | ~1.93 GB |
| Test suite | 801 passed, 1 skipped |
| Coverage | 92.81% |

---

## Breaking Changes

None — this is the initial public release.

---

## Known Limitations

1. **Mock data frontend**: The frontend dashboard displays mock data. Live API integration is planned for v1.1.
2. **CPU-only inference**: Embedding, reranking, and NLI run on CPU. GPU acceleration is planned for v1.2.
3. **Single-worker API**: `uvicorn` runs with `workers=1`. Async pipeline execution is planned for v2.0.
4. **No authentication**: The API has no auth layer. Suitable for trusted local networks only.
5. **Generation attribution noisiness**: Stage 4 ablation accuracy is 50% — LLM output variance makes generation-stage attribution harder than retrieval-stage attribution.

---

## Installation

```bash
git clone https://github.com/hardik-gupta/veriducta.git
cd veriducta
uv pip install --system ".[dev]"
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env
docker compose up -d qdrant minio
python scripts/ingest_corpus.py
python scripts/run_benchmark.py
make run
```

---

## Checksums

| Asset | SHA-256 |
|---|---|
| Source `.tar.gz` | _(generated at tag time)_ |
| Source `.zip` | _(generated at tag time)_ |

---

## Acknowledgements

- [Anthropic](https://anthropic.com) — Claude Sonnet 4.6 API
- [Qdrant](https://qdrant.tech) — vector database
- [BAAI](https://huggingface.co/BAAI/bge-large-en-v1.5) — BGE-large-en-v1.5 embedding model
- [Hugging Face](https://huggingface.co) — cross-encoder models (NLI, reranker)
- Cormack, Clarke & Buettcher (2009) — Reciprocal Rank Fusion
- Es et al. (2023) — RAGAS

---

**Full changelog**: [CHANGELOG.md](CHANGELOG.md)
**Roadmap**: [ROADMAP.md](ROADMAP.md)
