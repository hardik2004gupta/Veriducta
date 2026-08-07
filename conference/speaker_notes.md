# Conference — Speaker Notes

*Detailed notes for delivering the 20-minute talk.*

---

## Before the Talk

**Setup checklist**:
- [ ] `docker compose up -d` running at least 10 minutes before
- [ ] Browser at localhost:3000, dashboard loaded
- [ ] Ask page pre-loaded with query typed but not submitted
- [ ] Replay page ready to load a trace ID
- [ ] GitHub repo open in second tab
- [ ] Slides deck on second monitor or second window
- [ ] Backup: screenshots of every demo step in case of network issues

**Technical setup**:
- Check Qdrant is up: `curl localhost:6333/collections`
- Check API is up: `curl localhost:8080/api/v1/health`
- Test query produces expected incomplete answer before going on stage
- Have trace ID for the OSHA case pre-copied (saves live demo time)

---

## Opening (Slide 1-2)

**What to say**:
> "I want to start with a specific failure. I have a RAG pipeline answering questions about OSHA's crystalline silica exposure standard. The pipeline retrieved context. The generation completed. And RAGAS scored the answer 0.82.
>
> The answer was missing the permissible exposure limit. The primary regulatory threshold. The number that engineers in a construction context would need to make compliance decisions.
>
> And I had no idea which part of my pipeline to fix."

**What to watch for**: If the live demo is slow, narrate what's happening. If it fails, switch to the screenshot fallback immediately.

**Transition**: "Let me explain why finding the cause is harder than it sounds."

---

## Problem Statement (Slide 3-4)

**The four stages**:

> "Most RAG pipelines have four components that can introduce failures. Chunking — how you split documents. Retrieval — which chunks you pull. Reranking — how you filter from your retrieval list. And generation — what the LLM does with the context.
>
> Every one of these can produce a failure that looks identical from the outside: the answer is incomplete or wrong. A faithfulness score below 0.75 on a bad answer gives you no information about which of these four to fix.
>
> And the fix is completely different for each one. If it's chunking, you need to adjust your boundary detection. If it's retrieval, you need better embedding or BM25 parameters. If it's reranking, your cutoff threshold is wrong. If it's generation, you need a better prompt. Diagnosing the wrong one wastes engineering time."

**Transition**: "The solution I came to is forensic rather than evaluative."

---

## Architecture Section (Slide 5-7)

**Key point to emphasize**:

> "The architectural constraint that makes attribution possible is simple: each layer is independently substitutable. If retrieval and generation are coupled — if the generator knows how retrieval works — you can't test what would have happened with different retrieval. The strict dependency rule is what enables the counterfactual experiments."

**The evidence log**:

> "The evidence log is the core enabler. Append-only JSONL — one line per query, never modified. SQLite index stores the exact byte position of each entry. Lookup is a primary key read and a file seek. O(1).
>
> The content that matters most: the full pre-reranking top-40 candidate list with cross-encoder scores. Storing it costs 8 kilobytes per query. Not storing it would require re-running the cross-encoder — a 90-megabyte model, about 1 second of CPU — for every historical query the replay engine investigates. That's the tradeoff."

**Pause here** — this is the most conceptually dense slide. Give the audience 5 seconds to absorb before moving on.

---

## Ablation Engine (Slides 8-12)

**Stage 1 — What to emphasize**:

> "The chunking attribution is the most interesting because it requires maintaining two separate Qdrant collections — one boundary-aware, one boundary-naive. When you replay retrieval with the boundary-aware collection and Recall@5 improves significantly, chunking is the problem. You don't need to re-embed or re-rank — you're just querying the alternative collection."

**Stage 3 — What to emphasize** (this gets the most technical questions):

> "Stage 3 is the cleanest engineering win. I have 40 candidates in my trace with their cross-encoder scores. To test whether a wider cutoff would have included the correct chunk, I just construct the context from the top-N candidates and re-run generation. No cross-encoder. No embedding. This is why storing the pre-reranking list is worth the 8KB."

**Stage 4 — Be honest**:

> "Stage 4 is the hardest. LLMs are stochastic. Running the same context through a baseline prompt twice gives you different outputs. Distinguishing 'the prompt caused this failure' from 'temperature variance' requires an oracle — a reference answer. We don't have one for most production queries. Stage 4 accuracy is 50%. I'm honest about this in the output."

---

## Case Study (Slides 13-15)

**Tell the story, don't just show the numbers**:

> "The OSHA standard has a critical sentence: 'initiate medical surveillance for employees exposed at or above the action level of 25 micrograms per cubic meter.' The chunker split this sentence at 'action level.' Chunk 0041 ends with 'action level.' Chunk 0042 starts with 'of 25 micrograms.'
>
> Dense retrieval finds chunk 0042 because it starts with a measurement — dense retrieval responds well to numeric content in regulatory domains. It ranks third. Chunk 0041 ranks twelfth, below the top-8 cutoff.
>
> The generator receives 'of 25 micrograms per cubic meter as an 8-hour TWA' without the label 'action level.' It also receives 'Employers must initiate medical surveillance' without the threshold. It correctly cites both, but cannot synthesize the complete sentence because the label and the value are in different chunks.
>
> RAGAS faithfulness: 0.82. Every cited claim is entailed by its chunk. No alert.
>
> Stage 1 ablation: Recall@5 0.45 with boundary-naive, 0.80 with boundary-aware. Delta: 0.41. Attribution: chunking. Fix: one regex line in the chunker config. Effect: quality 0.41 to 0.93, omission rate 23% to 4%."

**This is the most memorable part of the talk** — slow down, let it land.

---

## Results (Slide 16)

**Don't just read the numbers**:

> "73.3% overall is above the 70% target. More importantly, 68.8% on the boundary-error subset — the hardest cases, where the split happens at semantically critical regulatory clause boundaries — is above the 65% target.
>
> The gap between retrieval accuracy (85%) and generation accuracy (50%) tells you something real: retrieval corruptions are detectable because they produce large, clean signal. Generation failures are genuinely ambiguous without an oracle.
>
> This isn't a weakness of the system — it's an honest characterization of what causal attribution can and can't do with current tooling."

---

## Closing

**For the open questions**:

> "The hardest open problem here is oracle-free Stage 2 attribution — testing retrieval failures without annotated gold chunks. I suspect the answer involves query-agnostic chunk importance scoring, but the research doesn't exist yet.
>
> If you're working on RAG evaluation or observability and you're interested in any of these problems, the code is on GitHub. MIT license. 801 tests. Contributions welcome."

**Last line**:

> "If you've built a RAG pipeline and hit a failure you couldn't explain — this was built for that. Thank you."
