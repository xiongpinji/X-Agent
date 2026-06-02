"""Integration tests for X-Agent functionality improvements."""

import asyncio
import pytest
from datetime import datetime

from backend.app.core.llm import OpenAIBackend, MockLLMBackend, LLMRouter, LLMResponse
from backend.app.core.error_recovery import (
    CircuitBreaker,
    RetryPolicy,
    CompensationChain,
    classify_error,
    ErrorCategory,
)
from backend.app.core.unified_memory import (
    UnifiedMemorySystem,
    MemoryType,
    MemoryValidator,
)
from backend.app.core.performance import (
    LRUCache,
    ResponseCache,
    PerformanceMonitor,
    BatchProcessor,
)


class TestLLMIntegration:
    """Test LLM backend integration."""

    async def test_mock_backend_basic(self):
        """Test mock backend basic functionality."""
        backend = MockLLMBackend()
        response = await backend.chat(
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
        )
        assert isinstance(response, LLMResponse)
        assert response.model == "mock"
        assert response.content is not None

    async def test_llm_router_fallback(self):
        """Test LLM router with fallback."""
        mock = MockLLMBackend()
        router = LLMRouter(backends=[mock])
        response = await router.chat(
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
        )
        assert response.content is not None

    async def test_llm_response_structure(self):
        """Test LLM response structure."""
        response = LLMResponse(
            content="Test response",
            tokens_used=10,
            model="test",
            cost=0.001,
            latency_ms=100.0,
        )
        assert response.content == "Test response"
        assert response.tokens_used == 10
        assert response.cost == 0.001


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    async def test_error_classification(self):
        """Test error classification."""
        # Test transient error
        exc = TimeoutError("Connection timeout")
        category = classify_error(exc)
        assert category == ErrorCategory.TRANSIENT

        # Test rate limit error
        exc = Exception("429 Rate limit exceeded")
        category = classify_error(exc)
        assert category == ErrorCategory.RATE_LIMIT

        # Test auth error
        exc = Exception("401 Unauthorized")
        category = classify_error(exc)
        assert category == ErrorCategory.AUTHENTICATION

    async def test_circuit_breaker_basic(self):
        """Test circuit breaker basic functionality."""
        breaker = CircuitBreaker("test", failure_threshold=2)

        # Simulate failures
        async def failing_coro():
            raise Exception("Test error")

        # First failure
        with pytest.raises(Exception):
            await breaker.call(failing_coro())

        # Second failure - should open circuit
        with pytest.raises(Exception):
            await breaker.call(failing_coro())

        # Circuit should be open now
        assert breaker.metrics.state.value == "open"

    async def test_retry_policy(self):
        """Test retry policy."""
        policy = RetryPolicy(max_attempts=3, initial_delay=0.1)
        delay = policy.get_delay(0)
        assert delay > 0
        assert delay <= policy.max_delay

    async def test_compensation_chain(self):
        """Test compensation chain."""
        chain = CompensationChain()
        executed = []

        async def action1():
            executed.append(1)

        async def action2():
            executed.append(2)

        chain.add("action1", action1)
        chain.add("action2", action2)

        await chain.execute_all()

        # Should execute in reverse order
        assert executed == [2, 1]


class TestUnifiedMemory:
    """Test unified memory system."""

    async def test_memory_storage(self):
        """Test memory storage."""
        memory_system = UnifiedMemorySystem()
        record = await memory_system.store_memory(
            content="Test memory",
            memory_type=MemoryType.FACT,
            tags=["test"],
        )
        assert record.id is not None
        assert record.content == "Test memory"
        assert record.memory_type == MemoryType.FACT

    async def test_memory_retrieval(self):
        """Test memory retrieval."""
        memory_system = UnifiedMemorySystem()
        await memory_system.store_memory(
            content="Important fact",
            memory_type=MemoryType.FACT,
        )
        results = await memory_system.retrieve_memories(
            query="fact",
            top_k=5,
        )
        assert len(results) > 0

    async def test_memory_validation(self):
        """Test memory validation."""
        validator = MemoryValidator()
        from backend.app.core.unified_memory import MemoryRecord

        record = MemoryRecord(
            id="test",
            content="Valid content",
            memory_type=MemoryType.FACT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        is_valid, errors = validator.validate_record(record)
        assert is_valid
        assert len(errors) == 0

    async def test_memory_relationships(self):
        """Test memory relationships."""
        memory_system = UnifiedMemorySystem()
        record1 = await memory_system.store_memory(
            content="Memory 1",
            memory_type=MemoryType.FACT,
        )
        record2 = await memory_system.store_memory(
            content="Memory 2",
            memory_type=MemoryType.FACT,
        )

        rel = await memory_system.create_relationship(
            source_id=record1.id,
            target_id=record2.id,
            relationship_type="related_to",
        )
        assert rel.source_id == record1.id
        assert rel.target_id == record2.id

    async def test_memory_stats(self):
        """Test memory statistics."""
        memory_system = UnifiedMemorySystem()
        await memory_system.store_memory(
            content="Test",
            memory_type=MemoryType.FACT,
        )
        stats = await memory_system.get_memory_stats()
        assert stats["total_memories"] > 0


class TestPerformanceOptimization:
    """Test performance optimization features."""

    async def test_lru_cache(self):
        """Test LRU cache."""
        cache = LRUCache[str, str](max_size=2)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        value = await cache.get("key1")
        assert value == "value1"

        # Add third item, should evict least recently used
        await cache.set("key3", "value3")
        stats = await cache.get_stats()
        assert stats["size"] <= 2

    async def test_response_cache(self):
        """Test response cache."""
        cache = ResponseCache(max_size=10, ttl=3600)

        async def test_func():
            return "result"

        # First call
        await cache.set("test_func", (), {}, "result")
        cached = await cache.get("test_func", (), {})
        assert cached == "result"

    async def test_performance_monitor(self):
        """Test performance monitor."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test_metric", 100.0)
        monitor.record_metric("test_metric", 200.0)

        stats = monitor.get_summary()["test_metric"]
        assert stats["count"] == 2
        assert stats["min"] == 100.0
        assert stats["max"] == 200.0

    async def test_batch_processor(self):
        """Test batch processor."""
        processor = BatchProcessor(batch_size=2, timeout=1.0)
        batches = []

        async def handler(batch):
            batches.append(batch)

        # Add items
        await processor.add(1)
        await processor.add(2)
        await processor.add(3)

        # Process with timeout
        task = asyncio.create_task(processor.process(handler))
        await asyncio.sleep(0.1)
        await processor.stop()

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            pass


class TestIntegrationScenarios:
    """Test integrated scenarios."""

    async def test_llm_with_error_recovery(self):
        """Test LLM with error recovery."""
        backend = MockLLMBackend()
        router = LLMRouter(backends=[backend])

        response = await router.chat(
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
        )
        assert response is not None

    async def test_memory_with_caching(self):
        """Test memory system with caching."""
        memory_system = UnifiedMemorySystem()
        cache = ResponseCache()

        # Store memory
        record = await memory_system.store_memory(
            content="Cached memory",
            memory_type=MemoryType.FACT,
        )

        # Cache retrieval
        await cache.set("retrieve", (), {}, [record])
        cached = await cache.get("retrieve", (), {})
        assert cached is not None

    async def test_error_recovery_with_compensation(self):
        """Test error recovery with compensation."""
        chain = CompensationChain()
        executed = []

        async def main_action():
            executed.append("main")
            raise Exception("Main action failed")

        async def compensate():
            executed.append("compensate")

        chain.add("compensate", compensate)

        try:
            await main_action()
        except Exception:
            await chain.execute_all()

        assert "compensate" in executed

    async def test_full_workflow(self):
        """Test full workflow integration."""
        # Initialize components
        llm_router = LLMRouter(backends=[MockLLMBackend()])
        memory_system = UnifiedMemorySystem()
        cache = ResponseCache()
        monitor = PerformanceMonitor()

        # Store memory
        memory = await memory_system.store_memory(
            content="Workflow test",
            memory_type=MemoryType.EXPERIENCE,
        )

        # Get LLM response
        response = await llm_router.chat(
            messages=[{"role": "user", "content": "Test"}],
            tools=[],
        )

        # Cache response
        await cache.set("workflow", (), {}, response)

        # Record metrics
        monitor.record_metric("workflow_latency", response.latency_ms)

        # Verify all components worked
        assert memory is not None
        assert response is not None
        stats = monitor.get_summary()["workflow_latency"]
        assert stats["count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
