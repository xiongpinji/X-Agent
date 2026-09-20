"""
Error Handling Quick Reference Card

One-page cheat sheet for common error handling tasks.
"""

# X-Agent Error Handling - Quick Reference Card

## Exception Types at a Glance

### Network Errors (Retryable)
```python
from backend.app.core.exceptions import (
    NetworkError,
    ConnectionError,
    TimeoutError,
    ServiceUnavailableError,
    RateLimitError,
)

# Use when external service fails
raise NetworkError("API call failed")
raise ConnectionError("Cannot connect to service")
raise TimeoutError("Request timed out")
raise ServiceUnavailableError("Service is down")
raise RateLimitError("Too many requests")
```

### Business Errors (Not Retryable)
```python
from backend.app.core.exceptions import (
    BusinessError,
    InvalidStateError,
    OperationNotAllowedError,
    ResourceExhaustedError,
)

# Use for business logic violations
raise InvalidStateError("Agent not in READY state")
raise OperationNotAllowedError("Cannot delete system agent")
raise ResourceExhaustedError("Memory quota exceeded")
```

### Resource Errors
```python
from backend.app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ConflictError,
    InsufficientResourcesError,
)

# Use for resource-related issues
raise NotFoundError("Agent not found")
raise AlreadyExistsError("Agent already exists")
raise ConflictError("Concurrent modification")
raise InsufficientResourcesError("Not enough memory")
```

### Validation Errors
```python
from backend.app.core.exceptions import (
    ValidationError,
    InvalidInputError,
    InvalidFormatError,
)

# Use for input validation
raise InvalidInputError("Name cannot be empty")
raise InvalidFormatError("Invalid JSON")
```

---

## Retry Decorator

### Basic Usage
```python
from backend.app.core.retry import retry

@retry(max_attempts=3, initial_delay=1.0)
async def call_api():
    return await api.fetch()
```

### Advanced Usage
```python
@retry(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    timeout=60.0,
    retryable_exceptions=(NetworkError,),
)
async def call_external_service():
    return await service.call()
```

### Pre-configured Retry Configs
```python
from backend.app.core.error_handling_config import (
    TRANSIENT_FAILURE_RETRY,
    RATE_LIMITED_API_RETRY,
    DATABASE_OPERATION_RETRY,
    LLM_API_RETRY,
)

# Use pre-configured settings
@retry(**TRANSIENT_FAILURE_RETRY.__dict__)
async def call_service():
    pass
```

---

## Circuit Breaker

### Basic Usage
```python
from backend.app.core.circuit_breaker import get_circuit_breaker_registry

registry = get_circuit_breaker_registry()
breaker = await registry.get_or_create("service_name")
result = await breaker.call(service_function)
```

### With Configuration
```python
from backend.app.core.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
)
breaker = await registry.get_or_create("service", config)
```

### Get Metrics
```python
metrics = breaker.get_metrics()
print(f"State: {metrics.state}")
print(f"Failures: {metrics.failure_count}")
```

---

## Graceful Degradation

### Cache Fallback
```python
from backend.app.core.fallback import CacheFallback

fallback = CacheFallback(ttl=300)
result = await fallback.get_or_fetch(
    "cache_key",
    fetch_fresh_data,
    use_stale=True,
)
```

### Default Value Fallback
```python
from backend.app.core.fallback import DefaultValueFallback

fallback = DefaultValueFallback({
    "user_prefs": {"theme": "light"},
})
result = await fallback.get_with_default(
    "user_prefs",
    fetch_user_prefs,
)
```

### Feature Flags
```python
from backend.app.core.fallback import get_degradation_policy

policy = get_degradation_policy()
flag = await policy.feature_flags.register("new_feature", enabled=True)

result = await flag.execute_if_enabled(
    new_implementation,
    fallback=old_implementation,
)
```

---

## Error Monitoring

### Record Error
```python
from backend.app.core.error_monitor import get_error_monitor

monitor = get_error_monitor()
await monitor.record_error(exception, duration=elapsed_time)
```

### Record Retry
```python
await monitor.record_retry(success=True, retry_count=2)
```

### Get Statistics
```python
error_stats = await monitor.get_error_stats()
retry_stats = await monitor.get_retry_stats()
degradation_stats = await monitor.get_degradation_stats()
all_stats = await monitor.get_all_stats()
```

### Get Error Rate
```python
error_rate = await monitor.get_error_rate(window_seconds=60)
print(f"Error rate: {error_rate:.2%}")
```

---

## Common Patterns

### Pattern 1: Retry + Circuit Breaker
```python
@retry(max_attempts=3, initial_delay=1.0)
async def call_service():
    breaker = await get_circuit_breaker_registry().get_or_create("service")
    return await breaker.call(external_service.call)
```

### Pattern 2: Fallback + Degradation
```python
async def get_data():
    try:
        return await fetch_fresh_data()
    except Exception:
        policy = get_degradation_policy()
        return await policy.apply_degradation(
            "data_key",
            fetch_fresh_data,
            use_cache=True,
            use_default=True,
        )
```

### Pattern 3: Compensating Transaction
```python
from backend.app.core.recovery import CompensatingTransaction

transaction = CompensatingTransaction()
transaction.add_operation(create_resource, compensation=delete_resource)
transaction.add_operation(update_db, compensation=rollback_db)

try:
    results = await transaction.execute()
except Exception:
    # Compensations automatically executed
    pass
```

### Pattern 4: Error Monitoring
```python
monitor = get_error_monitor()
start_time = time.time()

try:
    result = await operation()
except XAgentException as e:
    duration = time.time() - start_time
    await monitor.record_error(e, duration=duration)
    raise
```

---

## Configuration Quick Reference

### For LLM Service
```python
from backend.app.core.error_handling_config import ServiceConfigurations

config = ServiceConfigurations.LLM_SERVICE
# {
#     "retry": LLM_API_RETRY,
#     "circuit_breaker": LLM_SERVICE_CIRCUIT_BREAKER,
#     "enable_degradation": True,
#     "cache_ttl": 300,
# }
```

### For Database Service
```python
config = ServiceConfigurations.DATABASE_SERVICE
# {
#     "retry": DATABASE_OPERATION_RETRY,
#     "circuit_breaker": DATABASE_CIRCUIT_BREAKER,
#     "enable_degradation": False,
#     "cache_ttl": 0,
# }
```

### For Memory Service
```python
config = ServiceConfigurations.MEMORY_SERVICE
# {
#     "retry": TRANSIENT_FAILURE_RETRY,
#     "circuit_breaker": MEMORY_SERVICE_CIRCUIT_BREAKER,
#     "enable_degradation": True,
#     "cache_ttl": 300,
# }
```

### For External API
```python
config = ServiceConfigurations.EXTERNAL_API
# {
#     "retry": RATE_LIMITED_API_RETRY,
#     "circuit_breaker": EXTERNAL_API_CIRCUIT_BREAKER,
#     "enable_degradation": True,
#     "cache_ttl": 300,
# }
```

---

## Environment-Specific Settings

### Development
```python
from backend.app.core.error_handling_config import EnvironmentConfigurations

env_config = EnvironmentConfigurations.DEVELOPMENT
# Lenient, verbose logging, quick retries
```

### Staging
```python
env_config = EnvironmentConfigurations.STAGING
# Balanced settings
```

### Production
```python
env_config = EnvironmentConfigurations.PRODUCTION
# Strict, resilient, comprehensive monitoring
```

---

## Testing

### Test Retry
```python
@pytest.mark.asyncio
async def test_retry():
    call_count = 0
    
    @retry(max_attempts=3, initial_delay=0.01)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise NetworkError("Failed")
        return "success"
    
    result = await failing_func()
    assert result == "success"
    assert call_count == 2
```

### Test Circuit Breaker
```python
@pytest.mark.asyncio
async def test_circuit_breaker():
    async def failing_func():
        raise NetworkError("Failed")
    
    config = CircuitBreakerConfig(failure_threshold=2)
    breaker = CircuitBreaker("test", config)
    
    # Trigger failures
    for _ in range(2):
        with pytest.raises(NetworkError):
            await breaker.call(failing_func)
    
    # Circuit should be open
    assert breaker.metrics.state == CircuitBreakerState.OPEN
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Exceptions not caught | Wrong exception type | Update imports to use new types |
| Retries not working | Exception not retryable | Add `is_retryable=True` or custom condition |
| Circuit breaker always open | Threshold too low | Increase `failure_threshold` |
| Degradation not triggered | Cache empty or no defaults | Populate cache or set defaults |
| High latency | Too many retries | Reduce `max_attempts` or `initial_delay` |
| Memory usage high | Large error history | Reduce `max_history` in ErrorMonitor |

---

## Key Metrics to Monitor

```python
# Error rate (errors per second)
error_rate = await monitor.get_error_rate(window_seconds=60)

# Error distribution
error_stats = await monitor.get_error_stats()

# Retry success rate
retry_stats = await monitor.get_retry_stats()
success_rate = retry_stats["success_rate"]

# Circuit breaker state
breaker_metrics = await registry.get_all_metrics()

# Degradation events
degradation_stats = await monitor.get_degradation_stats()
```

---

## Alert Thresholds

```python
# Alert if error rate > 1% in 60 seconds
ERROR_RATE_THRESHOLD = 0.01

# Alert if circuit breaker open > 5 minutes
CIRCUIT_BREAKER_OPEN_THRESHOLD = 300

# Alert if retry success rate < 50%
RETRY_SUCCESS_RATE_THRESHOLD = 0.5

# Alert if degradation > 10 minutes
DEGRADATION_DURATION_THRESHOLD = 600
```

---

## Imports Cheat Sheet

```python
# Exceptions
from backend.app.core.exceptions import (
    XAgentException,
    NetworkError,
    NotFoundError,
    ValidationError,
    ErrorCode,
    ErrorSeverity,
)

# Retry
from backend.app.core.retry import retry, RetryConfig

# Circuit Breaker
from backend.app.core.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker_registry,
)

# Degradation
from backend.app.core.fallback import get_degradation_policy

# Monitoring
from backend.app.core.error_monitor import get_error_monitor

# Configuration
from backend.app.core.error_handling_config import (
    ServiceConfigurations,
    EnvironmentConfigurations,
)

# LLM Integration
from backend.app.core.llm_resilience import build_resilient_llm_router
```

---

## Documentation Links

- **Best Practices**: `backend/app/core/ERROR_HANDLING_GUIDE.md`
- **Integration Guide**: `backend/app/core/ERROR_HANDLING_INTEGRATION.md`
- **File Manifest**: `ERROR_HANDLING_FILE_MANIFEST.md`
- **Summary**: `UNIFIED_ERROR_HANDLING_SUMMARY.md`

---

## Quick Links

- **Exception Hierarchy**: `backend/app/core/exceptions.py`
- **Retry Mechanism**: `backend/app/core/retry.py`
- **Circuit Breaker**: `backend/app/core/circuit_breaker.py`
- **Graceful Degradation**: `backend/app/core/fallback.py`
- **Error Monitoring**: `backend/app/core/error_monitor.py`
- **Configuration**: `backend/app/core/error_handling_config.py`
- **Tests**: `tests/test_error_handling.py`

---

**Last Updated**: 2026-05-27
**Status**: ✅ Production Ready
