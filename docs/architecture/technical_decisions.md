# Technical Decisions

This document explains the non-obvious design choices in Veriducta and the reasoning behind each one.

---

## 1. Why store the pre-reranking top-40?

**Decision**: `RetrievalTrace.pre_rerank_top40` stores the complete list of 40 candidates with all scores before the cross-encoder reranks them.

**Why**: Stage 3 ablation needs to reconstruct retrieval contexts at different cutoffs (top-1, top-3, top-5, top-8) without re-running retrieval. Without the pre-reranking list, every ablation run would require re-querying Qdrant and BM25 - expensive, slow, and potentially non-deterministic (Qdrant's approximate nearest neighbour search is not guaranteed to be reproducible).

With the stored top-40, the replay engine seeks to the evidence log at the byte offset, reads the trace, and reconstructs any context slice in O(1). No inference, no network calls.

**Tradeoff**: The pre-rerank list adds ~2 KB to each evidence log entry. At 5,000 queries/day this is ~10 MB/day - negligible.

---

## 2. Why RRF with k=60?

**Decision**: Reciprocal rank fusion uses k=60: `rrf_score = 1/(60 + rank)`.

**Why**: k=60 is the value from Cormack, Clarke, and Buettcher (2009), which showed it performs well across a wide range of corpora without tuning. The implicit rank for candidates absent from one list is 101 (out of 100 candidates), which gives a score of `1/(60+101) = 0.0062` - low enough to deprioritise absent candidates without zeroing them.

**Tradeoff**: Any change to k requires re-benchmarking the full 40-question golden set. The constant is documented in code with a comment pointing to the paper.

---

## 3. Why BGE-large-en-v1.5 instead of text-embedding-3-small?

**Decision**: `BAAI/bge-large-en-v1.5` (1024-dimensional) as the embedding model.

**Why**: The corpus consists of dense technical regulatory text (OSHA standards, NIST publications, USGS reports). BGE-large was trained on MS-MARCO and NLI datasets with a focus on sentence-level semantic similarity, which maps better to the chunk-level retrieval task than token-completion-optimised models. Its 1024-dimensional vectors also provide more separation in the embedding space for domain-specific terminology.

The query prefix `"Represent this sentence for searching relevant passages: "` is the model's recommended prefix for asymmetric retrieval (query to passage).

**Tradeoff**: ~1.3 GB RAM. Changing the embedding model requires re-embedding and re-ingesting the entire corpus.

---

## 4. Why a 3-class NLI heuristic?

**Decision**: The NLI entailment checker produces three classes - supported, contradicted, ambiguous_conditional - rather than binary supported/unsupported.

**Why**: Binary NLI misses the important middle case where a claim is conditionally true. For example: "Medical surveillance is required at exposures above the action level" is supported for construction (§1926.1153) but not for maritime (§1915.1153 uses a different threshold). A binary model marks this as supported. The 3-class heuristic marks it as `ambiguous_conditional` if `neutral > 0.40 AND contradiction between 0.30 and 0.70`, which triggers expert review.

The thresholds (entailment > 0.65, contradiction > 0.85, neutral > 0.40) are from the deberta-v3-base model's calibration on the MultiNLI dev set.

**Tradeoff**: More expert review flags, more noise. The spec accepts this trade-off: it's better to over-flag than to mark a conditionally valid claim as fully supported.

---

## 5. Why O(1) evidence log lookup via SQLite?

**Decision**: Evidence log is JSONL with a SQLite index storing `(trace_id, log_file, byte_offset)`.

**Why**: The replay engine needs to fetch historical traces during ablation runs. A naïve implementation would scan the JSONL file linearly - O(n). With 5,000 queries/day, a 30-day log has 150,000 entries; linear scan would take seconds per lookup.

The SQLite index stores the byte offset where each trace starts in the JSONL file. Lookup is: `SELECT byte_offset FROM index WHERE trace_id = ?` (O(log n) with the index), then `lseek()` to that offset and read one line. Total: sub-millisecond.

**Tradeoff**: SQLite adds a write dependency on every query. The writer uses WAL mode to avoid blocking reads.

---

## 6. Why boundary-aware chunking as a separate collection?

**Decision**: Boundary-aware and boundary-naive chunking produce two separate Qdrant collections, not two fields in one collection.

**Why**: Stage 1 ablation requires swapping the entire retrieval collection. If both configurations share a collection, the ablation would need to filter by a chunking config field - which complicates the retrieval path and makes the temporal filter harder to apply consistently.

Separate collections keep the retrieval interface clean: `VeriductaRetriever` receives a collection name and is unaware of chunking strategy. The replay engine swaps the collection name when running Stage 1.

**Tradeoff**: Storage overhead. The two collections for a 50-document corpus are ~200 MB each in Qdrant.

---

## 7. Why a single-batch cross-encoder inference?

**Decision**: All 40 query-chunk pairs are scored in a single `model.predict(pairs)` call.

**Why**: The cross-encoder (`ms-marco-MiniLM-L-12-v2`) runs on CPU. Batching all 40 pairs in one call amortises the Python/C++ boundary overhead and uses the model's internal batching efficiently. Separate calls per pair would be ~10x slower.

40 pairs is the empirically determined maximum that fits within the model's sequence length and a reasonable memory budget. If the input exceeds 512 tokens per pair, pairs are truncated at the query side.

**Tradeoff**: The entire reranking step is sequential and blocks the retrieval response. For p99 latency reduction, this could be parallelised with a GPU or a reduced pair count.

---

## 8. Why no `print()` - ever?

**Decision**: All logging goes through structlog, even in utility scripts.

**Why**: Structured logging makes log lines machine-parseable. When Prometheus or Grafana needs to correlate a slow query with its retrieval trace, it does so by joining on `trace_id` in the log stream. `print()` output is unindexable and does not carry structured context.

Additionally, structlog's `bind()` and `contextvars` integration means context set at request entry (request_id, trace_id, path) propagates automatically to every log line in that request's call stack without explicit threading.

---

## 9. Why Pydantic v2 `model_dump(mode='json')`?

**Decision**: All JSON serialization uses `model_dump(mode='json')` not `model_dump()`.

**Why**: Pydantic v2's default `model_dump()` returns Python objects: `datetime` fields are `datetime` instances, not ISO strings. `json.dumps()` cannot serialize `datetime` without a custom encoder. `model_dump(mode='json')` serialises all fields to JSON-compatible types (datetimes → ISO strings, UUIDs → strings, etc.) in a single call.

This is a Pydantic v2 behaviour change from v1 (where `dict()` always returned JSON-compatible types for most common fields).

---

## 10. Why is temporal filtering mandatory?

**Decision**: Temporal filtering cannot be disabled in production. `Architecture Constraint #8`.

**Why**: Regulatory and geoscience documents are frequently superseded. A query on 2024-03-01 about seismic site classification should not retrieve a 2019 USGS hazard map that was superseded in 2023. Without temporal filtering, the retrieved context is a mix of current and obsolete standards, which the LLM cannot distinguish from each other.

The temporal filter is part of the retrieval contract, not a configuration option. Disabling it would make the pipeline's guarantees meaningless for temporal-validity-sensitive domains.
