# YouTube — Full Video Script

*Video title: "I Built a Tool That Tells You WHY Your RAG Pipeline Failed"*
*Target length: 18–22 minutes*
*Tone: Conversational, technical, no fluff*

---

## INTRO (0:00–1:30)

[Screen: terminal running `make run`]

Let me show you something.

I have a RAG pipeline here answering questions about OSHA's crystalline silica standard. I'm going to ask it: "What is the permissible exposure limit for respirable crystalline silica?"

[Screen: answer appears — missing the PEL value]

The answer looks reasonable. It mentions the action level. It mentions medical surveillance requirements. But notice what's missing — the actual permissible exposure limit. The 50 µg/m³ threshold. The primary regulatory number that the entire standard exists to enforce.

[Screen: RAGAS score appears — 0.82]

And here's the RAGAS faithfulness score for that answer: 0.82. Above the typical "acceptable" threshold of 0.75. Not a single alert.

If you've built RAG pipelines before, you've hit this. A metric that says "good." An answer that's wrong. And absolutely no idea which part of the pipeline to fix.

I'm Hardik, and I built Veriducta to solve exactly this problem. In this video I'm going to show you how it works, what makes the causal attribution possible, and what it actually found when it analyzed that failed answer.

---

## SECTION 1: THE DIAGNOSIS GAP (1:30–4:00)

[Screen: diagram of RAG pipeline stages]

Before I show you the demo, let me explain why this is a hard problem.

A RAG pipeline has four places where failures can originate:

Chunking — when you split your documents into chunks, you might split a critical clause across a boundary. Half the sentence is in chunk 42, the other half is in chunk 43. Dense retrieval finds chunk 42 (which starts mid-sentence) and completely misses chunk 43 (which starts with a number that looks like the beginning of a new sentence).

Retrieval — even if chunking is perfect, your retrieval might miss the right chunks. BM25 might not catch the right terminology. Dense retrieval might retrieve semantically adjacent but wrong chunks.

Reranking — you run BM25 and dense retrieval against 100 candidates each, fuse the lists, and pass the top 40 to a cross-encoder reranker. The correct chunk might be in the top 40 but rank 11th after reranking. If your cutoff is top-8, it's gone.

Generation — the LLM got the right context but omitted or misrepresented something. This is the failure mode people assume is always the cause, but it's usually the least common one.

Here's the problem: from a faithfulness score alone, these four failures look identical. All of them produce answers that are supported by the retrieved context. The difference is in what context was retrieved — and that's exactly what faithfulness doesn't measure.

---

## SECTION 2: THE ARCHITECTURE (4:00–8:00)

[Screen: architecture diagram, scrolling through layers]

Veriducta has eight layers. I'll go through the important ones quickly.

[Screen: ingestion code — chunker.py]

The ingestion pipeline parses PDFs with PyMuPDF, then runs boundary-aware hierarchical chunking. Parent chunks are 1,400–1,600 tokens at section boundaries. Child chunks are 200–400 tokens with 50-token overlap. The "boundary-aware" part is key — the chunker never splits a child window across a detected section boundary marker. Those boundaries include regex patterns like "Employer(s) must", "Section \d+", table headers.

Every ingestion run creates a configuration snapshot — a SHA-256 hash of the exact chunking parameters. That hash gets stored with every trace.

[Screen: retrieval trace JSONL]

The retrieval pipeline is where the magic happens. BM25 and dense retrieval each return 100 candidates. Reciprocal Rank Fusion combines them. Temporal filtering rejects superseded or not-yet-effective chunks. The cross-encoder reranker processes the top 40 and keeps the top 8.

And here's the critical part — before the reranker runs, the full top-40 list with all BM25 scores, dense scores, and cross-encoder scores is stored in the retrieval trace. This is what I call "the pre-reranking top-40 sacred list." It's what makes Stage 3 ablation possible without re-running inference.

[Screen: evidence log JSONL + SQLite index]

Every query appends a retrieval trace and generation trace to a JSONL evidence log. A SQLite index stores the exact byte offset of each entry. Lookup is O(1) — seek directly to the byte position, read one line.

---

## SECTION 3: THE CAUSAL REPLAY ENGINE (8:00–14:00)

[Screen: replay engine running, attribution report appearing]

Now let me show you how attribution actually works.

[Screen: stage 1 code — ablation.py]

Stage 1 tests chunking. The engine checks whether the failed query's document is in the "chunking failure corpus" — documents where boundary-aware and boundary-naive configurations produce different splits. If it is, the engine replays retrieval with the boundary-aware collection and computes the Recall@5 delta.

For the silica PEL case: Recall@5 was 0.45 with boundary-naive chunking. It was 0.80 with boundary-aware chunking. Delta: minus 0.41. That's far above the attribution threshold of 0.15. Chunking is flagged as the root cause.

[Screen: stage 1 replay output in terminal]

[Screen: stage 2 code — ablation.py]

Stage 2 tests retrieval. The engine loads the gold supporting chunk IDs from the ground-truth annotation, injects them directly into the generation context, and re-runs generation. If quality jumps, retrieval failed.

For this case: Stage 2 delta was only 0.06. The gold chunks didn't help much more than Stage 1's boundary-aware chunks already did. That confirms chunking, not retrieval, was the primary issue.

[Screen: stage 3 code — no cross-encoder re-inference]

Stage 3 is the clever one. The engine loads the pre-reranking top-40 from the stored trace. It constructs context at cutoffs of 1, 3, 5, and 8 candidates, replays generation four times, and measures quality at each cutoff.

Notice what it's NOT doing: it's not re-running the cross-encoder. Those scores were stored at query time. Stage 3 is pure data analysis.

For the silica case: Stage 3 delta was 0.03. The correct chunk wasn't in the top-40 at all — confirming it was a chunking problem, not a reranker problem.

[Screen: final replay report]

The final replay report: primary root cause is chunking, confidence 0.88, stage attributions show chunking at -0.41 and everything else under -0.06.

---

## SECTION 4: THE WORKED CASE IN FULL (14:00–18:00)

[Screen: OSHA document side-by-side with chunk split visualization]

Let me show you exactly what happened with the silica document.

[Screen: zoomed in on the chunk split]

The boundary-naive chunker split right here. Chunk 0041 ends with "initiate medical surveillance for employees exposed at or above the action level". Chunk 0042 starts with "of 25 micrograms per cubic meter as an 8-hour TWA".

The phrase "action level of 25 µg/m³" is the legally operative threshold. Split across a boundary, they become two orphaned half-sentences.

[Screen: retrieval scores for both chunks]

Dense retrieval for the query "permissible exposure limit crystalline silica": chunk 0042 (which starts with a measurement unit) scores 0.31. Chunk 0041 (which contains "action level" and "medical surveillance") scores 0.24. Both are retrieved, both in the top 100.

After RRF fusion and cross-encoder reranking: chunk 0042 ranks 3rd, chunk 0041 ranks 12th. Top 8 cutoff. Chunk 0041 is gone.

[Screen: generated answer]

The generator receives context including "of 25 micrograms per cubic meter as an 8-hour TWA" — the number without its label — and "Employers must initiate medical surveillance" — the obligation without the number. The answer correctly cites both but cannot synthesize the complete threshold because neither chunk contains both parts of the same sentence.

RAGAS faithfulness: 0.82. Every stated claim is entailed by the cited chunks. No alert.

Veriducta quality score: 0.41. Recall@5 with gold chunks: 0.80. Attribution: chunking.

[Screen: fix and re-run]

After extending the boundary regex to include "Employer(s)? must": chunk 0041 and 0042 merge into a single 312-token child chunk. Retrieval now finds the complete clause at rank 1. Quality score: 0.93. RAGAS faithfulness: 0.89. Omission rate for this document: 23% → 4%.

---

## OUTRO (18:00–19:30)

[Screen: GitHub repo]

This is what causal attribution gives you that faithfulness metrics don't: the specific fix, not just the signal that something is broken.

Veriducta is open source under MIT. The repo has the complete source, 801 tests, Docker Compose setup, and a blog post with this exact case study in more detail.

Link in the description.

If you hit a failure like this one — good RAGAS score, bad answer, no idea why — run the causal ablation. Stage 1 will tell you in under 10 seconds whether chunking is the culprit.

If this was useful, subscribe. I'll be posting more on RAG pipeline engineering and observability.

Thanks for watching.

---

## B-ROLL / SCREEN RECORDING CHECKLIST

- [ ] Terminal: `make run` starting the API
- [ ] Browser: dashboard showing query stats
- [ ] Browser: ask page — question typed, answer appearing
- [ ] Browser: replay page — attribution report generating in real time
- [ ] Code editor: chunker.py — boundary regex highlighted
- [ ] Code editor: ablation.py — stage 1, stage 2, stage 3 highlighted
- [ ] Terminal: JSONL evidence log tail
- [ ] Terminal: pytest output (801 passed)
- [ ] Split screen: OSHA PDF vs. chunk visualization
