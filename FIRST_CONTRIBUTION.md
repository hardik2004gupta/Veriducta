# Making Your First Contribution to Veriducta

Welcome! This guide gets you from zero to a merged pull request as efficiently as possible.

---

## Prerequisites

You'll need:
- Python 3.12+
- Docker and Docker Compose v2
- Node.js 20+ (for frontend contributions)
- An Anthropic API key (for end-to-end tests only; most contributions don't need one)

---

## Setup (10 minutes)

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/veriducta.git
cd veriducta

# 2. Install dependencies
uv pip install --system ".[dev]"

# 3. Start infrastructure (Qdrant is required for integration tests)
docker compose up -d qdrant minio

# 4. Run the test suite to verify everything works
make test
# Expected: 801 passed, 1 skipped

# 5. Run the quality checks
make lint && make type-check
```

If all checks pass, you're ready to contribute.

---

## Finding Something to Work On

### Good first issues

The `GOOD_FIRST_ISSUES.md` file lists pre-analyzed tasks that are well-scoped for first-time contributors. Each issue includes the file to edit, the expected change, and a test to add.

### Labels on GitHub

- `good first issue` - well-scoped, bounded changes
- `documentation` - doc improvements, no code required
- `tests` - adding missing test coverage
- `frontend` - Next.js/TypeScript frontend changes (no backend required)

---

## Making a Change

### 1. Create a branch

```bash
git checkout -b feat/your-feature-name
# or: fix/your-bugfix-name
```

### 2. Make your change

Read the relevant section of `CLAUDE.md` before touching any file. The document describes the architecture, coding standards, and import rules that every change must follow.

Key rules:
- No `print()` - use `structlog`
- No circular imports - check the dependency graph in Section 6 of CLAUDE.md
- All public functions need docstrings
- Type hints required everywhere (mypy --strict)

### 3. Add a test

Every new behavior needs a test. Test naming convention:
```python
def test_{what}_{condition}_{expected_outcome}():
```

### 4. Run all checks

```bash
make format       # ruff format + black
make lint         # ruff check
make type-check   # mypy --strict
make test         # pytest
```

All four must pass before submitting.

---

## Submitting a Pull Request

### PR title format

```
type(scope): short description in imperative mood
```

Examples:
- `feat(chunker): add sentence boundary detection for academic papers`
- `fix(retrieval): handle empty BM25 result set on sparse queries`
- `test(replay): add Stage 3 ablation test for reranker score inversion`
- `docs(api): add example curl commands to health endpoint docs`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

### PR checklist

- [ ] All four checks pass (`make lint && make format && make type-check && make test`)
- [ ] New public functions have docstrings
- [ ] New behavior has a test
- [ ] No new circular imports
- [ ] No `print()` statements added

### What to expect

- Initial response within 48 hours
- Review feedback is specific: a change request will name the exact line and the exact issue
- Once approved, maintainer will squash-merge

---

## Frontend Contributions

Frontend contributions don't require an Anthropic API key or a running backend. The frontend has a full mock data layer.

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
npx tsc --noEmit     # type check
npm run lint         # ESLint
npm run build        # verify build succeeds
```

The mock data is in `frontend/lib/mock-data.ts`. All pages use this by default.

---

## Getting Help

- Open a GitHub Discussion for questions about design or direction
- Open a GitHub Issue for bugs or well-specified feature requests
- For quick questions: comment on the relevant issue or PR

If you're unsure whether a change is in scope, open an issue first and describe what you want to do. A brief "yes, that fits" or "here's a better approach" saves time for everyone.

---

## Contribution License

By submitting a pull request, you agree that your contribution is licensed under the MIT License (the same license as the project). You represent that you have the right to license the contribution.
