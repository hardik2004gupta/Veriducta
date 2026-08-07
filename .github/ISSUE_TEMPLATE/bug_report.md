---
name: Bug report
about: Something is broken or producing incorrect results
title: "[BUG] "
labels: bug
assignees: ''
---

## Description

A clear description of what is broken and what the expected behaviour is.

## Pipeline Stage

Which stage is affected?

- [ ] Ingestion (parsing, chunking, embedding, Qdrant upsert)
- [ ] Retrieval (BM25, dense, RRF, temporal filter, reranker)
- [ ] Generation (LLM call, schema validation, token logging)
- [ ] Verification (NLI entailment, counterevidence scan)
- [ ] Causal Replay (ablation engine, corruption runner)
- [ ] Evaluation (metrics, regression gate, RAGAS baseline)
- [ ] API (routing, middleware, error handling)
- [ ] Frontend (dashboard, charts, evidence explorer)
- [ ] Other / unknown

## Steps to Reproduce

1. ...
2. ...
3. ...

## Expected Behaviour

What should happen.

## Actual Behaviour

What actually happens.

## Environment

- OS:
- Python version:
- `pip show veriducta` output:
- `VERIDUCTA_ENV`:

## Logs

```
# Paste relevant log output here (structlog JSON lines or console output)
# Remove any sensitive data before pasting
```

## Trace ID (if applicable)

If the bug is related to a specific query, include the `trace_id` from the response or evidence log.

```
trace_id:
```
