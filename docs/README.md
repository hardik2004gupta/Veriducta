# Veriducta - Documentation

This directory contains all technical documentation for the Veriducta project.

[Back to project root](../README.md)

---

## Architecture

How the eight-layer pipeline is designed, what each layer owns, and why the dependency graph is enforced at the CI level.

| Document | Description |
|:---|:---|
| [ARCHITECTURE.md](architecture/ARCHITECTURE.md) | Eight-layer design, component contracts, Mermaid diagrams, dependency graph |
| [PROJECT_STRUCTURE.md](architecture/PROJECT_STRUCTURE.md) | Per-directory ownership, allowed and forbidden imports |
| [technical_decisions.md](architecture/technical_decisions.md) | 10 non-obvious engineering decisions with explicit tradeoffs |

---

## Engineering

How to develop against the codebase, what the hard problems are, and how they were solved.

| Document | Description |
|:---|:---|
| [DEVELOPMENT.md](engineering/DEVELOPMENT.md) | Local setup, Makefile targets, virtual environment, pre-commit hooks |
| [engineering_challenges.md](engineering/engineering_challenges.md) | Causal attribution, temporal filtering, circular import prevention, boundary-aware chunking |

---

## Deployment

How to take the project from local to production.

| Document | Description |
|:---|:---|
| [DEPLOYMENT.md](deployment/DEPLOYMENT.md) | Local, Docker Compose, Railway, Fly.io, Render, VM deployment guides |

---

## Research

Limitations, threats to validity, and open questions.

| Document | Description |
|:---|:---|
| [research_notes.md](research/research_notes.md) | Limitations, future research directions, threats to validity |

---

## Case Study

End-to-end narrative and performance data from the 18-phase build.

| Document | Description |
|:---|:---|
| [case_study.md](case-study/case_study.md) | Full build narrative - design evolution, lessons learned, what failed |
| [blog_post.md](case-study/blog_post.md) | Technical write-up for publication, including the OSHA PEL chunking failure case |
| [performance_analysis.md](case-study/performance_analysis.md) | Latency budget breakdown, memory profile, scaling strategies |

---

## Assets

| Directory | Contents |
|:---|:---|
| [assets/](assets/) | Hero image, logo variants, dashboard screenshot, GIF walkthrough, architecture and replay engine diagrams |
| [screenshots/](screenshots/) | SVG page-level screenshots (ask, dashboard, evaluation, replay, retrieval) |
| [Veriducta MVP.pdf](Veriducta%20MVP.pdf) | Original engineering specification - the authoritative source for all phase requirements |
