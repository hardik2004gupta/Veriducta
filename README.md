# Veriducta

**RAG pipeline observability — causal root-cause attribution for answer failures.**

Veriducta is a technically rigorous proof of concept that answers one question no existing RAG observability tool can: given a failed answer, which pipeline stage caused the failure, and by how much?

> This repository is currently at **Phase 7** (evaluation framework). All pipeline phases are implemented: ingestion, retrieval, generation, verification, causal replay, and evaluation harness with CI regression gate.

---

## What Veriducta Solves

1. **Invisible chunking failures** — boundary-naive chunking splits critical clauses silently; standard faithfulness scores miss it.
2. **Unattributed retrieval misses** — without per-stage traces, a bad answer cannot be separated from a retrieval miss vs. a generation failure.
3. **Temporal validity drift** — superseded documents pollute retrieval; no standard metric tracks this.

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the five-layer architecture diagram.

---

## Quick Start

```bash
# Install dependencies
make install

# Start all infrastructure
make docker-up

# Ingest the document corpus
python scripts/ingest_corpus.py

# Run the API (development)
make run

# Run the full evaluation benchmark
python scripts/run_benchmark.py

# Check regression against a baseline
python scripts/regression_check.py ci_baseline.json evaluation_reports/latest.json

# Compare two evaluation runs
python scripts/compare_runs.py run_a.json run_b.json

# Run the test suite
make test
```

---

## Evaluation Scorecard

The evaluation harness measures four metric groups across the full 40-question golden QA set and 60-case corruption benchmark. Actual numbers populate after a complete pipeline run against the real corpus.

| Metric Group | Key Metrics |
|---|---|
| **Retrieval** | Recall@5, Recall@10, MRR, nDCG@10, temporal-valid retrieval rate |
| **Answer Quality** | Citation entailment rate (faithfulness), omission rate, contradiction acknowledgment rate |
| **Causal Attribution** | Root-cause localization accuracy (target ≥ 0.70), realistic boundary-error accuracy (target ≥ 0.65) |
| **Operational** | p50/p95/p99 latency, mean cost per query |

Four metrics computed by Veriducta that RAGAS cannot:
1. **Omission rate** — fraction of gold supporting chunks not cited
2. **Causal attribution accuracy** — ablation-based root-cause correctness
3. **Temporal-valid retrieval rate** — fraction of retrieved chunks with valid effective dates
4. **Contradiction acknowledgment rate** — claims flagged for expert review when evidence contradicts

---

## CI Regression Gate

Five blocking conditions checked on every CI run:

1. Faithfulness (citation entailment rate) drops > 2% from baseline
2. Recall@5 drops > 3% from baseline
3. p95 latency increases > 20% from baseline
4. Root-cause localization accuracy drops > 5% from baseline
5. Unauthorised evidence exposure rate > 0%

---

## Known Limitations

- MVP runs in single-worker mode; ML models (BGE-large, cross-encoder NLI, reranker) load on CPU (~2 GB combined).
- RAGAS integration is optional — gracefully skipped when the `ragas` package is not installed.
- No authentication; evidence logs must not be exposed over HTTP without access control.
- Corpus limited to 30–50 public-domain documents (USGS, NIST, OSHA).

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and component relationships |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local development setup |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Contribution guidelines |
| [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Directory layout |
