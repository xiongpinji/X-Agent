# X-Agent Quickstart — Get Running in 5 Minutes

This guide gets you from zero to a working X-Agent instance in two straightforward paths: **Lite** (no Docker, local SQLite) and **Full** (production-grade PostgreSQL + Docker).

Choose your path based on your needs:
- **Lite**: Perfect for learning, local development, prototyping
- **Full**: Recommended for production, teams, multi-tenant deployments

---

## Path 1: Lite (No Docker)

**Time: 3–4 minutes | Requirements: Python 3.11+, pip**

### Step 1: Clone and Setup

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

pip install -e ".[dev]"
```

### Step 2: Configure

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
# nano .env  (or open in your editor)
# Required:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=claude-...
```

### Step 3: Start

```bash
xagent start
```

**Expected output:**
```
[INFO] Initializing X-Agent...
[INFO] MCP manager initialized
[INFO] Hooks loaded from config
[INFO] Database ready (SQLite: ./data/xagent.db)
[INFO] Qdrant fallback (in-memory vector store)
[INFO] Langfuse disabled (set LANGFUSE_PUBLIC_KEY to enable)
[INFO] Uvicorn running on http://0.0.0.0:8000
```

### Step 4: Try It

In another terminal:

```bash
# Test the health endpoint
curl http://localhost:8000/health

# Execute your first agent task
curl -X POST http://localhost:8000/api/v1/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "What are the top 3 features of X-Agent?",
    "model": "claude-3-5-sonnet"
  }'
```

**Expected output:**
```json
{
  "agent_id": "agent_abc123",
  "status": "completed",
  "output": "X-Agent provides: 1. Multi-agent orchestration...",
  "tokens": {
    "input": 256,
    "output": 142
  },
  "trace_id": "trace_xyz789"
}
```

✅ **Success!** Your agent just completed its first task.

---

## Path 2: Full (Production with Docker)

**Time: 4–5 minutes | Requirements: Docker, Docker Compose, Python 3.11+**

This path sets up PostgreSQL, Qdrant (vector DB), and Redis for production workloads.

### Step 1: Clone and Start Services

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

# Start all services (postgres, qdrant, redis)
docker-compose up -d

# Verify services are running
docker-compose ps
```

**Expected output:**
```
NAME              STATUS
x-agent-postgres  Up 2 seconds
x-agent-qdrant    Up 2 seconds
x-agent-redis     Up 2 seconds
```

### Step 2: Setup Python & Dependencies

```bash
python -m venv venv
source venv/bin/activate
# Windows: venv\Scripts\activate

pip install -e ".[dev]"
```

### Step 3: Configure

```bash
cp .env.example .env

# Edit the Full deployment settings:
# nano .env
# Key variables:
#   DATABASE_URL=postgresql://xagent:xagent@localhost/xagent
#   QDRANT_URL=http://localhost:6333
#   REDIS_URL=redis://localhost:6379
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=claude-...
```

### Step 4: Initialize Database

```bash
python -c "from backend.local.migration import initialize_local_database; initialize_local_database()"
```

**Expected output:**
```
[INFO] Initializing local database...
[INFO] Database tables created
[INFO] Migrations applied
```

### Step 5: Start the Server

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
[INFO] Uvicorn running on http://0.0.0.0:8000
[INFO] Connected to PostgreSQL
[INFO] Qdrant vector store initialized
[INFO] Redis cache ready
[INFO] MCP manager initialized
```

### Step 6: Try It (Same as Lite)

In another terminal:

```bash
# Health check
curl http://localhost:8000/health

# Execute with workflow
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_workflow",
    "steps": [
      {
        "type": "agent",
        "instruction": "List top 5 Python async libraries",
        "model": "claude-3-5-sonnet"
      }
    ]
  }'
```

✅ **Success!** Full production setup is running.

---

## Verification Checklist

- [ ] Server running without errors (`xagent start` or `uvicorn ...`)
- [ ] Health endpoint responds: `curl http://localhost:8000/health` → `200 OK`
- [ ] Agent executes a task successfully
- [ ] API keys configured (check `.env` for `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`)
- [ ] (Full only) PostgreSQL, Qdrant, Redis all show `Up` in `docker-compose ps`

## What's Next

### 1. **Run Your First Workflow**

See [docs/EXAMPLES.md](../docs/EXAMPLES.md) for complete workflow examples.

```bash
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "example",
    "steps": [...]
  }'
```

### 2. **Explore the API**

Visit the interactive API docs at `http://localhost:8000/docs` (Swagger UI).

### 3. **Set Up Observability**

To see traces, add Langfuse:

```bash
export LANGFUSE_PUBLIC_KEY="pk_..."
export LANGFUSE_SECRET_KEY="sk_..."
# Restart server
```

Visit [Langfuse dashboard](https://cloud.langfuse.com/) to see all agent traces.

### 4. **Enable GitHub Integration** (Full path only)

For Issue→PR automation:

```bash
export GITHUB_TOKEN="ghp_..."
xagent start --enable-github-automation
```

### 5. **Deploy to Production**

See [DEPLOYMENT.md](../DEPLOYMENT.md) for:
- Kubernetes deployment
- Multi-tenant setup
- Security hardening
- Performance tuning

---

## Troubleshooting

### Server won't start

**Problem:** `Error: Database connection failed`

**Solution (Lite):** Ensure `./data/` directory is writable.
```bash
mkdir -p data
chmod 755 data
```

**Solution (Full):** Verify PostgreSQL is running:
```bash
docker-compose ps postgres
docker-compose logs postgres
```

---

### "ModuleNotFoundError" after install

**Solution:** Reinstall with editable mode:
```bash
pip install -e ".[dev]" --force-reinstall --no-cache-dir
```

---

### API returns 500 errors

**Solution:** Check server logs for details:
```bash
# If using uvicorn directly
tail -f /tmp/xagent.log

# If using xagent start
xagent logs
```

---

### Vector search not working

**Problem (Full):** `ConnectionError: Cannot reach Qdrant`

**Solution:** Restart Qdrant:
```bash
docker-compose down qdrant
docker-compose up -d qdrant
# Wait 3 seconds for it to be ready
```

---

## Next Steps

- **Learn the API**: [docs/API.md](../docs/API.md)
- **Build workflows**: [docs/ADVANCED_FEATURES.md](../docs/ADVANCED_FEATURES.md)
- **Multi-agent patterns**: [docs/EXAMPLES.md](../docs/EXAMPLES.md)
- **Deploy to production**: [DEPLOYMENT.md](../DEPLOYMENT.md)
- **Contribute**: [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Questions?** Open an issue on [GitHub](https://github.com/x-agent/x-agent-core/issues).
