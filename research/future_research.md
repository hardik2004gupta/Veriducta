# Research - Future Research Directions

*Open problems emerging from the Veriducta design and evaluation.*

---

## Priority 1: Oracle-Free Stage 2 Attribution

**Problem**: Stage 2 attribution (retrieval) requires annotated gold supporting chunk IDs. Without annotation, the engine cannot test whether gold context would have improved the answer.

**Why it's hard**: To test retrieval attribution without an oracle, you need to estimate which chunks *should* have been retrieved - without knowing the correct answer. This is a circularity: good retrieval is defined relative to a correct answer, but a correct answer requires good retrieval.

**Potential approaches**:

*Query-agnostic chunk importance*: Score chunks by their expected contribution to a correct answer using a trained estimator. Similar to ARES (Saad-Falcon et al. 2023), but designed for attribution rather than evaluation. Requires a labeled training set.

*Contrastive attribution*: Compare retrieval distributions between high-quality and low-quality answers on similar queries. Chunks that appear in high-quality contexts but not in low-quality contexts are candidates for "should have been retrieved." Requires a corpus of query-answer pairs with quality labels.

*Coverage-based estimation*: For a query Q and a claim set C from the answer, estimate whether C is completable from the retrieved chunks without requiring annotation of *which* chunks are gold. Uses NLI batch inference over all retrieved candidates. Partially implemented in the counterevidence retrieval step.

**Closest existing work**: ARES, RAGS (Ru et al. 2024), RAGTruth (Niu et al. 2024).

---

## Priority 2: Causal Graph vs. Sequential Ablation

**Problem**: Sequential ablation cannot model inter-stage interactions. Multiple stages may contribute to a failure, but only the largest delta is labeled as primary.

**Approach**: Replace the sequential ablation with a causal directed acyclic graph (DAG):

```
Chunking → Retrieval → Reranking → Generation
      ↘                   ↗
        (interaction edge)
```

Using Pearl's do-calculus, compute the causal effect of intervening at each node on the final quality score. This allows attribution of shared variance across stages rather than winner-take-all primary attribution.

**Challenge**: The interventional distributions are expensive to estimate. For a DAG with 4 nodes, the number of required interventions grows combinatorially. Practical approximations (e.g., only testing single-node interventions) may miss important interactions.

**Closest existing work**: Pearl (2009), causal inference in recommender systems (Schnabel et al. 2016), causal analysis of NLP models (Feder et al. 2022).

---

## Priority 3: Continuous Attribution Threshold Calibration

**Problem**: Attribution thresholds (τ₁=0.15 for chunking, τ₂=0.15 for retrieval, τ₃=0.15 for reranker, τ₄=0.10 for generation) were calibrated on the 60-case benchmark. As the corpus grows and query distribution shifts, these thresholds may become miscalibrated.

**Approach**: Online calibration using an expanding window of annotated feedback. As users flag failed answers and provide root-cause labels, the calibration set grows and thresholds are updated.

**Challenge**: User feedback is sparse and biased (users flag obvious failures, not subtle omissions). Active learning strategies are needed to select which queries to solicit feedback on.

**Related work**: Threshold calibration for anomaly detection (Hundman et al. 2018), active learning for evaluation (Settles 2009).

---

## Priority 4: NLI-Free Claim Verification

**Problem**: The 3-class NLI heuristic (cross-encoder/nli-deberta-v3-base) was calibrated on 120 hand-labeled pairs from one corpus. Calibration does not generalize to other domains without re-labeling.

**Approach**: Replace the 3-class heuristic with a learned quality scorer trained on human preference data (Bradley-Terry model over claim-context pairs). This eliminates the per-domain calibration requirement.

**Challenge**: Collecting human preference data at scale is expensive. The initial preference data needs to cover the full distribution of claim-context relationships, including nuanced conditionals.

**Related work**: RLHF (Christiano et al. 2017), Constitutional AI (Bai et al. 2022), learned NLI (Bowman et al. 2015 - SNLI).

---

## Priority 5: Cross-Pipeline Attribution

**Problem**: When two RAG systems (different architectures, different corpora) answer the same query differently, current tools cannot identify whether the divergence originates in retrieval or generation.

**Application**: A/B testing RAG systems. Given that System A produces answer X and System B produces answer Y on query Q, is the divergence due to different retrieval (different chunks) or different generation (same chunks, different synthesis)?

**Approach**: Run retrieval from both systems, cross-inject contexts (give System A's context to System B's generator and vice versa), and measure quality deltas. This is a two-system extension of Stage 2 and Stage 4 ablation.

**Challenge**: Quality comparison between systems requires a consistent quality metric that doesn't depend on either system's design choices.

---

## Priority 6: Temporal Drift Detection

**Problem**: Regulatory corpora evolve. New standards supersede old ones. The version graph requires manual maintenance - if a new document is added without updating its supersession relationships, outdated information can appear in answers.

**Approach**: Automatic temporal drift detection by monitoring retrieval patterns over time. If chunks from a specific document consistently appear in retrieval but the document's effective date is approaching its expected expiry, flag for sidecar review.

Additionally: monitor for external signals (new OSHA standards published, NIST document updates) via RSS feeds and trigger a version graph review alert.

**Challenge**: "Expected expiry" dates are not stored in the current schema. Adding them requires an assumption about how long regulatory standards typically remain valid, which is domain-specific.

---

## Secondary Research Questions

1. **What chunking granularity minimizes boundary split rate across regulatory corpora?** Current design (200–400 token child chunks) is empirically motivated. A systematic study across OSHA, NIST, USGS, and FDA regulatory corpora would identify optimal chunk sizes per document genre.

2. **Does RRF k=60 remain optimal for this retrieval task?** The original Cormack et al. (2009) validation was on TREC newswire corpora. Technical regulatory documents have different rank gap distributions. Re-benchmarking with k ∈ {30, 60, 90, 120} on the gold QA dataset would verify or refine the parameter.

3. **Can LLM-graded quality scoring replace heuristic quality metrics in ablation?** The current quality metric is a composite of Recall@5 and NLI entailment rate. An LLM-graded quality score (using Claude Sonnet 4.6 as a judge) might be more sensitive to subtle quality differences in Stage 4 ablation.

4. **What is the minimum annotation set size for calibrating NLI thresholds per domain?** The current 120-pair calibration set was chosen empirically. Learning curves for NLI threshold calibration would characterize how annotation efficiency scales with corpus complexity.
