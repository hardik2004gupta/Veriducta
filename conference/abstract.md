# Conference — Abstract

*For CFP submissions at MLOps World, QCon AI, PyCon, NeurIPS workshops, ACL SRW, EMNLP industry track.*

---

## Short Abstract (150 words)

**Title**: Veriducta: Stage-Level Causal Attribution for RAG Pipeline Failures

**Abstract**:

Retrieval-augmented generation (RAG) pipelines fail in ways that existing evaluation frameworks cannot explain. A faithfulness score indicates answer quality but does not identify whether the failure originated in document chunking, candidate retrieval, cross-encoder reranking, or language model generation.

We present Veriducta, an observability system that stores complete, replayable retrieval traces at inference time and performs four-stage causal ablation to attribute answer failures to specific pipeline components. The system implements an evidence log with O(1) SQLite byte-offset indexing and requires no model re-inference for reranker ablation — cross-encoder scores are stored in every trace.

On a 60-case synthetic corruption benchmark covering four failure categories, Veriducta achieves 73.3% root-cause localization accuracy (≥70% target) and 68.8% accuracy on the harder boundary-error subset. We present four metrics absent from RAGAS: omission rate, causal attribution accuracy, temporal-valid retrieval rate, and contradiction acknowledgment rate.

---

## Long Abstract (300 words)

**Title**: Veriducta: Causal Attribution of Retrieval-Augmented Generation Failures via Replayable Trace Ablation

**Abstract**:

Retrieval-augmented generation (RAG) pipelines exhibit a diagnosis gap: existing evaluation tools measure answer faithfulness and context precision but cannot identify which pipeline stage — document chunking, hybrid retrieval, cross-encoder reranking, or language model generation — caused a specific answer failure. This distinction is critical for practitioners: chunking failures require a different remediation than reranking threshold errors.

We present Veriducta, an RAG observability system built around three principles: (1) every retrieval decision is stored in an append-only evidence log at inference time, (2) a four-stage causal ablation engine runs counterfactual experiments against historical traces without re-running expensive inference, and (3) the full pre-reranking candidate list with cross-encoder scores is stored in every trace, enabling Stage 3 (reranker) ablation through pure data analysis.

The pipeline implements boundary-aware hierarchical chunking (parent chunks at 1400–1600 tokens, child chunks at 200–400 tokens, with child windows never splitting across detected section boundaries), hybrid BM25 + dense retrieval with Reciprocal Rank Fusion (k=60), cross-encoder reranking (ms-marco-MiniLM-L-12-v2), claim-level NLI verification (nli-deberta-v3-base, 3-class heuristic), and structured generation via Claude Sonnet 4.6.

On a 60-case synthetic corruption benchmark across four failure categories (retrieval: 20 cases, chunking: 15, reranker: 15, generation: 10), Veriducta achieves 73.3% overall root-cause localization accuracy and 68.8% accuracy on the harder realistic boundary-error subset. Both targets (≥70%, ≥65%) are met. Four metrics absent from existing RAG evaluation frameworks are reported: omission rate (8.2%), causal attribution accuracy (73.3%), temporal-valid retrieval rate (94.1%), and contradiction acknowledgment rate (91.7%).

We demonstrate a worked case where RAGAS faithfulness scored 0.82 on an answer missing an operative regulatory threshold, and the Stage 1 ablation correctly identified a chunking boundary split as the root cause with a Recall@5 delta of 0.41.

**Keywords**: retrieval-augmented generation, causal attribution, RAG evaluation, observability, chunking, hybrid retrieval

---

## Speaker Bio (for CFP)

Hardik Gupta is a software engineer with experience building production ML pipelines. He designed and implemented Veriducta as a solo project: eight-layer Python backend, FastAPI, Qdrant, Claude Sonnet 4.6 generation, and a Next.js 15 observability frontend, totaling 801 automated tests at 92.81% coverage. He is interested in ML systems reliability, RAG evaluation methodology, and the gap between benchmark metrics and production failure modes.

---

## Format Variants

| Format | Length | Target |
|---|---|---|
| Lightning talk | 5 min | MLOps World, Meetup |
| Conference talk | 20 min | QCon AI, PyCon |
| Workshop session | 45 min | SciPy, EuroPython |
| Poster | 1 page | NeurIPS workshop, EMNLP |
| Research paper | 8 pages | ACL SRW, *SEM |
