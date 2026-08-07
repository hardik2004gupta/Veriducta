# Veriducta — Deployment Guide

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | pyenv or system |
| uv | latest | Fast pip replacement |
| Docker | 24.0+ | For infrastructure services |
| Docker Compose | v2.20+ | Bundled with Docker Desktop |
| Node.js | 20+ | For frontend |
| npm | 10+ | Bundled with Node.js |

---

## 1. Local Development

### 1.1 Clone and install

```bash
git clone https://github.com/hardik-gupta/veriducta.git
cd veriducta

# Install Python dependencies
uv pip install --system ".[dev]"

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 1.2 Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

All other values have working defaults for local development.

### 1.3 Start infrastructure

```bash
docker compose up -d qdrant minio otel-collector prometheus grafana
```

Service URLs after startup:
- Qdrant: http://localhost:6333 (UI: http://localhost:6333/dashboard)
- MinIO: http://localhost:9001 (admin/minioadmin)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin/admin)

### 1.4 Ingest corpus

```bash
# Validate sidecars first
python scripts/validate_sidecars.py

# Run full ingestion
python scripts/ingest_corpus.py
```

Expected output: `Ingestion complete. N chunks indexed in Qdrant, BM25 index saved.`

### 1.5 Start API

```bash
make run
# or: uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8080 --reload
```

API: http://localhost:8080
Docs: http://localhost:8080/docs

### 1.6 Start frontend

```bash
cd frontend && npm run dev
```

Dashboard: http://localhost:3000

---

## 2. Docker Compose (Full Stack)

The full `docker compose up` starts all services including the API:

```bash
docker compose up -d
```

Services:
| Service | Internal Port | Host Port |
|---|---|---|
| API (FastAPI) | 8080 | 8080 |
| Qdrant | 6333/6334 | 6333/6334 |
| MinIO | 9000/9001 | 9000/9001 |
| OTel Collector | 4317/4318 | 4317/4318 |
| Prometheus | 9090 | 9090 |
| Grafana | 3000 | 3001 |

### Docker Compose environment overrides

Create a `docker-compose.override.yml` for environment-specific settings:

```yaml
services:
  api:
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      VERIDUCTA__QDRANT__HOST: qdrant
      VERIDUCTA__MINIO__HOST: minio
      VERIDUCTA_ENV: production
```

### Run benchmark after startup

```bash
docker compose exec api python scripts/run_benchmark.py
```

---

## 3. Production VM Deployment

### 3.1 Requirements

- Ubuntu 22.04 LTS (or equivalent)
- 8 GB RAM minimum (ML models: ~1.93 GB; OS + headroom: ~6 GB)
- 4 vCPU (CPU-bound inference)
- 50 GB disk (corpus, models, evidence logs)

### 3.2 Install dependencies

```bash
# System packages
sudo apt-get update && sudo apt-get install -y \
  python3.12 python3.12-dev git curl docker.io docker-compose-plugin

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 3.3 Clone and configure

```bash
git clone https://github.com/hardik-gupta/veriducta.git
cd veriducta
uv pip install --system "."
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and production values
```

### 3.4 Systemd service (API)

Create `/etc/systemd/system/veriducta-api.service`:

```ini
[Unit]
Description=Veriducta FastAPI
After=network.target docker.service
Requires=docker.service

[Service]
Type=exec
WorkingDirectory=/home/ubuntu/veriducta
ExecStart=/usr/local/bin/uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8080 --workers 1
Restart=on-failure
EnvironmentFile=/home/ubuntu/veriducta/.env
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable veriducta-api
sudo systemctl start veriducta-api
```

### 3.5 Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name your.domain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
    }
}
```

### 3.6 Build and serve frontend

```bash
cd frontend
npm run build
npm start  # or serve with a process manager
```

---

## 4. Vercel + Railway (Cloud)

### Frontend on Vercel

1. Push repo to GitHub
2. Connect repo to Vercel at vercel.com/new
3. Set root directory: `frontend`
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-railway-app.up.railway.app`
5. Deploy

### API on Railway

1. Connect repo to Railway at railway.app/new
2. Set root directory: `.` (repo root)
3. Set build command: `uv pip install --system "."`
4. Set start command: `uvicorn api.app:create_app --factory --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `ANTHROPIC_API_KEY`
   - `VERIDUCTA__QDRANT__HOST` (Railway Qdrant service hostname)
   - `VERIDUCTA__QDRANT__PORT`
   - `VERIDUCTA_ENV=production`
6. Add Railway Qdrant service (Plugin: qdrant)
7. Add Railway MinIO service or use external MinIO

---

## 5. Fly.io

### API

```toml
# fly.toml
app = "veriducta-api"
primary_region = "ord"

[build]
  dockerfile = "docker/Dockerfile.api"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 4096
```

```bash
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy
```

**Note**: CPU-heavy models (embedding, reranker) will be slow on shared CPU. Use `performance` CPU kind for production.

---

## 6. Render

### API service

- **Runtime**: Python
- **Build command**: `uv pip install --system "."`
- **Start command**: `uvicorn api.app:create_app --factory --host 0.0.0.0 --port $PORT`
- **Environment**: Add all variables from `.env.example`
- **Plan**: Standard (2 GB RAM minimum; 4 GB recommended)

### Static site (frontend)

- **Build command**: `cd frontend && npm install && npm run build`
- **Publish directory**: `frontend/out`
- Add `output: 'export'` to `frontend/next.config.ts` for static export

---

## 7. Production Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Claude API key |
| `VERIDUCTA_ENV` | No | `development` | Set to `production` |
| `VERIDUCTA__QDRANT__HOST` | No | `localhost` | Qdrant hostname |
| `VERIDUCTA__QDRANT__PORT` | No | `6333` | Qdrant port |
| `VERIDUCTA__MINIO__HOST` | No | `localhost` | MinIO hostname |
| `VERIDUCTA__MINIO__PORT` | No | `9000` | MinIO port |
| `VERIDUCTA__MINIO__ACCESS_KEY` | No | `minioadmin` | MinIO access key |
| `VERIDUCTA__MINIO__SECRET_KEY` | No | `minioadmin` | MinIO secret key |
| `API__PORT` | No | `8080` | API server port |
| `API__CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins (restrict in production) |
| `LOG__LEVEL` | No | `INFO` | Log level |
| `LOG__FORMAT` | No | `json` | `json` or `console` |
| `OTLP__ENDPOINT` | No | — | OTel Collector gRPC endpoint |

---

## 8. Scaling Notes

### Single-worker limitations

The v1.0 API runs single-worker (`workers=1`). ML models are loaded once per process and are not safe for concurrent writes. In practice, this means one in-flight query at a time for the ML-heavy operations (embedding, reranking, NLI).

For higher throughput:
1. Run multiple API instances behind a load balancer (each loads its own models — ~2GB RAM per instance)
2. Move ML inference to a dedicated model server (Triton, vLLM, or sentence-transformers serving)
3. Use async pipeline execution (planned for v2.0)

### Evidence log scaling

The JSONL evidence log grows at ~10KB per query. For 1,000 queries/day:
- Daily log: ~10MB
- Annual: ~3.6GB (after gzip: ~360MB)

For higher volume, consider a PostgreSQL or ClickHouse backend for the evidence log (planned for v2.0).

### Memory

| Component | Memory |
|---|---|
| BGE-large-en-v1.5 | ~1.3 GB |
| nli-deberta-v3-base | ~350 MB |
| ms-marco-MiniLM-L-12-v2 | ~90 MB |
| BM25 index (50 docs) | ~50 MB |
| API + overhead | ~200 MB |
| **Total** | **~1.99 GB** |

Minimum recommended RAM: **4 GB** (with OS overhead). Recommended: **8 GB**.

---

## 9. Health Check

```bash
curl http://localhost:8080/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "qdrant": "connected",
    "minio": "connected",
    "anthropic": "reachable"
  }
}
```

CI health check: `scripts/check_regression_gate.py` reads the evaluation report and verifies all five blocking conditions.
