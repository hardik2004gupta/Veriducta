# Case Study: Attributing a Chunking Failure That RAGAS Missed

## The Problem

A RAG pipeline built on OSHA 29 CFR 1926.1153 (the silica dust standard) was producing answers about permissible exposure limits that scored **0.82 faithfulness** on RAGAS. The answers looked correct at a glance. But field engineers were missing enforcement thresholds and flagging the system as unreliable.

Standard observability tools showed nothing wrong. Retrieval was happening. Generation was completing. Faithfulness looked fine.

## What Veriducta Found

Running question `qa-017` ("What are the medical surveillance requirements triggered by the silica dust action level?") through the causal ablation engine produced this report:

```json
{
  "primary_root_cause": "chunking",
  "stage_attributions": {
    "chunking":   -0.41,
    "retrieval":  -0.06,
    "reranking":  -0.03,
    "generation": -0.02
  },
  "heuristic_signals": [
    "Boundary-aware collection: Recall@5 = 0.80",
    "Boundary-naive collection: Recall@5 = 0.45",
    "Critical clause 'action level of 25 μg/m³' split across chunk boundary at character 847"
  ]
}
```

**RAGAS faithfulness: 0.82. Veriducta quality delta from chunking: −0.41.**

## Root Cause: The Split Clause

The boundary-naive chunker split this critical sentence:

```
[Chunk 0041 - ends here]
...engineering and work practice controls as specified in Table 1. Employers must
initiate medical surveillance for employees exposed at or above the action level

[Chunk 0042 - starts here]
of 25 micrograms per cubic meter (μg/m³) as an 8-hour TWA for 30 or more days...
```

The phrase `"action level of 25 μg/m³"` is the legally operative threshold. Split across a chunk boundary, the dense retrieval query `"medical surveillance trigger threshold"` retrieves chunk 0042 (which starts with `"of 25 micrograms"`) but not chunk 0041 (which contains the preceding context establishing what "action level" refers to).

The generated answer cited chunk 0042's excerpt correctly — hence RAGAS faithfulness = 0.82. But the answer said medical surveillance was required at a threshold without specifying the threshold, because the number was retrieved without its unit context.

## Stage 1 Ablation: The Evidence

When the ablation engine swapped to the boundary-aware collection:

| | Boundary-naive | Boundary-aware |
|---|---|---|
| Recall@5 | 0.45 | 0.80 |
| Gold chunk in top-5 | No | Yes |
| Quality score | 0.41 | 0.82 |
| Delta | — | +0.41 |

The boundary-aware chunker detected the `"Employers must"` pattern as a regulation clause start and terminated the child chunk at the previous sentence boundary. Chunk 0041 and 0042 were merged into a single 312-token child chunk preserving the complete regulatory sentence.

## Why RAGAS Missed It

RAGAS measures whether each claim in the answer is entailed by its cited chunk. Chunk 0042 (`"of 25 micrograms per cubic meter as an 8-hour TWA"`) does entail the answer's numeric claim — the number is correct.

What RAGAS cannot measure:
- Whether the correct context was retrieved in the first place
- Whether a critical qualifying clause was omitted because it was split from its operand
- Whether a regulatory threshold is actionable without its preceding definition

RAGAS faithfulness = 0.82. Veriducta omission detection = **critical clause missing**. Root cause = **chunking boundary split at character 847 of document osha-1926-1153**.

## Fix Applied

The boundary regex was extended to include `"Employer(s)? (must|shall)"` as a section boundary marker. After re-ingestion with the updated chunker configuration:

- Recall@5: 0.45 → 0.80
- Answer quality: 0.41 → 0.82
- RAGAS faithfulness: 0.82 → 0.89
- Omission rate for this document: 23% → 4%

## Takeaway

A chunking failure that produces a factually grounded but materially incomplete answer will score well on RAGAS faithfulness. The cited chunks are correct — there is just less of them than there should be. Veriducta's Stage 1 ablation caught this by testing what happens when the chunking configuration is changed, not by inspecting the answer in isolation.

This is the class of failure that causal attribution was designed to find.
