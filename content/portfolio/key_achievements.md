# Veriducta - Key Achievements

---

## Technical Achievements

### 1. Causal Attribution Engine - Core Innovation
**What**: A four-stage ablation engine that identifies the root-cause pipeline stage for answer failures, using stored retrieval traces for replay without re-inference.

**Why it's hard**: Most observability tools measure outcomes; attribution requires counterfactual reasoning over historical executions. Stage 3 (reranker) ablation in particular requires the full pre-reranking score list - otherwise you'd need to re-run the cross-encoder for every historical query investigated.

**Result**: 73.3% root-cause accuracy on 60-case benchmark; 68.8% on the harder boundary-error subset. Both targets exceeded.

### 2. Four Metrics RAGAS Cannot Compute
**What**: Omission rate (8.2%), causal attribution accuracy (73.3%), temporal-valid retrieval rate (94.1%), contradiction acknowledgment rate (91.7%).

**Why it matters**: Faithfulness-based metrics cannot measure what was not said. Omission detection requires comparing the retrieved context against the expected completeness profile - which requires knowing what should have been retrieved (Stage 2 annotation) or detecting boundary splits (Stage 1 ablation).

### 3. O(1) Evidence Log Lookup
**What**: JSONL append-only log with SQLite byte-offset index. Trace lookup is a single primary-key read + file seek.

**Why it's elegant**: JSONL gives human-readable, scannable output. The SQLite index eliminates the O(n) scan without requiring a full database. For an append-only write pattern with point reads, this is the correct tradeoff.

### 4. Boundary-Aware Chunking with Verifiable Reproducibility
**What**: Hierarchical chunker that never splits child windows across detected section boundaries. Configuration snapshots are SHA-256 hashed and stored, making every ingestion run comparable across time.

**Impact**: Chunking attribution accuracy 73% vs. estimated 40–50% with boundary-naive chunking. The OSHA silica case recovered a Recall@5 delta of 0.41 by switching to boundary-aware chunking.

### 5. 3-Class NLI Heuristic Calibrated on Corpus
**What**: Custom threshold calibration (120 hand-labeled pairs) for a 3-class NLI model (supported/contradicted/ambiguous-conditional). Reduced false positive contradictions by 60%.

**Why custom calibration matters**: Regulatory language uses conditional constructions that uncalibrated NLI models score as contradictions. The domain requires a more conservative contradiction threshold.

---

## Engineering Achievements

### 6. 801 Tests, 92.81% Coverage, mypy --strict
Solo implementation of a full test suite across 8 pipeline layers. All tests pass without mock-based shortcuts for Qdrant or MinIO (integration tests use real service instances).

mypy --strict enforced across 82 Python source files. CI type-check gate caught 23 type errors during development that would have been production runtime bugs.

### 7. Complete Infrastructure as Code
Single `docker compose up` starts: API, Qdrant, MinIO, OTel Collector, Prometheus, Grafana. No manual configuration. No service dependency issues. All volumes mounted and pre-configured.

### 8. Five-Condition CI Regression Gate
Blocks merges that introduce:
1. Faithfulness drop > 2%
2. Recall@5 drop > 3%
3. p95 latency increase > 20%
4. Root-cause accuracy drop > 5%
5. Any unauthorized evidence exposure

This gate ensures the pipeline cannot regress silently - every performance metric is gated.

### 9. Production Observability Stack
- 7-span OTel hierarchy across all pipeline stages
- 13 Prometheus metric families (latency histograms, token counters, cost accumulators, root-cause counters)
- Grafana dashboard with real-time latency, cost, and attribution distribution

### 10. Full-Stack Frontend in 8 Pages
Next.js 15, TypeScript strict, TailwindCSS (glassmorphism dark theme), Recharts, Framer Motion. Pages: Landing, Dashboard, Ask Veriducta, Retrieval Inspector, Replay Attribution Viewer, Evaluation, Evidence Log Explorer, Settings. All pages responsive with real data schemas.

---

## Quantitative Summary

| Achievement | Metric |
|---|---|
| Root-cause accuracy (primary) | **73.3%** |
| Root-cause accuracy (boundary-error) | **68.8%** |
| Faithfulness (citation entailment) | **84.2%** |
| Temporal-valid retrieval rate | **94.1%** |
| Contradiction acknowledgment rate | **91.7%** |
| Omission rate | **8.2%** |
| Test coverage | **92.81%** |
| Tests passing | **801** |
| p50 query latency | **2.8 s** |
| p95 query latency | **7.4 s** |
| Total model memory | **~1.93 GB** |
| Source files (Python) | **82** |
| Frontend pages | **8** |
