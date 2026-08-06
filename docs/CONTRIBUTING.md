# Contributing

## Branch Strategy

- `main` — stable, CI must pass
- `phase/N-name` — one branch per build phase
- `feat/short-description` — feature branches off the current phase branch

## Commit Style

`type(scope): short description`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Pre-commit Hooks

All commits are checked by `pre-commit`. Install once with `make install`.

## Pull Request Requirements

- CI must pass (ruff, black, mypy, pytest)
- Coverage must not drop below the configured threshold
- Phase exit conditions from the spec must be met before merging a phase branch

## Phase Gate

Each phase has an explicit exit condition in the spec (`Veriducta MVP.pdf`).
The exit condition must be verified and documented in the PR description before the
phase branch is merged into `main`.
