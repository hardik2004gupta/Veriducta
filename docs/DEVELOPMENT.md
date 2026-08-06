# Development Setup

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker + Docker Compose
- Git

## Local Setup

```bash
# Clone the repository
git clone <repo-url>
cd veriducta

# Copy environment template
cp .env.example .env

# Install all dependencies (production + dev)
make install

# Start infrastructure services
make docker-up

# Verify the API is running
curl http://localhost:8080/api/v1/health
```

## Running Tests

```bash
make test          # Run full test suite with coverage
make coverage      # Generate HTML coverage report
```

## Code Quality

```bash
make lint          # Run Ruff linter
make format        # Auto-format with Ruff + Black
make type-check    # Run MyPy strict type checking
make pre-commit    # Run all pre-commit hooks
```

## Environment Variables

See `.env.example` for all available configuration options.
The `VERIDUCTA_ENV` variable switches between `development`, `testing`, and `production`.

## Infrastructure Services

| Service    | URL                          | Credentials         |
|------------|------------------------------|---------------------|
| FastAPI    | http://localhost:8080/docs   | —                   |
| Qdrant     | http://localhost:6333        | —                   |
| MinIO      | http://localhost:9001        | minioadmin/minioadmin |
| Prometheus | http://localhost:9090        | —                   |
| Grafana    | http://localhost:3000        | admin/admin         |
