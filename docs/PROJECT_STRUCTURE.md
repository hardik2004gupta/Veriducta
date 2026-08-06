# Project Structure

```
veriducta/
├── api/                      # FastAPI application factory, routes, middleware, DI
│   └── routes/               # Route modules (health, future: query, ingest)
├── config/                   # Pydantic Settings — typed, environment-aware config
├── core/                     # Domain core: exceptions, abstract interfaces, logging
├── storage/                  # Storage backend abstractions (Qdrant, MinIO)
├── schemas/                  # Shared Pydantic models: Document, Chunk, Claim, Trace…
├── models/                   # ML model wrappers (embedding, NLI — Phase 1+)
├── utils/                    # Stateless utilities: hashing, IDs, timers, filesystem…
│
├── ingestion/                # Phases 1–6: sidecar, parser, chunker, version graph, embedder, ingestor
├── retrieval/                # Phases 7–10: BM25, dense, RRF, temporal filter, reranker, expander
├── generation/               # Phases 11–13: generator, entailment, counterevidence, verifier
├── verification/             # Phases 11–13: claim verification orchestration
├── replay/                   # Phase 17: ablation engine, heuristic attribution, corruption runner
├── evaluation/               # Phase 18: runner, metrics computation, RAGAS baseline, report writer
│
├── observability/            # Prometheus metrics, OpenTelemetry tracing, evidence log
├── scripts/                  # CLI entry points: ingest_corpus.py, check_regression…
├── tests/                    # pytest test suite
│
├── docker/                   # Docker support files: otel config, prometheus, grafana
├── docs/                     # Skeleton documentation
├── .github/workflows/        # GitHub Actions CI
│
├── pyproject.toml            # Project metadata, deps, tool config (ruff/black/mypy)
├── .env.example              # Environment variable template
├── Dockerfile                # Production container image
├── docker-compose.yml        # Full local stack (API, Qdrant, MinIO, OTEL, Prometheus, Grafana)
├── Makefile                  # Developer shortcuts
└── README.md
```

## Package Dependency Rules

- `schemas/` and `utils/` have **no dependencies** on other application packages.
- `core/` depends only on `config/`.
- All pipeline packages (`ingestion/`, `retrieval/`, etc.) depend on `core/`, `schemas/`, `utils/`.
- `api/` depends on `config/`, `core/`, and the pipeline packages for DI wiring.
- Circular imports are **not permitted**.
