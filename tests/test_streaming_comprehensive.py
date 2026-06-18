"""
Tests for Streaming API

Comprehensive tests for SSE streaming endpoints, event handling,
and connection management.
"""

import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock

from backend.app.main import app
from backend.app.api.streaming import (
    event_store,
    StreamEventStore,
    STREAM_TOKEN_TTL_SECONDS,
    MessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    ProgressEvent,
    ErrorEvent,
    LogEvent,
    MetricEvent,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app, headers={"x-api-key": "bootstrap"})


@pytest.fixture
def reset_event_store():
    """Reset event store before each test."""
    event_store.events.clear()
    event_store.subscribers.clear()
    event_store.sequence_counters.clear()
    event_store.connection_count.clear()
    yield
    event_store.events.clear()
    event_store.subscribers.clear()
    event_store.sequence_counters.clear()
    event_store.connection_count.clear()


class TestStreamEventStore:
    """Test StreamEventStore functionality."""

    def test_add_event_assigns_sequence(self, reset_event_store):
        """Test that events are assigned sequence numbers."""
        run_id = "test-run-1"
        event1 = MessageEvent(run_id=run_id, content="Message 1")
        event2 = MessageEvent(run_id=run_id, content="Message 2")

        event_store.add_event(run_id, event1)
        event_store.add_event(run_id, event2)

        assert event1.sequence == 1
        assert event2.sequence == 2

    def test_get_events_filters_by_sequence(self, reset_event_store):
        """Test that get_events filters by sequence number."""
        run_id = "test-run-1"
        events = [
            MessageEvent(run_id=run_id, content=f"Message {i}")
            for i in range(5)
        ]

        for event in events:
            event_store.add_event(run_id, event)

        # Get events after sequence 2
        filtered = event_store.get_events(run_id, since_sequence=2)
        assert len(filtered) == 3
        assert filtered[0].sequence == 3

    def test_subscribe_creates_queue(self, reset_event_store):
        """Test that subscribe creates a queue."""
        run_id = "test-run-1"
        queue = event_store.subscribe(run_id)

        assert queue is not None
        assert run_id in event_store.subscribers

    def test_unsubscribe_removes_queue(self, reset_event_store):
        """Test that unsubscribe removes a queue."""
        run_id = "test-run-1"
        queue = event_store.subscribe(run_id)
        event_store.unsubscribe(run_id, queue)

        assert len(event_store.subscribers.get(run_id, [])) == 0

    def test_add_event_notifies_subscribers(self, reset_event_store):
        """Test that add_event notifies subscribers."""
        run_id = "test-run-1"
        queue = event_store.subscribe(run_id)
        event = MessageEvent(run_id=run_id, content="Test message")

        event_store.add_event(run_id, event)

        # Check that event was added to queue
        assert not queue.empty()
        queued_event = queue.get_nowait()
        assert queued_event.content == "Test message"

    def test_get_connection_count(self, reset_event_store):
        """Test connection count tracking."""
        run_id = "test-run-1"
        queue1 = event_store.subscribe(run_id)
        queue2 = event_store.subscribe(run_id)

        assert event_store.get_connection_count(run_id) == 2

        event_store.unsubscribe(run_id, queue1)
        assert event_store.get_connection_count(run_id) == 1

    def test_get_stats(self, reset_event_store):
        """Test statistics collection."""
        run_id1 = "test-run-1"
        run_id2 = "test-run-2"

        # Add events to run 1
        for i in range(5):
            event = MessageEvent(run_id=run_id1, content=f"Message {i}")
            event_store.add_event(run_id1, event)

        # Add events to run 2
        for i in range(3):
            event = MessageEvent(run_id=run_id2, content=f"Message {i}")
            event_store.add_event(run_id2, event)

        # Add subscribers
        event_store.subscribe(run_id1)
        event_store.subscribe(run_id2)
        event_store.subscribe(run_id2)

        stats = event_store.get_stats()
        assert stats["total_runs"] == 2
        assert stats["total_events"] == 8
        assert stats["total_connections"] == 3


class TestStreamingEndpoints:
    """Test streaming API endpoints."""

    def test_create_streaming_run(self, client, reset_event_store):
        """Test creating a streaming run."""
        response = client.post(
            "/api/v1/agent/run/stream",
            json={"task": "Test task"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert "stream_url" in data
        assert data["status"] == "started"

    def test_emit_log_event(self, client, reset_event_store):
        """Test emitting a log event."""
        run_id = "test-run-1"
        response = client.post(
            f"/api/v1/agent/stream/{run_id}/log",
            params={
                "level": "info",
                "message": "Test log message",
                "source": "agent"
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "logged"

        # Verify event was stored
        events = event_store.get_events(run_id)
        assert len(events) == 1
        assert events[0].event_type == "log"
        assert events[0].message == "Test log message"

    def test_emit_metric_event(self, client, reset_event_store):
        """Test emitting a metric event."""
        run_id = "test-run-1"
        response = client.post(
            f"/api/v1/agent/stream/{run_id}/metric",
            params={
                "metric_name": "tokens_used",
                "metric_value": "1500",
                "unit": "tokens"
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "metric_emitted"

        # Verify event was stored
        events = event_store.get_events(run_id)
        assert len(events) == 1
        assert events[0].event_type == "metric"
        assert events[0].metric_name == "tokens_used"
        assert events[0].metric_value == 1500

    def test_emit_task_status_event(self, client, reset_event_store):
        """Test emitting a task status event."""
        run_id = "test-run-1"
        response = client.post(
            f"/api/v1/agent/stream/{run_id}/task-status",
            params={
                "task_id": "task-1",
                "status": "running",
                "title": "Test Task"
            }
        )

        assert response.status_code == 200
        assert response.json()["status"] == "task_status_emitted"

        # Verify event was stored
        events = event_store.get_events(run_id)
        assert len(events) == 1
        assert events[0].event_type == "task_status"
        assert events[0].task_id == "task-1"
        assert events[0].status == "running"

    def test_get_stream_events(self, client, reset_event_store):
        """Test getting buffered events."""
        run_id = "test-run-1"

        # Add some events
        for i in range(5):
            event = MessageEvent(run_id=run_id, content=f"Message {i}")
            event_store.add_event(run_id, event)

        response = client.get(f"/api/v1/agent/stream/{run_id}/events")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["total"] == 5
        assert len(data["events"]) == 5

    def test_get_stream_events_with_since_sequence(self, client, reset_event_store):
        """Test getting events since a sequence number."""
        run_id = "test-run-1"

        # Add some events
        for i in range(5):
            event = MessageEvent(run_id=run_id, content=f"Message {i}")
            event_store.add_event(run_id, event)

        response = client.get(
            f"/api/v1/agent/stream/{run_id}/events",
            params={"since_sequence": 2}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["events"]) == 3
        assert data["events"][0]["sequence"] == 3

    def test_get_stream_stats(self, client, reset_event_store):
        """Test getting stream statistics."""
        run_id = "test-run-1"

        # Add some events
        for i in range(3):
            event = MessageEvent(run_id=run_id, content=f"Message {i}")
            event_store.add_event(run_id, event)

        # Add a subscriber
        event_store.subscribe(run_id)

        response = client.get(f"/api/v1/agent/stream/{run_id}/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["total_events"] == 3
        assert data["active_connections"] == 1
        assert "event_counts" in data

    def test_stream_health(self, client, reset_event_store):
        """Test stream health endpoint."""
        response = client.get("/api/v1/agent/stream/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "store_stats" in data

    def test_create_stream_token_returns_signed_stream_url(self, client, reset_event_store):
        """Test creating a short-lived EventSource stream URL."""
        run_id = "test-run-1"
        response = client.post(f"/api/v1/agent/stream/{run_id}/token")

        assert response.status_code == 200
        data = response.json()
        assert data["token_expires_in"] == STREAM_TOKEN_TTL_SECONDS
        assert data["stream_url"].startswith(f"/api/v1/agent/stream/{run_id}?token=")
        assert "Bearer" not in data["stream_url"]

    def test_create_stream_token_encodes_reserved_run_id_characters(self, client, reset_event_store):
        """Test signed stream URLs keep reserved run_id characters out of the query."""
        run_id = "run with?reserved&chars"
        response = client.post("/api/v1/agent/stream/run%20with%3Freserved%26chars/token")

        assert response.status_code == 200
        stream_url = response.json()["stream_url"]
        assert stream_url.startswith("/api/v1/agent/stream/run%20with%3Freserved%26chars?token=")
        assert run_id not in stream_url
        assert stream_url.count("?token=") == 1

    def test_subscribe_to_stream_accepts_signed_stream_token(self, client, reset_event_store):
        """Test EventSource clients can authenticate with short-lived stream token."""
        run_id = "test-run-1"
        token_response = client.post(f"/api/v1/agent/stream/{run_id}/token")
        assert token_response.status_code == 200

        event_store.add_event(run_id, MessageEvent(run_id=run_id, content="ready"))
        stream_url = token_response.json()["stream_url"]
        response = TestClient(app).get(f"{stream_url}&since_sequence=0&replay_only=true")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "ready" in response.text

    def test_subscribe_to_stream_rejects_bad_signed_stream_token(self, reset_event_store):
        """Test invalid stream tokens cannot authenticate EventSource subscriptions."""
        response = TestClient(app).get("/api/v1/agent/stream/test-run-1?token=bad")

        assert response.status_code == 401


class TestEventTypes:
    """Test different event types."""

    def test_message_event(self, reset_event_store):
        """Test MessageEvent creation and storage."""
        run_id = "test-run-1"
        event = MessageEvent(
            run_id=run_id,
            content="Test message",
            role="assistant"
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "message"
        assert stored.content == "Test message"
        assert stored.role == "assistant"

    def test_tool_call_event(self, reset_event_store):
        """Test ToolCallEvent creation and storage."""
        run_id = "test-run-1"
        event = ToolCallEvent(
            run_id=run_id,
            tool_name="read_file",
            tool_id="tool-1",
            arguments={"path": "/test"}
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "tool_call"
        assert stored.tool_name == "read_file"
        assert stored.arguments == {"path": "/test"}

    def test_progress_event(self, reset_event_store):
        """Test ProgressEvent creation and storage."""
        run_id = "test-run-1"
        event = ProgressEvent(
            run_id=run_id,
            overall_progress=0.5,
            current_step="Executing",
            total_steps=4,
            completed_steps=2
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "progress"
        assert stored.overall_progress == 0.5
        assert stored.completed_steps == 2

    def test_error_event(self, reset_event_store):
        """Test ErrorEvent creation and storage."""
        run_id = "test-run-1"
        event = ErrorEvent(
            run_id=run_id,
            error_code="TEST_ERROR",
            error_message="Test error message",
            recoverable=True
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "error"
        assert stored.error_code == "TEST_ERROR"
        assert stored.recoverable is True

    def test_log_event(self, reset_event_store):
        """Test LogEvent creation and storage."""
        run_id = "test-run-1"
        event = LogEvent(
            run_id=run_id,
            level="warning",
            message="Test warning",
            source="tool"
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "log"
        assert stored.level == "warning"
        assert stored.source == "tool"

    def test_metric_event(self, reset_event_store):
        """Test MetricEvent creation and storage."""
        run_id = "test-run-1"
        event = MetricEvent(
            run_id=run_id,
            metric_name="execution_time",
            metric_value=1234,
            unit="ms"
        )
        event_store.add_event(run_id, event)

        stored = event_store.get_events(run_id)[0]
        assert stored.event_type == "metric"
        assert stored.metric_name == "execution_time"
        assert stored.metric_value == 1234


class TestConcurrency:
    """Test concurrent event handling."""

    def test_multiple_subscribers(self, reset_event_store):
        """Test multiple subscribers receiving events."""
        run_id = "test-run-1"
        queue1 = event_store.subscribe(run_id)
        queue2 = event_store.subscribe(run_id)

        event = MessageEvent(run_id=run_id, content="Test")
        event_store.add_event(run_id, event)

        # Both queues should receive the event
        assert not queue1.empty()
        assert not queue2.empty()

    def test_queue_overflow_handling(self, reset_event_store):
        """Test handling of queue overflow."""
        run_id = "test-run-1"
        queue = event_store.subscribe(run_id)

        # Fill the queue beyond capacity
        for i in range(150):
            event = MessageEvent(run_id=run_id, content=f"Message {i}")
            event_store.add_event(run_id, event)

        # Queue should still be functional
        assert not queue.empty()
        # Should have at most max_queue_size items
        assert queue.qsize() <= 100
