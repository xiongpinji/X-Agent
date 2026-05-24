from __future__ import annotations

from backend.app.core.memory import MemorySystem
from backend.app.core.runs import RunStore
from backend.app.core.tracing import TraceStore


def test_run_store_snapshot_for_missing_trace() -> None:
    store = RunStore()

    assert store.snapshot_for("missing") is None


def test_trace_store_resume_event_recording() -> None:
    store = TraceStore()

    class Context:
        trace_id = "trace-1"
        request_id = "req-1"
        agent_id = "agent-1"
        tenant_id = "tenant-1"
        user_id = "user-1"

    event = store.record_resume(Context(), "trace-0", stage="resuming:trace-0")

    assert event.event == "agent.resumed"
    assert event.data["resumed_from"] == "trace-0"
    assert store.event_count() == 1


def test_memory_session_snapshot_empty_when_missing() -> None:
    memory = MemorySystem()

    assert memory.session_snapshot("missing") is None
