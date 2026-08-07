# Research — Threats to Validity

*Analysis of threats to internal and external validity for the Veriducta evaluation.*

---

## Internal Validity

### 1. Benchmark Construction Bias

**Threat**: The 60-case synthetic corruption benchmark was constructed by the same person who implemented the ablation engine. Corruption cases may unconsciously align with the ablation engine's assumptions about what constitutes a detectable failure.

**Manifestation**: A case that "should" detect a chunking failure but uses a corruption method that the Stage 1 ablation isn't designed to catch might be excluded during benchmark design, inflating Stage 1 accuracy.

**Mitigation**: Each corruption case specifies a mechanistic corruption method (e.g., "replace correct chunk with lexically similar incorrect chunk"), not just a failure mode. The corruption methods were specified in the project spec before implementation began. Attribution accuracy was measured post-hoc against ground-truth labels.

**Remaining concern**: The realistic boundary-error subset (15 cases) was drawn from the actual corpus, which may have selection bias toward cases where boundary-aware chunking visibly differs from boundary-naive chunking. The truly hard cases may be systematically excluded.

---

### 2. Attribution Threshold Selection

**Threat**: The attribution thresholds (τ₁=0.15, τ₂=0.15, τ₃=0.15, τ₄=0.10) were calibrated to meet the ≥70% overall and ≥65% boundary-error targets. Different thresholds could produce different accuracy numbers.

**Manifestation**: If thresholds were selected by grid search over the 60-case benchmark, the reported accuracy is an in-sample metric, not a generalization estimate.

**Mitigation**: The thresholds were chosen based on the quality delta distribution from the first complete evaluation run, not by optimizing against the benchmark labels. A threshold of 0.15 represents approximately 1.5× the noise floor observed in Stage 4 ablation.

**Remaining concern**: The thresholds should be validated on a held-out test set not used during calibration. This was not done; the 60-case benchmark served as both calibration and evaluation.

---

### 3. Quality Metric Definition

**Threat**: The "quality score" used to measure attribution deltas (composite of Recall@5 and NLI entailment rate) may not capture all dimensions of answer quality. Low-quality answers might score well on both Recall@5 and NLI entailment while being operationally incorrect.

**Manifestation**: Stage 2 ablation computes quality delta by comparing quality_gold vs. quality_original. If both use the same composite metric, a failure mode that neither metric captures will produce a near-zero delta and be misattributed.

**Mitigation**: The gold QA dataset annotations include human quality judgments used for final validation. The composite metric was calibrated against human judgments on the 40-question gold QA dataset (Pearson r = 0.74, p < 0.001).

**Remaining concern**: Pearson r = 0.74 indicates meaningful correlation, not identity. Quality metric limitations may explain some of the 26.7% overall misclassification.

---

### 4. NLI Threshold Calibration

**Threat**: The NLI thresholds (entailment > 0.65, contradiction > 0.85) were calibrated on 120 hand-labeled claim-context pairs from the corpus. If the calibration set is not representative of the evaluation set, the verification metrics may be biased.

**Manifestation**: Claim verification accuracy (contradiction acknowledgment rate = 91.7%) may be inflated if the calibration and evaluation sets overlap or share the same distribution.

**Mitigation**: The 120 calibration pairs were drawn uniformly from the corpus across document types. The evaluation set (40-question gold QA) is drawn from the same corpus but at the question level, not the claim level.

**Remaining concern**: No formal train/test split was enforced for the NLI calibration. Contamination is possible if some calibration claims appeared in gold QA answers.

---

## External Validity

### 5. Corpus Specificity

**Threat**: All results are from a 30–50 document corpus of public engineering and regulatory documents (OSHA, NIST, USGS). This corpus has distinctive properties: precise technical terminology, section-structured layout, numeric thresholds, and temporal supersession relationships.

**Manifestation**: Chunking boundary detection relies on regulatory document conventions (section numbers, "Employer must" clauses, table headers). These patterns do not generalize to conversational corpora, academic papers, or code documentation.

**Mitigation**: The corpus choice is documented; results are presented for this corpus only. No claims are made about generalization.

**Remaining concern**: The 73.3% attribution accuracy is frequently cited in the README and blog post without adequate caveats about corpus specificity. External readers may generalize it incorrectly.

---

### 6. Synthetic vs. Real Corruptions

**Threat**: The corruption benchmark uses synthetic corruptions — mechanistically applied transformations. Real production failures may be qualitatively different from synthetic corruptions: the corruption distribution may not match the natural failure distribution.

**Manifestation**: The benchmark includes forced top-1 ranking for reranker corruption. In production, reranker errors are subtler — score compression near the cutoff boundary, not forced rank inversions. The synthetic version may be easier for Stage 3 to detect than real reranker failures.

**Mitigation**: The benchmark includes a "realistic boundary-error" flag to distinguish natural-distribution cases (drawn from real corpus documents) from artificially extreme corruptions. The boundary-error accuracy (68.8%) is presented separately.

**Remaining concern**: Only the chunking category has a "realistic" subset. Realistic retrieval, reranker, and generation corruption cases are not formally defined.

---

### 7. Single Developer / Single Design

**Threat**: Veriducta was designed and evaluated by a single developer. The design, corruption cases, and attribution thresholds all reflect one person's assumptions about what RAG failures look like.

**Manifestation**: Blind spots in the evaluation design may systematically favor the implemented approach. A failure mode that the single developer didn't consider won't appear in the benchmark.

**Mitigation**: The project spec (CLAUDE.md) was written before implementation began and defines success criteria that are independent of implementation approach. The spec was not modified during implementation.

**Remaining concern**: This is a genuine limitation that applies to any single-developer research project. Third-party replication on a different corpus with independently designed corruption cases would significantly strengthen the validity of the reported results.

---

## Summary Table

| Threat | Type | Severity | Mitigation Status |
|---|---|---|---|
| Benchmark construction bias | Internal | Medium | Partial |
| Attribution threshold selection | Internal | High | Partial |
| Quality metric definition | Internal | Medium | Addressed |
| NLI calibration contamination | Internal | Low | Unverified |
| Corpus specificity | External | High | Acknowledged |
| Synthetic vs. real corruptions | External | High | Partial |
| Single-developer design | External | Medium | Acknowledged |
