"""Fine-grained SSE agent stream event tests.

Covers the true-streaming bridge in backend/app/api/streaming.py:
- POST /api/v1/agent/run/stream bridges AgentLoop trace events
  (via the event_callback hook) onto the run's SSE channel
- GET  /api/v1/agent/stream/{run_id} replays buffered events and closes
  after the terminal completion event
- tool_call / tool_result events carry tool name + truncated summaries
- pending approvals surface as approval_required events
- pure mapping helpers (trace_to_stream_event / tool_call_to_result_event /
  approval_to_event) are covered without a server
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.app.api.streaming import (
    approval_to_event,
    event_store,
    tool_call_to_result_event,
    trace_to_stream_event,
)
from backend.app.core.approvals import ApprovalStore
from backend.app.core.contracts import RunContext, TraceEvent
from backend.app.main import app


def _reset_event_store() -> None:
    event_store.events.clear()
    event_store.subscribers.clear()
    event_store.sequence_counters.clear()
    event_store.connection_count.clear()


def _wait_for_completion(client: TestClient, run_id: str, timeout_s: float = 60.0) -> list[dict]:
    """Poll the buffered-events endpoint until a completion event lands."""
    deadline = time.time() + timeout_s
    events: list[dict] = []
    while time.time() < deadline:
        response = client.get(f"/api/v1/agent/stream/{run_id}/events", params={"limit": 1000})
        assert response.status_code == 200
        body = response.json()
        events = body["events"]
        if any(e["event_type"] in ("completion", "error") for e in events):
            return events
        time.sleep(0.2)
    raise AssertionError(f"run {run_id} did not reach a terminal event; events={events[:5]}")


class TestTraceToStreamMapping:
    """Pure mapping: AgentLoop TraceEvent -> SSE StreamEvent."""

    def test_iteration_started_maps_to_iteration(self):
        ev = trace_to_stream_event(
            "run-1",
            TraceEvent(
                trace_id="t1",
                event="agent.iteration.started",
                data={"iteration": "2", "step_kind": "tool", "instruction": "Run echo now"},
            ),
        )
        assert ev is not None
        assert ev.event_type == "iteration"
        assert ev.data["iteration"] == 2
        assert ev.data["step_kind"] == "tool"
        assert ev.data["instruction"] == "Run echo now"
        assert ev.data["trace_id"] == "t1"

    def test_tool_completed_maps_to_tool_call(self):
        ev = trace_to_stream_event(
            "run-1",
            TraceEvent(
                trace_id="t1",
                event="agent.tool.completed",
                data={"iteration": "1", "tool_name": "echo", "success": "true", "latency_ms": "12"},
            ),
        )
        assert ev is not None
        assert ev.event_type == "tool_call"
        assert ev.data["tool_name"] == "echo"
        assert ev.data["success"] is True
        assert ev.data["latency_ms"] == 12
        assert ev.data["phase"] == "completed"

    def test_plan_created_maps_to_plan(self):
        ev = trace_to_stream_event(
            "run-1",
            TraceEvent(trace_id="t1", event="agent.plan.created", data={"goal": "g", "step_count": "3"}),
        )
        assert ev is not None
        assert ev.event_type == "plan"
        assert ev.data["step_count"] == 3

    def test_long_instruction_is_truncated(self):
        ev = trace_to_stream_event(
            "run-1",
            TraceEvent(
                trace_id="t1",
                event="agent.iteration.started",
                data={"iteration": "1", "step_kind": "observe", "instruction": "x" * 500},
            ),
        )
        assert ev is not None
        assert len(ev.data["instruction"]) <= 200
        assert ev.data["instruction"].endswith("...")

    def test_internal_events_are_dropped(self):
        for name in ("agent.completed", "agent.finalized", "agent.started", "unknown.event"):
            assert trace_to_stream_event("run-1", TraceEvent(trace_id="t1", event=name, data={})) is None

    def test_generic_lifecycle_events_pass_through(self):
        ev = trace_to_stream_event(
            "run-1",
            TraceEvent(trace_id="t1", event="agent.fast_path", data={"task": "hi"}),
        )
        assert ev is not None
        assert ev.event_type == "agent"
        assert ev.data["trace_event"] == "agent.fast_path"

    def test_tool_call_record_to_result_event(self):
        from backend.app.core.contracts import ToolPolicyVerdict

        record = type("R", (), {})()  # lightweight duck-typed record
        record.tool_name = "write_file"
        record.success = True
        record.latency_ms = 33.0
        record.arguments_preview = {"path": "a.py", "content": "c" * 10_000}
        record.output = {"applied": True, "detail": "d" * 10_000}
        record.error = None
        ev = tool_call_to_result_event("run-1", record)
        assert ev.event_type == "tool_result"
        assert ev.data["tool_name"] == "write_file"
        assert ev.data["success"] is True
        assert len(ev.data["arguments"]) <= 303  # truncated (300 + ellipsis)
        assert len(ev.data["output"]) <= 403

    def test_approval_record_to_event(self):
        record = type("A", (), {})()
        record.id = "appr-1"
        record.resource_id = "write_file"
        record.action = "tool.execute"
        record.risk_level = type("RL", (), {"value": "high"})()
        record.reason = "writes to repo root"
        record.arguments_preview = {"path": "x.py"}
        ev = approval_to_event("run-1", record)
        assert ev.event_type == "approval_required"
        assert ev.data["approval_id"] == "appr-1"
        assert ev.data["tool_name"] == "write_file"
        assert ev.data["risk_level"] == "high"


class TestStreamingRunEvents:
    """End-to-end: run/stream produces a fine-grained event sequence."""

    def setup_method(self):
        _reset_event_store()
        # Context-managed TestClient keeps one portal/event loop alive for
        # the whole test, so the background agent task keeps running
        # between the POST and the polling GETs.
        self._client_cm = TestClient(app, headers={"x-api-key": "bootstrap"})
        self.client = self._client_cm.__enter__()

    def teardown_method(self):
        self._client_cm.__exit__(None, None, None)
        _reset_event_store()

    def test_run_stream_event_sequence(self):
        # A task containing complex keywords ("file"/"run") forces the full
        # pipeline (fast-path skipped), so iterations and tool calls occur.
        response = self.client.post(
            "/api/v1/agent/run/stream",
            json={"task": "echo: run the file check now"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "started"
        run_id = body["run_id"]
        assert body["trace_id"]

        events = _wait_for_completion(self.client, run_id)
        types = [e["event_type"] for e in events]

        # Fine-grained agent events must be present alongside legacy ones
        assert "iteration" in types, f"missing iteration event in {types}"
        assert "tool_call" in types, f"missing tool_call event in {types}"
        assert "completion" in types, f"missing completion event in {types}"
        # legacy compatibility events preserved
        assert "message" in types
        assert "progress" in types

        # tool_call carries tool name + success
        tool_events = [e for e in events if e["event_type"] == "tool_call"]
        assert tool_events, "no tool_call events"
        executed = [e for e in tool_events if e["data"].get("tool_name")]
        assert executed, f"tool_call events lack tool_name: {[e['data'] for e in tool_events]}"
        assert executed[0]["data"]["success"] is True
        executed_tool = executed[0]["data"]["tool_name"]

        # tool_result detail event with arguments/output summaries
        result_events = [
            e for e in events
            if e["event_type"] == "tool_result" and e["data"].get("tool_name") == executed_tool
        ]
        assert result_events
        assert "arguments" in result_events[0]["data"]
        assert result_events[0]["data"]["output"]

        # completion is last
        assert types[-1] == "completion"

        # sequences are strictly increasing
        seqs = [e["sequence"] for e in events]
        assert seqs == sorted(seqs)

    def test_sse_stream_closes_after_completion(self):
        response = self.client.post(
            "/api/v1/agent/run/stream",
            json={"task": "echo: run the file closure check"},
        )
        assert response.status_code == 200
        run_id = response.json()["run_id"]

        # Subscribe via the SSE endpoint; the server must close the stream
        # after the terminal completion event instead of hanging on
        # heartbeats.
        with self.client.stream(
            "GET", f"/api/v1/agent/stream/{run_id}", timeout=60.0
        ) as stream:
            assert stream.status_code == 200
            text = "".join(chunk for chunk in stream.iter_text())

        assert "event: completion" in text
        assert "event: iteration" in text
        assert "event: tool_call" in text
        # terminal close means iter_text() returned without a timeout

    def test_error_event_on_invalid_run_isolated(self):
        # A run on an unknown run_id simply has no buffered events yet.
        response = self.client.get("/api/v1/agent/stream/does-not-exist/events")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestApprovalRequiredEvents:
    """Pending approvals surface as approval_required SSE events."""

    def setup_method(self):
        _reset_event_store()
        self._client_cm = TestClient(app, headers={"x-api-key": "bootstrap"})
        self.client = self._client_cm.__enter__()

    def teardown_method(self):
        self._client_cm.__exit__(None, None, None)
        _reset_event_store()

    def test_pending_approval_emits_event(self, monkeypatch):
        from backend.app.dependencies import get_agent

        agent = get_agent()
        store = ApprovalStore()
        context = RunContext(tenant_id="default", user_id="bootstrap-admin", trace_id="t-approval")
        store.create_tool_approval(
            context=context,
            tool_name="write_file",
            risk_level=context.risk_level,
            reason="high risk write",
            arguments_preview={"path": "cfg.py"},
        )
        monkeypatch.setattr(agent, "approval_store", store)
        try:
            response = self.client.post(
                "/api/v1/agent/run/stream",
                json={"task": "echo: run the file approval flow"},
            )
            assert response.status_code == 200
            run_id = response.json()["run_id"]
            events = _wait_for_completion(self.client, run_id)

            approval_events = [e for e in events if e["event_type"] == "approval_required"]
            assert approval_events, f"no approval_required event in {[e['event_type'] for e in events]}"
            data = approval_events[0]["data"]
            assert data["tool_name"] == "write_file"
            assert data["approval_id"]
            assert data["reason"] == "high risk write"

            # approval_required must precede the terminal completion event
            types = [e["event_type"] for e in events]
            assert types.index("approval_required") < types.index("completion")
        finally:
            monkeypatch.setattr(agent, "approval_store", None)
