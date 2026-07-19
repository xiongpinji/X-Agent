"""Tests for LLM routing, caching, and deduplication system."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.app.core.llm import LLMResponse, LLMRouter, MockLLMBackend
from backend.app.core.llm_cache import LLMCacheManager
from backend.app.core.llm_deduplicator import LLMDeduplicator
from backend.app.core.llm_manager import LLMManager


@pytest.fixture(autouse=True)
def _reset_llm_globals():
    """Isolate process-global LLM singletons between tests.

    LLMManager defaults to the module-global cache manager and deduplicator
    (get_llm_cache_manager / get_deduplicator), which in turn share the global
    CacheManager store. Without a reset, cached responses and in-flight
    signatures leak across tests and make cache_hits/total_calls assertions
    order-dependent (and can mask the dedup deadlock fix). Reset to None so each
    test rebuilds fresh singletons on first use.
    """
    import backend.app.core.cache as _cache_mod
    import backend.app.core.llm_cache as _llm_cache_mod
    import backend.app.core.llm_deduplicator as _dedup_mod
    import backend.app.core.llm_manager as _mgr_mod

    for mod, attr in (
        (_cache_mod, "_cache_manager"),
        (_llm_cache_mod, "_llm_cache_manager"),
        (_dedup_mod, "_deduplicator"),
        (_mgr_mod, "_llm_manager"),
    ):
        setattr(mod, attr, None)
    yield
    for mod, attr in (
        (_cache_mod, "_cache_manager"),
        (_llm_cache_mod, "_llm_cache_manager"),
        (_dedup_mod, "_deduplicator"),
        (_mgr_mod, "_llm_manager"),
    ):
        setattr(mod, attr, None)


class TestLLMDeduplicator:
    """Tests for LLM deduplicator."""

    @pytest.mark.asyncio
    async def test_register_and_resolve_in_flight(self):
        """Test registering and resolving in-flight requests."""
        dedup = LLMDeduplicator()
        messages = [{"role": "user", "content": "test"}]

        # Register request
        sig1 = await dedup.register_in_flight(messages, "gpt-4", 0.7)
        assert sig1 is not None

        # Register same request again
        sig2 = await dedup.register_in_flight(messages, "gpt-4", 0.7)
        assert sig1 == sig2

        # Resolve request
        response = LLMResponse(content="test response", model="gpt-4")
        await dedup.resolve_in_flight(sig1, response)

        # Get response
        result = await dedup.get_in_flight_response(sig1, timeout=1.0)
        assert result is not None
        assert result.content == "test response"

    @pytest.mark.asyncio
    async def test_deduplication_stats(self):
        """Test deduplication statistics."""
        dedup = LLMDeduplicator()

        # Record some deduplication events
        dedup.record_request()
        dedup.record_deduplication("cache")
        dedup.record_request()
        dedup.record_deduplication("in_flight")

        stats = dedup.get_stats()
        assert stats["total_requests"] == 2
        assert stats["deduplicated_requests"] == 2
        assert stats["deduplication_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_cleanup_expired_requests(self):
        """Test cleanup of expired in-flight requests."""
        dedup = LLMDeduplicator(in_flight_timeout=0.1)
        messages = [{"role": "user", "content": "test"}]

        # Register request
        sig = await dedup.register_in_flight(messages, "gpt-4", 0.7)

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Cleanup
        await dedup.cleanup_in_flight(max_age=0.1)

        # Request should be gone
        result = await dedup.get_in_flight_response(sig, timeout=0.1)
        assert result is None


class TestLLMCacheManager:
    """Tests for LLM cache manager."""

    @pytest.mark.asyncio
    async def test_cache_and_retrieve_response(self):
        """Test caching and retrieving responses."""
        cache = LLMCacheManager()
        messages = [{"role": "user", "content": "test"}]
        response = LLMResponse(content="test response", model="gpt-4", cost=0.01)

        # Cache response
        await cache.cache_response(messages, response, "gpt-4", 0.7)

        # Retrieve response
        cached = await cache.get_cached_response(messages, "gpt-4", 0.7)
        assert cached is not None
        assert cached.content == "test response"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics."""
        cache = LLMCacheManager()
        messages = [{"role": "user", "content": "test"}]
        response = LLMResponse(content="test response", model="gpt-4", cost=0.01)

        # Cache response
        await cache.cache_response(messages, response, "gpt-4", 0.7)

        # Get cached response (hit)
        await cache.get_cached_response(messages, "gpt-4", 0.7)

        # Get different response (miss)
        await cache.get_cached_response([{"role": "user", "content": "different"}], "gpt-4", 0.7)

        stats = cache.get_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Test cost tracking in cache."""
        cache = LLMCacheManager()
        messages = [{"role": "user", "content": "test"}]
        response = LLMResponse(
            content="test response",
            model="gpt-4",
            cost=0.05,
            tokens_used=100,
        )

        # Cache response
        await cache.cache_response(messages, response, "gpt-4", 0.7)

        stats = cache.get_stats()
        assert stats["total_cost_saved"] == 0.05
        assert stats["total_tokens_saved"] == 100


class TestLLMManager:
    """Tests for integrated LLM manager."""

    @pytest.mark.asyncio
    async def test_chat_with_cache(self):
        """Test chat with caching."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router, enable_cache=True, enable_dedup=False)

        messages = [{"role": "user", "content": "test"}]

        # First call - cache miss
        response1 = await manager.chat(messages)
        assert response1 is not None

        # Second call - cache hit
        response2 = await manager.chat(messages)
        assert response2 is not None

        metrics = manager.get_metrics()
        assert metrics["cache_hits"] == 1
        assert metrics["cache_hit_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_chat_with_dedup(self):
        """Test chat with deduplication."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router, enable_cache=False, enable_dedup=True)

        messages = [{"role": "user", "content": "test"}]

        # Simulate concurrent requests
        tasks = [
            manager.chat(messages),
            manager.chat(messages),
            manager.chat(messages),
        ]

        responses = await asyncio.gather(*tasks)
        assert len(responses) == 3
        assert all(r is not None for r in responses)

        metrics = manager.get_metrics()
        # At least 2 should be deduplicated
        assert metrics["dedup_hits"] >= 2

    @pytest.mark.asyncio
    async def test_chat_with_cache_and_dedup(self):
        """Test chat with both caching and deduplication."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router, enable_cache=True, enable_dedup=True)

        messages = [{"role": "user", "content": "test"}]

        # First call
        response1 = await manager.chat(messages)
        assert response1 is not None

        # Second call - should hit cache
        response2 = await manager.chat(messages)
        assert response2 is not None

        metrics = manager.get_metrics()
        assert metrics["cache_hits"] >= 1

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self):
        """Test metrics aggregation."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router)

        messages = [{"role": "user", "content": "test"}]

        # Make multiple calls
        for _ in range(5):
            await manager.chat(messages)

        metrics = manager.get_metrics()
        assert metrics["total_calls"] == 5
        assert metrics["total_tokens"] > 0
        assert metrics["total_cost"] >= 0.0
        assert metrics["average_latency_ms"] > 0.0

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing cache."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router, enable_cache=True)

        messages = [{"role": "user", "content": "test"}]

        # Cache a response
        await manager.chat(messages)

        # Clear cache
        await manager.clear_cache()

        # Next call should be a cache miss
        await manager.chat(messages)

        metrics = manager.get_metrics()
        # Both calls should be counted
        assert metrics["total_calls"] == 2


class TestCostOptimization:
    """Tests for cost optimization."""

    @pytest.mark.asyncio
    async def test_cost_savings_from_cache(self):
        """Test cost savings from caching."""
        cache = LLMCacheManager()
        messages = [{"role": "user", "content": "test"}]

        # Cache 10 responses with cost
        for i in range(10):
            response = LLMResponse(
                content=f"response {i}",
                model="gpt-4",
                cost=0.01,
                tokens_used=100,
            )
            await cache.cache_response(messages, response, "gpt-4", 0.7)

        stats = cache.get_stats()
        # Only first response is cached, rest are hits
        assert stats["total_cost_saved"] >= 0.01

    @pytest.mark.asyncio
    async def test_dedup_cost_savings(self):
        """Test cost savings from deduplication."""
        dedup = LLMDeduplicator()

        # Simulate 100 requests, 50 deduplicated
        for i in range(100):
            dedup.record_request()
            if i % 2 == 0:
                dedup.record_deduplication("in_flight")

        stats = dedup.get_stats()
        assert stats["deduplication_rate"] == 50.0


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test full workflow with routing, caching, and deduplication."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router, enable_cache=True, enable_dedup=True)

        # Make multiple requests
        messages_list = [
            [{"role": "user", "content": "test 1"}],
            [{"role": "user", "content": "test 1"}],  # Duplicate
            [{"role": "user", "content": "test 2"}],
            [{"role": "user", "content": "test 1"}],  # Duplicate
        ]

        responses = []
        for messages in messages_list:
            response = await manager.chat(messages)
            responses.append(response)

        assert len(responses) == 4
        assert all(r is not None for r in responses)

        # Check metrics
        metrics = manager.get_metrics()
        assert metrics["total_calls"] == 4
        assert metrics["cache_hits"] >= 1
        assert metrics["dedup_hits"] >= 1

        # Check cache stats
        cache_stats = manager.get_cache_stats()
        assert cache_stats["cache_hits"] >= 1

        # Check dedup stats
        dedup_stats = manager.get_dedup_stats()
        assert dedup_stats["deduplicated_requests"] >= 1

    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup operations."""
        router = LLMRouter(backend=MockLLMBackend())
        manager = LLMManager(router)

        messages = [{"role": "user", "content": "test"}]
        await manager.chat(messages)

        # Cleanup should not raise
        await manager.cleanup()

        # Clear cache should not raise
        await manager.clear_cache()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
