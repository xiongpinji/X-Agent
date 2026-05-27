# Troubleshooting Guide

Solutions to common issues and problems.

## Installation Issues

### Python Version Error

**Error**: `Python 3.11 or higher required`

**Cause**: Your Python version is too old.

**Solution**:
```bash
# Check current version
python --version

# Install Python 3.11+
# Ubuntu/Debian:
sudo apt-get install python3.11 python3.11-venv

# macOS:
brew install python@3.11

# Windows: Download from python.org
```

### Virtual Environment Not Activating

**Error**: `command not found: python` or module import errors

**Cause**: Virtual environment not properly activated.

**Solution**:
```bash
# Linux/macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate

# Verify activation (should show (venv) prefix)
which python  # or 'where python' on Windows
```

### Dependency Installation Fails

**Error**: `pip install` fails with permission or compilation errors

**Solution**:
```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install with no cache
pip install --no-cache-dir -e ".[dev]"

# If still failing, check for system dependencies
# Ubuntu/Debian:
sudo apt-get install build-essential python3-dev

# macOS:
xcode-select --install
```

## Database Issues

### PostgreSQL Connection Error

**Error**: `could not connect to server: Connection refused`

**Cause**: PostgreSQL is not running or not accessible.

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

# Test connection
psql -U postgres -h localhost
```

### Database Already Exists

**Error**: `database "xagent_db" already exists`

**Cause**: Database was already created in a previous run.

**Solution**:
```bash
# Option 1: Drop and recreate
psql -U postgres -c "DROP DATABASE xagent_db;"
python -m backend.app.core.migration init

# Option 2: Skip migration
# Just use the existing database
```

### Migration Fails

**Error**: `Migration failed: table already exists`

**Cause**: Partial migration or manual schema changes.

**Solution**:
```bash
# Check migration status
python -m backend.app.core.migration status

# Rollback to previous version
python -m backend.app.core.migration rollback

# Re-run migrations
python -m backend.app.core.migration init
```

### Connection Pool Exhausted

**Error**: `QueuePool limit exceeded`

**Cause**: Too many database connections.

**Solution**:
```bash
# Increase pool size in .env
DATABASE_POOL_SIZE=30
DATABASE_MAX_OVERFLOW=20

# Or restart the application
# Check for connection leaks in code
```

## Service Issues

### Port Already in Use

**Error**: `Address already in use: ('0.0.0.0', 8000)`

**Cause**: Another process is using port 8000.

**Solution**:
```bash
# Find process using port
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows

# Or use different port
uvicorn backend.app.web:app --port 8001
```

### Qdrant Connection Error

**Error**: `Failed to connect to Qdrant at http://localhost:6333`

**Cause**: Qdrant service is not running.

**Solution**:
```bash
# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant

# Or check if running
curl http://localhost:6333/health

# Check Qdrant logs
docker logs <container_id>
```

### API Server Won't Start

**Error**: `ModuleNotFoundError` or `ImportError`

**Cause**: Missing dependencies or incorrect Python path.

**Solution**:
```bash
# Reinstall dependencies
pip install -e ".[dev]"

# Check Python path
python -c "import sys; print(sys.path)"

# Verify installation
python -c "from backend.app.web import app; print('OK')"

# Start with verbose output
uvicorn backend.app.web:app --log-level debug
```

## Runtime Issues

### Out of Memory

**Error**: `MemoryError` or process killed

**Cause**: Insufficient RAM or memory leak.

**Solution**:
```bash
# Check available memory
free -h  # Linux
vm_stat  # macOS
wmic OS get TotalVisibleMemorySize  # Windows

# Reduce batch size
# In configuration or code:
BATCH_SIZE=10  # Reduce from default

# Enable memory profiling
pip install memory-profiler
python -m memory_profiler script.py
```

### Slow Performance

**Error**: API responses are slow

**Cause**: Database queries, LLM latency, or resource constraints.

**Solution**:
```bash
# Check database performance
EXPLAIN ANALYZE SELECT * FROM workflows;

# Enable query logging
export LOG_LEVEL=DEBUG

# Check resource usage
top  # Linux/macOS
Task Manager  # Windows

# Optimize database
VACUUM ANALYZE;
CREATE INDEX idx_workflow_status ON workflows(status);
```

### High CPU Usage

**Error**: CPU usage is consistently high

**Cause**: Inefficient code, infinite loops, or too many workers.

**Solution**:
```bash
# Check running processes
ps aux | grep python  # Linux/macOS

# Reduce worker count
gunicorn backend.app.web:app --workers 2

# Profile code
pip install py-spy
py-spy record -o profile.svg -- python script.py
```

## API Issues

### 401 Unauthorized

**Error**: `{"error": "Unauthorized"}`

**Cause**: Missing or invalid API key/token.

**Solution**:
```bash
# Check API key
echo $X_API_KEY

# Generate new API key
python -m backend.app.core.admin create_api_key

# Use correct header
curl -H "X-API-Key: your-key" http://localhost:8000/api/workflows
```

### 404 Not Found

**Error**: `{"error": "Workflow not found"}`

**Cause**: Resource doesn't exist or wrong ID.

**Solution**:
```bash
# List available workflows
curl http://localhost:8000/api/workflows

# Check workflow ID
curl http://localhost:8000/api/workflows/wf_123

# Verify resource exists in database
psql -U xagent -d xagent_db -c "SELECT * FROM workflows WHERE id='wf_123';"
```

### 429 Too Many Requests

**Error**: `{"error": "Rate limit exceeded"}`

**Cause**: Too many requests in short time.

**Solution**:
```bash
# Wait before retrying
sleep 60

# Increase rate limit in configuration
RATE_LIMIT_REQUESTS=2000
RATE_LIMIT_PERIOD=3600

# Implement exponential backoff in client
```

### 500 Internal Server Error

**Error**: `{"error": "Internal server error"}`

**Cause**: Server-side error.

**Solution**:
```bash
# Check server logs
docker-compose logs backend

# Enable debug mode
DEBUG=true uvicorn backend.app.web:app

# Check error details
curl -v http://localhost:8000/api/workflows

# Review application logs
tail -f logs/app.log
```

## Testing Issues

### Tests Fail with Database Error

**Error**: `could not connect to test database`

**Cause**: Test database not set up.

**Solution**:
```bash
# Create test database
psql -U postgres -c "CREATE DATABASE xagent_test;"

# Run migrations for test DB
TEST_DATABASE_URL=postgresql://postgres:password@localhost/xagent_test \
  python -m backend.app.core.migration init

# Run tests
pytest
```

### Tests Timeout

**Error**: `test session timeout`

**Cause**: Tests taking too long or hanging.

**Solution**:
```bash
# Increase timeout
pytest --timeout=300

# Run specific test
pytest tests/test_api.py::test_create_workflow -v

# Run with verbose output
pytest -vv -s
```

### Mock LLM Not Working

**Error**: `LLM call failed` in tests

**Cause**: Mock not properly configured.

**Solution**:
```python
# Use mock in tests
from unittest.mock import patch

@patch('backend.app.core.llm.LLMRouter.call')
async def test_workflow(mock_llm):
    mock_llm.return_value = "mocked response"
    # Test code
```

## Docker Issues

### Container Won't Start

**Error**: `docker-compose up` fails

**Cause**: Port conflict, image not found, or configuration error.

**Solution**:
```bash
# Check logs
docker-compose logs

# Rebuild images
docker-compose build --no-cache

# Check port availability
lsof -i :5432  # PostgreSQL
lsof -i :6333  # Qdrant
lsof -i :8000  # API

# Verify docker-compose.yml
docker-compose config
```

### Container Exits Immediately

**Error**: Container starts then stops

**Cause**: Application error or missing dependencies.

**Solution**:
```bash
# Check container logs
docker logs <container_id>

# Run with interactive terminal
docker run -it x-agent-core:latest bash

# Check environment variables
docker-compose config | grep environment
```

## Getting Help

### Collect Debug Information

When reporting issues, collect:

```bash
# System information
python --version
psql --version
docker --version

# Application logs
docker-compose logs > logs.txt

# Configuration (without secrets)
cat .env | grep -v KEY | grep -v PASSWORD

# Error traceback
# Include full error message and stack trace
```

### Report Issue

1. Check [GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
2. Search for similar issues
3. Create new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Debug information
   - Environment details

### Contact Support

- **Email**: support@x-agent.dev
- **GitHub**: [Issues](https://github.com/x-agent/x-agent-core/issues)
- **Discussions**: [Community](https://github.com/x-agent/x-agent-core/discussions)

---

For more help, see [Installation Guide](../INSTALL.md) and [FAQ](./FAQ.md).
