# Deployment Quickstart

This guide describes the shortest supported paths for running X-Agent in development, real-LLM pilot, and Docker Compose modes.

## Important configuration rule

The backend settings loader reads variables with the `XAGENT_` prefix. Prefer `XAGENT_*` variables for all application configuration. Un-prefixed variables may still be used by infrastructure tools such as Celery, Docker Compose, PostgreSQL, or Redis, but they are not the primary application settings interface.

## Local development with mock LLM

Use this mode to verify installation without external secrets.

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env -ErrorAction SilentlyContinue
$env:XAGENT_LLM_BACKEND="mock"
$env:XAGENT_QDRANT_URL=""
uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/health`.

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
cp -n .env.example .env || true
export XAGENT_LLM_BACKEND=mock
export XAGENT_QDRANT_URL=""
uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000/health`.

## Local pilot with DeepSeek

Set a real DeepSeek key in `.env` or in the shell:

```env
XAGENT_LLM_BACKEND=deepseek
XAGENT_DEEPSEEK_API_KEY=your_key_here
XAGENT_DEEPSEEK_MODEL=deepseek-chat
XAGENT_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

For real code-modification e2e tests only, high-risk tools must be explicitly enabled:

```powershell
$env:XAGENT_E2E="1"
$env:XAGENT_E2E_LLM="1"
$env:XAGENT_ENABLE_HIGH_RISK_TOOLS="true"
python -m pytest tests/e2e/test_agent_fix_real_llm.py -s -q -o addopts="" -p no:cov -p no:cacheprovider --tb=short
```

Do not leave `XAGENT_ENABLE_HIGH_RISK_TOOLS=true` as a broad production default.

## Docker Compose development stack

The root `docker-compose.yml` starts PostgreSQL, Redis, Qdrant, Neo4j, the API container, a worker, and a scheduler. The API/worker/beat services now pass `XAGENT_*` application variables into the containers.

```bash
docker compose up -d postgres redis qdrant
# optional: include neo4j if a feature path needs it
docker compose up -d xagent-api
curl http://127.0.0.1:8000/health
```

For a production-like compose run, create an environment file with at least:

```env
XAGENT_APP_MODE=production
XAGENT_REQUIRE_API_KEY=true
XAGENT_AUDIT_HMAC_SECRET=REPLACE_WITH_GENERATED_SECRET
XAGENT_JWT_SECRET=REPLACE_WITH_GENERATED_SECRET_MIN_64_CHARS
XAGENT_ENCRYPTION_KEY=REPLACE_WITH_GENERATED_SECRET_MIN_64_CHARS
XAGENT_CORS_ORIGINS=https://your-app.example.com
XAGENT_LLM_BACKEND=deepseek
XAGENT_DEEPSEEK_API_KEY=REPLACE_WITH_DEEPSEEK_API_KEY
XAGENT_ENABLE_HIGH_RISK_TOOLS=false
```

Generate secrets with:

```bash
python scripts/generate_secrets.py
```

## Three-tier deployment strategy

X-Agent supports three deployment modes. The API key enforcement setting differs by tier.

**Cloud server (production)** — The API is public-facing and must be authenticated.

```env
XAGENT_APP_MODE=production
XAGENT_REQUIRE_API_KEY=true
XAGENT_BOOTSTRAP_API_KEY=your-admin-key
XAGENT_GITHUB_WEBHOOK_SECRET=your-webhook-secret
XAGENT_CORS_ORIGINS=https://your-app.example.com
```

Run via Docker Compose. Mobile apps and web clients authenticate with the `x-api-key` header.

**Desktop (local)** — User is the sole operator. API key auth is optional.

```env
XAGENT_APP_MODE=development
XAGENT_REQUIRE_API_KEY=false
XAGENT_LLM_BACKEND=deepseek
```

Start with `uvicorn backend.app.main:app --reload`.

**Mobile App** — App authenticates against the cloud server above using a provisioned API key. No separate backend needed; configure the app to point at the cloud server URL and include `x-api-key` in all requests.

---

## Release-candidate validation

See `RELEASE_READINESS.md` for the current targeted baseline commands, known limits, and production checklist.
