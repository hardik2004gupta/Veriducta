# Conference — Presentation Outline

*20-minute conference talk outline for QCon AI, PyCon, NeurIPS workshops.*

---

## Talk Title Options

1. "Veriducta: Causal Attribution for RAG Pipeline Failures"
2. "Which Stage Broke Your RAG? Building a Four-Stage Attribution Engine"
3. "Beyond Faithfulness: Root-Cause Localization in RAG Pipelines"
4. "The Diagnosis Gap: Why RAG Evaluation Metrics Aren't Enough"

---

## Full Outline

### 1. Hook and Problem Statement (3 minutes)

**Opening**: Live demo — ask a question, show the incomplete answer, show the RAGAS score of 0.82.

**The gap**: Faithfulness measures what was said. Not what was omitted. Not which stage failed. 

**Stakes**: In high-stakes domains (regulatory, medical, engineering), omissions are more dangerous than hallucinations. Omissions don't trigger citation error checks.

**Preview**: I'll show a tool that tells you, reproducibly, which of four pipeline stages caused a specific failure.

---

### 2. Architecture Overview (4 minutes)

**High-level**: Eight layers with strict downward dependency enforcement. Each layer is independently substitutable — this is what makes attribution possible.

**Evidence log**: Append-only JSONL + SQLite byte-offset index. O(1) lookup. Why not a database: append-only writes + point reads = JSONL + index is optimal.

**Key design constraint**: Every pipeline stage stores its inputs, outputs, and configuration hash. Without this, replay is impossible.

**The pre-reranking top-40**: The most non-obvious decision. 8KB per query. Enables Stage 3 without model re-inference.

---

### 3. Four-Stage Causal Ablation (8 minutes)

**Stage 1 — Chunking** (2 min):
- What it tests: boundary-aware vs. boundary-naive chunking config
- How: replay retrieval with alternative Qdrant collection
- What it detects: clause splits, table fragmentation, section boundary errors
- Example: OSHA silica case — Recall@5 0.45 → 0.80

**Stage 2 — Retrieval** (1.5 min):
- What it tests: does gold context fix the answer?
- How: inject annotated supporting chunks, replay generation
- Limitation: oracle-dependent (requires gold annotation)
- When to use: confirms retrieval as root cause when Stage 1 is ambiguous

**Stage 3 — Reranker** (2 min):
- What it tests: was the correct chunk in top-40 but dropped at cutoff?
- How: load stored pre-reranking top-40, test cutoffs at 1/3/5/8
- Key detail: no model re-inference — data-only analysis
- What it detects: reranker threshold errors, score inversion artifacts

**Stage 4 — Generation** (2.5 min):
- What it tests: does the same context + baseline prompt produce a better answer?
- How: replay generation with original context + baseline prompt
- Honest limitation: 50% accuracy — LLM stochasticity makes this hard
- Current approach: wider threshold + confidence flags in ReplayReport

---

### 4. The OSHA Silica Case Study (3 minutes)

**Full walkthrough** of qa-017:
- Show the document and the exact split location
- Show the chunk ID and retrieval scores for both halves
- Show the attribution report
- Show the fix (one regex line in chunker config)
- Show before/after metrics: Recall@5 0.45 → 0.80, quality 0.41 → 0.93, omission 23% → 4%

**Key point**: RAGAS scored 0.82 both before and after the fix (0.82 → 0.89 after, but both above threshold). RAGAS never would have triggered an alert. The attributor catches it.

---

### 5. Evaluation and Results (1.5 minutes)

**60-case benchmark**: 4 corruption categories, ground-truth labels, realistic boundary-error subset.

**Numbers**: 73.3% overall, 68.8% boundary-error, targets met. Stage accuracy table.

**RAGAS comparison**: 4 metrics Veriducta computes that RAGAS cannot. Not a replacement — a complement.

---

### 6. Q&A Setup (0.5 minutes)

**Open questions for the audience**:
- How would oracle-free Stage 2 attribution work?
- Can causal graphs (DAGs) replace sequential ablation to model inter-stage interactions?
- What's the right threshold for generation attribution given LLM stochasticity?

**GitHub**: github.com/hardik2004gupta/Veriducta

---

## Q&A Prep

| Likely question | Key answer |
|---|---|
| "Why not just use better evaluation metrics?" | Attribution requires counterfactual reasoning, not measurement. A better metric can't tell you which stage to fix. |
| "How does Stage 2 work without annotation?" | It doesn't — Stage 2 requires gold annotation. This is a documented limitation. Stages 1, 3, 4 are oracle-free. |
| "Is 73.3% good enough for production?" | It's better than the alternative (0% — no attribution at all). Calibrate by use case: diagnostic tool vs. automated decision-maker. |
| "Could you use a learned ranker instead of RRF?" | Yes, but it requires labeled fusion training data we don't have at this corpus size. RRF is the correct default. |
| "What about retrieval-heavy RAG (no chunking)?" | Stage 1 would be a no-op. Stages 2, 3, 4 still work. Adjust attribution based on corpus structure. |
