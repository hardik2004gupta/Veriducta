# Veriducta

**RAG pipeline observability — causal root-cause attribution for answer failures.**

Veriducta is a technically rigorous proof of concept that answers one question no existing RAG observability tool can: given a failed answer, which pipeline stage caused the failure, and by how much?

> This repository is currently at **Phase 1** (ingestion pipeline). The document parsing, chunking, version graph, embedding, BM25 index, and Qdrant upsert are complete. Retrieval is not yet implemented.

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

# Run the API (development)
make run

# Run the test suite
make test
```

---

## Evaluation Scorecard

*Populated in Phase 18 after evaluation runs complete.*

---

## Known Limitations

*Documented in Phase 18.*

---

## Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and component relationships |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local development setup |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Contribution guidelines |
| [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Directory layout |
