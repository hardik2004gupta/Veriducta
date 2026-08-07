# Maintainer Guide

*For current and future maintainers of the Veriducta repository.*

---

## Responsibilities

As a maintainer you are responsible for:
1. Reviewing pull requests within 48 hours of submission
2. Keeping CI green on the `main` branch
3. Tagging releases following the release process in `RELEASE_PROCESS.md`
4. Triaging issues (label, prioritize, respond within 1 week)
5. Keeping `CLAUDE.md` up to date when architecture changes

---

## Pull Request Review Checklist

Before approving a PR, verify:

**Code quality**:
- [ ] `make lint` passes (ruff)
- [ ] `make format` passes (ruff format + black)
- [ ] `make type-check` passes (mypy --strict)
- [ ] `make test` passes with no new failures
- [ ] Coverage does not drop below 80%

**Architecture**:
- [ ] No new imports violate the dependency graph (Section 6 of CLAUDE.md)
- [ ] No new circular imports
- [ ] New modules have module-level docstrings
- [ ] New public functions have Google-style docstrings
- [ ] No `print()` statements

**Test quality**:
- [ ] New behavior has at least one test
- [ ] Test follows naming convention: `test_{what}_{condition}_{expected_outcome}`
- [ ] No `try/except` in tests
- [ ] No mocking of Qdrant in integration tests

**Safety**:
- [ ] No secrets or API keys in code
- [ ] No hardcoded file paths (use `project_root()`)
- [ ] No mutation of `Settings` or `ConfigurationSnapshot` after creation

---

## Merging Strategy

- **Squash merge** for feature branches (keeps `main` history linear)
- **Merge commit** for hotfix branches (preserves incident context)
- Never rebase public branches after they've been shared

**Squash message format**:
```
type(scope): short description (#PR_NUMBER)

Optional body paragraph if the change needs explanation.
```

---

## Issue Triage

### Labels to apply

| Label | When |
|---|---|
| `bug` | Confirmed incorrect behavior |
| `enhancement` | New feature or improvement |
| `documentation` | Doc-only changes |
| `good first issue` | Well-scoped, bounded, has a clear solution |
| `help wanted` | Valid issue, maintainer won't prioritize immediately |
| `wontfix` | Out of scope or invalid |
| `question` | Needs clarification before triaging |
| `blocked` | Waiting on external dependency |

### Response templates

**Bug confirmed**:
```
Thanks for the report. Confirmed — [brief description of what's happening and why].
Labeling as `bug`. [If fix is straightforward: "PR welcome — see FIRST_CONTRIBUTION.md"]. 
[If complex: "This is on the roadmap for v1.x."]
```

**Feature request in scope**:
```
Good idea. This fits the roadmap direction for v1.x. 
Labeling as `enhancement` + `help wanted`. 
If you'd like to implement this, see FIRST_CONTRIBUTION.md and GOOD_FIRST_ISSUES.md for the PR process.
```

**Feature request out of scope**:
```
Thanks for the suggestion. This is outside the v1.x scope — [brief reason].
It may be a good fit for the community to explore independently.
Closing as `wontfix`.
```

---

## Keeping CI Green

If CI fails on `main` after a merge:

1. Create a `fix/ci-{description}` branch immediately
2. Fix the failure without adding unrelated changes
3. PR against `main` with high priority
4. If the fix takes > 1 hour, pin the last green commit in the README status badge

Common CI failures:
- **ruff format**: run `make format` locally before pushing
- **mypy**: new third-party library added without a type stub — add `ignore_missing_imports = true` under `[[tool.mypy.overrides]]` in `pyproject.toml`
- **pytest**: Qdrant connection timeout — the CI starts Qdrant via Docker service; check `docker-compose.ci.yml` if timeouts increase

---

## Dependency Updates

Update dependencies monthly:

```bash
uv pip compile pyproject.toml -o requirements.txt  # if using lockfile
# or: uv pip install --upgrade ".[dev]"
make test  # verify nothing broke
```

For major version bumps (e.g., Pydantic v2 → v3, FastAPI v0 → v1), create a `chore/upgrade-{package}` branch and do a full review before merging.

---

## Security Vulnerability Reports

If a security report comes in:
1. Do not publicly comment on the issue before a fix is ready
2. Respond privately via the SECURITY.md contact
3. Create a fix on a private fork if possible
4. Coordinate a disclosure timeline with the reporter (typically 90 days)
5. Tag a patch release the day of public disclosure

---

## Tagging a Release

See `RELEASE_PROCESS.md` for the complete release checklist. The short version:

```bash
git tag -a v1.x.y -m "Release v1.x.y"
git push origin v1.x.y
gh release create v1.x.y --title "v1.x.y" --notes-file RELEASE_NOTES.md
```

Update `VERSION` and `CHANGELOG.md` before tagging.
