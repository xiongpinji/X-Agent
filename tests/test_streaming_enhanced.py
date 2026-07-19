"""
Test suite for streaming enhanced API.

Tests cover:
- Event store operations
- SSE streaming
- Connection management
- Performance benchmarks
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.api.streaming_enhanced import (
    OptimizedEventStore,
    event_store,
    _stream_events_optimized,
)


class TestOptimizedEventStore:
    """Test OptimizedEventStore functionality."""

    @pytest.fixture
    def store(self):
        """Create a fresh event store for each test."""
        return OptimizedEventStore(
            max_events_per_run=100,
            max_queue_size=50,
            event_batch_size=5,
            event_batch_timeout_ms=50,
        )

    def test_add_event(self, store):
        """Test adding events to store."""
        run_id = "test-run-1"
        event = {
            "event_type": "log",
            "message": "Test message",
            "level": "info",
        }

        store.add_event(run_id, event)

        assert run_id in store.events
        assert len(store.events[run_id]) == 1
        assert store.events[run_id][0]["sequence"] == 1

    def test_sequence_numbering(self, store):
        """Test that events are numbered sequentially."""
        run_id = "test-run-2"

        for i in range(5):
            store.add_event(run_id, {"event_type": "log", "index": i})

        events = store.get_events(run_id)
        sequences = [e["sequence"] for e in events]
        assert sequences == [1, 2, 3, 4, 5]

    def test_circular_buffer(self, store):
        """Test that old events are removed when buffer is full."""
        run_id = "test-run-3"

        # Add more events than max
        for i in range(150):
            store.add_event(run_id, {"event_type": "log", "index": i})

        # Should only keep last 100
        assert len(store.events[run_id]) == 100

    def test_subscribe_unsubscribe(self, store):
        """Test subscription management."""
        run_id = "test-run-4"

        queue1 = store.subscribe(run_id)
        queue2 = store.subscribe(run_id)

        assert store.connection_count[run_id] == 2

        store.unsubscribe(run_id, queue1)
        assert store.connection_count[run_id] == 1

        store.unsubscribe(run_id, queue2)
        assert store.connection_count[run_id] == 0

    def test_get_events_since_sequence(self, store):
        """Test retrieving events since a sequence number."""
        run_id = "test-run-5"

        for i in range(10):
            store.add_event(run_id, {"event_type": "log", "index": i})

        # Get events after sequence 5
        events = store.get_events(run_id, since_sequence=5)
        assert len(events) == 5
        assert events[0]["sequence"] == 6

    def test_metrics_tracking(self, store):
        """Test that metrics are tracked correctly."""
        run_id = "test-run-6"

        store.add_event(run_id, {"event_type": "log"})
        store.add_event(run_id, {"event_type": "log"})

        metrics = store.get_stats(run_id)
        assert metrics["total_events"] == 2
        assert metrics["total_subscribers"] == 0

    def test_get_stats(self, store):
        """Test getting overall statistics."""
        store.add_event("run-1", {"event_type": "log"})
        store.add_event("run-2", {"event_type": "log"})
        store.add_event("run-2", {"event_type": "log"})

        stats = store.get_stats()
        assert stats["total_runs"] == 2
        assert stats["total_events"] == 3


class TestStreamingEndpoints:
    """Test streaming API endpoints."""

    @pytest.mark.asyncio
    async def test_stream_events_optimized(self):
        """Test optimized event streaming."""
        run_id = "test-run-stream"
        queue: asyncio.Queue = asyncio.Queue()

        # Add test events
        await queue.put({"event_type": "log", "message": "Test 1"})
        await queue.put({"event_type": "log", "message": "Test 2"})

        # Create stream generator
        stream = _stream_events_optimized(run_id, queue, heartbeat_interval=0.1)

        # Collect output
        output = []
        try:
            async for chunk in stream:
                output.append(chunk)
                if len(output) >= 4:  # 2 events * 2 lines each
                    break
        except asyncio.TimeoutError:
            pass

        # Verify output format
        assert any("event:" in line for line in output)
        assert any("data:" in line for line in output)

    @pytest.mark.asyncio
    async def test_event_batching(self):
        """Test that events are batched correctly."""
        run_id = "test-batch"
        queue: asyncio.Queue = asyncio.Queue()

        # Add multiple events
        for i in range(10):
            await queue.put({"event_type": "log", "index": i})

        # Create stream with small batch size
        stream = _stream_events_optimized(run_id, queue, heartbeat_interval=0.5)

        # Collect output
        output = []
        try:
            async for chunk in stream:
                output.append(chunk)
                if len(output) >= 20:  # Enough for batched events
                    break
        except asyncio.TimeoutError:
            pass

        # Should have multiple events
        assert len(output) > 0


class TestPerformance:
    """Performance and load tests."""

    def test_event_store_throughput(self):
        """Test event store throughput."""
        store = OptimizedEventStore()
        run_id = "perf-test"

        import time
        start = time.time()

        # Add 1000 events
        for i in range(1000):
            store.add_event(run_id, {
                "event_type": "log",
                "index": i,
                "message": f"Event {i}",
            })

        elapsed = time.time() - start
        throughput = 1000 / elapsed

        print(f"Throughput: {throughput:.0f} events/sec")
        assert throughput > 1000  # Should handle 1000+ events/sec

    def test_memory_efficiency(self):
        """Test memory efficiency with circular buffer."""
        store = OptimizedEventStore(max_events_per_run=5000)

        # Add events to multiple runs
        for run_num in range(100):
            run_id = f"run-{run_num}"
            for i in range(100):
                store.add_event(run_id, {
                    "event_type": "log",
                    "index": i,
                    "data": "x" * 100,  # 100 bytes per event
                })

        # Total events: 100 runs * 100 events = 10,000
        # But each run only keeps 100 (circular buffer)
        # So total stored: 100 runs * 100 events = 10,000
        total_events = sum(len(e) for e in store.events.values())
        assert total_events == 10000

    def test_concurrent_subscriptions(self):
        """Test handling multiple concurrent subscriptions."""
        store = OptimizedEventStore()
        run_id = "concurrent-test"

        # Create multiple subscriptions
        queues = [store.subscribe(run_id) for _ in range(50)]

        assert store.connection_count[run_id] == 50

        # Add event - should notify all
        store.add_event(run_id, {"event_type": "log"})

        # All queues should have the event
        for queue in queues:
            assert not queue.empty()

        # Cleanup
        for queue in queues:
            store.unsubscribe(run_id, queue)

        assert store.connection_count[run_id] == 0


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_queue_full_handling(self):
        """Test handling of full queues."""
        store = OptimizedEventStore(max_queue_size=5)
        run_id = "queue-full-test"

        queue = store.subscribe(run_id)

        # Fill queue
        for i in range(5):
            store.add_event(run_id, {"event_type": "log", "index": i})

        # Queue should be full
        assert queue.full()

        # Add more events - should handle gracefully
        for i in range(5, 10):
            store.add_event(run_id, {"event_type": "log", "index": i})

        # Should still work
        assert not queue.empty()

    def test_empty_store_retrieval(self):
        """Test retrieving from empty store."""
        store = OptimizedEventStore()

        events = store.get_events("nonexistent-run")
        assert events == []

        stats = store.get_stats("nonexistent-run")
        assert stats == {}

    def test_invalid_sequence_number(self):
        """Test with invalid sequence numbers."""
        store = OptimizedEventStore()
        run_id = "seq-test"

        store.add_event(run_id, {"event_type": "log"})

        # Get with sequence beyond available
        events = store.get_events(run_id, since_sequence=1000)
        assert events == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
