# Security Policy

## Scope

Veriducta is an MVP / portfolio project. It is not deployed in production environments handling sensitive data. The scope of this security policy is limited accordingly.

## Secrets

- `ANTHROPIC_API_KEY` is the only secret in the codebase.
- It must never be committed to the repository.
- It must never appear in log output, error messages, or API responses.
- Store it in `.env` locally (which is git-ignored) or in GitHub Secrets for CI.

## Known Security Limitations

1. **No authentication** — The API has no auth layer. The MVP assumes a trusted local network environment. Do not expose the API publicly without adding authentication.

2. **Evidence log exposure** — Evidence logs contain query text. The API does not expose evidence logs over HTTP. If this changes, access control must be added first.

3. **CORS** — Default CORS setting is `"*"` for development. Production deployments must set `API_CORS_ORIGINS` to specific allowed origins.

4. **BM25 index pickle** — The BM25 index is serialised as `corpus/bm25_index.pkl`. Pickle files can execute arbitrary code if tampered with. The file is internal and never received from external sources, but ensure the file path is not writable by untrusted processes.

5. **Input validation** — All user-facing inputs (query text, query_date) are validated via Pydantic before entering the pipeline. Max query length is 2000 characters.

## Reporting

This is a personal portfolio project with no production deployment. If you discover a significant vulnerability in the code:

1. Open a GitHub issue with the label `security`.
2. If the issue involves sensitive information, email `nikunjhardik2006@gmail.com` directly.

There is no formal security response SLA for this project.
