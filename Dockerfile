FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------------------------------------------------------------------------
# Dependency layer (cached unless pyproject.toml changes)
# ---------------------------------------------------------------------------
FROM base AS deps

RUN pip install uv==0.5.1

COPY pyproject.toml ./

RUN uv pip install --system --no-cache .

# ---------------------------------------------------------------------------
# Final image
# ---------------------------------------------------------------------------
FROM base AS final

COPY --from=deps /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=deps /usr/local/bin /usr/local/bin

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/api/v1/health').raise_for_status()"

CMD ["python", "-m", "api.app"]
