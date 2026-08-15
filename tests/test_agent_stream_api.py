from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import ANY

import pytest
from fastapi.testclient import TestClient

from backend.app.api import agents as agents_api
from backend.app.core.contracts import AgentRunResponse, RunStatus
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app


class _AuditSink:
    def record(self, **_kwargs: Any) -> None:
        return None


class _CompletingAgent:
    max_iterations = 20

    async def run(self, context, task, extra_context, event_callback=None) -> AgentRunResponse:
        assert task == "summarize this workspace"
        assert extra_context == {"source": "chat"}
        return AgentRunResponse(
            trace_id="trace-success",
            agent_id=context.agent_id,
            status=RunStatus.COMPLETED,
            answer="A real routed answer",
            iterations=1,
            memory_hits=0,
        )


class _FailingAgent:
    max_iterations = 20

    async def run(self, context, task, extra_context, event_callback=None) -> AgentRunResponse:
        raise RuntimeError("SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK")


def _principal() -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=list(ROLE_SCOPES["user"]),
        authenticated=True,
    )


@pytest.fixture
def client(monkeypatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_current_principal] = _principal
    monkeypatch.setattr(agents_api, "get_audit_store", lambda: _AuditSink())
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_principal, None)


def _completed_frames(response_text: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for block in response_text.split("\n\n"):
        if "event: completed" not in block:
            continue
        data = "".join(line.removeprefix("data: ") for line in block.splitlines() if line.startswith("data: "))
        frames.append(json.loads(data))
    return frames


def test_post_sse_emits_stable_completed_final_frame(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace", "extra_context": {"source": "chat"}},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _completed_frames(response.text) == [
        {
            "_final": True,
            "result": {
                "trace_id": "trace-success",
                "agent_id": ANY,
                "status": "completed",
                "answer": "A real routed answer",
                "iterations": 1,
                "memory_hits": 0,
                "tool_calls": [],
                "events": [],
                "plan": [],
                "execution_summary": {},
                "error": None,
                "snapshot": {},
            },
        }
    ]


def test_post_sse_emits_stable_failed_final_frame(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(agents_api, "get_agent", lambda: _FailingAgent())

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace", "extra_context": {"source": "chat"}},
    )

    assert response.status_code == 200
    final = _completed_frames(response.text)
    assert len(final) == 1
    assert final[0]["_final"] is True
    assert final[0]["result"]["status"] == "failed"
    assert final[0]["result"]["trace_id"]
    assert final[0]["result"]["answer"] == ""
    assert final[0]["result"]["error_code"] == "agent_execution_failed"
    assert final[0]["result"]["error"] == "Agent execution failed"
    assert "SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK" not in response.text
