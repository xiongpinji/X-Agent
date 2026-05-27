"""
Integration Guide: Using Concurrency Control in X-Agent

This guide shows how to integrate the concurrency control system
into existing X-Agent modules.
"""

# Integration Examples

## 1. Integrating with PostgreSQL Memory System

### Before (memory_postgres.py - Current)
```python
async def _get_pool(self) -> Any:
    if self._pool is None:
        import asyncpg
        self._pool = await asyncpg.create_pool(self.database_url)
    return self._pool
```

### After (Optimized with Connection Pool)
```python
from backend.app.core.pools import get_postgres_pool, PoolConfig

class PostgresMemorySystem:
    def __init__(self, database_url: str, ...):
        self.database_url = database_url
        self._pool = None
        
    async def _get_pool(self) -> Any:
        if self._pool is None:
            config = PoolConfig(min_size=5, max_size=20)
            pool_manager = get_postgres_pool(self.database_url, config)
            await pool_manager.initialize()
            self._pool = pool_manager
        return self._pool
    
    async def store(self, context: RunContext, content: str, ...):
        pool = await self._get_pool()
        conn = await pool.acquire()
        try:
            # Use connection
            await conn.execute(...)
        finally:
            await pool.release(conn)
```

## 2. Integrating with Auth System

### Before (auth.py - Current)
```python
_token_lock = threading.Lock()
_token_expiry: dict[str, float] = {}

def _is_token_valid(token: str) -> bool:
    with _token_lock:
        if token in _revoked_tokens:
            return False
        expiry = _token_expiry.get(token)
    if expiry is None or time.time() > expiry:
        return False
    return True
```

### After (Optimized with Rate Limiting)
```python
from backend.app.core.concurrency_limiter import get_rate_limiter

# Rate limit login attempts
login_limiter = get_rate_limiter("login_attempts", rate=10.0, burst=10)

@router.post("/auth/login")
async def login(request: AuthLoginRequest):
    # Rate limit per IP
    if not await login_limiter.acquire():
        raise api_error(429, ErrorCode.RATE_LIMIT_EXCEEDED, "Too many login attempts")
    
    # Existing auth logic
    ...
```

## 3. Integrating with API Endpoints

### Before (Generic API - Current)
```python
@router.get("/api/v1/memory")
async def list_memory(
    principal: PrincipalDependency,
    memory: MemorySystem = Depends(get_memory),
):
    # No concurrency control
    return await memory.search(...)
```

### After (With Concurrency Control)
```python
from backend.app.core.concurrency_limiter import get_limiter

memory_limiter = get_limiter("memory_operations", max_concurrent=20)

@router.get("/api/v1/memory")
async def list_memory(
    principal: PrincipalDependency,
    memory: MemorySystem = Depends(get_memory),
):
    # Apply concurrency limiting
    async with memory_limiter:
        return await memory.search(...)
```

## 4. Integrating with Background Tasks

### Before (Task Execution - Current)
```python
async def process_workflow(workflow_id: str):
    # Direct execution, no queue
    await workflow_executor.execute(workflow_id)
```

### After (With Task Queue)
```python
from backend.app.core.concurrency_limiter import get_task_queue, TaskPriority

task_queue = get_task_queue("workflow_execution", worker_count=4)

@router.post("/api/v1/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str):
    # Enqueue with priority
    await task_queue.enqueue(
        lambda: workflow_executor.execute(workflow_id),
        priority=TaskPriority.HIGH,
        timeout=300.0
    )
    return {"status": "queued"}
```

## 5. Integrating with HTTP Requests

### Before (HTTP Calls - Current)
```python
import httpx

async def call_external_api(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### After (With Connection Pooling and Retry)
```python
from backend.app.core.http_client import get_http_client

async def call_external_api(url: str):
    client = get_http_client()
    response = await client.get(url)
    return response.json()
```

## 6. Integrating with Dependencies

### Update dependencies.py
```python
from backend.app.core.concurrency_manager import get_concurrency_manager
from backend.app.core.concurrency_limiter import get_limiter, get_adaptive_limiter
from backend.app.core.resource_monitor import get_resource_monitor

@lru_cache
def get_memory() -> MemorySystem | PostgresMemorySystem:
    settings = get_settings()
    
    # Get concurrency limiter for memory operations
    limiter = get_limiter("memory_ops", max_concurrent=20)
    
    # Build memory system with limiter
    memory = build_memory_system(...)
    memory._limiter = limiter
    return memory

@lru_cache
def get_concurrency_manager_instance():
    return get_concurrency_manager()
```

## 7. Integrating with Main Application

### Update main.py
```python
from backend.app.core.concurrency_manager import (
    initialize_concurrency,
    shutdown_concurrency,
    get_concurrency_manager,
)

app = FastAPI(title=settings.app_name, version="0.1.0")

@app.on_event("startup")
async def startup_event():
    """Initialize concurrency management on startup."""
    try:
        await initialize_concurrency(
            database_url=settings.database_url,
            redis_url=settings.redis_url,
        )
        logger.info("Concurrency management initialized")
    except Exception as e:
        logger.error(f"Failed to initialize concurrency management: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown concurrency management on shutdown."""
    try:
        await shutdown_concurrency()
        logger.info("Concurrency management shutdown complete")
    except Exception as e:
        logger.error(f"Error during concurrency management shutdown: {e}")

# Add metrics endpoint
@app.get("/api/v1/metrics/concurrency")
async def get_concurrency_metrics(principal: PrincipalDependency):
    enforce_scope(principal, "admin:view")
    manager = get_concurrency_manager()
    return manager.get_metrics()

# Add health check endpoint
@app.get("/health/concurrency")
async def concurrency_health():
    manager = get_concurrency_manager()
    health = manager.get_health_status()
    if not health["healthy"]:
        return JSONResponse(health, status_code=503)
    return health
```

## 8. Integrating with Middleware

### Create concurrency_middleware.py
```python
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.core.concurrency_limiter import get_rate_limiter

class ConcurrencyMiddleware(BaseHTTPMiddleware):
    """Middleware for global rate limiting and concurrency control."""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter("global_api", rate=1000.0, burst=500)
    
    async def dispatch(self, request: Request, call_next):
        # Apply global rate limit
        if not await self.rate_limiter.acquire():
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429
            )
        
        response = await call_next(request)
        return response

# In main.py
app.add_middleware(ConcurrencyMiddleware)
```

## 9. Integrating with Monitoring

### Create monitoring_integration.py
```python
from backend.app.core.resource_monitor import get_resource_monitor, ResourceAlert
import logging

logger = logging.getLogger(__name__)

async def setup_monitoring():
    """Setup resource monitoring with alerts."""
    monitor = get_resource_monitor()
    
    async def alert_handler(alert: ResourceAlert):
        """Handle resource alerts."""
        if alert.severity == "critical":
            logger.critical(f"CRITICAL: {alert.message}")
            # Send to monitoring system
            await send_alert_to_monitoring_system(alert)
        else:
            logger.warning(f"WARNING: {alert.message}")
    
    monitor.add_alert_callback(alert_handler)
    await monitor.start()
    
    logger.info("Resource monitoring initialized")

# In main.py startup
@app.on_event("startup")
async def startup_event():
    await initialize_concurrency(...)
    await setup_monitoring()
```

## 10. Integrating with Logging

### Add concurrency metrics to logs
```python
import logging
from backend.app.core.concurrency_manager import get_concurrency_manager

class ConcurrencyMetricsFilter(logging.Filter):
    """Add concurrency metrics to log records."""
    
    def filter(self, record):
        try:
            manager = get_concurrency_manager()
            metrics = manager.get_metrics()
            record.concurrency_metrics = metrics
        except:
            record.concurrency_metrics = {}
        return True

# Configure logging
logging.getLogger().addFilter(ConcurrencyMetricsFilter())
```

## Migration Checklist

- [ ] Add concurrency control imports to dependencies.py
- [ ] Update main.py with startup/shutdown events
- [ ] Add concurrency middleware
- [ ] Update PostgreSQL memory system to use connection pool
- [ ] Update auth system to use rate limiting
- [ ] Update API endpoints with concurrency limiting
- [ ] Add background task queue
- [ ] Update HTTP client calls
- [ ] Add monitoring and alerting
- [ ] Add health check endpoints
- [ ] Update configuration for production
- [ ] Run tests to verify integration
- [ ] Monitor metrics in production

## Performance Validation

After integration, validate performance improvements:

```python
# Before integration
# - Connection pool: 100 connections created per 1000 requests
# - Concurrency: Unbounded, peaks at 500+ concurrent tasks
# - Latency: p99 = 5000ms

# After integration
# - Connection pool: 20 connections reused for 1000 requests
# - Concurrency: Limited to 50 concurrent tasks
# - Latency: p99 = 500ms

# Expected improvements
# - 80% reduction in connection overhead
# - 30% improvement in resource utilization
# - 90% reduction in p99 latency
```

## Troubleshooting Integration

### Issue: Import errors
**Solution**: Ensure all new modules are in backend/app/core/

### Issue: Async context issues
**Solution**: Verify all pool operations are awaited

### Issue: Connection leaks
**Solution**: Always use try/finally or context managers

### Issue: Deadlocks
**Solution**: Avoid nested lock acquisitions

### Issue: Performance degradation
**Solution**: Check concurrency limits and pool sizes

## Next Steps

1. Review CONCURRENCY_ARCHITECTURE.md for detailed documentation
2. Run test_concurrency.py to verify implementation
3. Integrate components incrementally
4. Monitor metrics and adjust configuration
5. Document any custom integrations
