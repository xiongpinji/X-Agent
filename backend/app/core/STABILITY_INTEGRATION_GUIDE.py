"""
X-Agent Stability Enhancement Integration Guide

This document provides comprehensive guidance on integrating and using the
stability enhancement modules in X-Agent.

## Overview

Four core stability modules have been implemented:

1. Circuit Breaker (stability_circuit_breaker.py)
   - Prevents cascading failures
   - Automatic state management (CLOSED/OPEN/HALF_OPEN)
   - Per-service configuration

2. Degradation Strategy (stability_degradation.py)
   - Feature-level degradation
   - Read-only mode support
   - Caching fallback

3. Distributed Lock (stability_distributed_lock.py)
   - Multi-instance coordination
   - Redis-based locking
   - Automatic expiration

4. Retry Mechanism (stability_retry.py)
   - Exponential backoff with jitter
   - Retry budget management
   - Configurable strategies

## Integration Points

### 1. Circuit Breaker Integration

Location: backend/app/core/stability_circuit_breaker.py

Usage in API endpoints:

```python
from backend.app.core.stability_circuit_breaker import (
    CircuitBreakerConfig,
    get_circuit_breaker_registry,
)

# In dependencies.py or initialization
registry = get_circuit_breaker_registry()

# Create circuit breaker for external service
config = CircuitBreakerConfig(
    name="llm_service",
    failure_threshold=5,
    success_threshold=2,
    timeout=60,
)
breaker = registry.get_or_create(config)

# In API handler
@app.get("/api/chat")
async def chat(request: Request):
    try:
        result = await breaker.call_async(
            llm_service.generate_response,
            prompt=request.prompt,
        )
        return result
    except CircuitBreakerException:
        return {"error": "Service temporarily unavailable"}
```

### 2. Degradation Strategy Integration

Location: backend/app/core/stability_degradation.py

Usage in feature management:

```python
from backend.app.core.stability_degradation import (
    FeatureConfig,
    DegradationLevel,
    get_degradation_strategy,
)

# In initialization
strategy = get_degradation_strategy()

# Register features
strategy.register_feature(FeatureConfig(
    name="advanced_search",
    critical=False,
    has_fallback=True,
))

strategy.register_feature(FeatureConfig(
    name="memory_consolidation",
    critical=False,
    cache_enabled=True,
))

# In API handler
@app.get("/api/search")
async def search(query: str):
    if not strategy.is_feature_enabled("advanced_search"):
        # Use fallback search
        return basic_search(query)

    return advanced_search(query)

# During degradation
if system_load_high():
    strategy.set_degradation_level(DegradationLevel.DEGRADED)
    strategy.disable_feature("advanced_search", reason="High load")
```

### 3. Distributed Lock Integration

Location: backend/app/core/stability_distributed_lock.py

Usage in critical sections:

```python
from backend.app.core.stability_distributed_lock import (
    DistributedLockConfig,
    get_lock_manager,
)
import redis

# In dependencies.py
redis_client = redis.Redis(host='localhost', port=6379)
lock_manager = get_lock_manager(redis_client)

# In critical operation
@app.post("/api/workflow/execute")
async def execute_workflow(workflow_id: str):
    config = DistributedLockConfig(
        name=f"workflow_{workflow_id}",
        timeout=30,
        auto_renewal=True,
    )
    lock = lock_manager.get_or_create(config)

    if not lock.acquire(blocking=False):
        return {"error": "Workflow already executing"}

    try:
        result = await execute_workflow_impl(workflow_id)
        return result
    finally:
        lock.release()

# Or use context manager
with lock:
    result = await execute_workflow_impl(workflow_id)
```

### 4. Retry Mechanism Integration

Location: backend/app/core/stability_retry.py

Usage in external service calls:

```python
from backend.app.core.stability_retry import (
    RetryConfig,
    RetryStrategy,
    RetryableException,
    get_retry_registry,
)

# In dependencies.py
registry = get_retry_registry()

# Create retry executor
config = RetryConfig(
    name="database_query",
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    max_retries=3,
    initial_delay=1.0,
    max_delay=30.0,
    budget_per_minute=100,
)
executor = registry.get_or_create(config)

# In database operation
@app.get("/api/data/{id}")
async def get_data(id: str):
    try:
        result = await executor.execute_async(
            db.query,
            id=id,
        )
        return result
    except RetryableException as e:
        return {"error": "Service temporarily unavailable"}
```

## Monitoring and Metrics

### Circuit Breaker Metrics

```python
registry = get_circuit_breaker_registry()
metrics = registry.get_all_metrics()

for name, metric in metrics.items():
    print(f"{name}:")
    print(f"  State: {metric.state}")
    print(f"  Success rate: {metric.successful_requests / metric.total_requests}")
    print(f"  Consecutive failures: {metric.consecutive_failures}")
```

### Degradation Metrics

```python
strategy = get_degradation_strategy()
metrics = strategy.get_metrics()

print(f"Degradation level: {metrics.current_level}")
print(f"Enabled features: {metrics.enabled_features}")
print(f"Disabled features: {metrics.disabled_features}")
print(f"Read-only mode: {metrics.read_only_mode}")
```

### Lock Metrics

```python
manager = get_lock_manager()
metrics = manager.get_all_metrics()

for name, metric in metrics.items():
    print(f"{name}:")
    print(f"  Active locks: {metric.active_locks}")
    print(f"  Average hold time: {metric.average_hold_time:.2f}s")
```

### Retry Metrics

```python
registry = get_retry_registry()
metrics = registry.get_all_metrics()

for name, metric in metrics.items():
    print(f"{name}:")
    print(f"  Success rate: {metric.successful_attempts / metric.total_attempts}")
    print(f"  Budget remaining: {executor.get_budget_status()['remaining']}")
```

## API Endpoints for Monitoring

Add these endpoints to backend/app/api/stability.py:

```python
from fastapi import APIRouter
from backend.app.core.stability_circuit_breaker import get_circuit_breaker_registry
from backend.app.core.stability_degradation import get_degradation_strategy
from backend.app.core.stability_distributed_lock import get_lock_manager
from backend.app.core.stability_retry import get_retry_registry

router = APIRouter(prefix="/api/stability", tags=["stability"])

@router.get("/circuit-breakers")
async def get_circuit_breakers():
    registry = get_circuit_breaker_registry()
    return registry.get_all_metrics()

@router.get("/degradation")
async def get_degradation():
    strategy = get_degradation_strategy()
    return {
        "metrics": strategy.get_metrics(),
        "features": strategy.get_all_feature_status(),
    }

@router.get("/locks")
async def get_locks():
    manager = get_lock_manager()
    return manager.get_all_metrics()

@router.get("/retries")
async def get_retries():
    registry = get_retry_registry()
    return registry.get_all_metrics()

@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(name: str):
    registry = get_circuit_breaker_registry()
    breaker = registry.get(name)
    if breaker:
        breaker.reset()
        return {"status": "reset"}
    return {"error": "Circuit breaker not found"}

@router.post("/degradation/recover")
async def recover_degradation():
    strategy = get_degradation_strategy()
    strategy.recover()
    return {"status": "recovered"}
```

## Testing

Run the comprehensive test suite:

```bash
pytest backend/app/core/test_stability_enhancements.py -v
```

Test coverage includes:
- Circuit breaker state transitions
- Degradation level changes
- Lock acquisition and release
- Retry with exponential backoff
- Budget exhaustion
- Integration between modules

## Best Practices

1. Circuit Breaker
   - Use for external service calls
   - Set appropriate failure thresholds
   - Monitor state transitions
   - Implement fallback logic

2. Degradation
   - Register all features upfront
   - Mark critical features appropriately
   - Implement fallback implementations
   - Use caching for read operations

3. Distributed Lock
   - Use for critical sections only
   - Set reasonable timeouts
   - Enable auto-renewal for long operations
   - Always release locks in finally blocks

4. Retry
   - Use exponential backoff for I/O operations
   - Set appropriate retry budgets
   - Classify exceptions as retryable
   - Monitor retry metrics

## Failure Injection Testing

For chaos engineering and resilience testing:

```python
from backend.app.core.stability_circuit_breaker import CircuitBreakerException

# Simulate circuit breaker open
def test_circuit_breaker_failure():
    breaker = get_circuit_breaker_registry().get("test_service")
    breaker.state = CircuitBreakerState.OPEN

    with pytest.raises(CircuitBreakerException):
        breaker.call(lambda: "success")

# Simulate degradation
def test_degradation_fallback():
    strategy = get_degradation_strategy()
    strategy.disable_feature("advanced_search")

    assert not strategy.is_feature_enabled("advanced_search")
```

## Performance Considerations

1. Circuit Breaker
   - Minimal overhead in CLOSED state
   - Fast rejection in OPEN state
   - Thread-safe with RLock

2. Degradation
   - O(1) feature status lookup
   - Efficient cache with TTL
   - Minimal memory footprint

3. Distributed Lock
   - Redis-based for scalability
   - Atomic Lua scripts for safety
   - Automatic expiration prevents deadlocks

4. Retry
   - Configurable backoff strategies
   - Budget-based rate limiting
   - Efficient async support

## Troubleshooting

### Circuit Breaker stuck in OPEN state
- Check timeout configuration
- Verify underlying service is recovering
- Use reset endpoint to manually recover

### High retry count
- Check retry budget configuration
- Verify retryable exception classification
- Monitor underlying service health

### Lock contention
- Increase lock timeout if operations are slow
- Enable auto-renewal for long operations
- Monitor lock hold times

### Degradation not triggering
- Verify feature registration
- Check degradation level thresholds
- Monitor system metrics

## Future Enhancements

1. Adaptive thresholds based on system metrics
2. Machine learning-based failure prediction
3. Distributed tracing integration
4. Advanced metrics aggregation
5. Automatic remediation actions
"""

# This is a documentation file - no executable code
