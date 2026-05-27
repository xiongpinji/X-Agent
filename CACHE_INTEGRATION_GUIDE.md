"""Integration Guide for Redis Cache Layer

This guide explains how to integrate the Redis cache layer into existing X-Agent modules.
"""

# Memory System Integration

## Step 1: Update memory.py search method

In `backend/app/core/memory.py`, update the `search_with_scores` method:

```python
from backend.app.core.memory_cache import (
    get_cached_search_results,
    cache_search_results,
    invalidate_search_cache,
)

async def search_with_scores(
    self,
    context: RunContext,
    query: str,
    layers: list[int] | None = None,
    top_k: int = 5,
    scope: MemoryScope | None = None,
) -> list[MemorySearchHit]:
    # Try to get from cache first
    cached_results = await get_cached_search_results(
        context.tenant_id,
        query,
        layers=layers,
        top_k=top_k,
    )
    if cached_results:
        logger.debug(f"Cache hit for memory search: {query}")
        return cached_results

    # Original search logic
    query_terms = {term.lower() for term in query.split() if term.strip()}
    graph_query_terms = set(MemoryGraph.extract_terms(query))
    related_terms = self._graph.related_terms(query_terms | graph_query_terms)
    allowed_layers = set(layers or list(range(1, 11)))
    query_embedding = await self._embed(query)
    scope = self._normalize_scope(scope, context, None, {})
    scored: list[MemorySearchHit] = []
    
    # ... rest of search logic ...
    
    # Cache results before returning
    await cache_search_results(
        context.tenant_id,
        query,
        scored[:top_k],
        layers=layers,
        top_k=top_k,
    )
    
    return scored[:top_k]
```

## Step 2: Invalidate cache on memory updates

In `backend/app/core/memory.py`, update methods that modify memory:

```python
from backend.app.core.memory_cache import (
    invalidate_memory_item_cache,
    invalidate_search_cache,
)

async def store_layer(
    self,
    context: RunContext,
    layer: int,
    content: str,
    # ... other parameters ...
) -> str:
    # ... existing logic ...
    
    # Invalidate search cache when new memory is added
    await invalidate_search_cache(context.tenant_id)
    
    return item.id

def share_memory(
    self,
    memory_id: str,
    share_scope: str,
    # ... other parameters ...
) -> MemoryItem | None:
    # ... existing logic ...
    
    # Invalidate cache when memory is modified
    await invalidate_memory_item_cache(memory_id)
    await invalidate_search_cache(item.tenant_id)
    
    return item
```

# LLM System Integration

## Step 1: Update LLM backend chat method

In `backend/app/core/llm.py`, update the `chat` method:

```python
from backend.app.core.llm_cache import (
    get_cached_llm_response,
    cache_llm_response,
)

class OpenAIResponsesBackend(BaseLLMBackend):
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> LLMResponse:
        # Try cache first
        cached_response = await get_cached_llm_response(
            messages,
            self.model,
            temperature=0.7,
        )
        if cached_response:
            logger.debug(f"Cache hit for LLM response: {self.model}")
            return cached_response

        # Original chat logic
        try:
            from openai import APIError, AsyncOpenAI
        except ImportError as exc:
            raise LLMBackendError("openai package is not installed") from exc

        # ... existing OpenAI API call logic ...
        
        response = LLMResponse(
            content=content,
            tool_calls=tool_calls,
            tokens_used=tokens_used,
            model=self.model,
        )
        
        # Cache response
        await cache_llm_response(messages, response, self.model)
        
        return response
```

## Step 2: Cache embeddings

In `backend/app/core/embeddings.py`, update embedding methods:

```python
from backend.app.core.llm_cache import (
    get_cached_embedding,
    cache_embedding,
)

class OpenAIEmbeddingModel(EmbeddingModel):
    async def embed(self, text: str) -> list[float]:
        # Try cache first
        cached = await get_cached_embedding(text, self.model)
        if cached:
            logger.debug(f"Cache hit for embedding: {self.model}")
            return cached

        # Original embedding logic
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.embeddings.create(
            model=self.model,
            input=text,
        )
        
        embedding = response.data[0].embedding
        
        # Cache embedding
        await cache_embedding(text, embedding, self.model)
        
        return embedding
```

# Database Query Caching

## Step 1: Cache user lookups

In `backend/app/core/admin.py` or user store:

```python
from backend.app.core.db_cache import (
    get_cached_user,
    cache_user,
    invalidate_user_cache,
)

class UserStore:
    def get(self, user_id: str) -> User | None:
        # Try cache first
        cached = await get_cached_user(user_id)
        if cached:
            return User(**cached)

        # Database query
        user = self._db.query(User).filter(User.id == user_id).first()
        
        if user:
            # Cache user data
            await cache_user(user_id, user.model_dump(mode="json"))
        
        return user

    def update(self, user_id: str, **updates) -> User:
        # Update database
        user = self._db.query(User).filter(User.id == user_id).first()
        for key, value in updates.items():
            setattr(user, key, value)
        self._db.commit()
        
        # Invalidate cache
        await invalidate_user_cache(user_id)
        
        return user
```

## Step 2: Cache API key lookups

In `backend/app/core/security.py`:

```python
from backend.app.core.db_cache import (
    get_cached_api_key,
    cache_api_key,
    invalidate_api_key_cache,
)

class APIKeyStore:
    def authenticate(self, raw_key: str) -> Principal | None:
        # Try cache first
        cached = await get_cached_api_key(raw_key)
        if cached:
            return Principal(**cached)

        # Database query
        key_record = self._db.query(APIKey).filter(
            APIKey.key_hash == hash_key(raw_key)
        ).first()
        
        if key_record:
            principal = Principal(
                tenant_id=key_record.tenant_id,
                user_id=key_record.user_id,
                # ... other fields ...
            )
            # Cache principal
            await cache_api_key(raw_key, principal.model_dump(mode="json"))
            return principal
        
        return None
```

# Dependencies Integration

## Update dependencies.py

In `backend/app/dependencies.py`, initialize cache manager:

```python
from backend.app.core.cache import get_cache_manager
from backend.app.settings import get_settings

@lru_cache
def get_cache() -> CacheManager:
    """Get cache manager instance."""
    settings = get_settings()
    return get_cache_manager(redis_url=settings.redis_url)
```

# API Endpoints for Cache Management

## Add cache management endpoints

Create `backend/app/api/cache.py`:

```python
from fastapi import APIRouter, Depends
from backend.app.core.cache import get_cache_manager, get_cache_stats
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])

@router.get("/stats")
async def get_cache_statistics(principal: Principal = Depends(get_current_principal)):
    """Get cache statistics."""
    enforce_scope(principal, "admin")
    stats = get_cache_stats()
    return stats

@router.post("/clear")
async def clear_cache(principal: Principal = Depends(get_current_principal)):
    """Clear all cache."""
    enforce_scope(principal, "admin")
    cache = get_cache_manager()
    await cache.clear()
    return {"status": "cleared"}

@router.post("/invalidate")
async def invalidate_pattern(
    pattern: str,
    principal: Principal = Depends(get_current_principal),
):
    """Invalidate cache by pattern."""
    enforce_scope(principal, "admin")
    cache = get_cache_manager()
    await cache.invalidate_pattern(pattern)
    return {"status": "invalidated", "pattern": pattern}
```

# Monitoring and Observability

## Add cache metrics to observability

In `backend/app/services/observability/langfuse_client.py`:

```python
from backend.app.core.cache import get_cache_stats

def record_cache_metrics():
    """Record cache metrics to observability system."""
    stats = get_cache_stats()
    
    langfuse_client.trace(
        name="cache_metrics",
        metadata={
            "hits": stats["hits"],
            "misses": stats["misses"],
            "errors": stats["errors"],
            "hit_rate": stats["hit_rate"],
        },
    )
```

# Testing Integration

## Add cache tests to existing test files

In `tests/test_memory_retrieval.py`:

```python
@pytest.mark.asyncio
async def test_memory_search_caching(memory_system):
    """Test that memory search results are cached."""
    context = RunContext(tenant_id="test", user_id="user1", agent_id="agent1")
    
    # First search
    results1 = await memory_system.search_with_scores(
        context, "test query", top_k=5
    )
    
    # Second search should hit cache
    results2 = await memory_system.search_with_scores(
        context, "test query", top_k=5
    )
    
    assert results1 == results2
    
    # Check cache stats
    stats = get_cache_stats()
    assert stats["hits"] > 0
```

# Deployment Considerations

## Redis Setup

```bash
# Docker Compose
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

## Environment Configuration

```bash
# .env
XAGENT_REDIS_URL=redis://redis:6379/0
XAGENT_APP_MODE=production
```

## Performance Tuning

```python
# For high-traffic deployments
cache = CacheManager(
    redis_url=settings.redis_url,
    max_connections=100,  # Increase connection pool
    socket_timeout=10,
    socket_connect_timeout=10,
)
```

# Rollback Plan

If cache layer causes issues:

1. Set `XAGENT_REDIS_URL` to empty string
2. Cache layer automatically falls back to in-memory
3. Application continues working without Redis
4. No code changes required

# Monitoring Checklist

- [ ] Cache hit rate > 50% for memory searches
- [ ] Cache hit rate > 70% for LLM responses
- [ ] Redis connection pool utilization < 80%
- [ ] Cache error rate < 1%
- [ ] Memory usage stable (no memory leaks)
- [ ] Response times improved by 10x+ for cached operations
