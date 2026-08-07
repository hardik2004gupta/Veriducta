# Conference — Lightning Talk Script

*5 minutes. For MLOps World, local AI meetups, hackathon pitches.*

---

## Slides (10 slides, 30 seconds each)

### Slide 1 — Hook

**Title**: "RAGAS: 0.82. Answer: Wrong."

**Say**: "This happened to me. My RAG pipeline answered a question about OSHA silica exposure limits with a faithfulness score of 0.82. The answer was missing the permissible exposure limit — the primary regulatory threshold. No alert. No trace. No idea why."

---

### Slide 2 — The Problem

**Title**: "Four stages. Which one broke?"

**Say**: "Every bad RAG answer comes from one of four places: chunking, retrieval, reranking, or generation. Existing tools tell you the answer is bad. They can't tell you which of these four stages to fix."

---

### Slide 3 — The Insight

**Title**: "Store everything. Replay later."

**Say**: "The key insight is forensic: if you store a complete, replayable trace at inference time, you can run counterfactual experiments later without re-running expensive models. That's the foundation of Veriducta."

---

### Slide 4 — The Critical Detail

**Title**: "Pre-reranking top-40: 8KB per query. Saves 264 model calls."

**Say**: "The most non-obvious decision: store the full pre-reranking candidate list with all 40 cross-encoder scores in every trace. Stage 3 ablation (reranker testing) becomes pure data analysis. No re-inference. 8 kilobytes per query."

---

### Slide 5 — Four-Stage Ablation

**Title**: "Stage 1: Chunking. Stage 2: Retrieval. Stage 3: Reranker. Stage 4: Generation."

**Say**: "Each stage runs a counterfactual: different chunking config, gold chunk injection, different reranker cutoff, different prompt. The stage with the largest quality delta is the root cause."

---

### Slide 6 — The Worked Case

**Title**: "Chunk 0041 ends. Chunk 0042 begins. The sentence is split."

**Say**: "The OSHA chunker split mid-sentence between the label 'action level' and the value '25 µg/m³'. Dense retrieval found the value without the label. The answer cited it correctly but couldn't synthesize the complete threshold. RAGAS: 0.82. Veriducta Stage 1 delta: minus 0.41. Chunking: root cause."

---

### Slide 7 — The Fix

**Title**: "Recall@5: 0.45 → 0.80"

**Say**: "Extended the boundary regex to include 'Employer(s) must'. One line. Re-ingested. Recall@5 doubled. Answer quality went from 0.41 to 0.93. Omission rate for that document: 23% to 4%."

---

### Slide 8 — Benchmark Results

**Title**: "73.3% overall. 68.8% on boundary-errors. Both targets met."

**Say**: "60-case synthetic corruption benchmark across four failure categories. Overall target was 70%. Boundary-error target was 65%. Both met."

---

### Slide 9 — What RAGAS Misses

**Title**: "4 metrics RAGAS can't compute."

**Say**: "Omission rate, causal attribution accuracy, temporal-valid retrieval rate, contradiction acknowledgment rate. These are the metrics you need when a pipeline fails in production, not just on a benchmark."

---

### Slide 10 — CTA

**Title**: "github.com/hardik-gupta/veriducta · MIT"

**Say**: "Open source. MIT. 801 tests. Docker Compose setup. If you've built a RAG pipeline and hit a failure you couldn't explain, Veriducta was built for you. Thank you."

---

## Timing

| Slide | Time | Cumulative |
|---|---|---|
| Hook | 0:30 | 0:30 |
| Problem | 0:30 | 1:00 |
| Insight | 0:30 | 1:30 |
| Critical detail | 0:30 | 2:00 |
| Four stages | 0:30 | 2:30 |
| Worked case | 0:45 | 3:15 |
| Fix | 0:30 | 3:45 |
| Benchmark | 0:30 | 4:15 |
| Metrics | 0:20 | 4:35 |
| CTA | 0:25 | 5:00 |

---

## Notes

- Practice the chunk split explanation — it's the core narrative and needs to be crisp
- Have the GitHub URL on every slide (people photograph the screen during the talk)
- Slide 4 (pre-reranking top-40) will get the most technical questions — have the answer ready
- The "64 cross-encoder calls → 8KB per query" tradeoff is the most memorable engineering insight
