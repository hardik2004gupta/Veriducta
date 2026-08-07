# LinkedIn - Comment Reply Templates

*Pre-written responses for common comments on the launch post.*

---

## "How is this different from RAGAS / TruLens / DeepEval?"

> Great question - the key distinction is measurement vs. attribution.
>
> RAGAS tells you *whether* an answer is faithfully supported by retrieved context. Veriducta tells you *which stage* caused the failure when the answer is bad.
>
> If RAGAS gives you a low faithfulness score, you still don't know whether to fix your chunking strategy, retrieval recall, reranker threshold, or generation prompt. Veriducta answers that question specifically, using counterfactual replay over stored retrieval traces.
>
> They're complementary - the evaluation scorecard in Veriducta actually includes a RAGAS comparison adapter for the metrics that overlap.

---

## "How do you handle the stochasticity of LLM outputs in Stage 4?"

> Honestly, Stage 4 (generation attribution) is the weakest part of the system. LLM outputs are stochastic, and distinguishing "the prompt caused a poor answer" from "temperature variance produced a suboptimal output" requires an oracle.
>
> The current approach: wider attribution threshold for Stage 4, and explicit confidence notes in the `ReplayReport`. Stage 4 attribution accuracy is 50% - documented as a known limitation.
>
> This is genuinely an open research problem. If you have thoughts on oracle-free generation attribution, I'd love to hear them.

---

## "What kind of corpus does this work best on?"

> Technical regulatory and engineering documents - the kind with precise terminology, version supersession relationships, and section-structured layouts where boundary-aware chunking makes a material difference.
>
> OSHA standards, NIST guidelines, engineering specifications. The temporal filtering component (which rejects chunks from superseded document versions) is most valuable here.
>
> It would need adjustment for conversational corpora, where "section boundaries" aren't meaningful and temporal supersession doesn't apply. The chunker's boundary regex would need to be empty or replaced with a sentence-based approach.

---

## "Is this production-ready?"

> Functionally yes for the backend pipeline - 801 tests, 92.81% coverage, mypy --strict. The API is single-worker (asyncio/thread pool for v2.0), so it's not suitable for high-concurrency production without modification.
>
> The frontend currently runs on mock data - live API integration is planned for v1.1.
>
> Think of it as production-ready in the sense that the code is clean and tested, but with known architectural limitations documented in the RELEASE_NOTES.

---

## "Can I use this with OpenAI / Gemini / open-source models?"

> The generator currently uses Claude Sonnet 4.6 via the Anthropic SDK. The `BaseGenerator` interface is abstract, so adding a new implementation for OpenAI or Gemini is a ~100-line addition that implements the same interface.
>
> Multi-LLM support is on the v2.0 roadmap. If you want to contribute a GPT-4o or Gemini adapter, the FIRST_CONTRIBUTION.md has a good-first-issues section that's a great place to start.

---

## "What's the chunking failure corpus?"

> It's a subset of the corpus documents where boundary-naive and boundary-aware chunking produce materially different splits at semantically critical clauses.
>
> For each document in the corpus, I ran both configurations and identified locations where the split crossed a regulatory clause, table cell, or section header. Documents with ≥ 1 such location are in the failure corpus. I then created a separate Qdrant collection for the boundary-aware chunks.
>
> The Stage 1 ablation only runs for documents in this corpus - for other documents, the chunking configuration is assumed to be equivalent.

---

## "Did you use LangChain / LlamaIndex?"

> No - the pipeline is built from scratch using the underlying libraries directly: sentence-transformers for embedding and reranking, qdrant-client for vector search, rank-bm25 for BM25, the Anthropic SDK for generation.
>
> The reason: the replay engine needs precise control over what data is stored at each stage and how retrieval is replayed. Framework abstractions would have made the pre-reranking trace storage and counterfactual replay much harder to implement cleanly.
>
> For applications where you don't need causal attribution, LangChain or LlamaIndex would be the right choice - they handle a lot of boilerplate.
