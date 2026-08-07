# Release Process

*Step-by-step guide for tagging and publishing a Veriducta release.*

---

## Versioning

Veriducta follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (`2.0.0`): Breaking API or schema changes
- **MINOR** (`1.1.0`): New features, backward-compatible
- **PATCH** (`1.0.1`): Bug fixes, no new features

Current version is in `VERSION` (single line: `1.0.0`).

---

## Pre-Release Checklist

Complete all items before tagging:

### Code

- [ ] All CI checks pass on `main`: ruff, black, mypy, pytest
- [ ] Coverage ≥ 80%
- [ ] No uncommitted changes on `main`
- [ ] `make test` output: `X passed, Y failed` — Y must be 0
- [ ] All blocking regression gate conditions pass

### Documentation

- [ ] `CHANGELOG.md` updated with the new version section
  - Move items from `[Unreleased]` to the new version
  - Add release date
  - Add evaluation metrics if changed
- [ ] `RELEASE_NOTES.md` updated for the new version
  - Clear headline of what's new
  - Known limitations updated
  - Installation steps verified
- [ ] `ROADMAP.md` updated — completed items checked off, new planned items added
- [ ] `VERSION` updated to the new version number
- [ ] `README.md` version badge and evaluation numbers reflect current state

### Architecture (for minor/major releases)

- [ ] `docs/ARCHITECTURE.md` Mermaid diagrams are accurate
- [ ] `CLAUDE.md` reflects any architecture changes
- [ ] New external dependencies documented in README and DEPLOYMENT.md

---

## Release Steps

### 1. Update version files

```bash
# Update VERSION
echo "1.1.0" > VERSION

# Update CHANGELOG.md — move [Unreleased] to [1.1.0] with today's date
# Update RELEASE_NOTES.md
```

### 2. Commit the release

```bash
git add VERSION CHANGELOG.md RELEASE_NOTES.md ROADMAP.md README.md
git commit -m "chore(release): v1.1.0"
git push origin main
```

### 3. Wait for CI

Verify the CI run on the release commit passes all checks before tagging.

### 4. Tag the release

```bash
git tag -a v1.1.0 -m "Release v1.1.0 — [one-line summary of what's new]"
git push origin v1.1.0
```

### 5. Create GitHub release

```bash
gh release create v1.1.0 \
  --title "v1.1.0 — [Short headline]" \
  --notes-file RELEASE_NOTES.md
```

Or create via GitHub UI: Releases → Draft a new release → Tag: v1.1.0.

### 6. Post-release

- [ ] Update the GitHub repository description if the tagline changed
- [ ] Post LinkedIn announcement (see `linkedin/announcement.md`)
- [ ] Close resolved GitHub issues and milestones

---

## Hotfix Release (patch)

For urgent bug fixes that can't wait for the next minor release:

```bash
# Branch from the tag, not main
git checkout -b fix/critical-bug v1.0.0
# ... make fix ...
git commit -m "fix(component): description"
git push origin fix/critical-bug

# After review and merge to main:
echo "1.0.1" > VERSION
# Update CHANGELOG with the patch
git commit -m "chore(release): v1.0.1"
git tag -a v1.0.1 -m "Release v1.0.1 — [fix description]"
git push origin main v1.0.1
gh release create v1.0.1 --title "v1.0.1 — [Fix description]" --notes "[Brief fix description]"
```

---

## Phase Tagging (development milestones)

After completing each implementation phase, tag the commit:

```bash
git tag phase-{N}-complete
git push origin phase-{N}-complete
```

Phase tags are lightweight (no annotation needed) and are used for development tracking, not for distribution.

---

## Release Cadence

| Type | Frequency |
|---|---|
| Patch releases | As needed for bugs |
| Minor releases | Every 4–8 weeks |
| Major releases | When breaking changes accumulate |

The `ROADMAP.md` has planned v1.1 and v1.2 scopes. Releases ship when the planned scope is complete, not on a fixed calendar.
