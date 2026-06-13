# X-Agent — Enterprise Autonomous Agent Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Tests: 3850+](https://img.shields.io/badge/Tests-3850%2B-green)](tests/)
[![Code: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](RELEASE_READINESS.md)

> Build, deploy, and orchestrate autonomous AI agents at enterprise scale. Self-hosted. Open source. Multi-tenant. Built for teams that demand auditability, security, and control.

X-Agent is a modern agent framework for enterprises—not a desktop IDE. It powers teams building multi-agent AI systems, enabling them to route work across multiple LLMs, execute complex workflows with human oversight, and maintain full observability and compliance.

## 30-Second Quickstart

```bash
# Install
pip install xagent-framework

# Configure environment
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="claude-..."

# Start the server
xagent start --host 0.0.0.0 --port 8000

# In another terminal, try it
curl -X POST http://localhost:8000/api/v1/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Find GitHub repos about AI agents",
    "model": "claude-3-5-sonnet"
  }'
```

See [docs/QUICKSTART.md](./docs/QUICKSTART.md) for detailed setup and two deployment paths (Lite & Full).

## Why X-Agent

| Capability | X-Agent | Codex | Devin | LangChain |
|-----------|---------|-------|-------|-----------|
| Self-hosted | ✅ | ❌ | ❌ | ✅ |
| Multi-agent orchestration | ✅ | ❌ | ⚠️ | ⚠️ |
| Enterprise audit trail | ✅ | ❌ | ❌ | ❌ |
| HMAC/RBAC security | ✅ | ❌ | ❌ | ❌ |
| Open source | ✅ | ❌ | ❌ | ✅ |
| Multi-model routing | ✅ | ⚠️ | ✅ | ✅ |

## Core Capabilities

- **🤖 Multi-Agent Orchestration** — Delegate tasks between specialized agents with capability matching and automatic load balancing
- **🔐 Enterprise Security** — Multi-tenant isolation, HMAC audit trails, RBAC, encrypted policy evaluation
- **🔌 MCP Protocol + Plugins** — Discover and integrate tools via Model Context Protocol; extend with custom plugins
- **📊 Full Observability** — Langfuse tracing, Prometheus metrics, structured logging for every agent decision
- **⚙️ Workflow Engine** — Define multi-step workflows with conditionals, loops, templates, and approval gates
- **☁️ Cloud Sandbox** — Execute untrusted code safely; GitHub Issue→PR automation; fire-and-forget task queuing

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  CLI / REST API / SDKs                              │
│  xagent start  │  /api/v1/workflows  │  Python lib  │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│  Agent Engine (FastAPI)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ LLM Router   │  │ Memory Graph │  │ Policy    │ │
│  │ (multi-model)│  │ + Vector DB  │  │ Engine    │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└────────────────────┬────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│  Infrastructure                                     │
│  PostgreSQL │ Qdrant │ Playwright │ Docker Sandbox  │
│  Langfuse   │ Redis  │ Prometheus │ GitHub API      │
└─────────────────────────────────────────────────────┘
```

## Installation

Choose your deployment path:

### 1. Lite (No Docker, SQLite, single-machine)

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"

export OPENAI_API_KEY="sk-..."
xagent start
# Server running at http://localhost:8000
```

### 2. Standard (PostgreSQL, Production-grade)

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core

docker-compose up -d postgres qdrant redis

python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

export DATABASE_URL="postgresql://xagent:password@localhost/xagent"
export QDRANT_URL="http://localhost:6333"
xagent start
```

### 3. Full (Cloud Sandbox, GitHub Integration, Multi-tenant)

```bash
docker-compose up -d  # Runs postgres, qdrant, redis, sandbox orchestrator

export GITHUB_TOKEN="ghp_..."
xagent start --enable-sandbox --enable-github-automation
```

## Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](./docs/QUICKSTART.md) | 5-minute setup guide (two paths: Lite & Full) |
| [INSTALL.md](./INSTALL.md) | Detailed installation and troubleshooting |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Local, DeepSeek, Docker Compose, production checklist |
| [RELEASE_READINESS.md](./RELEASE_READINESS.md) | Validation commands and delivery status |
| [API.md](./docs/API.md) | REST API reference and examples |
| [ADVANCED_FEATURES.md](./docs/ADVANCED_FEATURES.md) | Workflows, multi-agent, memory, sandbox |
| [ARCHITECTURE.md](./docs/ARCHITECTURE.md) | System design deep-dive |
| [EXAMPLES.md](./docs/EXAMPLES.md) | Code snippets and use cases |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (full suite)
pytest

# Run fast baseline (release candidate check)
python scripts/release_candidate_check.py

# Lint and format
ruff check .
ruff format .
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for:
- Development setup
- Code style and standards
- Git workflow
- PR process

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Support & Community

- **Issues** — [GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
- **Docs** — [Full documentation](./docs/)
- **Examples** — [docs/EXAMPLES.md](./docs/EXAMPLES.md)

---

**Built for enterprises that need control, visibility, and scale.**
