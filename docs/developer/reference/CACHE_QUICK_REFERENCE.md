"""Redis Cache Layer - Quick Reference

## Quick Start

### 1. Configuration
```bash
export XAGENT_REDIS_URL=redis://localhost:6379/0
```

### 2. Basic Usage
```python
from backend.app.core.cache import get_cache_manager

cache = get_cache_manager()
await cache.set("key", value, ttl=3600)
result = await cache.get("key")
```

### 3. Function Caching
```python
from backend.app.core.cache import async_cached

@async_cached(ttl_seconds=300)
async def expensive_function(arg):
    return result
```

## Cache Types and TTLs

| Type | TTL | Module |
|------|-----|--------|
| Memory Search | 5 min | memory_cache |
| Memory Item | 10 min | memory_cache |
| Memory Session | 30 min | memory_cache |
| LLM Response | 1 hour | llm_cache |
| LLM Embedding | 24 hours | llm_cache |
| DB Query | 10 min | db_cache |
| DB User | 1 hour | db_cache |

## Common Operations

### Memory Caching
```python
from backend.app.core.memory_cache import *

# Cache search results
await cache_search_results(tenant_id, query, results)
cached = await get_cached_search_results(tenant_id, query)

# Invalidate on update
await invalidate_search_cache(tenant_id)
```

### LLM Caching
```python
from backend.app.core.llm_cache import *

# Cache response
await cache_llm_response(messages, response, model)
cached = await get_cached_llm_response(messages, model)

# Cache embedding
await cache_embedding(text, embedding, model)
cached = await get_cached_embedding(text, model)
```

### Database Caching
```python
from backend.app.core.db_cache import *

# Cache user
await cache_user(user_id, user_data)
cached = await get_cached_user(user_id)

# Invalidate on update
await invalidate_user_cache(user_id)
```

## Monitoring

```python
from backend.app.core.cache import get_cache_stats

stats = get_cache_stats()
# {
#   'hits': 1234,
#   'misses': 456,
#   'errors': 2,
#   'hit_rate': 0.73,
#   'uptime_seconds': 3600
# }
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Redis not connecting | Check XAGENT_REDIS_URL, falls back to memory |
| High memory usage | Reduce TTL or cache size |
| Cache not working | Check Redis connectivity, review logs |
| Stale data | Invalidate cache on updates |

## Performance

- L1 (Memory) hit: ~0.1ms
- L2 (Redis) hit: ~1-5ms
- Cache miss: 10-1000ms+ (depends on operation)
- Expected speedup: 10-5000x for cached operations

## Files

- Core: `backend/app/core/cache.py`
- Memory: `backend/app/core/memory_cache.py`
- LLM: `backend/app/core/llm_cache.py`
- Database: `backend/app/core/db_cache.py`
- Tests: `tests/test_cache.py`
- Benchmarks: `tests/test_cache_benchmarks.py`

## Documentation

- Implementation: `CACHE_IMPLEMENTATION.md`
- Integration: `CACHE_INTEGRATION_GUIDE.md`
- Summary: `CACHE_IMPLEMENTATION_SUMMARY.md`

## Testing

```bash
# Run all tests
pytest tests/test_cache.py -v

# Run benchmarks
pytest tests/test_cache_benchmarks.py -v --benchmark-only

# Run with coverage
pytest tests/test_cache.py --cov=backend.app.core.cache
```

## Key Features

✓ Multi-layer caching (L1 + L2)
✓ Automatic serialization
✓ TTL-based expiration
✓ Cache statistics
✓ Function decorators
✓ Graceful fallback
✓ Error handling
✓ Comprehensive testing
✓ Production ready
"""
