# Veriducta — System Design Walkthrough

*For system design interviews, whiteboard sessions, and technical deep-dives.*

---

## Starting Point: What Problem Are We Solving?

**The question**: Given a RAG pipeline that produced a bad answer, which of the four stages caused it?

The four stages are: chunking (did we split the right clauses?), retrieval (did we fetch the right chunks?), reranking (did we keep the right chunks after filtering?), generation (did the LLM use the context correctly?).

**Why existing tools don't answer this**: Faithfulness metrics (RAGAS, TruLens) measure whether the answer is supported by the retrieved context. They don't measure whether the retrieved context was complete or whether the right context was retrieved. They can't identify which stage introduced the failure.

---

## Data Flow: One Query, End to End

```
User query: "What is the PEL for crystalline silica?"
Query date: 2024-01-15

[1] BM25Retriever: tokenize → rank-bm25 → top 100 candidates with scores
[2] DenseRetriever: embed with BGE-large prefix → Qdrant query → top 100 candidates
[3] RRFusion: merge lists with k=60 formula → unified ranked list
[4] TemporalFilter: check version graph → reject superseded/future chunks
[5] CrossEncoderReranker: batch 40 pairs → reorder → keep top 8
          ↑ STORE: pre_rerank_top40 with all scores ← KEY FOR STAGE 3 REPLAY
[6] ParentChildExpander: fetch parent section for each of top 8
[7] VeriductaGenerator: call Claude API → JSON response → validate schema
[8] VeriductaVerifier: NLI entailment per claim → counterevidence scan
[9] EvidenceLog: write RetrievalTrace + GenerationTrace → SQLite index update
```

Every step produces a typed output that is the typed input to the next step. No global state. No mutable shared objects.

---

## Storage Architecture

### Three stores

**Qdrant** — vector index for dense retrieval. Collection: `veriducta_chunks`. 1024-dim cosine. Each point payload: chunk_id, text, parent_chunk_id, token_count, effective_date, expiry_date.

**MinIO** — object store for raw PDFs and configuration snapshots.

**Evidence log** — where causal attribution lives:
- `evidence_logs/YYYY-MM-DD.jsonl`: append-only, one JSON object per query
- `evidence_logs/index.db`: SQLite, schema: `(trace_id TEXT PK, log_file TEXT, byte_offset INTEGER, ...)`
- Lookup: `SELECT byte_offset, log_file FROM traces WHERE trace_id = ?` → seek → read one line

### Why SQLite for the index?

Single file, zero config, ACID transactions, primary key lookup is effectively O(1). For a single-worker API with a local corpus, PostgreSQL adds infrastructure complexity without benefit. v2.0 migrates when distributed deployment is needed.

### Why JSONL for the log?

Append-only writes are the fastest possible write pattern. JSONL is human-readable and parseable without loading the entire file. The byte-offset index turns an otherwise O(n) scan into a single seek operation.

---

## The Replay Engine: Causal Attribution

### What the engine needs

1. The `RetrievalTrace` for the historical query (loaded via byte-offset lookup)
2. The gold annotations for the query (from `data/golden_qa.jsonl`)
3. Access to the chunking variants (both boundary-aware and boundary-naive Qdrant collections)

### Stage 1 — Chunking Attribution

```
load trace → get chunking config hash from trace
if document in chunking_failure_corpus:
    replay_with_config(boundary_aware=True) → get Recall@5
    compare Recall@5 against original → delta
    if delta > 0.15: attribute to chunking
```

This works because the chunking config hash in the trace tells us whether boundary-aware chunking was used. If it wasn't, we can test it without re-ingesting — we maintain a separate Qdrant collection for boundary-aware chunks.

### Stage 2 — Retrieval Attribution

```
gold_chunks = load_gold_annotations(question_id).supporting_chunk_ids
replay_with_context(context=gold_chunks) → quality_score_gold
compare against original quality score → delta
if delta > 0.15: attribute to retrieval
```

This requires gold annotation. Stage 2 is oracle-dependent by design. It's the most reliable stage precisely because the counterfactual is known.

### Stage 3 — Reranker Attribution

```
candidates = trace.pre_rerank_top40  # loaded from evidence log
for cutoff in [1, 3, 5, 8]:
    context = candidates[:cutoff]
    quality = replay_with_context(context) 
    record quality at each cutoff
if quality_at_8 - quality_at_1 > 0.15: attribute to reranker
```

No re-inference. The cross-encoder scores are in the trace. Stage 3 is the cheapest ablation stage to run.

### Stage 4 — Generation Attribution

```
replay_with_context(
    context=original_retrieval_context,
    prompt=baseline_prompt  # not the production prompt
) → quality_score_baseline
compare against original → delta
if delta > 0.15: attribute to generation
```

Noisiest stage. LLM outputs are stochastic. Stage 4 accuracy: 50%. Documented as a known limitation.

### Primary root cause selection

```python
deltas = {
    "chunking": stage1_delta,
    "retrieval": stage2_delta,
    "reranker": stage3_delta,
    "generation": stage4_delta,
}
primary = max(deltas, key=deltas.get)
if deltas[primary] < ATTRIBUTION_THRESHOLD:
    primary = "unknown"
```

---

## Key Numbers for System Design Interviews

| Component | Latency | Memory |
|---|---|---|
| BM25 retrieval | 45ms p50 | 50MB (index) |
| Dense retrieval | 680ms p50 | 1.3GB (model) |
| RRF + temporal filter | 8ms p50 | — |
| Cross-encoder reranking | 950ms p50 | 90MB (model) |
| Claude generation | 800ms p50 | — (API) |
| NLI verification | 180ms p50 | 350MB (model) |
| **End-to-end** | **2.8s p50** | **~1.93GB** |

---

## Bottlenecks and Mitigations

**Primary bottleneck**: dense embedding inference (680ms) and cross-encoder reranking (950ms) both run on CPU.

**Mitigation 1 (implemented)**: LRU embedding cache on query hash — TTL 1 hour, 1000 entries max. Repeat queries skip embedding inference entirely.

**Mitigation 2 (planned v1.2)**: GPU acceleration — expected 8–10× improvement, bringing p95 below 2 seconds.

**Mitigation 3 (available)**: Reduce reranker input from 40 → 20 candidates. Tradeoff: ~25% reduction in Stage 3 attribution quality.

---

## What to Draw on the Whiteboard

```
  ┌─────────────────────────────────────────────────────┐
  │                  User Query                         │
  └──────────────────────┬──────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────┐
  │  BM25 Retriever (top-100)                           │
  │  Dense Retriever (top-100, Qdrant)                  │
  │         ↓                                           │
  │  RRF Fusion (k=60) → Temporal Filter                │
  │         ↓                                           │
  │  Cross-Encoder Reranker (40→8)   ←── STORE TOP-40  │
  │         ↓                                           │
  │  Parent-Child Expander                              │
  └──────────────────────┬──────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────┐
  │  Claude Sonnet 4.6 Generator                        │
  │  NLI Verifier (3-class)                             │
  └──────────────────────┬──────────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────────┐
  │  Evidence Log (JSONL + SQLite index)                │
  │  → Causal Replay Engine (4 stages)                  │
  └─────────────────────────────────────────────────────┘
```

The arrow pointing to "STORE TOP-40" is the key detail to call out: this is what enables Stage 3 ablation without re-inference.
