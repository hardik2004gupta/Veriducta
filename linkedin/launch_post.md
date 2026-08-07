# LinkedIn - Launch Post

*Target: 1200–1500 characters. Conversational, specific, skimmable.*

---

## Draft

I built a tool that answers the question no RAG evaluation framework can:

**"Which pipeline stage caused this answer failure?"**

Existing tools tell you *that* an answer is bad. They don't tell you whether to fix your chunking, your retrieval, your reranker, or your prompt.

So I built Veriducta - a RAG observability tool with a four-stage causal ablation engine.

Here's the core insight: every retrieval decision is stored in a replayable trace. When an answer fails, the replay engine runs four counterfactual experiments:

1. What if we'd used better chunking?
2. What if we'd retrieved the right chunks?
3. What if the reranker had a different cutoff?
4. What if the prompt had been different?

The stage with the largest quality delta is the root cause.

On a 60-case synthetic benchmark: **73.3% attribution accuracy**. And four metrics that RAGAS can't compute - including omission rate and temporal-valid retrieval rate.

The stack: Python 3.12 · FastAPI · Qdrant · Claude Sonnet 4.6 · Next.js 15 · Docker

🔗 github.com/hardik2004gupta/Veriducta

The full write-up (including a worked case study where RAGAS scored 0.82 but the answer was missing the operative regulatory threshold) is in the README and the technical blog post.

If you've built RAG pipelines and hit failures you couldn't explain - this was built for that.

#RAG #NLP #MachineLearning #LLM #OpenSource #SoftwareEngineering

---

## Alt Version (Shorter, More Technical)

RAGAS gave my RAG pipeline an 0.82 faithfulness score. The answer was missing the most critical number in the document.

RAGAS measures whether what was said is supported. It doesn't measure what was omitted.

I built Veriducta to close that gap - specifically, to answer "which pipeline stage (chunking, retrieval, reranking, generation) caused this failure?" with a reproducible, evidence-based method.

The causal replay engine stores full retrieval traces and runs counterfactual experiments against historical queries. Stage 3 (reranker) ablation requires no re-inference - the pre-reranking top-40 candidate list with scores is stored in every trace.

Result: **73.3% root-cause accuracy** on 60 synthetic corruption cases.

Code: github.com/hardik2004gupta/Veriducta

#RAG #LLM #Observability #NLP #Python

---

## Posting Tips

- Post Tuesday/Wednesday 8–10am (highest LinkedIn reach)
- Pin the comment with the GitHub link + blog post link
- Tag the Anthropic account in the mention of Claude Sonnet 4.6
- First 2–3 lines appear before "see more" - make them the hook
- Avoid leading with "I built" - start with the problem or the insight
