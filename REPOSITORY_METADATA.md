# Repository Metadata

*Content for GitHub repository settings, social preview, and discovery.*

---

## GitHub Repository Description

```
RAG pipeline observability tool that identifies which stage (chunking, retrieval, reranking, or generation) caused an answer failure. Four-stage causal ablation engine. 73.3% attribution accuracy on 60-case benchmark.
```

*Keep under 350 characters for GitHub.*

---

## Short Tagline

```
Find out WHY your RAG pipeline failed, not just that it did.
```

---

## GitHub Topics

```
rag
retrieval-augmented-generation
llm
observability
causal-attribution
nlp
python
fastapi
qdrant
opentelemetry
evaluation
benchmarking
machine-learning
```

*Add as GitHub topics for discoverability.*

---

## OpenGraph / Social Preview Text

**Title**: Veriducta — RAG Pipeline Attribution

**Description**:
```
Given a failed RAG answer, which pipeline stage caused it?
Chunking • Retrieval • Reranking • Generation
Four-stage causal ablation engine. 73.3% accuracy. Open source.
```

**Visual**: Architecture diagram or dashboard screenshot. File: `docs/screenshots/social-preview.png` (1280×640px)

---

## README Badges

```markdown
[![CI](https://github.com/hardik2004gupta/Veriducta/actions/workflows/ci.yml/badge.svg)](https://github.com/hardik2004gupta/Veriducta/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-92.81%25-brightgreen)](https://github.com/hardik2004gupta/Veriducta)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![mypy](https://img.shields.io/badge/mypy-strict-blue)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
```

---

## GitHub Release — v1.0.0

**Release title**: `v1.0.0 — Initial Release`

**Release tag**: `v1.0.0`

**Release description**:

```markdown
## Veriducta v1.0.0

First public release of Veriducta — a RAG pipeline observability tool that identifies which 
pipeline stage (chunking, retrieval, reranking, or generation) caused an answer failure.

### Highlights

- **73.3% root-cause localization accuracy** on 60-case synthetic corruption benchmark
- **Four metrics RAGAS cannot compute**: omission rate, causal attribution accuracy, 
  temporal-valid retrieval rate, contradiction acknowledgment rate
- **Four-stage causal ablation engine** with replayable evidence traces
- **O(1) evidence log lookup** via SQLite byte-offset indexing
- **801 tests, 92.81% coverage**, mypy --strict
- **Next.js 15 observability dashboard**

### Installation

```bash
git clone https://github.com/hardik2004gupta/Veriducta.git
cd veriducta
uv pip install --system ".[dev]"
cp .env.example .env  # set ANTHROPIC_API_KEY
docker compose up -d qdrant minio
python scripts/ingest_corpus.py
make run
```

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for the full changelog.
```

---

## HuggingFace Spaces Description

**Space name**: `hardik2004gupta/Veriducta`

**Space description**:
```
Veriducta demo: ask a question about OSHA/NIST engineering standards and see which pipeline 
stage (chunking, retrieval, reranking, or generation) was responsible if the answer is 
incomplete. Causal attribution via four-stage ablation engine.
```

**Tags**: `rag`, `llm`, `observability`, `retrieval`, `python`

---

## Papers With Code Entry

**Title**: Veriducta: Stage-Level Causal Attribution for RAG Pipeline Failures

**Tasks**: Information Retrieval, Question Answering, RAG Evaluation

**Methods**:
- Reciprocal Rank Fusion (Retrieval)
- Boundary-Aware Chunking (Document Processing)
- Cross-Encoder Reranking (Re-ranking)
- NLI Entailment Verification (Fact Verification)
- Causal Ablation (Evaluation)

**Datasets**: Synthetic corruption benchmark (60 cases), Golden QA dataset (40 questions)
