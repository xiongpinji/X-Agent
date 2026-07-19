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

## TLS termination (production required)

In production (`XAGENT_APP_MODE=production`) the API MUST be reachable only
over HTTPS. Uvicorn MUST NOT be exposed directly to the network; terminate
TLS at a reverse proxy in front of it and keep uvicorn bound to localhost.

**Full-chain TLS requirements:**

1. **Client → proxy:** HTTPS only. Redirect port 80 to 443, enable HSTS
   (the backend already emits `Strict-Transport-Security` via
   `SecurityHeadersMiddleware`).
2. **Proxy → uvicorn:** same-host loopback (`http://127.0.0.1:8000`) is
   acceptable; if the proxy and the API run on different hosts or containers
   crossing a network boundary, this hop MUST also be TLS (or an equivalent
   private-network encrypted tunnel such as WireGuard/mTLS).
3. **API → databases (PostgreSQL/Redis/Qdrant):** enable TLS or keep them on
   the same private network with no public exposure. Never expose database
   ports on `0.0.0.0` in production.
4. Interactive docs (`/docs`, `/redoc`, `/openapi.json`) are disabled in
   production (see `ProductionDocsGuardMiddleware`); do not re-enable them
   through the proxy.

### nginx reference configuration

```nginx
server {
    listen 80;
    server_name your-app.example.com;
    # ACME http-01 challenge (if using certbot)
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 443 ssl;
    http2 on;
    server_name your-app.example.com;

    ssl_certificate     /etc/letsencrypt/live/your-app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-app.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    # HSTS is also emitted by the backend middleware; keeping it here too is fine.
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # CRITICAL: lets the app know the original scheme was HTTPS.
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

Run uvicorn bound to loopback only:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Caddy reference configuration

Caddy obtains and renews certificates automatically:

```caddyfile
your-app.example.com {
    reverse_proxy 127.0.0.1:8000
    # X-Forwarded-Proto is set automatically by Caddy's reverse_proxy.
}
```

### Docker Compose note

The development `docker-compose.yml` exposes port 8000 for local use. For a
production compose deployment, do NOT publish `8000:8000` on `0.0.0.0`;
either bind it to `127.0.0.1:8000:8000` or place an nginx/Caddy container in
front and keep the API port internal to the compose network.

---

## Release-candidate validation

See `RELEASE_READINESS.md` for the current targeted baseline commands, known limits, and production checklist.
