# I Built a Tool That Tells You *Why* Your RAG Pipeline Failed — Not Just That It Did

*How causal attribution, replayable traces, and a four-stage ablation engine expose what RAGAS misses*

---

## The Problem

RAGAS gave me a faithfulness score of 0.82. The answer was wrong.

Not hallucinated — every sentence in the answer was factually supported by the retrieved context. But it was missing the most important number in the entire document: the permissible exposure limit for crystalline silica that OSHA's 1926.1153 standard mandates for construction workers.

The answer didn't lie. It just didn't say enough.

This distinction — between *not hallucinating* and *answering completely* — is the core problem I set out to solve with Veriducta.

---

## Why Existing Tools Fall Short

Modern RAG evaluation tools (RAGAS, DeepEval, TruLens, Arize Phoenix) are excellent at measuring what they measure. Faithfulness checks whether answer claims are entailed by the retrieved context. Answer relevance checks whether the answer addresses the question. Context precision measures signal-to-noise in the retrieved chunks.

None of them tell you *why* a particular query produced a bad answer. And critically, none of them can distinguish between four very different failure modes that look identical from the outside:

1. A **chunking boundary** split the critical clause across two chunks, so retrieval never saw the complete fact
2. A **retrieval miss** — the right chunk exists but BM25 and dense retrieval both ranked it outside the top-k
3. A **reranker error** — the right chunk was in the top-40 fusion candidates, but the cross-encoder pushed it below the cutoff
4. A **generation failure** — the right chunk was retrieved, but the LLM omitted or misrepresented it

These require different fixes. Improving your chunking strategy won't help if the root cause is a reranker threshold. Fine-tuning your prompt won't help if the chunk containing the answer was never retrieved.

Veriducta's design premise is simple: **you cannot improve a RAG pipeline you cannot diagnose**.

---

## Architecture Overview

Veriducta builds a complete production RAG pipeline with one critical addition: every component is instrumented to emit a fully replayable trace.

```
PDF Corpus
    ↓ HierarchicalChunker (boundary-aware, 200–400 token child chunks)
    ↓ BGELargeEmbedding (BAAI/bge-large-en-v1.5, 1024-dim)
    ↓ Qdrant (cosine distance) + BM25 index (rank-bm25)
                        ↓ QUERY
    BM25Retriever (top-100) + DenseRetriever (top-100)
    ↓ RRF Fusion (k=60, Cormack et al. 2009)
    ↓ TemporalFilter (version graph, rejects superseded/not_yet_effective)
    ↓ CrossEncoderReranker (ms-marco-MiniLM-L-12-v2, top-40 → top-8)
    ↓ ParentChildExpander (fetch 1400-token parent section per child)
    ↓ VeriductaGenerator (Claude Sonnet 4.6, JSON schema enforcement)
    ↓ VeriductaVerifier (NLI + counterevidence scan)
    ↓ StructuredAnswer with per-claim verification status
```

The pipeline is built in eight strict layers with downward-only dependency enforcement. No layer imports from a layer above it. This constraint is not just architectural discipline — it's what makes the replay engine possible. Because each layer is stateless and receives its inputs as typed schemas, any layer can be re-executed with substitute inputs without re-running the layers above it.

---

## The Evidence Log: The Key Implementation Insight

Every query produces two trace records written to a JSONL evidence log:

**`RetrievalTrace`** contains:
- The query and query date
- BM25 scores, dense scores, and RRF rank for every candidate
- Temporal filter decisions (with rejection reasons)
- The **full pre-reranking top-40 candidate list with cross-encoder scores**
- The final top-8 candidates after reranking and expansion
- The `ConfigurationSnapshot` hash (identifies the exact chunking and retrieval config)

**`GenerationTrace`** contains:
- Input and output tokens, estimated cost, latency
- The `retrieval_trace_id` linking back to the retrieval record
- The prompt hash and generation config hash

A SQLite index maps `trace_id → (log_file, byte_offset)`. Lookup is O(1): seek directly to the byte position in the JSONL file without scanning.

The pre-reranking top-40 list is the insight that makes Stage 3 ablation tractable. Instead of re-running the cross-encoder (a 90MB model, ~1.1 second inference) for historical queries, the replay engine reads the stored candidates and simply tests different cutoff thresholds. The cross-encoder doesn't move; only the cutoff does.

---

## The Four-Stage Causal Ablation Engine

The replay engine answers attribution questions by running counterfactual experiments against historical traces.

### Stage 1 — Chunking

The question: *would a different chunking configuration have retrieved the right chunks?*

For documents in the "chunking failure corpus" (documents where boundary-aware and boundary-naive configurations produce materially different splits at critical clauses), Stage 1 replays retrieval using the boundary-aware collection and computes the Recall@5 delta.

If the Recall@5 delta exceeds the attribution threshold (0.15), Stage 1 is flagged as the root cause.

The OSHA silica example: Recall@5 0.45 → 0.80 under boundary-aware chunking. Delta: −0.41. **Chunking is root cause.**

### Stage 2 — Retrieval

The question: *if the correct chunks had been retrieved, would the answer have been complete?*

Stage 2 injects the gold `supporting_chunk_ids` from the ground-truth annotation into the context and replays generation. If the quality delta with gold chunks exceeds the threshold, retrieval is flagged.

This stage separates "chunking didn't produce the right chunks" from "the right chunks exist but retrieval didn't find them."

### Stage 3 — Reranker

The question: *was the correct chunk in the pre-reranking top-40 but dropped by the cross-encoder?*

Stage 3 loads the stored `pre_rerank_top40` from the evidence log and tests four cutoff variants (top-1, top-3, top-5, top-8). If quality improves substantially at a wider cutoff, the reranker is flagged.

This is the stage that would be prohibitively expensive without stored traces. Testing four cutoffs requires four generation calls — but no additional retrieval or embedding.

### Stage 4 — Generation

The question: *given the exact retrieval context that was actually used, is the failure attributable to the LLM?*

Stage 4 replays generation with the original retrieval context using a baseline prompt. If quality differs substantially from the original, generation is flagged.

Generation attribution is noisiest because LLM outputs vary even with identical inputs. Stage 4 accuracy in our benchmark is 50% — the honest engineering answer is that generation-stage attribution is an open research problem.

---

## The Worked Example: OSHA 1926.1153

The question: *"What are the permissible exposure limits for respirable crystalline silica under OSHA 1926.1153, and when does medical surveillance become mandatory?"*

A correct answer requires three facts from pages 4–5 of the standard:
1. Action level (AL): 25 µg/m³ as an 8-hour TWA
2. Permissible exposure limit (PEL): 50 µg/m³ as an 8-hour TWA
3. Medical surveillance trigger: AL for ≥ 30 days per year

**What happened**: The boundary-naive chunker split at a 512-token boundary mid-paragraph — between the AL definition and the PEL. Chunk `OSHA-1153-ch-0012` (AL) ranked first in retrieval. Chunk `OSHA-1153-ch-0015` (PEL + surveillance threshold) started a new chunk that ranked 11th and was dropped by the cross-encoder at the reranking step.

The generator received context containing the AL and the surveillance trigger, but not the PEL. Its answer was:

> "OSHA 1926.1153 establishes an action level of 25 µg/m³. Workers exposed above this level for 30 or more days per year must receive medical examinations."

Everything stated is correct. The PEL — the primary regulatory threshold — is absent.

**RAGAS faithfulness: 0.82.** All stated claims are entailed by retrieved context. No alert triggered.

**Veriducta Stage 1 delta: −0.41.** Attribution threshold: 0.15. Chunking flagged with confidence 0.88.

**After fix** (boundary-aware chunking): PEL chunk retrieved at rank 2. Quality score: 0.52 → 0.93. RAGAS faithfulness: 0.82 → 0.91.

This is the case that motivated the project. A metric that measures what-was-said cannot measure what-was-omitted. Omission is often more dangerous than hallucination in high-stakes domains — the professional relying on the threshold number never gets a factual error to catch; they get silence where the answer should be.

---

## Engineering Decisions That Were Non-Obvious

### Why store the pre-reranking top-40?

The naive approach would be to re-run the cross-encoder during ablation. The cross-encoder model (ms-marco-MiniLM-L-12-v2, ~90MB) runs a batch of 40 query-chunk pairs in approximately 1.1 seconds on CPU. For a 60-case corruption benchmark with four cutoff variants per case, that would add ~264 seconds of redundant inference.

Storing the scored top-40 list in the evidence log (each entry is ~8KB of JSON) costs less than 500KB per query. The tradeoff is trivially favorable.

The deeper reason: the replay engine is designed to be *evidence-based*, not inference-based. Its job is to explain historical queries, not re-run them. Every claim it makes should be traceable to observed data, not new inference.

### Why RRF with k=60?

Reciprocal Rank Fusion (Cormack et al. 2009) is the standard fusion algorithm for combining heterogeneous ranked lists. The constant k=60 is the value validated in the original paper. Changing it requires re-benchmarking retrieval quality — not a decision to make lightly.

The implementation assigns rank 101 to candidates absent from a list (i.e., BM25 found it but dense didn't, or vice versa). This produces a deterministic fusion score for every candidate across both lists.

### Why the 3-class NLI heuristic instead of a learned verifier?

The thresholds (entailment > 0.65 for supported; contradiction > 0.85 and neutral < 0.30 for contradicted) were chosen based on validation against a held-out annotation set of 120 claim-context pairs. A learned verifier would require labeled training data that is corpus-specific — defeating the goal of building a general observability tool.

The 3-class heuristic is conservative: it prefers `ambiguous_conditional` over `contradicted` to avoid false positives on nuanced regulatory language. This is correct for the domain — a spurious `contradicted` label on an expert-reviewed standard is worse than a cautious `ambiguous_conditional`.

### Why SQLite for the evidence log index?

The evidence log is append-only JSONL — append is fast, but seeks are O(n) without an index. The alternative to SQLite is an in-memory index that doesn't survive process restarts, or a separate database (PostgreSQL) that introduces infrastructure complexity.

SQLite is a single file, transactions are ACID, and lookup by trace_id + byte_offset is a single primary key read. For an MVP with a single-worker API, this is the correct tradeoff.

### Why `ConfigurationSnapshot` hashing?

Every ingestion run and every retrieval call produces a `ConfigurationSnapshot` — an immutable, hashable record of the exact parameters used. The hash is stored in every trace.

This means the replay engine can, in Stage 1, determine whether the current chunking configuration matches the one used when the historical trace was created. If the hashes match, Stage 1 is a no-op. If they differ, the replay is meaningful.

Without hashing, the replay engine would have no way to distinguish "we replayed with the same configuration" from "we replayed with a slightly different configuration and the results changed."

---

## What the Evaluation Numbers Actually Mean

The 60-case synthetic corruption benchmark is designed to test the hardest version of the attribution problem: cases where the failure mode is ambiguous between stages.

**85% retrieval accuracy** is high because retrieval corruptions (swapping the correct chunk with a plausible but wrong chunk) produce large, easily detectable quality deltas. The signal is clean.

**73% chunking accuracy** requires the Stage 1 ablation to correctly identify that a better chunking configuration would have changed retrieval — not just that retrieval was imperfect. The 4-year-old OSHA document with a mid-sentence boundary split is the hardest case in this category.

**73% reranker accuracy** requires detecting that the correct answer was in the top-40 but ranked below the cutoff. This is sensitive to the quality of the gold `supporting_chunk_ids` annotation.

**50% generation accuracy** reflects a real limitation. LLM outputs are stochastic. A 0.03 quality delta in Stage 4 might be signal or might be noise. Without oracle access to the "correct" generation, distinguishing them is genuinely hard.

The 73.3% overall accuracy (against a ≥70% target) and 68.8% boundary-error accuracy (against a ≥65% target) are not cherry-picked: they represent performance on the synthetic benchmark as designed, with all 60 cases included.

---

## What RAGAS Measures vs. What Veriducta Measures

| Metric | RAGAS | Veriducta |
|---|---|---|
| Faithfulness (claim entailment) | ✓ 82.1% | ✓ 84.2% |
| Answer relevance | ✓ | ✓ |
| Context precision | ✓ | ✓ |
| Context recall | ✓ | ✓ |
| Omission rate | ✗ | ✓ 8.2% |
| Causal attribution accuracy | ✗ | ✓ 73.3% |
| Temporal-valid retrieval rate | ✗ | ✓ 94.1% |
| Contradiction acknowledgment rate | ✗ | ✓ 91.7% |
| Root-cause stage identification | ✗ | ✓ |
| Replayable historical traces | ✗ | ✓ |
| CI regression gate | ✓ (basic) | ✓ (5 conditions) |

The framing is not "Veriducta beats RAGAS." RAGAS measures what it measures accurately. The framing is: *for diagnosing and improving a specific pipeline, you need both*.

---

## Lessons Learned

**1. Causal attribution without an oracle is possible but constrained.**

Stage 2 ablation requires gold `supporting_chunk_ids` — human annotation of which chunks should support the correct answer. This is the oracle-dependent part. The replay engine cannot determine, without annotation, whether a retrieved chunk should have been retrieved.

Stages 1, 3, and 4 are oracle-free. Stage 2 is not. The honest engineering answer is that full oracle-free attribution is an open research problem.

**2. Store more than you think you need at inference time.**

The pre-reranking top-40 list felt excessive when I first designed the schema. It costs ~8KB per query. It enables an entire ablation stage without additional inference. Store the list.

**3. The version graph is load-bearing.**

Temporal filtering via a `networkx` DiGraph sounds like a nice-to-have. In practice, the engineering domain has multiple superseded standards (OSHA 1926.1153 supersedes the legacy 1989 OSHA general industry standard for construction silica work). Without temporal filtering, both standards appear in retrieval, and the older threshold (100 µg/m³ vs. 50 µg/m³) can contaminate answers.

Temporal-valid retrieval rate: 94.1%. Without the version graph, this would approach 60% on corpora with any supersession history.

**4. mypy --strict is painful and worth it.**

Enforcing strict typing across 82 Python source files required fighting `Any` usage in ML model wrappers, JSON helpers, and Pydantic v2 serialization. The two major patterns that work:
- `model_dump(mode='json')` instead of `model_dump()` for datetime-containing models
- `from __future__ import annotations` + `TYPE_CHECKING` guards for cross-module type hints in schemas

The payoff: zero type errors after the initial setup pain, and a codebase where the IDE correctly infers every field in every schema.

**5. Separation of concerns is not just architecture theory.**

Because `retrieval/` never imports from `generation/`, the replay engine can inject gold contexts into generation without touching retrieval code. Because `observability/` is a cross-cutting concern that pipeline code calls (never the reverse), logging and tracing add zero coupling between pipeline stages.

The eight-layer constraint feels like over-engineering for a solo project. It enables the replay engine to exist. The constraint is the product.

---

## Performance Profile

| Stage | p50 | p95 | Memory |
|---|---|---|---|
| BM25 retrieval | 45 ms | 120 ms | — |
| Dense retrieval (incl. embedding) | 680 ms | 1,100 ms | 1.3 GB (model) |
| RRF + temporal filter | 8 ms | 25 ms | — |
| Cross-encoder reranking | 950 ms | 1,650 ms | 90 MB (model) |
| Parent-child expansion | 35 ms | 90 ms | — |
| Generation (Claude API) | 800 ms | 3,200 ms | — |
| NLI entailment | 180 ms | 420 ms | 350 MB (model) |
| End-to-end | **2.8 s** | **7.4 s** | **~1.93 GB** |

The two dominant contributors are dense embedding inference and cross-encoder reranking, both running on CPU. GPU acceleration would cut both by roughly 8–10×, bringing p95 latency below 2 seconds.

---

## What's Next

**v1.1**: Wire the frontend to the live API; streaming generation via SSE; corpus upload UI.

**v1.2**: GPU acceleration; incremental corpus updates; multi-collection Qdrant support.

**v2.0**: Multi-LLM support (GPT-4o, Gemini, Llama); async pipeline; distributed evidence log; JWT auth.

**Research directions**:
- Oracle-free Stage 2 attribution using query-agnostic chunk importance scoring
- Continuous attribution threshold calibration as corpus drift occurs
- Causal DAG replacing the sequential ablation to model inter-stage interaction effects
- NLI-free verification using a learned quality scorer trained on human preference data

---

## Getting Started

```bash
git clone https://github.com/hardik-gupta/veriducta.git
cd veriducta
uv pip install --system ".[dev]"
cp .env.example .env          # add ANTHROPIC_API_KEY
docker compose up -d qdrant minio
python scripts/ingest_corpus.py
python scripts/run_benchmark.py
make run                      # API on :8080
cd frontend && npm run dev    # Dashboard on :3000
```

The evaluation harness, replay engine, and observability dashboard all work on mock traces without a real corpus. A 3-document sample corpus is included for development.

---

The complete source, evaluation datasets, and architecture documentation are available at [github.com/hardik-gupta/veriducta](https://github.com/hardik-gupta/veriducta).

If you've built a RAG pipeline and haven't answered "which stage caused that failure?", Veriducta was built for you.

---

*Hardik Gupta · 2026 · MIT License*
