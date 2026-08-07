# LinkedIn — Carousel Content

*10-slide carousel: "Why your RAG pipeline fails and how to find out which part is responsible"*

---

## Slide 1 — Hook (Cover)

**Headline**: Your RAG pipeline failed. RAGAS says it's fine.

**Body**: Here's how to actually find out what went wrong.

**Visual**: Dark background, large text, arrow pointing to → "slide 2"

---

## Slide 2 — The Problem

**Headline**: The diagnosis gap in RAG evaluation

**Body**:
- Faithfulness score: 0.82 ✓ (looks good)
- The answer: missing the operative regulatory threshold ✗
- RAGAS measures what was said. Not what was omitted.

**Visual**: Side-by-side: RAGAS score (green check) vs. user complaint (red X)

---

## Slide 3 — The Four Failure Modes

**Headline**: Which stage failed?

**Body**:
Every bad RAG answer comes from one of four places:

① Chunking — critical clause split across a boundary
② Retrieval — right chunk exists but wasn't fetched
③ Reranking — right chunk in top-40, but dropped at cutoff
④ Generation — context was right, LLM used it wrong

**Visual**: 4 boxes in a pipeline diagram, each with a question mark

---

## Slide 4 — Why This Matters

**Headline**: Wrong diagnosis = wrong fix

**Body**:
- Fixed your prompt → problem was chunking → no improvement
- Upgraded your embedding model → problem was reranker → no improvement
- Added more context → problem was generation → answer got worse

**Visual**: Engineer at computer, 3 crossed-out "improvements"

---

## Slide 5 — The Solution: Replayable Traces

**Headline**: Store everything. Replay later.

**Body**:
The key innovation: every retrieval decision is stored in an append-only evidence log.

Includes:
- All BM25 and dense scores
- Full pre-reranking top-40 with cross-encoder scores
- SQLite byte-offset index → O(1) lookup

**Visual**: Database icon + JSONL file + SQLite db

---

## Slide 6 — Stage 1: Chunking

**Headline**: Did chunking cause this failure?

**Body**:
Replay retrieval with boundary-aware chunking configuration.

Before: Recall@5 = 0.45
After: Recall@5 = 0.80
Delta: +0.41 → chunking is root cause ✓

**Visual**: Two chunk diagrams: split clause vs. preserved clause

---

## Slide 7 — Stage 3: Reranker (No Re-Inference!)

**Headline**: Was the right answer in the top-40?

**Body**:
The pre-reranking top-40 list is stored in every trace.

Test cutoffs at 1, 3, 5, 8 → no need to re-run the cross-encoder.

If quality improves at a wider cutoff: reranker threshold is root cause.

**Visual**: Score table with 40 rows, top-8 highlighted vs. candidate #12 highlighted

---

## Slide 8 — The Benchmark

**Headline**: How accurate is the attribution?

**Body**:
60-case synthetic corruption benchmark:

- Retrieval corruptions: 85% accuracy
- Chunking corruptions: 73% accuracy
- Reranker corruptions: 73% accuracy
- Generation corruptions: 50% accuracy
- **Overall: 73.3%**

Target was ≥ 70%. ✓

**Visual**: Bar chart with 4 accuracy bars

---

## Slide 9 — Metrics RAGAS Can't Compute

**Headline**: What RAGAS misses

**Body**:

| Metric | RAGAS | Veriducta |
|---|---|---|
| Omission rate | ✗ | ✓ 8.2% |
| Causal attribution | ✗ | ✓ 73.3% |
| Temporal retrieval rate | ✗ | ✓ 94.1% |
| Contradiction ack rate | ✗ | ✓ 91.7% |

**Visual**: Table with X and check marks

---

## Slide 10 — Call to Action

**Headline**: Built for engineers who need to know *why*

**Body**:
Stack: Python 3.12 · FastAPI · Qdrant · Claude Sonnet 4.6 · Next.js 15

Open source · MIT License

🔗 github.com/hardik-gupta/veriducta

"If you've built a RAG pipeline and haven't answered 'which stage caused that failure?' — this was built for you."

**Visual**: GitHub repo screenshot or architecture diagram

---

## Posting Tips

- Use Canva or Figma with dark glassmorphism theme (matches the dashboard)
- Text should be readable at mobile scale (20pt+ equivalent)
- Carousel posts get 3× more reach than single image posts on LinkedIn
- Last slide always needs a clear CTA and URL
- Save as PDF (LinkedIn renders PDFs as carousels natively)
