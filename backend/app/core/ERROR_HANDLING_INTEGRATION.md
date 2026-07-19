"""
Error Handling Integration Guide

This document explains how to integrate the unified error handling mechanism
into existing X-Agent modules.
"""

# Error Handling Integration Guide

## Overview

This guide explains how to integrate the unified error handling mechanism into existing X-Agent modules and services.

## Quick Start

### 1. Import Required Modules

```python
from backend.app.core.exceptions import (
    XAgentException,
    NetworkError,
    NotFoundError,
    ValidationError,
)
from backend.app.core.retry import retry, RetryConfig, ExponentialBackoffRetry
from backend.app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker_registry,
)
from backend.app.core.fallback import get_degradation_policy
from backend.app.core.error_monitor import get_error_monitor
```

### 2. Replace Existing Exception Handling

**Before:**
```python
class LLMBackendError(RuntimeError):
    """Raised when a provider backend cannot complete a chat request."""
    pass

try:
    response = await client.responses.create(...)
except Exception as exc:
    raise LLMBackendError(f"LLM call failed: {exc}") from exc
```

**After:**
```python
from backend.app.core.exceptions import NetworkError, ErrorCode

try:
    response = await client.responses.create(...)
except Exception as exc:
    raise NetworkError(
        f"LLM call failed: {exc}",
        error_code=ErrorCode.SERVICE_UNAVAILABLE,
    ) from exc
```

### 3. Add Retry Decorator

**Before:**
```python
async def call_llm(messages, tools):
    return await llm_router.chat(messages, tools)
```

**After:**
```python
from backend.app.core.retry import retry

@retry(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
)
async def call_llm(messages, tools):
    return await llm_router.chat(messages, tools)
```

### 4. Add Circuit Breaker

**Before:**
```python
async def chat(self, messages, tools):
    for backend in self._backends:
        try:
            return await backend.chat(messages, tools)
        except LLMBackendError:
            continue
    raise LLMBackendError("No backend available")
```

**After:**
```python
async def chat(self, messages, tools):
    breaker = await get_circuit_breaker_registry().get_or_create("llm_router")
    return await breaker.call(self._call_backends, messages, tools)

async def _call_backends(self, messages, tools):
    for backend in self._backends:
        try:
            return await backend.chat(messages, tools)
        except NetworkError:
            continue
    raise NetworkError("No backend available")
```

### 5. Add Error Monitoring

**Before:**
```python
async def process_request(self, request):
    try:
        return await self.handle_request(request)
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise
```

**After:**
```python
async def process_request(self, request):
    monitor = get_error_monitor()
    start_time = time.time()
    
    try:
        return await self.handle_request(request)
    except XAgentException as e:
        duration = time.time() - start_time
        await monitor.record_error(e, duration=duration)
        logger.error(f"Request failed: {e}")
        raise
```

## Integration Patterns

### Pattern 1: LLM Service Integration

```python
from backend.app.core.llm_resilience import build_resilient_llm_router
from backend.app.core.llm import build_llm_router

# In your initialization code
base_router = build_llm_router(
    llm_backend="auto",
    fallback_order="openai,deepseek,mock",
    openai_api_key=settings.OPENAI_API_KEY,
    openai_model="gpt-4",
    deepseek_api_key=settings.DEEPSEEK_API_KEY,
    deepseek_model="deepseek-chat",
    deepseek_base_url="https://api.deepseek.com",
)

# Add resilience features
self.llm_router = build_resilient_llm_router(
    base_router,
    enable_retry=True,
    enable_circuit_breaker=True,
    enable_degradation=True,
)

# Use in your code
response = await self.llm_router.chat(messages, tools)
```

### Pattern 2: Database Service Integration

```python
from backend.app.core.retry import retry
from backend.app.core.exceptions import DatabaseError
from backend.app.core.error_handling_config import ServiceConfigurations

class DatabaseService:
    def __init__(self):
        self.config = ServiceConfigurations.DATABASE_SERVICE
        self.retry_config = self.config["retry"]
    
    @retry(
        max_attempts=3,
        initial_delay=0.1,
        max_delay=1.0,
        timeout=5.0,
    )
    async def query(self, sql, params=None):
        try:
            return await self._execute_query(sql, params)
        except Exception as e:
            raise DatabaseError(f"Query failed: {e}") from e
    
    async def _execute_query(self, sql, params):
        # Actual database query
        pass
```

### Pattern 3: Memory Service Integration

```python
from backend.app.core.fallback import get_degradation_policy
from backend.app.core.circuit_breaker import get_circuit_breaker_registry

class MemoryService:
    def __init__(self):
        self.degradation_policy = get_degradation_policy()
        self.circuit_breaker_registry = get_circuit_breaker_registry()
    
    async def search(self, query):
        breaker = await self.circuit_breaker_registry.get_or_create("memory_search")
        
        try:
            return await breaker.call(self._search_impl, query)
        except ServiceUnavailableError:
            # Use degradation
            return await self.degradation_policy.apply_degradation(
                f"memory_search_{query}",
                self._search_impl,
                query,
                use_cache=True,
                use_default=True,
            )
    
    async def _search_impl(self, query):
        # Actual search implementation
        pass
```

### Pattern 4: API Endpoint Integration

```python
from fastapi import APIRouter, HTTPException
from backend.app.core.exceptions import XAgentException, ErrorCode
from backend.app.core.error_monitor import get_error_monitor

router = APIRouter()
monitor = get_error_monitor()

@router.post("/api/agents")
async def create_agent(request: CreateAgentRequest):
    try:
        agent = await agent_service.create(request)
        return agent
    
    except ValidationError as e:
        await monitor.record_error(e)
        raise HTTPException(status_code=400, detail=str(e))
    
    except AlreadyExistsError as e:
        await monitor.record_error(e)
        raise HTTPException(status_code=409, detail=str(e))
    
    except XAgentException as e:
        await monitor.record_error(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error: {e.error_code.value}",
        )
```

### Pattern 5: Compensating Transaction Integration

```python
from backend.app.core.recovery import CompensatingTransaction

async def create_agent_with_resources(agent_config):
    transaction = CompensatingTransaction()
    
    # Add operations with compensations
    transaction.add_operation(
        create_agent,
        agent_config,
        compensation=delete_agent,
    )
    
    transaction.add_operation(
        allocate_resources,
        agent_config.resource_requirements,
        compensation=deallocate_resources,
    )
    
    transaction.add_operation(
        initialize_memory,
        agent_config.memory_config,
        compensation=cleanup_memory,
    )
    
    try:
        results = await transaction.execute()
        return results[0]  # Return created agent
    except Exception as e:
        # Compensations are automatically executed
        logger.error(f"Agent creation failed, compensating: {e}")
        raise
```

### Pattern 6: Feature Flag Integration

```python
from backend.app.core.fallback import get_degradation_policy

class AdvancedSearchService:
    def __init__(self):
        self.degradation_policy = get_degradation_policy()
    
    async def search(self, query):
        flag = await self.degradation_policy.feature_flags.get("advanced_search")
        
        if flag:
            return await flag.execute_if_enabled(
                self._advanced_search,
                query,
                fallback=self._basic_search,
            )
        else:
            return await self._basic_search(query)
    
    async def _advanced_search(self, query):
        # Advanced search with ML models
        pass
    
    async def _basic_search(self, query):
        # Basic keyword search
        pass
```

## Module-Specific Integration

### LLM Module (backend/app/core/llm.py)

**Changes:**
1. Replace `LLMBackendError` with `NetworkError`
2. Add `@retry` decorator to `chat` methods
3. Wrap router with circuit breaker
4. Add error monitoring

**Example:**
```python
from backend.app.core.exceptions import NetworkError, ErrorCode
from backend.app.core.retry import retry
from backend.app.core.error_monitor import get_error_monitor

class OpenAIResponsesBackend(BaseLLMBackend):
    @retry(max_attempts=3, initial_delay=1.0, max_delay=10.0)
    async def chat(self, messages, tools):
        monitor = get_error_monitor()
        start_time = time.time()
        
        try:
            # Existing implementation
            response = await client.responses.create(...)
            return response
        except Exception as exc:
            duration = time.time() - start_time
            error = NetworkError(f"OpenAI API error: {exc}")
            await monitor.record_error(error, duration=duration)
            raise error from exc
```

### Memory Module (backend/app/core/memory.py)

**Changes:**
1. Add circuit breaker for memory operations
2. Add degradation for search operations
3. Add error monitoring
4. Add compensating transactions for complex operations

**Example:**
```python
from backend.app.core.circuit_breaker import get_circuit_breaker_registry
from backend.app.core.fallback import get_degradation_policy

class MemoryManager:
    async def search(self, query):
        breaker = await get_circuit_breaker_registry().get_or_create("memory_search")
        degradation = get_degradation_policy()
        
        try:
            return await breaker.call(self._search_impl, query)
        except ServiceUnavailableError:
            return await degradation.apply_degradation(
                f"memory_{query}",
                self._search_impl,
                query,
                use_cache=True,
            )
```

### API Module (backend/app/api/errors.py)

**Changes:**
1. Update error handler to use new exception types
2. Add error monitoring
3. Add circuit breaker metrics endpoint

**Example:**
```python
from backend.app.core.exceptions import XAgentException
from backend.app.core.error_monitor import get_error_monitor

async def xagent_exception_handler(request: Request, exc: XAgentException):
    monitor = get_error_monitor()
    await monitor.record_error(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": exc.error_code.value,
            "message": exc.message,
            "error_id": exc.error_id,
        },
    )

@router.get("/api/metrics/errors")
async def get_error_metrics():
    monitor = get_error_monitor()
    return await monitor.get_all_stats()

@router.get("/api/metrics/circuit-breakers")
async def get_circuit_breaker_metrics():
    registry = get_circuit_breaker_registry()
    return await registry.get_all_metrics()
```

## Testing Integration

### Unit Tests

```python
import pytest
from backend.app.core.retry import retry
from backend.app.core.exceptions import NetworkError

@pytest.mark.asyncio
async def test_llm_service_with_retry():
    call_count = 0
    
    @retry(max_attempts=3, initial_delay=0.01)
    async def failing_llm_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise NetworkError("Connection failed")
        return "success"
    
    result = await failing_llm_call()
    assert result == "success"
    assert call_count == 2
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_memory_service_with_degradation():
    service = MemoryService()
    
    # Simulate service failure
    with patch.object(service, '_search_impl', side_effect=NetworkError()):
        result = await service.search("test query")
        
        # Should return degraded response
        assert result is not None
```

## Migration Checklist

- [ ] Replace all custom exception classes with unified exceptions
- [ ] Add `@retry` decorators to network-dependent functions
- [ ] Wrap external service calls with circuit breakers
- [ ] Add error monitoring to critical paths
- [ ] Add feature flags for new features
- [ ] Update API error handlers
- [ ] Add metrics endpoints
- [ ] Update tests to use new exception types
- [ ] Document error handling in module docstrings
- [ ] Add error handling to configuration
- [ ] Test degradation scenarios
- [ ] Monitor error rates in production

## Troubleshooting

### Issue: Exceptions Not Being Caught

**Cause**: Using old exception types

**Solution**: Update imports to use new exception types from `backend.app.core.exceptions`

### Issue: Retries Not Working

**Cause**: Exception not marked as retryable

**Solution**: Ensure exception has `is_retryable=True` or add custom `retry_condition`

### Issue: Circuit Breaker Always Open

**Cause**: Failure threshold too low

**Solution**: Increase `failure_threshold` in `CircuitBreakerConfig`

### Issue: Degradation Not Triggered

**Cause**: Cache not populated or defaults not set

**Solution**: Ensure cache is populated before failures or set default values

## Performance Considerations

1. **Retry Overhead**: Retries add latency. Use appropriate `max_attempts` and `initial_delay`.
2. **Circuit Breaker Overhead**: Minimal overhead. Use for external services.
3. **Error Monitoring**: Async monitoring has minimal impact. Monitor error rates.
4. **Degradation Cache**: Cache TTL affects memory usage. Balance between freshness and memory.

## Security Considerations

1. **Error Messages**: Don't expose sensitive information in error messages.
2. **Error Logging**: Log errors securely without exposing credentials.
3. **Circuit Breaker**: Prevents information leakage through timing attacks.
4. **Degradation**: Ensure degraded responses don't expose sensitive data.

## Next Steps

1. Start with LLM module integration
2. Add error monitoring to critical paths
3. Integrate circuit breakers for external services
4. Add feature flags for new features
5. Monitor error rates and adjust configurations
6. Document error handling in your modules
7. Train team on error handling best practices
