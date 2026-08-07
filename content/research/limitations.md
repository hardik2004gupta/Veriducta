# Research - Known Limitations

*Honest analysis of what Veriducta cannot do and why.*

---

## 1. Stage 2 Requires Oracle Annotation

**What**: Retrieval attribution (Stage 2) requires human-annotated `supporting_chunk_ids` - a list of chunks that should ground the correct answer.

**Why it matters**: Without annotation, the replay engine cannot determine whether a given retrieval context is "correct." Stage 2 is oracle-dependent by design.

**Impact**: Stage 2 cannot run on unannotated production queries. For unannotated queries, the system falls back to the heuristic-only attribution mode, which uses Stages 1, 3, and 4 only.

**Potential mitigation**: Query-agnostic chunk importance scoring - rank chunks by expected contribution to a correct answer without a reference. This is an open research problem. The closest existing work is ARES (Saad-Falcon et al. 2023), which trains domain-specific judges, but these require labeled data.

---

## 2. Stage 4 LLM Stochasticity

**What**: Generation attribution (Stage 4) compares original generation quality against baseline-prompt generation. LLM outputs are stochastic - the same context and prompt produce different outputs at temperature > 0.

**Why it matters**: A 0.02–0.05 quality delta might be signal (the prompt caused the failure) or noise (temperature variance). The two are indistinguishable without an oracle.

**Impact**: Stage 4 attribution accuracy: 50% - equivalent to random attribution on generation cases.

**Current mitigation**: Wider attribution threshold for Stage 4 (0.10 vs. 0.15 for other stages). Explicit confidence flag in ReplayReport. Heuristic disclaimer on all Stage 4 attribution outputs.

**Potential mitigations** (not implemented):
- Run Stage 4 N=3 times, average quality scores (reduces variance, 3× latency)
- Use temperature=0 for both original and baseline replay (deterministic, but changes the generation distribution)
- Train a learned quality scorer as a reference-free judge

---

## 3. Sequential Ablation Cannot Model Inter-Stage Interactions

**What**: The four stages are run sequentially, and the stage with the largest quality delta is labeled the primary root cause. This ignores inter-stage interactions.

**Example interaction**: A reranker error drops the correct chunk, which was retrieved because the chunker put the right tokens in the right chunk. Fix: Stage 1 doesn't help (chunking was fine). Stage 3 fires (reranker dropped the chunk). But the Stage 3 delta and Stage 1 delta may be similar, causing ambiguous attribution.

**Impact**: Cases where multiple stages contribute roughly equally to the failure are misclassified or attributed to the wrong stage. This partially explains the 26.7% misclassification rate overall.

**Potential mitigation**: Replace sequential ablation with a causal directed acyclic graph (DAG) that explicitly models inter-stage dependencies and uses do-calculus for attribution. This is a significant research extension.

---

## 4. Chunking Failure Corpus Coverage

**What**: Stage 1 ablation only runs for documents in the "chunking failure corpus" - documents where boundary-aware and boundary-naive configurations produce materially different splits. Documents not in the corpus are assumed chunking-neutral.

**Why**: Maintaining a boundary-aware Qdrant collection for every document would double storage requirements and complicate the ingestion pipeline.

**Impact**: Chunking failures in documents not in the failure corpus will be missed by Stage 1 and potentially misattributed to retrieval (Stage 2) or treated as unknown.

**Mitigation**: Expand the failure corpus coverage during ingestion by running both configurations on every new document and flagging those with material differences. This adds ~20% ingestion latency.

---

## 5. Single-Corpus Generalization

**What**: All evaluation results are from a 30–50 document corpus of public engineering and regulatory documents (OSHA, NIST, USGS). The benchmark covers four failure modes constructed for this corpus.

**Unknown generalization**: Performance on conversational corpora, multilingual documents, academic papers, or code documentation is untested. Chunking boundary detection uses regulatory document conventions (section numbers, "Employer must" clauses, table headers) that don't apply to other genres.

**Impact**: Attribution accuracy on other domains may be materially lower. The 73.3% figure should not be cited as a general benchmark.

---

## 6. CPU-Only Inference Latency

**What**: All three ML models (BGE-large-en-v1.5, ms-marco-MiniLM-L-12-v2, nli-deberta-v3-base) run on CPU. GPU acceleration is not implemented.

**Impact**:
- Dense embedding: 680ms p50 (vs. ~70ms on GPU)
- Cross-encoder reranking: 950ms p50 (vs. ~100ms on GPU)
- p95 end-to-end: 7.4s (vs. estimated ~1.5s on GPU)

This limits real-time interactive use cases with strict latency requirements.

**Mitigation**: v1.2 plans GPU acceleration via sentence-transformers CUDA backend. Until then, the LRU embedding cache (TTL 1 hour) partially mitigates repeat query latency.

---

## 7. Single-Worker API

**What**: The FastAPI application runs with `uvicorn` in single-worker mode. ML models are not thread-safe for concurrent write operations; they are loaded once and used read-only.

**Impact**: Not suitable for high-concurrency production deployments. Concurrent queries serialize at the model inference step.

**Mitigation**: v2.0 plans async pipeline execution with a thread pool for ML inference and multi-worker uvicorn support.

---

## 8. No Authentication

**What**: The API has no authentication layer. All endpoints are publicly accessible.

**Impact**: Not suitable for deployment on public networks without a reverse proxy with authentication (nginx, Caddy, or Cloudflare Access).

**Mitigation**: v2.0 plans JWT authentication. For v1.0, the intended deployment is trusted local network or private cloud VM.

---

## 9. Temporal Graph Requires Manual Maintenance

**What**: The version graph (which documents supersede which, and when) is built from JSON sidecar metadata. Sidecar fields (`supersedes`, `effective_date`) must be maintained manually when new corpus documents are added.

**Impact**: A stale version graph silently fails: superseded documents appear as current, temporal filtering doesn't reject them, and answers may use outdated information.

**Mitigation**: `scripts/validate_sidecars.py` validates all sidecars and reports inconsistencies. v1.2 plans automatic temporal drift detection.

---

## 10. RAGAS Comparison Adapter

**What**: The RAGAS comparison adapter is an optional dependency (`pip install veriducta[ragas]`). When unavailable, the evaluation report omits RAGAS metrics.

**Impact**: The RAGAS comparison table in evaluation reports is conditional. CI cannot enforce RAGAS metrics if the optional dependency is not installed.

**Note**: This is a documentation limitation, not a measurement limitation. Veriducta's own metrics are computed without RAGAS.
