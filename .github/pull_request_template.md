## Summary

<!-- 2–3 sentences describing what this PR does and why -->

## Phase / Task

<!-- Which phase from the roadmap does this implement or fix? -->
Phase: 

## Changes

<!-- List the files changed and what changed in each -->
- `path/to/file.py` — description

## Testing

- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes (or `make format` was run)
- [ ] `mypy .` passes (`--strict`)
- [ ] `pytest` passes (all tests green, coverage ≥ 80%)
- [ ] New behaviour has corresponding tests

## Regression Gate

<!-- For phases 7+ only -->
- [ ] `python scripts/check_regression_gate.py` passes (or N/A for pre-eval phases)

## Interface Contracts

<!-- Did any abstract interface in core/interfaces.py change? If yes: -->
- [ ] No interface changes
- [ ] Interface changed — all concrete implementations updated

## Schema Changes

<!-- Did schemas/models.py change? -->
- [ ] No schema changes
- [ ] Fields added (backwards compatible)
- [ ] Fields renamed/removed — migration documented

## Notes for Reviewer

<!-- Anything non-obvious the reviewer should know -->
