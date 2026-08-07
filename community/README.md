# Veriducta - Community and Governance

This directory contains everything related to contributing, releasing, and maintaining the Veriducta project.

[Back to project root](../README.md)

---

## Contributing

| Document | Description |
|:---|:---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute - setup, branch strategy, commit style, PR requirements |
| [FIRST_CONTRIBUTION.md](FIRST_CONTRIBUTION.md) | Step-by-step guide for first-time contributors - what to expect, where to start |
| [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) | Curated list of beginner-friendly issues and small improvements |

---

## Release Process

| Document | Description |
|:---|:---|
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | How releases are cut, what triggers a release, the checklist |
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | Detailed release notes for v1.0.0 |

---

## Maintainers

| Document | Description |
|:---|:---|
| [MAINTAINER_GUIDE.md](MAINTAINER_GUIDE.md) | Responsibilities, review standards, merge criteria, on-call rotation |
| [REPOSITORY_METADATA.md](REPOSITORY_METADATA.md) | Repository settings, CI configuration, branch protection rules |

---

## Issue Workflow

1. Check [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) for recommended starting points.
2. Open a GitHub issue using the template in `.github/ISSUE_TEMPLATE/`.
3. Reference the issue in your PR using the pull request template in `.github/pull_request_template.md`.
4. CI must pass: `ruff`, `black`, `mypy --strict`, `pytest` (801 tests, 92.8% coverage minimum).

---

## Code of Conduct

This project follows the [Code of Conduct](../CODE_OF_CONDUCT.md) in the repository root.

---

## Security

Report vulnerabilities using the process described in [SECURITY.md](../SECURITY.md).
