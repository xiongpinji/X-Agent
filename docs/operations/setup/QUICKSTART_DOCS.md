# Quick Start Guide

Get X-Agent Core up and running in 5 minutes.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or Docker)
- Git

## Installation (5 Steps)

### 1. Clone Repository
```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -e ".[dev]"
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 5. Start Services
```bash
# Terminal 1: Start databases
docker-compose up -d

# Terminal 2: Initialize database
python -m backend.app.core.migration init

# Terminal 3: Start server
uvicorn backend.app.web:app --reload
```

## Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Run tests
pytest tests/test_ready_checks.py
```

## Next Steps

- Read [README](../README.md) for project overview
- Check [Installation Guide](./INSTALL.md) for detailed setup
- See [Examples](../../developer/sdk/EXAMPLES.md) for code samples
- Review [Contributing Guide](../CONTRIBUTING.md) to contribute

## Common Commands

```bash
# Run all tests
pytest

# Format code
ruff format .

# Check code style
ruff check .

# Start workflow worker
xagent-workflow-worker

# View API docs
# Open http://localhost:8000/docs
```

## Troubleshooting

**Port 8000 already in use?**
```bash
uvicorn backend.app.web:app --port 8001
```

**Database connection error?**
```bash
docker-compose up -d  # Start PostgreSQL
```

**Module not found?**
```bash
pip install -e ".[dev]"  # Reinstall dependencies
```

See [Troubleshooting](../support/TROUBLESHOOTING.md) for more help.
