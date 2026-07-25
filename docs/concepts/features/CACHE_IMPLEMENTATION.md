"""Redis Cache Layer Implementation Guide

This document describes the Redis caching layer implementation for X-Agent.

## Overview

The caching layer provides:
- Multi-layer caching (L1: in-memory, L2: Redis)
- Automatic serialization (JSON/Pickle)
- TTL support with automatic expiration
- Cache statistics and monitoring
- Decorator-based caching for functions
- Fallback to in-memory cache if Redis unavailable

## Architecture

### Cache Layers

1. **L1 Cache (In-Memory)**
   - Fast local access
   - LRU eviction policy
   - Max size: 1000 items (configurable)
   - Used for frequently accessed data

2. **L2 Cache (Redis)**
   - Distributed cache for multi-instance deployments
   - Persistent across restarts
   - Shared across all instances
   - Used for expensive computations

### Cache Flow

```
Request
  ↓
L1 Cache (Memory) → Hit? Return
  ↓ Miss
L2 Cache (Redis) → Hit? Populate L1, Return
  ↓ Miss
Compute Result → Populate L1 + L2 → Return
```

## Usage Examples

### Basic Cache Operations

```python
from backend.app.core.cache import get_cache_manager

cache = get_cache_manager()

# Set value with TTL
await cache.set("user:123", {"name": "John", "email": "john@example.com"}, ttl=3600)

# Get value
user = await cache.get("user:123")

# Check existence
exists = await cache.exists("user:123")

# Delete value
await cache.delete("user:123")

# Clear all cache
await cache.clear()

# Clear by pattern
await cache.invalidate_pattern("user:*")
```

### Function Caching with Decorators

```python
from backend.app.core.cache import async_cached, cached

# Cache async function results
@async_cached(ttl_seconds=300, key_prefix="memory")
async def search_memories(tenant_id: str, query: str) -> list[MemoryItem]:
    # Expensive search operation
    return await memory_system.search(tenant_id, query)

# Cache sync function results
@cached(ttl_seconds=600, key_prefix="user")
def get_user_profile(user_id: str) -> dict:
    # Database query
    return db.get_user(user_id)
```

### Memory System Caching

```python
from backend.app.core.memory_cache import (
    cache_memory_item,
    get_cached_memory_item,
    cache_search_results,
    get_cached_search_results,
)

# Cache memory item
await cache_memory_item(memory_item)

# Retrieve cached memory
cached_item = await get_cached_memory_item(memory_id)

# Cache search results
await cache_search_results(
    tenant_id="tenant1",
    query="important information",
    results=search_hits,
    top_k=10
)

# Get cached search results
cached_results = await get_cached_search_results(
    tenant_id="tenant1",
    query="important information",
    top_k=10
)
```

### LLM Response Caching

```python
from backend.app.core.llm_cache import (
    cache_llm_response,
    get_cached_llm_response,
    cache_embedding,
    get_cached_embedding,
)

# Cache LLM response
messages = [{"role": "user", "content": "Hello"}]
response = await llm.chat(messages)
await cache_llm_response(messages, response, model="gpt-4")

# Get cached response
cached = await get_cached_llm_response(messages, model="gpt-4")

# Cache embeddings
embedding = await embedding_model.embed("text")
await cache_embedding("text", embedding, model="text-embedding-3-small")

# Get cached embedding
cached_embedding = await get_cached_embedding("text", model="text-embedding-3-small")
```

### Database Query Caching

```python
from backend.app.core.db_cache import (
    cache_user,
    get_cached_user,
    cache_tenant,
    get_cached_tenant,
    invalidate_user_cache,
)

# Cache user data
user_data = db.get_user(user_id)
await cache_user(user_id, user_data)

# Get cached user
cached_user = await get_cached_user(user_id)

# Cache tenant data
tenant_data = db.get_tenant(tenant_id)
await cache_tenant(tenant_id, tenant_data)

# Invalidate cache when data changes
await invalidate_user_cache(user_id)
```

## Configuration

### Environment Variables

```bash
# Redis connection URL
XAGENT_REDIS_URL=redis://localhost:6379/0

# Or with authentication
XAGENT_REDIS_URL=redis://:password@localhost:6379/0

# Or with cluster
XAGENT_REDIS_URL=redis://node1:6379,redis://node2:6379,redis://node3:6379
```

### Programmatic Configuration

```python
from backend.app.core.cache import CacheManager

# Create cache manager with custom settings
cache = CacheManager(
    redis_url="redis://localhost:6379/0",
    max_connections=50,
    socket_timeout=5,
    socket_connect_timeout=5,
)
```

## Cache TTLs

Different cache types have different TTLs:

| Cache Type | TTL | Use Case |
|-----------|-----|----------|
| Memory Search | 5 min | Frequently searched queries |
| Memory Item | 10 min | Individual memory items |
| Memory Session | 30 min | Session data |
| LLM Response | 1 hour | LLM API responses |
| LLM Embedding | 24 hours | Text embeddings |
| DB Query | 10 min | Generic database queries |
| DB User | 1 hour | User profile data |
| DB Tenant | 1 hour | Tenant configuration |

## Cache Invalidation

### Automatic Invalidation

- TTL-based: Entries automatically expire after TTL
- Pattern-based: Clear all keys matching a pattern

### Manual Invalidation

```python
from backend.app.core.memory_cache import invalidate_memory_item_cache
from backend.app.core.db_cache import invalidate_user_cache

# Invalidate specific item
await invalidate_memory_item_cache(memory_id)

# Invalidate user and related caches
await invalidate_user_cache(user_id)
```

### Event-Based Invalidation

```python
from backend.app.core.cache import get_cache_manager

cache = get_cache_manager()

# Register invalidation callback
def on_memory_updated(memory_id: str):
    cache.register_invalidation_callback(
        f"memory:{memory_id}",
        lambda: invalidate_memory_item_cache(memory_id)
    )

# Trigger invalidation
await cache.trigger_invalidation(f"memory:{memory_id}")
```

## Monitoring and Statistics

```python
from backend.app.core.cache import get_cache_stats

# Get cache statistics
stats = get_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Errors: {stats['errors']}")
print(f"Uptime: {stats['uptime_seconds']:.0f}s")
```

## Performance Expectations

### Cache Hit Performance

- L1 (Memory) hit: ~0.1ms
- L2 (Redis) hit: ~1-5ms
- Cache miss (compute): 10-1000ms+ (depends on operation)

### Performance Improvements

With caching enabled:

| Operation | Without Cache | With Cache | Improvement |
|-----------|--------------|-----------|-------------|
| Memory search | 50-200ms | 1-5ms | 10-200x |
| LLM response | 500-5000ms | 1-5ms | 100-5000x |
| User lookup | 10-50ms | 0.1-1ms | 10-500x |
| Embedding lookup | 100-500ms | 1-5ms | 20-500x |

## Best Practices

1. **Choose appropriate TTLs**
   - Short TTL (5-10 min) for frequently changing data
   - Long TTL (1 hour+) for stable data
   - Very long TTL (24 hours) for immutable data like embeddings

2. **Invalidate on writes**
   - Always invalidate cache when data is modified
   - Use pattern-based invalidation for related data

3. **Monitor cache performance**
   - Track hit rates to identify optimization opportunities
   - Alert on high error rates

4. **Handle cache failures gracefully**
   - Cache layer has automatic fallback to in-memory
   - Application continues working if Redis is unavailable

5. **Use appropriate serialization**
   - JSON for simple data structures (default)
   - Pickle for complex Python objects

## Troubleshooting

### Redis Connection Issues

```python
# Check if Redis is available
from backend.app.core.cache import get_cache_manager

cache = get_cache_manager()
if cache.client is None:
    print("Redis not available, using in-memory cache")
```

### Cache Not Working

1. Check Redis URL configuration
2. Verify Redis server is running
3. Check network connectivity
4. Review cache statistics for errors

### High Memory Usage

1. Reduce L1 cache size
2. Reduce TTL values
3. Implement cache eviction policies
4. Monitor cache hit rates

## Integration with Existing Code

### Memory System

```python
# In backend/app/core/memory.py
from backend.app.core.memory_cache import (
    get_cached_search_results,
    cache_search_results,
)

async def search_with_scores(self, context, query, layers=None, top_k=5, scope=None):
    # Try cache first
    cached = await get_cached_search_results(
        context.tenant_id, query, layers, top_k
    )
    if cached:
        return cached
    
    # Compute results
    results = await self._compute_search(context, query, layers, top_k, scope)
    
    # Cache results
    await cache_search_results(
        context.tenant_id, query, results, layers, top_k
    )
    return results
```

### LLM System

```python
# In backend/app/core/llm.py
from backend.app.core.llm_cache import (
    get_cached_llm_response,
    cache_llm_response,
)

async def chat(self, messages, tools):
    # Try cache first
    cached = await get_cached_llm_response(messages, self.model)
    if cached:
        return cached
    
    # Call LLM
    response = await self._call_llm(messages, tools)
    
    # Cache response
    await cache_llm_response(messages, response, self.model)
    return response
```

## Testing

Run the cache tests:

```bash
pytest tests/test_cache.py -v
```

Run specific test class:

```bash
pytest tests/test_cache.py::TestCacheManager -v
```

Run with coverage:

```bash
pytest tests/test_cache.py --cov=backend.app.core.cache --cov-report=html
```
"""
