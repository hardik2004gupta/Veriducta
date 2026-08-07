# Why RAGAS Scored 0.82 Faithfulness on an Answer That Was Missing Half Its Content

*A worked example of causal attribution with Veriducta*

---

## The Problem With Aggregate Metrics

RAG evaluation tools give you a number. They cannot tell you *why* the number is what it is, and they cannot tell you which component of your pipeline caused a failure that somehow still scored well.

This post documents a real failure case from the Veriducta evaluation benchmark — a case where RAGAS faithfulness scored **0.82** on an answer that was missing the single most important quantitative threshold in the source document. We then show how Veriducta's causal replay engine correctly attributed the failure to a chunking boundary split, not retrieval, not generation.

---

## The Question

> "What are the permissible exposure limits for respirable crystalline silica under OSHA 1926.1153, and when does medical surveillance become mandatory?"

This is a numerical-threshold question from the OSHA Construction Silica Standard. A correct answer requires:

1. The **action level (AL)**: 25 µg/m³ as an 8-hour TWA
2. The **permissible exposure limit (PEL)**: 50 µg/m³ as an 8-hour TWA
3. The **medical surveillance trigger**: exposure at or above the AL for ≥ 30 days per year

All three facts appear on pages 4–5 of OSHA 1926.1153.

---

## What the Baseline Pipeline Produced

The boundary-naive chunker split the document at a 512-token boundary that landed mid-paragraph — between the definition of the action level and the PEL. The chunk containing the AL definition was retrieved (rank 1, BM25 score 0.94). The chunk containing the PEL and surveillance threshold started a new chunk that received a lower RRF rank (rank 11) and was dropped by the cross-encoder at the reranking step.

The generator received context that contained the AL definition and the medical surveillance section, but not the PEL. It produced:

> "OSHA 1926.1153 establishes an action level of 25 µg/m³. Workers exposed above this level for 30 or more days per year must receive medical examinations, including chest X-rays and pulmonary function tests."

The answer is factually correct for everything it says. It just omits the PEL entirely.

RAGAS faithfulness scored this at **0.82** because all stated claims are entailed by the retrieved context. The metric cannot measure what was *not* said.

---

## Veriducta's Attribution Report

```
ReplayReport
├── pipeline_trace_id:  a3f2c8e1-...
├── question_id:        qa-041
│
├── stage1_chunking
│   ├── config_override:  boundary_aware=True
│   ├── Recall@5_baseline: 0.45   (supporting chunk OSHA-1153-ch-0015 ranked 11th)
│   ├── Recall@5_gold:     0.80   (chunk retrieved at rank 2 with boundary-aware config)
│   └── quality_delta:    −0.41  ← exceeds attribution threshold (0.15)
│
├── stage2_retrieval
│   ├── gold_chunks_injected: 5 (supporting chunk IDs from annotation)
│   ├── quality_delta:        −0.08
│   └── below threshold → not root cause
│
├── stage3_reranker
│   ├── cutoffs_tested:  top-1, top-3, top-5, top-8
│   ├── max_delta:       −0.12
│   └── below threshold → not root cause
│
├── stage4_generation
│   ├── context:         historical retrieval (baseline chunks)
│   ├── quality_delta:   −0.03
│   └── below threshold → not root cause
│
├── primary_root_cause:  chunking_boundary
└── attribution_confidence: 0.88
```

**Stage 1 is decisive.** When the pipeline is replayed with the boundary-aware chunker (which never splits a window across a detected section boundary regex match), the critical PEL chunk is retrieved at rank 2. The quality delta of −0.41 clears the attribution threshold by 2.7×.

Stages 2–4 contribute noise but not the root cause. The generator, given the correct context, produces a complete answer with all three thresholds correctly cited.

---

## Why RAGAS Missed It

RAGAS faithfulness asks: *are the claims in the answer supported by the retrieved context?*

It does not ask: *did the retrieved context contain everything needed for a complete answer?*

The omission rate — the fraction of expected claims from the gold annotation that were absent from the answer — is a metric RAGAS cannot compute, because it requires a gold annotation of what the answer *should* contain. Veriducta's evaluation harness computes this directly from the `supporting_chunk_ids` and `expected_entities` fields in the golden QA dataset.

For this case:
- RAGAS faithfulness: **0.82** (high — no hallucination)
- Veriducta omission rate: **0.67** (2 of 3 expected claims missing)
- Veriducta quality score: **0.52** (weighted composite)

The 0.82 RAGAS score is not wrong — it correctly measures what it measures. But it would not trigger any alert or investigation in a standard evaluation pipeline. Veriducta's ablation engine flags this query automatically because the quality score falls below 0.65, and the Stage 1 delta exceeds the attribution threshold.

---

## The Fix

Activating `boundary_aware=True` in the `HierarchicalChunker` for the OSHA corpus eliminates this class of failure for documents with detectable section boundaries. The chunker checks the configured `section_boundary_markers` regex set (headers matching `^\d+\.\d+`, `^[A-Z][A-Z\s]+:`, and explicit `§` markers) before placing a window boundary, and if the boundary would split a detected marker, it terminates the window at the previous safe point.

After the fix:
- Recall@5 for qa-041: 0.45 → 0.80
- Quality score: 0.52 → 0.93
- All 3 expected claims: present and supported
- RAGAS faithfulness: 0.82 → 0.91

---

## What This Means for RAG Evaluation

Aggregate faithfulness metrics are necessary but not sufficient for evaluating a production RAG system. They measure hallucination; they do not measure completeness.

A system that retrieves a partial view of the relevant evidence, omits key quantitative thresholds, but accurately cites what it did retrieve will score well on faithfulness. It will score poorly on user trust the first time a professional relies on that threshold.

Veriducta's causal attribution approach addresses a specific gap: given a failed or low-quality answer, it tells you *which stage* of the pipeline caused the failure, and by *how much* — without requiring an oracle, without re-running expensive inference for historical queries, and without conflating correlation with causation across pipeline stages.

The pre-reranking top-40 candidate list stored in every `RetrievalTrace` is the key implementation detail that makes Stage 3 ablation tractable. By storing the full scored candidate list at inference time, the replay engine can test counterfactual reranker cutoffs (top-1, top-3, top-5, top-8) against any historical query in O(1) from the evidence log — no re-embedding, no re-retrieval, no additional API calls.

---

## Veriducta Evaluation Results (60-case benchmark)

| Stage | Cases | Correctly attributed | Accuracy |
|---|---|---|---|
| Retrieval corruptions | 20 | 17 | 85% |
| Chunking corruptions | 15 | 11 | 73% |
| Reranker corruptions | 15 | 11 | 73% |
| Generation corruptions | 10 | 5 | 50% |
| **Overall** | **60** | **44** | **73.3%** |

The 73.3% overall accuracy exceeds the ≥ 0.70 target from the specification. The boundary-error subset (cases where failures are ambiguous between chunking and retrieval) achieves 68.8% accuracy, above the ≥ 0.65 target.

Generation corruptions are the hardest to attribute because the quality signal from the LLM is noisier — prompting changes produce more variance than retrieval configuration changes. This is an open research problem.

---

## Running This Yourself

```bash
# Run the full evaluation harness
python scripts/run_benchmark.py

# Run ablation on a single failed query
python scripts/run_evaluation.py --trace-id a3f2c8e1

# Check regression gate against baseline
python scripts/regression_check.py
```

The evidence log (`evidence_logs/YYYY-MM-DD.jsonl`) contains the full retrieval trace for every query, including the pre-reranking top-40 candidate list. The SQLite index (`evidence_logs/index.db`) provides O(1) lookup by trace ID.

---

## Source

- OSHA Standard 29 CFR 1926.1153 — Respirable Crystalline Silica
- Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). Reciprocal rank fusion outperforms condorcet and individual rank learning methods. *SIGIR 2009*.
- Es, S., et al. (2023). RAGAS: Automated Evaluation of Retrieval Augmented Generation. *arXiv 2309.15217*.
