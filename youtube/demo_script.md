# YouTube — Demo Script

*Short demo video: "Veriducta in 5 Minutes"*
*Target: 4–6 minutes, screen recording only, minimal narration*

---

## Script

[0:00] Open terminal. Run:

```bash
docker compose up -d qdrant minio
make run
```

"Starting the Veriducta stack — Qdrant, MinIO, and the FastAPI backend."

[0:20] Open browser at localhost:3000. Dashboard loads.

"This is the Veriducta observability dashboard. You can see real-time query stats, latency distribution, and root-cause attribution breakdown."

[0:35] Click "Ask Veriducta" in sidebar.

"Let's ask a question about OSHA silica exposure limits."

Type: "What is the permissible exposure limit for respirable crystalline silica under OSHA 1926.1153?"

Hit enter. Answer starts streaming.

[0:55] Answer appears. Point out: mentions action level, mentions medical surveillance. Missing: the PEL value (50 µg/m³).

"The answer looks plausible — but notice it's missing the permissible exposure limit itself. RAGAS would score this 0.82. Let's find out why."

[1:15] Click "Replay" button on the answer card (or navigate to Replay page, paste trace ID).

[1:25] The replay attribution report begins generating. Show the stage-by-stage output:

- Stage 1: Recall@5 0.45 → 0.80. Delta: -0.41. **CHUNKING FLAGGED**
- Stage 2: Delta 0.06. Retrieval: not primary cause.
- Stage 3: Candidate 12 was not in top-40. Reranker: not primary cause.
- Stage 4: Delta 0.02. Generation: not primary cause.

[2:00] Attribution report complete. "Primary root cause: **chunking**. Confidence: 0.88."

[2:10] Click "Evidence" in sidebar. Show the retrieval trace — scrollable list of candidates with BM25, dense, RRF, and reranker scores.

"You can see chunk 0042 ranked 3rd after reranking. Chunk 0041 ranked 12th — dropped at the top-8 cutoff. These two chunks contain the two halves of the same sentence."

[2:35] Navigate to "Retrieval Inspector". Show the score breakdown bars. Highlight the temporal filter section — show 0 rejections on this query.

[2:55] Navigate back to the main terminal. Run:

```bash
python scripts/run_benchmark.py --cases 5
```

Show 5 corruption cases being attributed. Show accuracy summary.

[3:30] "73.3% attribution accuracy on 60 corruption cases. Four metrics RAGAS can't compute."

[3:45] Show GitHub README briefly.

"Full source at github.com/hardik-gupta/veriducta. MIT license. 801 tests, 92.81% coverage."

[4:00] End screen with links: GitHub, blog post, LinkedIn.

---

## Recording Notes

- Record at 1920×1080, 60fps
- Use dark OS theme (matches the UI)
- Browser zoom: 90% to show more content
- Have the query pre-typed — don't type it on camera (wastes time)
- Have the benchmark pre-configured for 5 cases (full 60 takes too long for demo)
- Edit out any API latency waits > 3s with a cut
