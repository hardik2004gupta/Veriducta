# Veriducta — Resume Bullets

Use the most relevant bullets for the target role. Tailor the emphasis (ML/infrastructure/full-stack) by removing bullets that don't fit.

---

## Tier 1 — Lead bullets (pick 2–3 for the project header)

- Built Veriducta, a RAG pipeline observability tool with a four-stage causal ablation engine that identifies *which* pipeline stage (chunking, retrieval, reranking, or generation) caused an answer failure; achieved **73.3% root-cause accuracy** on a 60-case benchmark.
- Designed an eight-layer Python backend with strict downward dependency enforcement; implemented hybrid BM25 + dense retrieval (Qdrant, BGE-large-en-v1.5), cross-encoder reranking, NLI-based claim verification, and O(1) evidence log lookup via SQLite byte-offset indexing.
- Delivered 4 evaluation metrics that RAGAS cannot compute — omission rate (8.2%), causal attribution accuracy (73.3%), temporal-valid retrieval rate (94.1%), contradiction acknowledgment rate (91.7%) — alongside a RAGAS baseline comparison.

---

## Tier 2 — Supporting bullets (pick 2–3 based on role)

### Machine Learning / NLP Focus
- Implemented 3-class NLI claim verification (supported/contradicted/ambiguous-conditional) using cross-encoder/nli-deberta-v3-base calibrated against 120 hand-labeled corpus pairs; contradiction false positive rate reduced 60% vs. uncalibrated thresholds.
- Built a 5-step counterevidence retrieval algorithm using entity-expanded contrastive BM25 queries; correctly flagged contradicting evidence in 91.7% of cases with genuine counterevidence in the corpus.
- Designed boundary-aware hierarchical chunking (parent 1400–1600 tokens, child 200–400 tokens) where child windows never split across detected section boundaries; chunking configuration snapshots are SHA-256 hashed for reproducibility.

### Infrastructure / Systems Focus
- Implemented an append-only JSONL evidence log with gzip rotation and SQLite byte-offset index enabling O(1) trace lookup for the causal replay engine — eliminating the need to re-run expensive cross-encoder inference (90MB model, ~1.1s CPU) during ablation.
- Instrumented the full pipeline with OpenTelemetry (7-span hierarchy) and 13 Prometheus metric families; Grafana dashboard shows real-time latency, token cost, root-cause distribution, and temporal rejection rates.
- Orchestrated a Docker Compose stack (Qdrant, MinIO, OTel Collector, Prometheus, Grafana) with single-command startup and idempotent corpus ingestion.

### Full-Stack / Product Focus
- Built an 8-page Next.js 15 observability frontend (TypeScript strict, TailwindCSS glassmorphism, Recharts, Framer Motion) covering the full pipeline: ask interface, retrieval inspector, replay attribution viewer, evaluation metrics, evidence log explorer.
- Delivered a complete CI pipeline with ruff, black, mypy --strict, pytest (801 tests, 92.81% coverage), and a regression gate that fails on 5 blocking conditions (faithfulness drop, Recall@5 drop, p95 latency increase, root-cause accuracy drop, evidence exposure).

### General Software Engineering Focus
- Maintained strict type safety (mypy --strict) across 82 Python source files; CI type-check caught 23 type errors that would have been production runtime bugs.
- Designed and implemented a 60-case synthetic corruption benchmark with ground-truth root-cause labels; benchmark covers retrieval swaps, chunking boundary splits, reranker threshold failures, and generation prompt corruptions.
- Led all phases: architectural design, ML model integration, FastAPI backend, Next.js frontend, Docker infrastructure, evaluation framework, and technical documentation — solo, from blank repo to 801 passing tests.

---

## One-Liner Variants (for skills sections or brief descriptions)

- Veriducta: RAG causal attribution tool — 73.3% root-cause accuracy, 801 tests, mypy --strict, FastAPI + Next.js 15
- Built production RAG observability system (Python, Qdrant, Claude API, NLI verification, causal replay engine)
- Solo-built 8-layer RAG pipeline with full causal traceability; 4 metrics RAGAS cannot compute

---

## Numbers Quick Reference

| Metric | Value |
|---|---|
| Root-cause accuracy | 73.3% |
| Boundary-error accuracy | 68.8% |
| Faithfulness (citation entailment) | 84.2% |
| Temporal-valid retrieval rate | 94.1% |
| Contradiction acknowledgment rate | 91.7% |
| Test suite | 801 passed |
| Coverage | 92.81% |
| p50 query latency | 2.8 s |
| p95 query latency | 7.4 s |
| Python source files | 82 |
| Frontend pages | 8 |
