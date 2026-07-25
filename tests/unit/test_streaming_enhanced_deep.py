"""Deep coverage tests for backend/app/api/streaming_enhanced.py — OptimizedEventStore + models + endpoints."""
import asyncio
import time
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip entire module if orjson is not installed
pytest.importorskip("orjson", reason="orjson not installed")

from backend.app.api.streaming_enhanced import (
    CompletionEvent,
    HeartbeatEvent,
    LogEntry,
    MetricUpdate,
    OptimizedEventStore,
    ProgressUpdate,
    StreamEventBase,
    TaskStatusUpdate,
    ToolInvocation,
    ToolResult,
    _send_event_batch,
    _stream_events_optimized,
    event_store,
    get_stream_stats,
    stream_health,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Event Models
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventModels:
    def test_stream_event_base(self):
        e = StreamEventBase(event_type="test", run_id="r1")
        assert e.event_type == "test"
        assert e.run_id == "r1"
        assert e.sequence == 0
        assert e.timestamp  # auto-generated

    def test_task_status_update(self):
        e = TaskStatusUpdate(run_id="r1", task_id="t1", status="running", title="T", progress=0.5)
        assert e.event_type == "task_status"
        assert e.details == {}

    def test_progress_update(self):
        e = ProgressUpdate(run_id="r1", overall_progress=0.7, current_step="s2", total_steps=5, completed_steps=3)
        assert e.event_type == "progress"
        assert e.estimated_remaining_seconds is None

    def test_log_entry(self):
        e = LogEntry(run_id="r1", level="error", message="boom", source="tool", context={"k": "v"})
        assert e.event_type == "log"
        assert e.context == {"k": "v"}

    def test_metric_update(self):
        e = MetricUpdate(run_id="r1", metric_name="cpu", metric_value=95.5, unit="%", tags={"host": "a"})
        assert e.event_type == "metric"

    def test_tool_invocation(self):
        e = ToolInvocation(run_id="r1", tool_id="ti1", tool_name="search", arguments={"q": "x"})
        assert e.event_type == "tool_call"
        assert e.status == "pending"

    def test_tool_result(self):
        e = ToolResult(run_id="r1", tool_id="ti1", tool_name="search", result="ok", success=True, execution_time_ms=12.3)
        assert e.event_type == "tool_result"

    def test_completion_event(self):
        e = CompletionEvent(run_id="r1", status="completed", result={"answer": "42"}, summary={"steps": 3})
        assert e.event_type == "completion"

    def test_heartbeat_event(self):
        e = HeartbeatEvent(run_id="r1")
        assert e.event_type == "heartbeat"


# ═══════════════════════════════════════════════════════════════════════════════
# OptimizedEventStore — init / add_event / get_events / get_stats
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimizedEventStoreBasic:
    def test_init_defaults(self):
        store = OptimizedEventStore()
        assert store.max_events_per_run == 5000
        assert store.max_queue_size == 500
        assert store.cleanup_interval_seconds == 300
        assert store.event_batch_size == 10
        assert store.event_batch_timeout_ms == 50
        assert store._cleanup_task is None

    def test_init_custom(self):
        store = OptimizedEventStore(max_events_per_run=10, max_queue_size=5, cleanup_interval_seconds=60,
                                    event_batch_size=2, event_batch_timeout_ms=10)
        assert store.max_events_per_run == 10

    def test_add_event_assigns_sequence(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "a"})
        store.add_event("r1", {"event_type": "b"})
        assert store.events["r1"][0]["sequence"] == 1
        assert store.events["r1"][1]["sequence"] == 2

    def test_add_event_updates_metrics(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "x"})
        m = store.metrics["r1"]
        assert m["total_events"] == 1
        assert m["last_event_time"] is not None

    def test_add_event_circular_buffer(self):
        store = OptimizedEventStore(max_events_per_run=3)
        for i in range(5):
            store.add_event("r1", {"event_type": f"e{i}"})
        assert len(store.events["r1"]) == 3
        # Oldest events evicted
        assert store.events["r1"][0]["sequence"] == 3

    def test_get_events_empty(self):
        store = OptimizedEventStore()
        assert store.get_events("nonexistent") == []

    def test_get_events_since_sequence(self):
        store = OptimizedEventStore()
        for i in range(5):
            store.add_event("r1", {"event_type": f"e{i}"})
        events = store.get_events("r1", since_sequence=3)
        assert len(events) == 2
        assert events[0]["sequence"] == 4

    def test_get_events_all(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "a"})
        events = store.get_events("r1", since_sequence=0)
        assert len(events) == 1

    def test_get_stats_specific_run(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "a"})
        stats = store.get_stats("r1")
        assert stats["total_events"] == 1

    def test_get_stats_unknown_run(self):
        store = OptimizedEventStore()
        assert store.get_stats("unknown") == {}

    def test_get_stats_global(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "a"})
        store.add_event("r2", {"event_type": "b"})
        stats = store.get_stats()
        assert stats["total_runs"] == 2
        assert stats["total_events"] == 2
        assert stats["active_connections"] == 0
        assert "r1" in stats["runs"]


# ═══════════════════════════════════════════════════════════════════════════════
# OptimizedEventStore — subscribe / unsubscribe / notify
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimizedEventStoreSubscribers:
    def test_subscribe(self):
        store = OptimizedEventStore()
        q = store.subscribe("r1")
        assert isinstance(q, asyncio.Queue)
        assert store.connection_count["r1"] == 1
        assert store.metrics["r1"]["total_subscribers"] == 1
        assert store.metrics["r1"]["peak_connections"] == 1

    def test_subscribe_multiple(self):
        store = OptimizedEventStore()
        store.subscribe("r1")
        store.subscribe("r1")
        assert store.connection_count["r1"] == 2
        assert store.metrics["r1"]["peak_connections"] == 2

    def test_unsubscribe(self):
        store = OptimizedEventStore()
        q = store.subscribe("r1")
        store.unsubscribe("r1", q)
        assert store.connection_count["r1"] == 0

    def test_unsubscribe_unknown_run(self):
        store = OptimizedEventStore()
        q = asyncio.Queue()
        store.unsubscribe("nonexist", q)  # should not raise

    def test_unsubscribe_not_in_list(self):
        store = OptimizedEventStore()
        store.subscribe("r1")
        other_q = asyncio.Queue()
        store.unsubscribe("r1", other_q)  # ValueError suppressed
        assert store.connection_count["r1"] == 1

    def test_notify_subscribers_receives_event(self):
        store = OptimizedEventStore()
        q = store.subscribe("r1")
        store.add_event("r1", {"event_type": "test"})
        assert not q.empty()
        item = q.get_nowait()
        assert item["event_type"] == "test"

    def test_notify_no_subscribers(self):
        store = OptimizedEventStore()
        store.add_event("r1", {"event_type": "test"})  # no crash

    def test_notify_queue_full_drops_oldest(self):
        store = OptimizedEventStore(max_queue_size=2)
        q = store.subscribe("r1")
        # Fill the queue
        q.put_nowait({"old": 1})
        q.put_nowait({"old": 2})
        # This should trigger QueueFull → drop oldest
        store.add_event("r1", {"event_type": "new"})
        # Queue should still have 2 items, oldest dropped
        assert q.qsize() == 2

    def test_notify_dead_queue_removed(self):
        store = OptimizedEventStore()
        q = MagicMock()
        q.put_nowait = MagicMock(side_effect=RuntimeError("dead"))
        store.subscribers["r1"].append(q)
        store.connection_count["r1"] = 1
        store.add_event("r1", {"event_type": "x"})
        # Dead queue removed
        assert q not in store.subscribers.get("r1", [])
        assert store.connection_count["r1"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# OptimizedEventStore — cleanup
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimizedEventStoreCleanup:
    def test_cleanup_old_events_removes_stale(self):
        store = OptimizedEventStore()
        old_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        new_time = datetime.utcnow().isoformat()
        store.events["r1"] = deque([
            {"timestamp": old_time, "sequence": 1},
            {"timestamp": new_time, "sequence": 2},
        ], maxlen=5000)
        store._cleanup_old_events()
        assert len(store.events["r1"]) == 1
        assert store.events["r1"][0]["sequence"] == 2

    def test_cleanup_old_events_removes_empty_run(self):
        store = OptimizedEventStore()
        old_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        store.events["r1"] = deque([{"timestamp": old_time, "sequence": 1}], maxlen=5000)
        store.batch_buffers["r1"] = [{"x": 1}]
        store._cleanup_old_events()
        assert "r1" not in store.events
        assert "r1" not in store.batch_buffers

    def test_cleanup_old_events_no_timestamp(self):
        store = OptimizedEventStore()
        store.events["r1"] = deque([{"sequence": 1}], maxlen=5000)
        store._cleanup_old_events()
        # Event with no timestamp has "" >= cutoff → False → removed
        assert "r1" not in store.events

    def test_cleanup_dead_connections(self):
        store = OptimizedEventStore()
        q = asyncio.Queue()
        # Simulate a dead queue: empty and _finished set
        q._finished.set()
        store.subscribers["r1"] = [q]
        store.connection_count["r1"] = 1
        store._cleanup_dead_connections()
        assert "r1" not in store.subscribers

    def test_cleanup_dead_connections_keeps_alive(self):
        store = OptimizedEventStore()
        q = asyncio.Queue()
        q.put_nowait("alive")
        store.subscribers["r1"] = [q]
        store.connection_count["r1"] = 1
        store._cleanup_dead_connections()
        assert len(store.subscribers["r1"]) == 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        store = OptimizedEventStore(cleanup_interval_seconds=0.01)
        await store.start()
        assert store._cleanup_task is not None
        await store.stop()
        assert store._cleanup_task.cancelled() or store._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        store = OptimizedEventStore(cleanup_interval_seconds=100)
        await store.start()
        task1 = store._cleanup_task
        await store.start()
        assert store._cleanup_task is task1
        await store.stop()

    @pytest.mark.asyncio
    async def test_stop_no_task(self):
        store = OptimizedEventStore()
        await store.stop()  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# _send_event_batch
# ═══════════════════════════════════════════════════════════════════════════════

class TestSendEventBatch:
    @pytest.mark.asyncio
    async def test_send_batch_yields_sse(self):
        events = [
            {"event_type": "log", "msg": "hello"},
            {"event_type": "metric", "val": 1},
        ]
        chunks = []
        async for chunk in _send_event_batch(events, "r1"):
            chunks.append(chunk)
        assert "event: log\n" in chunks
        assert "event: metric\n" in chunks
        # Each event yields 2 chunks (event line + data line)
        assert len(chunks) == 4

    @pytest.mark.asyncio
    async def test_send_batch_default_event_type(self):
        events = [{"no_type": True}]
        chunks = []
        async for chunk in _send_event_batch(events, "r1"):
            chunks.append(chunk)
        assert "event: message\n" in chunks


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints (unit-level with mocked dependencies)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndpoints:
    @pytest.mark.asyncio
    async def test_stream_health(self):
        result = await stream_health()
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "stats" in result

    @pytest.mark.asyncio
    async def test_get_stream_stats(self):
        principal = MagicMock()
        with patch("backend.app.api.streaming_enhanced.enforce_scope"):
            result = await get_stream_stats("run123", principal)
        assert result["run_id"] == "run123"
        assert "total_events" in result
        assert "active_connections" in result

    @pytest.mark.asyncio
    async def test_emit_event(self):
        from backend.app.api.streaming_enhanced import emit_event
        principal = MagicMock()
        with patch("backend.app.api.streaming_enhanced.enforce_scope"):
            result = await emit_event("r1", event_type="custom", principal=principal)
        assert result["status"] == "emitted"
        assert result["run_id"] == "r1"
        assert result["sequence"] is not None

    @pytest.mark.asyncio
    async def test_emit_task_status(self):
        from backend.app.api.streaming_enhanced import emit_task_status
        principal = MagicMock()
        with patch("backend.app.api.streaming_enhanced.enforce_scope"):
            result = await emit_task_status("r1", task_id="t1", status="running",
                                           title="Test", progress=0.5, principal=principal)
        assert result["status"] == "emitted"

    @pytest.mark.asyncio
    async def test_emit_progress(self):
        from backend.app.api.streaming_enhanced import emit_progress
        principal = MagicMock()
        with patch("backend.app.api.streaming_enhanced.enforce_scope"):
            result = await emit_progress("r1", overall_progress=0.8,
                                        current_step="step3", total_steps=5,
                                        completed_steps=4, principal=principal)
        assert result["status"] == "emitted"

    @pytest.mark.asyncio
    async def test_startup_shutdown(self):
        from backend.app.api.streaming_enhanced import startup, shutdown
        with patch.object(event_store, "start", new_callable=AsyncMock) as mock_start:
            await startup()
            mock_start.assert_called_once()
        with patch.object(event_store, "stop", new_callable=AsyncMock) as mock_stop:
            await shutdown()
            mock_stop.assert_called_once()
