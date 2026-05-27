"""Unit tests for Redis cache layer."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.cache import (
    CacheManager,
    CacheStats,
    async_cached,
    cached,
    get_cache_manager,
    get_cache_stats,
    record_cache_error,
    record_cache_hit,
    record_cache_miss,
)
from backend.app.core.db_cache import (
    cache_api_key,
    cache_query,
    cache_tenant,
    cache_user,
    get_cached_api_key,
    get_cached_query,
    get_cached_tenant,
    get_cached_user,
    invalidate_api_key_cache,
    invalidate_query_cache,
    invalidate_tenant_cache,
    invalidate_user_cache,
)
from backend.app.core.llm_cache import (
    cache_embedding,
    cache_llm_response,
    get_cached_embedding,
    get_cached_llm_response,
)
from backend.app.core.memory_cache import (
    cache_memory_item,
    cache_search_results,
    cache_session,
    get_cached_memory_item,
    get_cached_search_results,
    get_cached_session,
    invalidate_memory_item_cache,
    invalidate_search_cache,
    invalidate_session_cache,
)


class TestCacheStats:
    """Test cache statistics tracking."""

    def test_cache_stats_initialization(self) -> None:
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate(self) -> None:
        stats = CacheStats()
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        assert stats.hit_rate == pytest.approx(2 / 3)

    def test_cache_stats_to_dict(self) -> None:
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()
        stats.record_error()
        result = stats.to_dict()
        assert result["hits"] == 1
        assert result["misses"] == 1
        assert result["errors"] == 1
        assert "hit_rate" in result
        assert "uptime_seconds" in result


class TestCacheManager:
    """Test cache manager functionality."""

    @pytest.mark.asyncio
    async def test_cache_manager_get_set(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", {"data": "value"}, ttl=60)
        result = await manager.get("test_key")
        assert result == {"data": "value"}

    @pytest.mark.asyncio
    async def test_cache_manager_ttl_expiry(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value", ttl=1)
        await asyncio.sleep(1.1)
        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_manager_delete(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value")
        await manager.delete("test_key")
        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_manager_exists(self) -> None:
        manager = CacheManager()
        await manager.set("test_key", "value")
        assert await manager.exists("test_key") is True
        await manager.delete("test_key")
        assert await manager.exists("test_key") is False

    @pytest.mark.asyncio
    async def test_cache_manager_clear(self) -> None:
        manager = CacheManager()
        await manager.set("key1", "value1")
        await manager.set("key2", "value2")
        await manager.clear()
        assert await manager.exists("key1") is False
        assert await manager.exists("key2") is False

    @pytest.mark.asyncio
    async def test_cache_manager_in_memory_fallback(self) -> None:
        """Test in-memory fallback when Redis is unavailable."""
        manager = CacheManager(redis_url=None)
        await manager.set("test_key", {"data": "value"}, ttl=60)
        result = await manager.get("test_key")
        assert result == {"data": "value"}


class TestMemoryCaching:
    """Test memory system caching."""

    @pytest.mark.asyncio
    async def test_cache_memory_item(self) -> None:
        from backend.app.core.memory import MemoryItem, MemoryScope

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        await cache_memory_item(item)
        cached = await get_cached_memory_item(item.id)
        assert cached is not None
        assert cached["content"] == "Test memory"

    @pytest.mark.asyncio
    async def test_invalidate_memory_item_cache(self) -> None:
        from backend.app.core.memory import MemoryItem

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        await cache_memory_item(item)
        await invalidate_memory_item_cache(item.id)
        cached = await get_cached_memory_item(item.id)
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_search_results(self) -> None:
        from backend.app.core.memory import MemoryItem, MemorySearchHit

        item = MemoryItem(
            tenant_id="test_tenant",
            content="Test memory",
            layer=3,
        )
        hit = MemorySearchHit(item=item, score=0.95)
        results = [hit]
        await cache_search_results("test_tenant", "test query", results)
        cached = await get_cached_search_results("test_tenant", "test query")
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].score == 0.95

    @pytest.mark.asyncio
    async def test_cache_session(self) -> None:
        session_data = {
            "session_id": "test_session",
            "tenant_id": "test_tenant",
            "user_id": "test_user",
        }
        await cache_session("test_session", session_data)
        cached = await get_cached_session("test_session")
        assert cached == session_data

    @pytest.mark.asyncio
    async def test_invalidate_session_cache(self) -> None:
        session_data = {"session_id": "test_session"}
        await cache_session("test_session", session_data)
        await invalidate_session_cache("test_session")
        cached = await get_cached_session("test_session")
        assert cached is None


class TestLLMCaching:
    """Test LLM response caching."""

    @pytest.mark.asyncio
    async def test_cache_llm_response(self) -> None:
        from backend.app.core.llm import LLMResponse

        messages = [{"role": "user", "content": "Hello"}]
        response = LLMResponse(content="Hi there", tokens_used=10)
        await cache_llm_response(messages, response, "gpt-4")
        cached = await get_cached_llm_response(messages, "gpt-4")
        assert cached is not None
        assert cached.content == "Hi there"
        assert cached.tokens_used == 10

    @pytest.mark.asyncio
    async def test_cache_embedding(self) -> None:
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        await cache_embedding("test text", embedding, "text-embedding-3-small")
        cached = await get_cached_embedding("test text", "text-embedding-3-small")
        assert cached == embedding


class TestDatabaseCaching:
    """Test database query caching."""

    @pytest.mark.asyncio
    async def test_cache_user(self) -> None:
        user_data = {"id": "user1", "email": "test@example.com", "name": "Test User"}
        await cache_user("user1", user_data)
        cached = await get_cached_user("user1")
        assert cached == user_data

    @pytest.mark.asyncio
    async def test_invalidate_user_cache(self) -> None:
        user_data = {"id": "user1", "email": "test@example.com"}
        await cache_user("user1", user_data)
        await invalidate_user_cache("user1")
        cached = await get_cached_user("user1")
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_tenant(self) -> None:
        tenant_data = {"id": "tenant1", "name": "Test Tenant"}
        await cache_tenant("tenant1", tenant_data)
        cached = await get_cached_tenant("tenant1")
        assert cached == tenant_data

    @pytest.mark.asyncio
    async def test_cache_api_key(self) -> None:
        key_data = {"id": "key1", "user_id": "user1", "key": "secret"}
        await cache_api_key("key1", key_data)
        cached = await get_cached_api_key("key1")
        assert cached == key_data

    @pytest.mark.asyncio
    async def test_generic_query_cache(self) -> None:
        result = {"count": 42, "items": []}
        await cache_query("custom_query", result, ttl=300, param1="value1")
        cached = await get_cached_query("custom_query", param1="value1")
        assert cached == result


class TestCacheDecorators:
    """Test cache decorators."""

    @pytest.mark.asyncio
    async def test_async_cached_decorator(self) -> None:
        call_count = 0

        @async_cached(ttl_seconds=60, key_prefix="test")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again

        # Different argument should execute function
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cached_decorator(self) -> None:
        call_count = 0

        @cached(ttl_seconds=60, key_prefix="test")
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute function
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_record_cache_hit(self) -> None:
        record_cache_hit()
        stats = get_cache_stats()
        assert stats["hits"] >= 1

    def test_record_cache_miss(self) -> None:
        record_cache_miss()
        stats = get_cache_stats()
        assert stats["misses"] >= 1

    def test_record_cache_error(self) -> None:
        record_cache_error()
        stats = get_cache_stats()
        assert stats["errors"] >= 1


class TestCacheIntegration:
    """Integration tests for cache layer."""

    @pytest.mark.asyncio
    async def test_multi_layer_cache_hit(self) -> None:
        """Test L1 and L2 cache layers."""
        manager = CacheManager()
        test_data = {"key": "value", "nested": {"data": 123}}

        # Set in both layers
        await manager.set("test_key", test_data, ttl=60)

        # Get should return from cache
        result = await manager.get("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_cache_serialization(self) -> None:
        """Test JSON serialization of complex objects."""
        manager = CacheManager()
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "string": "test",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
        }

        await manager.set("complex", complex_data)
        result = await manager.get("complex")
        assert result == complex_data

    @pytest.mark.asyncio
    async def test_cache_performance(self) -> None:
        """Test cache performance improvement."""
        manager = CacheManager()
        test_data = {"data": "x" * 1000}

        # Measure cache hit time
        await manager.set("perf_test", test_data)
        start = time.time()
        for _ in range(100):
            await manager.get("perf_test")
        cache_time = time.time() - start

        # Cache should be very fast (< 100ms for 100 operations)
        assert cache_time < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
