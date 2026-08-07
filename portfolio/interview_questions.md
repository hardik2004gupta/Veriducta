# Veriducta — Interview Q&A Preparation

Likely interview questions and strong answers for different question types.

---

## System Design Questions

### "Walk me through the architecture of Veriducta."

**Answer framework**: Layer → responsibility → key design decision → tradeoff.

> Veriducta has eight layers with strict downward dependency enforcement. The foundation (schemas, utils, config, core) has no business logic — just types, exceptions, and interfaces. Above that are five pipeline layers: ingestion, retrieval, generation, verification, and replay. The API layer sits at the top and has no business logic either — it delegates immediately to pipeline components.
>
> The key design decision that enables causal attribution is the evidence log. Every query produces a `RetrievalTrace` and a `GenerationTrace` written to JSONL and indexed in SQLite by byte offset. That index gives O(1) lookup, which the replay engine needs to investigate historical queries without scanning the log.
>
> The tradeoff: the system is optimized for diagnostic capability over simplicity. An 8-layer architecture with strict import rules is overkill for a simple Q&A app. It's the right tradeoff for a system whose core value proposition is causal attribution.

### "How does the causal replay engine work?"

> The replay engine runs four ablation stages sequentially against historical trace data.
>
> Stage 1 tests chunking: it replays retrieval using a boundary-aware chunking configuration and measures the Recall@5 delta. If the correct chunks are retrieved with the better chunking config, chunking is the root cause.
>
> Stage 2 tests retrieval: it injects gold supporting chunks (from human annotation) into the generation context and measures quality delta. If the answer improves dramatically with correct context, retrieval failed.
>
> Stage 3 tests the reranker: it loads the stored pre-reranking top-40 candidate list from the evidence log and tests different cutoff thresholds. No re-inference needed — the cross-encoder scores were stored at query time.
>
> Stage 4 tests generation: it replays generation with the original context and a baseline prompt, measuring whether the LLM introduced the failure.
>
> The primary root cause is the stage with the largest quality delta above the attribution threshold (0.15).

### "Why store the pre-reranking top-40 list?"

> The cross-encoder reranker takes 40 query-chunk pairs and re-orders them. Testing whether a different rerank cutoff would have included the correct chunk requires those 40 scored candidates. Without storing them, Stage 3 ablation requires re-running the cross-encoder — approximately 1.1 seconds of CPU inference per query, multiplied by every ablation run.
>
> Storing 40 scored candidates costs ~8KB of JSON per query. For a 60-case benchmark with multiple cutoff variants per case, this eliminates dozens of redundant inference calls. The tradeoff is clearly favorable, and it makes Stage 3 a pure data analysis step rather than an inference step.

### "How does the temporal filter work?"

> The corpus contains multiple versions of the same regulatory document. The version graph is a `networkx` DiGraph where each node is a document and edges represent supersession relationships.
>
> At query time, the temporal filter receives the query date and checks every retrieved candidate: if the chunk's document has a superseding document whose effective date is before the query date, the chunk is rejected with reason `"superseded"`. If the chunk's effective date is after the query date, it's rejected with `"not_yet_effective"`.
>
> The filter is mandatory — there's no way to disable it in the production code path. This is a deliberate constraint because silent supersession errors (answering with an old standard's threshold) are worse than a missed retrieval.

---

## Behavioral / Experience Questions

### "Tell me about a technical decision you had to change during development."

> I originally built Stage 3 ablation (reranker testing) to re-run the cross-encoder at ablation time. The idea was that the ablation engine should be able to test any cutoff configuration, not just what was run at inference time.
>
> After two days of implementation, I realized this was solving the wrong problem. The replay engine is supposed to explain *historical* queries — what actually happened, not what would happen with a different setup. Re-running the cross-encoder introduces variance (model weights are the same, but input ordering can affect batch normalization) and makes the results non-deterministic.
>
> The right answer: store the scores at inference time, do the cutoff analysis during replay without re-inference. 8KB per query, zero additional inference. The new approach is more principled and faster. The lesson: "replayable" means using evidence from the original run, not recreating the original run.

### "What was the hardest part of this project?"

> Generation attribution (Stage 4). LLM outputs are stochastic — even with the same context and prompt, you get different outputs. Testing whether the generation stage caused a failure requires establishing a "correct" output baseline, which is only possible with human annotation or a reference answer.
>
> I tried running Stage 4 multiple times and averaging, tried widening the attribution threshold, tried using a deterministic lower-temperature run. None of them solved the fundamental problem: you can't distinguish "the prompt caused a poor answer" from "the LLM made a random error" without an oracle.
>
> I ended up accepting 50% Stage 4 accuracy as an honest limitation and documenting it clearly in the `ReplayReport`. The right engineering answer to an unsolvable problem is sometimes "acknowledge it, bound it, move on."

### "How did you validate that the system worked?"

> Two validation layers: unit tests (801, 92.81% coverage, mypy --strict) and a 60-case synthetic corruption benchmark.
>
> The corruption benchmark was designed to test attribution under adversarial conditions. Each case has a known ground-truth root cause and a flag for whether it's a "realistic boundary-error" (the hardest category). I built 4 corruption categories: retrieval swaps, chunking boundary splits, reranker threshold failures, generation prompt corruptions.
>
> The benchmark showed 73.3% overall accuracy (target: ≥ 70%) and 68.8% boundary-error accuracy (target: ≥ 65%). Both targets were met on the first complete benchmark run after calibrating the attribution thresholds.

---

## ML-Specific Questions

### "How did you choose the NLI thresholds?"

> I built a labeled validation set of 120 claim-context pairs, drawn from the actual corpus. Each pair was hand-labeled as supported, contradicted, or ambiguous-conditional.
>
> The initial thresholds from the model documentation (entailment > 0.70, contradiction > 0.80) produced too many false positives on regulatory language — `"except where"` and `"unless otherwise specified"` phrases scored as contradictions. After calibration:
> - Supported: entailment > 0.65
> - Contradicted: contradiction > 0.85 AND neutral < 0.30
> - Ambiguous-conditional: neutral > 0.40 AND contradiction between 0.30 and 0.70
>
> Adding the `neutral < 0.30` cap for contradictions reduced false positives by 60%. The additional `ambiguous-conditional` class captures genuinely nuanced claims that need expert review without flagging them as outright contradictions.

### "Why RRF over learned fusion?"

> For this corpus size (30–50 documents), learned fusion would require a labeled fusion training set that doesn't exist. RRF (Reciprocal Rank Fusion with k=60) is parameter-free given a fixed k, validated in the original Cormack et al. 2009 paper, and produces stable results without overfitting.
>
> The alternative — learning fusion weights per query type — requires enough query-level relevance labels to estimate weights. The 40-question gold QA dataset is too small for this.
>
> Practical tradeoff: RRF is slightly suboptimal compared to a well-trained learned ranker, but it's reliable, reproducible, and requires no training data. For a 50-document corpus, that's the right choice.

---

## "Why did you build this?" / Motivation Questions

> During an earlier RAG evaluation project, I hit a failure pattern that existing tools couldn't explain: answers that scored well on faithfulness (0.80+) were incomplete in ways that made them operationally useless. RAGAS confirmed the answers were supported by retrieved context. The context was incomplete.
>
> The gap was the diagnosis question: faithfulness tells you the answer is bad, but not which component to fix. Improving chunking when the problem is retrieval wastes engineering effort. Improving the prompt when the problem is a missing chunk doesn't help.
>
> I built Veriducta to close that gap — specifically to answer "which stage caused this failure?" with a reproducible, evidence-based method rather than guesswork.
