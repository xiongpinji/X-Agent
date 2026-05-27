"""
Error Handling Best Practices and Configuration Guide for X-Agent

This document provides comprehensive guidance on using the unified error handling
mechanism in X-Agent.
"""

# Error Handling Best Practices and Configuration Guide

## Overview

X-Agent implements a comprehensive, unified error handling mechanism that provides:

- **Hierarchical Exception System**: Organized exception types for different error categories
- **Intelligent Retry Strategies**: Exponential backoff with jitter for transient failures
- **Circuit Breaker Pattern**: Automatic fault detection and recovery
- **Error Recovery Strategies**: Multiple recovery approaches including retry, fallback, and compensation
- **Graceful Degradation**: Service continues with reduced functionality during failures
- **Error Monitoring**: Comprehensive error tracking and metrics collection

## Exception Hierarchy

### Base Exception: `XAgentException`

All X-Agent exceptions inherit from `XAgentException`, which provides:
- Error code (ErrorCode enum)
- Severity level (ErrorSeverity enum)
- Retryability flag
- Error context with user/tenant/correlation IDs

```python
from backend.app.core.exceptions import XAgentException, ErrorCode, ErrorSeverity

try:
    # Some operation
    pass
except XAgentException as e:
    print(f"Error: {e.message}")
    print(f"Code: {e.error_code}")
    print(f"Severity: {e.severity}")
    print(f"Retryable: {e.is_retryable}")
```

### Exception Categories

#### 1. Business Exceptions
Used for business logic errors that don't indicate system failures.

```python
from backend.app.core.exceptions import (
    BusinessError,
    InvalidStateError,
    OperationNotAllowedError,
    ResourceExhaustedError,
)

# Invalid state
raise InvalidStateError("Agent is not in READY state")

# Operation not allowed
raise OperationNotAllowedError("Cannot delete system agent")

# Resource exhausted
raise ResourceExhaustedError("Memory quota exceeded", is_retryable=True)
```

#### 2. System Exceptions
Used for internal system errors.

```python
from backend.app.core.exceptions import (
    SystemError,
    ConfigurationError,
    InitializationError,
)

# Configuration error
raise ConfigurationError("Missing required configuration: LLM_API_KEY")

# Initialization error
raise InitializationError("Failed to initialize database connection")
```

#### 3. Network Exceptions
Used for network-related failures (automatically retryable).

```python
from backend.app.core.exceptions import (
    NetworkError,
    ConnectionError,
    TimeoutError,
    ServiceUnavailableError,
    RateLimitError,
)

# Connection error
raise ConnectionError("Failed to connect to LLM service")

# Timeout
raise TimeoutError("LLM request timed out after 30s")

# Service unavailable
raise ServiceUnavailableError("LLM service is temporarily unavailable")

# Rate limit
raise RateLimitError("API rate limit exceeded, retry after 60s")
```

#### 4. Resource Exceptions
Used for resource-related errors.

```python
from backend.app.core.exceptions import (
    NotFoundError,
    AlreadyExistsError,
    ConflictError,
    InsufficientResourcesError,
)

# Not found
raise NotFoundError("Agent with ID 'agent123' not found")

# Already exists
raise AlreadyExistsError("Agent with name 'MyAgent' already exists")

# Conflict
raise ConflictError("Cannot update agent: concurrent modification detected")

# Insufficient resources
raise InsufficientResourcesError("Insufficient memory for operation")
```

#### 5. Validation Exceptions
Used for input validation errors.

```python
from backend.app.core.exceptions import (
    ValidationError,
    InvalidInputError,
    InvalidFormatError,
)

# Invalid input
raise InvalidInputError("Agent name must not be empty")

# Invalid format
raise InvalidFormatError("Invalid JSON format in request body")
```

## Retry Mechanism

### Using the @retry Decorator

The `@retry` decorator automatically retries failed operations with exponential backoff.

```python
from backend.app.core.retry import retry
from backend.app.core.exceptions import NetworkError

@retry(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    timeout=30.0,
)
async def call_external_api():
    # This will be retried up to 3 times with exponential backoff
    response = await api.fetch()
    return response
```

### Retry Configuration

```python
from backend.app.core.retry import RetryConfig, ExponentialBackoffRetry

config = RetryConfig(
    max_attempts=3,              # Maximum retry attempts
    initial_delay=1.0,           # Initial delay in seconds
    max_delay=60.0,              # Maximum delay in seconds
    exponential_base=2.0,        # Exponential backoff base
    jitter=True,                 # Add randomness to prevent thundering herd
    jitter_range=(0.5, 1.5),    # Jitter multiplier range
    timeout=30.0,                # Total timeout for all retries
    retryable_exceptions=(NetworkError,),  # Exception types to retry
    retry_condition=lambda e: e.is_retryable,  # Custom retry condition
)

strategy = ExponentialBackoffRetry(config)
result = await strategy.execute(some_async_function)
```

### Retry Backoff Calculation

The retry mechanism uses exponential backoff with optional jitter:

```
delay = min(initial_delay * (exponential_base ^ attempt), max_delay)
if jitter:
    delay *= random.uniform(jitter_min, jitter_max)
```

Example with default settings:
- Attempt 1: ~1.0s (with jitter: 0.5-1.5s)
- Attempt 2: ~2.0s (with jitter: 1.0-3.0s)
- Attempt 3: ~4.0s (with jitter: 2.0-6.0s)

## Circuit Breaker Pattern

### Using Circuit Breaker

The circuit breaker prevents cascading failures by stopping requests to failing services.

```python
from backend.app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker_registry,
)

# Create circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60.0,    # Try recovery after 60s
    success_threshold=2,      # Close after 2 successes in half-open
)
breaker = CircuitBreaker("llm_service", config)

# Use circuit breaker
try:
    result = await breaker.call(llm_service.chat, messages, tools)
except ServiceUnavailableError:
    # Circuit is open, service is unavailable
    logger.error("LLM service is unavailable")
```

### Circuit Breaker States

1. **CLOSED**: Normal operation, requests pass through
2. **OPEN**: Service failing, requests rejected immediately
3. **HALF_OPEN**: Testing if service recovered, limited requests allowed

### Global Circuit Breaker Registry

```python
from backend.app.core.circuit_breaker import get_circuit_breaker_registry

registry = get_circuit_breaker_registry()

# Get or create circuit breaker
breaker = await registry.get_or_create("service_name", config)

# Get metrics for all breakers
metrics = await registry.get_all_metrics()
print(metrics)

# Reset a specific breaker
await registry.reset("service_name")

# Reset all breakers
await registry.reset_all()
```

## Error Recovery Strategies

### Retry Recovery

Automatically retry the operation.

```python
from backend.app.core.recovery import RetryRecovery, RecoveryContext

recovery = RetryRecovery()
context = RecoveryContext()

try:
    result = await some_operation()
except NetworkError as e:
    result = await recovery.recover(
        e,
        context,
        some_operation,
    )
```

### Fallback Recovery

Use an alternative function when primary fails.

```python
from backend.app.core.recovery import FallbackRecovery

async def fallback_operation():
    return "fallback_result"

recovery = FallbackRecovery(fallback_operation)

try:
    result = await primary_operation()
except Exception as e:
    result = await recovery.recover(e, context)
```

### Compensating Transactions

Execute compensations if operation fails.

```python
from backend.app.core.recovery import CompensatingTransaction

transaction = CompensatingTransaction()

# Add operations with compensations
transaction.add_operation(
    create_resource,
    compensation=delete_resource,
)
transaction.add_operation(
    update_database,
    compensation=rollback_database,
)

try:
    results = await transaction.execute()
except Exception:
    # Compensations are automatically executed in reverse order
    pass
```

### Error Isolation

Isolate errors to prevent cascading failures.

```python
from backend.app.core.recovery import ErrorIsolation

isolation = ErrorIsolation(isolation_level="operation")

# Errors are caught and isolated
result = await isolation.isolate(risky_operation)

# Get isolated errors
errors = await isolation.get_isolated_errors()
```

## Graceful Degradation

### Service Degradation

Degrade service level when failures occur.

```python
from backend.app.core.fallback import ServiceDegradation, DegradationLevel

degradation = ServiceDegradation()

# Set degradation level
await degradation.set_degradation_level(DegradationLevel.REDUCED_FEATURES)

# Get degraded response
response = await degradation.get_degraded_response(
    "key",
    default_value="default_response",
)
```

### Cache Fallback

Use cached values when fresh data unavailable.

```python
from backend.app.core.fallback import CacheFallback

fallback = CacheFallback(ttl=300)  # 5 minute TTL

# Get or fetch with cache fallback
result = await fallback.get_or_fetch(
    "cache_key",
    fetch_func=fetch_fresh_data,
    use_stale=True,  # Use stale cache if fetch fails
)
```

### Default Value Fallback

Use default values when operation fails.

```python
from backend.app.core.fallback import DefaultValueFallback

fallback = DefaultValueFallback({
    "user_preferences": {"theme": "light"},
    "system_config": {"timeout": 30},
})

result = await fallback.get_with_default(
    "user_preferences",
    fetch_user_preferences,
)
```

### Feature Flags

Control feature availability for graceful degradation.

```python
from backend.app.core.fallback import FeatureFlagRegistry

registry = FeatureFlagRegistry()

# Register feature
flag = await registry.register("advanced_search", enabled=True)

# Execute with feature flag
result = await flag.execute_if_enabled(
    advanced_search_func,
    fallback=basic_search_func,
)

# Disable feature
await registry.disable("advanced_search")

# Get all flags
flags = await registry.get_all_flags()
```

## Error Monitoring

### Recording Errors

```python
from backend.app.core.error_monitor import get_error_monitor

monitor = get_error_monitor()

try:
    result = await some_operation()
except Exception as e:
    await monitor.record_error(e, duration=elapsed_time)
```

### Recording Retries

```python
await monitor.record_retry(success=True, retry_count=2)
```

### Recording Degradation

```python
await monitor.record_degradation("reduced_features", duration=60.0)
```

### Getting Statistics

```python
# Error statistics
error_stats = await monitor.get_error_stats()

# Retry statistics
retry_stats = await monitor.get_retry_stats()

# Degradation statistics
degradation_stats = await monitor.get_degradation_stats()

# All statistics
all_stats = await monitor.get_all_stats()

# Error rate in last 60 seconds
error_rate = await monitor.get_error_rate(window_seconds=60)

# Errors by severity
critical_errors = await monitor.get_errors_by_severity(ErrorSeverity.CRITICAL)

# Errors by code
not_found_errors = await monitor.get_errors_by_code(ErrorCode.RESOURCE_NOT_FOUND)
```

## Integration Examples

### LLM Service with Resilience

```python
from backend.app.core.llm_resilience import build_resilient_llm_router
from backend.app.core.llm import build_llm_router

# Build base router
base_router = build_llm_router(
    llm_backend="auto",
    fallback_order="openai,deepseek,mock",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_model="gpt-4",
    deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
    deepseek_model="deepseek-chat",
    deepseek_base_url="https://api.deepseek.com",
)

# Add resilience features
resilient_router = build_resilient_llm_router(
    base_router,
    enable_retry=True,
    enable_circuit_breaker=True,
    enable_degradation=True,
)

# Use resilient router
response = await resilient_router.chat(messages, tools)

# Get metrics
metrics = await resilient_router.get_metrics()
```

### Memory System with Degradation

```python
from backend.app.core.fallback import get_degradation_policy

policy = get_degradation_policy()

# Apply degradation policy
result = await policy.apply_degradation(
    key="memory_search",
    fetch_func=memory_service.search,
    query=search_query,
    use_cache=True,
    use_default=True,
)
```

## Configuration Best Practices

### Retry Configuration

```python
# For transient failures (network, timeouts)
TRANSIENT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
    timeout=30.0,
)

# For rate-limited APIs
RATE_LIMITED_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    initial_delay=2.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    timeout=300.0,
)

# For quick retries (database operations)
QUICK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=False,
    timeout=5.0,
)
```

### Circuit Breaker Configuration

```python
# For external APIs
API_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
)

# For database connections
DB_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=1,
)

# For cache services
CACHE_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=10,
    recovery_timeout=120.0,
    success_threshold=3,
)
```

## Error Handling Patterns

### Pattern 1: Retry with Circuit Breaker

```python
@retry(max_attempts=3, initial_delay=1.0)
async def call_external_service():
    breaker = await get_circuit_breaker_registry().get_or_create("service")
    return await breaker.call(external_service.call)
```

### Pattern 2: Fallback with Degradation

```python
async def get_data():
    try:
        return await fetch_fresh_data()
    except Exception:
        return await get_degradation_policy().apply_degradation(
            "data_key",
            fetch_fresh_data,
            use_cache=True,
            use_default=True,
        )
```

### Pattern 3: Compensating Transaction

```python
async def complex_operation():
    transaction = CompensatingTransaction()
    
    transaction.add_operation(
        step1,
        compensation=undo_step1,
    )
    transaction.add_operation(
        step2,
        compensation=undo_step2,
    )
    
    return await transaction.execute()
```

### Pattern 4: Feature Flag with Fallback

```python
async def use_feature():
    flag = await feature_registry.get("new_feature")
    return await flag.execute_if_enabled(
        new_implementation,
        fallback=old_implementation,
    )
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Error Rate**: Errors per second
2. **Error Distribution**: Errors by severity and code
3. **Retry Success Rate**: Percentage of successful retries
4. **Circuit Breaker State**: Current state of each breaker
5. **Degradation Events**: Number and duration of degradation
6. **Response Time**: Impact of retries on latency

### Alert Thresholds

```python
# Alert if error rate exceeds 1% in 60 seconds
ERROR_RATE_THRESHOLD = 0.01

# Alert if circuit breaker is open for more than 5 minutes
CIRCUIT_BREAKER_OPEN_THRESHOLD = 300

# Alert if retry success rate drops below 50%
RETRY_SUCCESS_RATE_THRESHOLD = 0.5

# Alert if degradation lasts more than 10 minutes
DEGRADATION_DURATION_THRESHOLD = 600
```

## Testing Error Handling

### Unit Tests

```python
@pytest.mark.asyncio
async def test_retry_on_transient_failure():
    call_count = 0
    
    @retry(max_attempts=3, initial_delay=0.01)
    async def failing_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise NetworkError("Connection failed")
        return "success"
    
    result = await failing_func()
    assert result == "success"
    assert call_count == 2
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_circuit_breaker_with_recovery():
    # Simulate service failures
    # Verify circuit breaker opens
    # Wait for recovery timeout
    # Verify circuit breaker recovers
    pass
```

## Troubleshooting

### Issue: Retries Not Working

**Cause**: Exception type not in `retryable_exceptions`

**Solution**: Ensure exception is retryable or add custom `retry_condition`

### Issue: Circuit Breaker Always Open

**Cause**: Failure threshold too low or service still failing

**Solution**: Increase `failure_threshold` or fix underlying service issue

### Issue: Degradation Not Triggered

**Cause**: Cache not populated or default values not set

**Solution**: Ensure cache is populated before failures or set default values

## Summary

The unified error handling mechanism provides:

1. **Comprehensive Exception System**: Organized, hierarchical exceptions
2. **Intelligent Retry**: Exponential backoff with jitter
3. **Fault Tolerance**: Circuit breaker pattern
4. **Recovery Strategies**: Multiple approaches to recover from failures
5. **Graceful Degradation**: Service continues with reduced functionality
6. **Monitoring**: Comprehensive error tracking and metrics

Use these tools to build resilient, fault-tolerant systems that gracefully handle failures.
