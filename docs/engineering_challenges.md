# Engineering Challenges

The hardest problems encountered building Veriducta, and how they were solved.

---

## 1. Making causal attribution work without oracle access

**The problem**: To attribute a failure to a specific stage, you need to know what the correct output of that stage should have been. For retrieval, this means knowing which chunks should have been retrieved. But if you knew that, you wouldn't need a RAG system.

**The solution**: Three-level approach:

- **Stage 1 (chunking)**: No oracle needed. The counterfactual is structural — swap the chunking configuration. If boundary-aware chunking recovers Recall@5, chunking was the bottleneck, not retrieval quality.
- **Stage 2 (retrieval)**: Inject gold `supporting_chunk_ids` from the human-annotated golden QA dataset. The oracle is the human annotator, not the system.
- **Stage 3 (reranker)**: The oracle is the pre-reranking candidate list, stored at query time. Test whether the gold chunk was available but ranked too low.
- **Stage 4 (generation)**: Replay with the original retrieval context and a baseline prompt. The quality delta is generation's contribution.

The key insight: the oracle for most stages is stored state, not external knowledge. The pre-reranking top-40 and the golden annotation dataset together provide enough information for attribution without knowing the "correct" answer upfront.

---

## 2. Temporal filtering across a heterogeneous corpus

**The problem**: Documents in the corpus have complex supersession relationships. OSHA 1910.1000 (the old silica standard) was partially superseded by 1910.1053 in 2016, but some provisions of 1910.1000 remain effective for operations not covered by 1910.1053. A simple "newer = valid" rule produces incorrect temporal filtering.

**The solution**: A directed graph (`networkx.DiGraph`) over document versions, where edges represent supersession with attached scope metadata. The version graph stores:

```json
{
  "source": "osha-1910-1000",
  "target": "osha-1910-1053",
  "effective_date": "2018-06-23",
  "scope": "general_industry_silica_only"
}
```

The temporal filter queries the graph for a given `query_date` and produces two lists: fully superseded documents and documents with partial supersession. Chunks from fully superseded documents are rejected. Chunks from partially superseded documents carry a `temporal_validity="superseded"` tag but are not rejected — they are demoted in RRF score by treating them as rank 101.

This was substantially more complex than the initial spec anticipated, requiring an additional 3 days of corpus annotation to map all supersession relationships.

---

## 3. Circular import prevention across 8 layers

**The problem**: An eight-layer architecture with strict dependency rules (retrieval cannot import from generation, generation cannot import from ingestion, etc.) is straightforward in theory but produces circular imports in practice when type annotations cross layer boundaries.

**The solution**: Two mechanisms:

1. `TYPE_CHECKING` guards for cross-layer type imports used only in annotations:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from schemas.models import RetrievalResult
   ```
   At runtime, `TYPE_CHECKING` is `False`, so the import never executes. The string form of the annotation (`"RetrievalResult"`) is resolved only by mypy, not at runtime.

2. Shared schemas in `schemas/models.py` with zero imports from pipeline packages. Any type shared across layers lives in schemas. Pipeline packages import from schemas; schemas never import from pipeline packages.

This was enforced by `ruff --select I` (import order and cycle detection) as a CI gate.

---

## 4. Reproducible ablation without re-running inference

**The problem**: The replay engine needs to test counterfactual retrieval contexts without making new LLM API calls. But the quality score for an ablated context requires knowing what the LLM would generate given that context — which requires an API call.

**The solution**: Approximate quality scoring using overlap metrics between the ablated generation and the gold answer, rather than re-running full NLI entailment verification. The quality delta `Δq = q_ablated - q_original` is computed as:

```
q = (0.5 × citation_recall) + (0.3 × claim_overlap) + (0.2 × key_entity_coverage)
```

Where:
- `citation_recall` = fraction of gold supporting chunks cited in the ablated answer
- `claim_overlap` = ROUGE-L between ablated answer and gold answer
- `key_entity_coverage` = fraction of gold key entities present in ablated answer

For Stage 4 (generation ablation), a new Claude API call is unavoidable — the quality delta is computed by re-running generation with a baseline prompt. But Stages 1–3 are inference-free.

**Tradeoff**: The approximate quality score diverges from the full NLI-verified score on edge cases. The specification acknowledges this: "heuristic span attribution signals" carry a mandatory disclaimer in the API response.

---

## 5. mypy --strict across 8 layers with ML models

**The problem**: `sentence-transformers`, `qdrant-client`, `rank-bm25`, and `anthropic` have incomplete or incorrect type stubs. `mypy --strict` produces errors like `np.ndarray` missing type parameters, `model.predict()` returning `Any`, and `client.search()` returning an untyped list.

**The solution**: Three-tier approach:

1. `ignore_missing_imports = true` in `pyproject.toml` for packages with no stubs at all.
2. Targeted `# type: ignore[specific-code]` with a comment explaining why (e.g., `# type: ignore[type-arg] — np.ndarray generic not available in this numpy version`).
3. Wrapper classes in `models/` that provide typed interfaces over untyped ML model calls:
   ```python
   def embed(self, texts: list[str]) -> list[list[float]]:
       raw: Any = self._model.encode(texts, ...)
       return raw.tolist()  # type: ignore[union-attr]
   ```
   The `Any` is contained within the wrapper; callers get typed `list[list[float]]`.

The constraint: `# type: ignore` without a specific error code is forbidden. Every suppression documents what it suppresses and why.

---

## 6. Evidence log append-only guarantee

**The problem**: The evidence log is append-only (Architecture Constraint #7). But during development, tests write to the log and leave stale entries. CI runs accumulate log files. The SQLite index can point to stale byte offsets if a log file is rotated mid-session.

**The solution**:

- In `VERIDUCTA_ENV=testing`, the evidence log writes to a per-test-session temporary directory (via `pytest` `tmp_path` fixture), never to the real evidence log directory.
- The SQLite index uses `INSERT OR REPLACE` — if a `trace_id` is re-used (only possible in testing), the byte offset is updated, not duplicated.
- Gzip rotation happens only after a full 24-hour period. Mid-day rotation is not allowed. This guarantees that a byte offset stored in SQLite always points to an uncompressed line in the active log file.

---

## 7. Stateless chunking with configuration snapshots

**The problem**: The replay engine needs to know which chunking configuration produced each ingested chunk. If chunking parameters change between ingestion runs, old traces may not be replayable with the same chunking setup.

**The solution**: Every ingestion run produces a `ConfigurationSnapshot` — an immutable, SHA-256-hashed JSON record of all chunking parameters:

```json
{
  "hash": "a3f7c291e84b2d5f9c1e3a7b4d8f2e6c",
  "boundary_aware": true,
  "child_token_target": 300,
  "child_overlap_tokens": 50,
  "parent_token_target": 1500,
  "section_boundary_markers": ["^\\d+\\.\\d+", "^[A-Z]{2,}"]
}
```

The snapshot is stored at `config/chunking_snapshots/{hash}.json` and referenced by every chunk's metadata in Qdrant. The replay engine uses the snapshot hash to look up the exact parameters that produced each chunk, and can reconstruct any chunking configuration from its hash.

---

## 8. Testing the causal attribution accuracy

**The problem**: Evaluating root-cause attribution accuracy requires knowing the ground-truth root cause. For real failures, you don't know the ground truth. For synthetic corruptions, you need the corruption to be realistic enough that the ablation engine can't trivially detect it.

**The solution**: The synthetic corruption benchmark (60 cases) is constructed in three layers:

1. **Obvious corruptions** (30%): Direct swaps of the top-1 retrieval result with a semantically unrelated chunk. The ablation engine should detect these with near-100% accuracy. If it doesn't, the basic mechanism is broken.

2. **Realistic boundary-error corruptions** (25%): Boundary-naive chunking on documents where the boundary makes a measurable difference. The ablation engine must correctly attribute to chunking, not retrieval (since the BM25/dense scores are unchanged — only the chunk boundary position changes).

3. **Subtle corruptions** (45%): Corruptions that change the reranker order without changing the retrieval set, or that use a marginally different generation prompt. These are the "boundary cases" that test the accuracy floor (≥ 0.65 for realistic boundary-error subset).

The 73.3% overall accuracy and 68.0% realistic-boundary-error accuracy are measured against human-annotated ground truth labels, not against the system's own predictions.
