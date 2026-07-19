# Installation Guide

Complete installation and setup instructions for X-Agent Core.

## Table of Contents

- [System Requirements](#system-requirements)
- [Prerequisites](#prerequisites)
- [Standard Installation](#standard-installation)
- [Development Setup](#development-setup)
- [Docker Installation](#docker-installation)
- [Environment Configuration](#environment-configuration)
- [Database Initialization](#database-initialization)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements

- **OS**: Linux, macOS, or Windows 10+
- **Python**: 3.11 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 2GB for installation and dependencies
- **CPU**: 2 cores minimum (4+ recommended)

### Supported Platforms

- Ubuntu 20.04 LTS and later
- Debian 11 and later
- macOS 11 (Big Sur) and later
- Windows 10/11 with WSL2 (recommended)

## Prerequisites

### Required Software

1. **Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

2. **PostgreSQL 14+**
   ```bash
   psql --version  # Should be 14 or higher
   ```

3. **Git**
   ```bash
   git --version
   ```

### Optional but Recommended

- **Docker & Docker Compose** (for containerized deployment)
- **Make** (for running common tasks)
- **curl** or **wget** (for downloading files)

## Standard Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/x-agent/x-agent-core.git
cd x-agent-core
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install package with dependencies
pip install -e .

# Install optional development dependencies
pip install -e ".[dev]"
```

### Step 4: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration (see Environment Configuration section)
nano .env  # or use your preferred editor
```

### Step 5: Initialize Database

```bash
# Create database and run migrations
python -m backend.app.core.migration init

# Verify database connection
python -c "from backend.app.core.memory_postgres import PostgresMemory; print('Database OK')"
```

### Step 6: Verify Installation

```bash
# Run basic tests
pytest tests/test_ready_checks.py -v

# Start the server (Ctrl+C to stop)
uvicorn backend.app.main:app --reload
```

## Development Setup

### Additional Development Tools

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Running Development Server

```bash
# Terminal 1: Start PostgreSQL and Qdrant
docker-compose up -d

# Terminal 2: Start FastAPI server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Start workflow worker
xagent-workflow-worker

# Terminal 4: Run tests (optional)
pytest --watch
```

### Code Quality Tools

```bash
# Run linter
ruff check .

# Format code
ruff format .

# Run tests with coverage
pytest --cov=backend tests/

# Type checking (if mypy is installed)
mypy backend/
```

## Docker Installation

### Using Docker Compose

1. **Ensure Docker is installed**
   ```bash
   docker --version
   docker-compose --version
   ```

2. **Clone repository**
   ```bash
   git clone https://github.com/x-agent/x-agent-core.git
   cd x-agent-core
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Verify services**
   ```bash
   docker-compose ps
   ```

5. **View logs**
   ```bash
   docker-compose logs -f backend
   ```

### Docker Compose Services

The `docker-compose.yml` includes:

- **PostgreSQL**: Database server (port 5432)
- **Qdrant**: Vector database (port 6333)
- **Backend**: FastAPI application (port 8000)
- **Redis** (optional): Caching layer

### Building Custom Docker Image

```bash
# Build image
docker build -t x-agent-core:latest .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/xagent \
  -e QDRANT_URL=http://qdrant:6333 \
  x-agent-core:latest
```

## Environment Configuration

### Configuration File (.env)

Create `.env` file in project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://xagent:xagent@localhost:5432/xagent_db
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# LLM Configuration
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
LLM_DEFAULT_MODEL=gpt-4

# Langfuse Configuration (Optional)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=false

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `QDRANT_URL` | Qdrant vector DB URL | http://localhost:6333 | Yes |
| `OPENAI_API_KEY` | OpenAI API key | - | No |
| `ANTHROPIC_API_KEY` | Anthropic API key | - | No |
| `LLM_DEFAULT_MODEL` | Default LLM model | gpt-4 | No |
| `SERVER_PORT` | API server port | 8000 | No |
| `DEBUG` | Debug mode | false | No |
| `SECRET_KEY` | JWT secret key | - | Yes |

## Database Initialization

### Automatic Migration

```bash
# Run all pending migrations
python -m backend.app.core.migration init

# Check migration status
python -m backend.app.core.migration status
```

### Manual Database Setup

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE xagent_db;

# Create user
CREATE USER xagent WITH PASSWORD 'xagent';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE xagent_db TO xagent;

# Exit
\q
```

### Seed Sample Data (Optional)

```bash
python -m backend.app.core.migration seed
```

## Verification

### Health Check

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "0.1.0"}
```

### Database Connection

```bash
# Test database connection
python -c "
from backend.app.core.memory_postgres import PostgresMemory
memory = PostgresMemory()
print('Database connection OK')
"
```

### Run Test Suite

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage report
pytest --cov=backend --cov-report=html
```

## Troubleshooting

### Common Issues

#### 1. Python Version Error

**Error**: `Python 3.11 or higher required`

**Solution**:
```bash
# Check Python version
python --version

# If using Python 3.10 or lower, install Python 3.11+
# Ubuntu/Debian:
sudo apt-get install python3.11 python3.11-venv

# macOS:
brew install python@3.11

# Windows: Download from python.org
```

#### 2. PostgreSQL Connection Error

**Error**: `could not connect to server: Connection refused`

**Solution**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Or use Docker
docker run -d -p 5432:5432 \
  -e POSTGRES_PASSWORD=xagent \
  postgres:14
```

#### 3. Virtual Environment Issues

**Error**: `No module named 'backend'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Reinstall package
pip install -e .
```

#### 4. Port Already in Use

**Error**: `Address already in use: ('0.0.0.0', 8000)`

**Solution**:
```bash
# Find process using port 8000
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn backend.app.main:app --port 8001
```

#### 5. Qdrant Connection Error

**Error**: `Failed to connect to Qdrant`

**Solution**:
```bash
# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant

# Or check if running
curl http://localhost:6333/health
```

#### 6. Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Reinstall dependencies
pip install -e ".[dev]"

# Or install specific package
pip install fastapi uvicorn
```

### Getting Help

If you encounter issues not listed above:

1. Check the [GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
2. Review [Architecture Guide](./docs/ARCHITECTURE.md)
3. Check logs: `docker-compose logs -f`
4. Contact support: dev@x-agent.dev

### Performance Optimization

For production deployments:

```bash
# Use production ASGI server
pip install gunicorn

# Run with multiple workers
gunicorn backend.app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# Enable caching
export REDIS_URL=redis://localhost:6379

# Optimize database
# In PostgreSQL:
VACUUM ANALYZE;
CREATE INDEX idx_memory_embedding ON memory USING ivfflat (embedding);
```

---

For more information, see [README.md](./README.md) and [CONTRIBUTING.md](./CONTRIBUTING.md).
