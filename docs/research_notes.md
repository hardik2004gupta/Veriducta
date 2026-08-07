# Research Notes

References, relevant literature, and research context for Veriducta's design choices.

---

## Retrieval

### Reciprocal Rank Fusion
**Cormack, G.V., Clarke, C.L.A., & Buettcher, S. (2009)**. Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods. *SIGIR 2009*.

The paper that established RRF as a standard baseline for rank aggregation. The k=60 constant was shown to be robust across a wide range of test collections without tuning. Veriducta uses k=60 with an implicit rank of 101 for absent candidates (out of 100 retrieved per source).

### BGE Embedding Models
**Xiao, S., et al. (2023)**. C-Pack: Packaged Resources To Advance General Chinese Embedding. *arXiv:2309.07597*.

BGE-large-en-v1.5's training procedure uses a general text corpus with hard-negative mining and instruction-following fine-tuning. The recommended asymmetric retrieval prefix (`"Represent this sentence for searching relevant passages: "`) is designed to shift the embedding toward passage retrieval semantics.

### Dense Passage Retrieval
**Karpukhin, V., et al. (2020)**. Dense Passage Retrieval for Open-Domain Question Answering. *EMNLP 2020*.

Establishes the foundational approach for dual-encoder retrieval (query encoder + passage encoder). Veriducta uses a single shared encoder (BGE-large) rather than separate query/passage encoders, relying on the query prefix to handle the asymmetry.

### Cross-Encoder Reranking
**Nogueira, R., & Cho, K. (2019)**. Passage Re-ranking with BERT. *arXiv:1901.04085*.

Established cross-encoder reranking as the standard approach for passage retrieval. The `ms-marco-MiniLM-L-12-v2` model used in Veriducta is a distilled version trained on MS MARCO with knowledge distillation from a larger cross-encoder.

---

## NLI and Claim Verification

### NLI for RAG Faithfulness
**Honovich, O., et al. (2022)**. TRUE: Re-Evaluating Factual Consistency Evaluation. *NAACL 2022*.

Demonstrates that NLI-based evaluation of factual consistency outperforms n-gram overlap metrics (ROUGE, BLEU) for factuality evaluation. Veriducta's claim-level NLI approach follows this methodology.

### DeBERTa
**He, P., et al. (2021)**. DeBERTaV3: Improving DeBERTa using ELECTRA-Style Pre-Training with Gradient-Disentangled Embedding Sharing. *arXiv:2111.09543*.

`cross-encoder/nli-deberta-v3-base` achieves state-of-the-art NLI performance on MultiNLI. The 3-class output (entailment/contradiction/neutral) is the input to Veriducta's heuristic thresholding.

### Counterevidence Retrieval
**Guo, Z., et al. (2022)**. A Survey on Automated Fact-Checking. *TACL 2022*.

Surveys fact-checking approaches including claim decomposition and evidence retrieval. Veriducta's 5-step counterevidence algorithm is informed by the contrastive query expansion approach from this survey.

---

## Chunking

### Hierarchical Chunking
**Edge, J., et al. (2024)**. From Local to Global: A Graph RAG Approach to Query-Focused Summarization. *arXiv:2404.16130*.

While focused on graph-based RAG, this paper discusses the limitations of flat chunking for documents with hierarchical structure. Veriducta's parent-child chunking scheme addresses the same limitation differently — by preserving the hierarchical structure in the Qdrant payload rather than a graph.

### The Chunking Problem
**Gao, Y., et al. (2024)**. Retrieval-Augmented Generation for Large Language Models: A Survey. *arXiv:2312.10997*.

Section 4.1 identifies chunking strategy as one of the most underexplored aspects of RAG systems. Most evaluations treat chunking as fixed. Veriducta treats it as an attributable variable.

---

## Evaluation

### RAGAS
**Es, S., et al. (2023)**. RAGAS: Automated Evaluation of Retrieval Augmented Generation. *arXiv:2309.15217*.

Establishes faithfulness, answer relevance, context precision, and context recall as the four primary RAG evaluation metrics. Veriducta computes these for baseline comparison but adds four additional metrics that RAGAS cannot compute.

### Causal Attribution in ML
**Peters, J.M., Janzing, D., & Schölkopf, B. (2017)**. *Elements of Causal Inference: Foundations and Learning Algorithms*. MIT Press.

The theoretical basis for counterfactual attribution. Veriducta's ablation approach is a form of structural causal model evaluation — fix one variable (inject gold inputs at a stage) and measure the effect on the output.

---

## Related Work

### LangSmith / Langfuse
Trace-level observability for LLM applications. Captures inputs and outputs at each pipeline stage. **Does not**: store retrieval scores, support counterfactual replay, compute quality deltas between stages, or provide causal attribution.

### Arize Phoenix
Provides UMAP-based embedding visualization and drift detection. Strong for data quality monitoring. **Does not**: support stage-level quality attribution or causal ablation.

### TruLens
Computes TruLens feedback functions (groundedness, context relevance, answer relevance). Closer in spirit to RAGAS. **Does not**: support causal attribution or replayable traces.

### DeepEval
Evaluation framework with multiple metrics including G-Eval and contextual recall. Metric-focused rather than trace-focused. **Does not**: store the retrieval state needed for counterfactual replay.

---

## Open Questions

1. **Does the quality approximation in Stages 1–3 diverge significantly from NLI-verified quality?** The current approximation (citation recall + ROUGE-L + entity coverage) is known to underperform NLI on adversarial examples. A comparative study would be valuable.

2. **Is 60 cases sufficient for the synthetic benchmark?** Statistical power for a 73.3% accuracy claim requires larger samples. A 200-case benchmark would tighten the confidence interval from ±12% to ±6%.

3. **Does boundary-aware chunking generalise beyond regulatory text?** Section boundary markers were tuned for OSHA/NIST/USGS documents. Medical, legal, and academic corpora have different structural conventions.

4. **Can the 3-class NLI heuristic thresholds be learned from data?** The current thresholds (entailment > 0.65, contradiction > 0.85) are calibrated on MultiNLI. Domain-specific calibration on regulatory text might improve attribution precision.
