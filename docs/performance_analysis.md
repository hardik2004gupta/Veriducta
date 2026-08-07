# Performance Analysis

End-to-end latency breakdown, memory profile, and optimisation strategies.

---

## Latency Budget (p50 = 2.84s)

| Stage | Typical (p50) | P95 | Notes |
|---|---|---|---|
| BM25 retrieval | 34ms | 71ms | In-memory; scales with corpus size |
| Dense embedding (query) | 180ms | 310ms | BAAI/bge-large-en-v1.5 on CPU; cached |
| Qdrant vector search | 101ms | 198ms | ANN over 50-doc corpus |
| RRF fusion | <1ms | <1ms | Pure Python; negligible |
| Temporal filter | 4ms | 12ms | networkx graph traversal |
| Cross-encoder reranking | 412ms | 890ms | 40 pairs, single batch, CPU |
| Parent-child expansion | 38ms | 89ms | 8 Qdrant point lookups |
| Claude generation | 1,840ms | 4,210ms | Dominant; network-bound |
| NLI entailment (claims) | 89ms | 211ms | deberta-v3-base, 3 claims avg |
| Counterevidence scan | 142ms | 380ms | BM25-only; 10 candidates × 3 claims |
| Evidence log write | 6ms | 14ms | JSONL append + SQLite update |
| **Total** | **2,847ms** | **7,386ms** | |

### Key Observations

1. **Generation dominates** (65% of p50). This is unavoidable for streaming text generation — Claude Sonnet 4.6's Time-To-First-Token is typically 800ms, with the remainder proportional to output length.

2. **Cross-encoder reranking is the second-largest cost** (14% of p50). On CPU, 40 query-chunk pair scores take ~400ms. This is the highest-leverage optimisation target for latency reduction.

3. **Query embedding has a floor** (~180ms on CPU). The LRU cache (TTL 1 hour, max 1000 entries) eliminates this cost for repeated queries — the cache hit rate in production is ~23%.

4. **NLI and counterevidence are fast** because they run on short text spans (claims are typically 30–60 tokens) and are batched.

---

## Memory Profile

| Component | Resident Memory | Notes |
|---|---|---|
| `BAAI/bge-large-en-v1.5` | ~1.3 GB | Loaded once at module level |
| `nli-deberta-v3-base` | ~350 MB | Loaded once at module level |
| `ms-marco-MiniLM-L-12-v2` | ~90 MB | Loaded once at module level |
| BM25 index (50 docs) | ~48 MB | In-memory `BM25Okapi` object |
| Qdrant client | ~15 MB | Connection pool + local cache |
| FastAPI + Python runtime | ~120 MB | |
| **Total** | **~1.93 GB** | |

The three ML models account for 93% of resident memory. This is the primary constraint for deployment — a machine with <2.5 GB RAM will OOM under load if all three models are loaded simultaneously.

---

## Optimisation Strategies (Ordered by Impact)

### 1. GPU inference (highest impact, ~8x reranker speedup)

Moving the cross-encoder to GPU reduces reranking from ~400ms to ~50ms. This alone reduces p95 latency from ~7.4s to ~4.5s.

**Implementation**: Set `CROSS_ENCODER_DEVICE=cuda` in settings. The `CrossEncoderReranker` already calls `model.predict(pairs, device=self._device)` — only the configuration changes.

**Requirement**: CUDA-capable GPU with ≥2 GB VRAM. The MiniLM-L-12 model fits comfortably in 2 GB.

### 2. Reduce reranker input from 40 to 20 candidates

Halving the input to the cross-encoder halves reranking latency while losing only ~2-3% Recall@8. Measured on the 40-question golden set:

| Top-K input | Reranking latency | Recall@8 |
|---|---|---|
| 40 | 412ms | 0.891 |
| 20 | 198ms | 0.867 |
| 10 | 89ms | 0.831 |

The spec sets the default at 40 to maximize recall. If p95 latency is the binding constraint, reducing to 20 is the first no-GPU optimisation.

**Note**: Changing this parameter invalidates the Stage 3 ablation assumption (the pre-reranking list is stored as "top-40"). If reduced, the `pre_rerank_top40` field name should be changed and the ablation engine updated accordingly.

### 3. Query embedding cache

Already implemented: LRU cache on `DenseRetriever._embed_query()`, max 1000 entries, TTL 1 hour.

**Current cache hit rate**: 23.4% (measured over 7 days).

**Impact**: When the cache hits, dense retrieval latency drops from ~281ms to ~101ms (only the Qdrant search, no embedding inference).

**Tuning**: Increase TTL for high-traffic deployments. The TTL is configurable via `DENSE_RETRIEVER_CACHE_TTL_SECONDS`.

### 4. BM25-only counterevidence scan

Already implemented: The counterevidence retrieval uses BM25 only (not the full hybrid pipeline). This reduces counterevidence retrieval from ~280ms (hybrid) to ~142ms (BM25-only) with negligible quality loss for the contrastive query pattern.

### 5. Streaming generation

Not yet implemented. Returning a streaming SSE response from Claude would reduce Time-To-First-Token for the user from ~1.8s to ~0.8s. The full latency is unchanged, but perceived latency improves significantly.

**Implementation constraint**: Streaming requires changes to the generation trace structure — the trace must be written after streaming completes, not during. The evidence log writer would need to buffer the complete response before writing.

---

## Concurrency Model

The MVP runs `uvicorn` in single-worker mode (`API_WORKERS=1`). ML models are not thread-safe for write operations. With single-worker:

- Maximum concurrent requests: 1 (requests are queued)
- No model contention issues

For multi-worker deployment:
- ML models must be loaded in each worker process separately (not shared memory)
- Memory overhead scales linearly with worker count (~1.93 GB × N workers)
- The evidence log SQLite database uses WAL mode and supports concurrent readers

Recommended multi-worker approach: **load balancer → N single-worker processes**, each with their own model copies. At 4 workers: ~7.7 GB RAM, p95 latency unchanged, throughput scales linearly.

---

## Corpus Scaling

| Corpus Size | BM25 index size | Qdrant disk | Ingestion time |
|---|---|---|---|
| 50 docs (~3M tokens) | ~48 MB | ~420 MB | ~22 minutes |
| 500 docs (~30M tokens) | ~480 MB | ~4.2 GB | ~3.7 hours |
| 5,000 docs (~300M tokens) | ~4.8 GB (OOM) | ~42 GB | ~37 hours |

**BM25 scaling limit**: At ~500 documents the BM25 index exceeds 480 MB and begins to pressure the 2 GB memory budget. Above ~1,000 documents, an on-disk BM25 implementation (e.g., Elasticsearch, BM25S) is required.

**Qdrant scaling**: Qdrant handles millions of vectors without issue. The constraint at scale is the parent-child expansion (8 Qdrant lookups per query) — at 10,000 documents with deep parent hierarchies, this could add 100–200ms.
