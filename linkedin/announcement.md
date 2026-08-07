# LinkedIn — Project Announcement

*For announcing the GitHub repository launch. More formal than the launch post.*

---

## Draft

I'm open-sourcing Veriducta — a RAG pipeline observability tool I've been building over the last 8 weeks.

**What it does**: Given a failed RAG answer, it identifies which pipeline stage (chunking, retrieval, reranking, or generation) caused the failure, using a four-stage causal ablation engine over stored retrieval traces.

**The problem it solves**: RAG evaluation tools measure faithfulness (is the answer supported?). They don't answer "which component broke?" Veriducta does.

**How it works**:
The pipeline stores a complete, replayable trace for every query — including the full pre-reranking top-40 candidate list with cross-encoder scores. The replay engine runs four counterfactual experiments against historical traces to identify the root cause.

**By the numbers**:
- 73.3% root-cause accuracy on 60-case benchmark
- 801 tests, 92.81% coverage
- 4 metrics RAGAS cannot compute
- p50 latency: 2.8s, p95: 7.4s

**Stack**: Python 3.12 (mypy --strict), FastAPI, Qdrant, BGE-large-en-v1.5, Claude Sonnet 4.6, Next.js 15, Docker Compose

**Open source**: MIT License, GitHub

I wrote a full technical writeup explaining the chunking failure case study (where RAGAS scored 0.82 but the answer was missing the operative PEL) in the blog post linked in the repo.

Contributions welcome — see FIRST_CONTRIBUTION.md for where to start.

🔗 github.com/hardik-gupta/veriducta

#RAG #LLM #MachineLearning #NLP #OpenSource #Python #GenAI

---

## Short Version (for profile post / sharing someone else's post)

Just open-sourced Veriducta — a RAG pipeline observability tool that tells you *which* stage (chunking/retrieval/reranking/generation) caused an answer failure.

73.3% root-cause accuracy · 801 tests · MIT

github.com/hardik-gupta/veriducta

#RAG #LLM #OpenSource
