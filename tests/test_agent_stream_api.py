from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.api import agents as agents_api
from backend.app.core.artifacts import ArtifactStorage
from backend.app.core.contracts import AgentRunResponse, RunStatus
from backend.app.core.run_artifacts import RunArtifactManager, get_run_artifact_manager
from backend.app.core.security import ROLE_SCOPES, Principal
from backend.app.dependencies import get_current_principal
from backend.app.main import app


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)
        return None


class _CompletingAgent:
    max_iterations = 20

    def __init__(self) -> None:
        self.context = None
        self.task: str | None = None
        self.extra_context: dict[str, Any] | None = None

    async def run(self, context, task, extra_context, event_callback=None) -> AgentRunResponse:
        self.context = context
        self.task = task
        self.extra_context = extra_context
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


class _FailingAuditSink:
    def record(self, **_kwargs: Any) -> None:
        raise RuntimeError("SENSITIVE_AUDIT_DETAIL_DO_NOT_LEAK")


def _principal() -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id="user-a",
        role="user",
        scopes=list(ROLE_SCOPES["user"]),
        authenticated=True,
    )


@pytest.fixture
def client(monkeypatch, tmp_path) -> Iterator[TestClient]:
    manager = RunArtifactManager(
        tmp_path / "runs",
        artifact_storage=ArtifactStorage(tmp_path / "artifacts"),
    )
    app.dependency_overrides[get_current_principal] = _principal
    app.dependency_overrides[get_run_artifact_manager] = lambda: manager
    monkeypatch.setattr(agents_api, "get_audit_store", lambda: _AuditSink())
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
        app.dependency_overrides.pop(get_run_artifact_manager, None)


def _completed_frames(response_text: str) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for block in response_text.split("\n\n"):
        if "event: completed" not in block:
            continue
        data = "".join(line.removeprefix("data: ") for line in block.splitlines() if line.startswith("data: "))
        frames.append(json.loads(data))
    return frames


def test_post_sse_emits_stable_completed_final_frame(client: TestClient, monkeypatch) -> None:
    agent = _CompletingAgent()
    monkeypatch.setattr(agents_api, "get_agent", lambda: agent)

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace", "extra_context": {"source": "chat"}},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _completed_frames(response.text)
    assert len(frames) == 1
    result = frames[0]["result"]
    assert {key: result[key] for key in (
        "trace_id",
        "agent_id",
        "status",
        "answer",
        "iterations",
        "memory_hits",
        "tool_calls",
        "events",
        "plan",
        "execution_summary",
        "error",
        "snapshot",
    )} == {
        "trace_id": "trace-success",
        "agent_id": "default-agent",
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
    }
    assert result["manifest"]["run_id"] == "trace-success"
    assert result["manifest"]["trace_id"] == "trace-success"
    assert result["manifest"]["status"] == "completed"
    assert result["manifest"]["tenant_id"] == "tenant-a"
    assert result["manifest"]["user_id"] == "user-a"
    assert len(result["manifest"]["artifacts"]) == 1
    assert agent.context.agent_id == "default-agent"
    assert agent.context.session_id is None
    assert agent.task == "summarize this workspace"
    assert agent.extra_context == {"source": "chat"}


def test_post_sse_binds_server_agent_and_session_context(client: TestClient, monkeypatch) -> None:
    agent = _CompletingAgent()
    monkeypatch.setattr(agents_api, "get_agent", lambda: agent)
    server_profile = {"system_prompt": "server-only", "temperature": 0.2}
    monkeypatch.setitem(
        agents_api._AGENTS,
        "custom-agent",
        {"id": "custom-agent", "name": "Custom", "status": "active", "persona": server_profile},
    )

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={
            "task": "summarize this workspace",
            "agent_id": "custom-agent",
            "session_id": "session-123",
            "extra_context": {
                "source": "chat",
                "agent_profile": {"system_prompt": "client override"},
                "persona": {"system_prompt": "client persona"},
                "profile": {"system_prompt": "client profile"},
            },
        },
    )

    assert response.status_code == 200
    assert agent.context.agent_id == "custom-agent"
    assert agent.context.session_id == "session-123"
    assert agent.extra_context == {"source": "chat", "agent_profile": server_profile}


def test_post_sse_rejects_unknown_agent(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace", "agent_id": "missing-agent"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "resource_not_found"


def test_post_sse_rejects_inactive_agent(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(agents_api, "get_agent", lambda: _CompletingAgent())
    monkeypatch.setitem(
        agents_api._AGENTS,
        "paused-agent",
        {"id": "paused-agent", "name": "Paused", "status": "paused"},
    )

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace", "agent_id": "paused-agent"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "resource_conflict"


def test_post_sse_emits_stable_failed_final_frame(client: TestClient, monkeypatch, caplog) -> None:
    audit_sink = _AuditSink()
    monkeypatch.setattr(agents_api, "get_agent", lambda: _FailingAgent())
    monkeypatch.setattr(agents_api, "get_audit_store", lambda: audit_sink)
    caplog.set_level(logging.ERROR, logger=agents_api.__name__)

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
    assert "SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK" not in caplog.text
    assert audit_sink.records == [
        {
            "action": "agent.run.stream",
            "resource_type": "agent",
            "resource_id": "default-agent",
            "tenant_id": "tenant-a",
            "actor_id": "user-a",
            "outcome": "failure",
            "trace_id": final[0]["result"]["trace_id"],
            "run_id": final[0]["result"]["trace_id"],
            "details": {"status": "failed", "error_code": "agent_execution_failed"},
        }
    ]


def test_failed_audit_write_does_not_block_or_leak_into_final(client: TestClient, monkeypatch, caplog) -> None:
    monkeypatch.setattr(agents_api, "get_agent", lambda: _FailingAgent())
    monkeypatch.setattr(agents_api, "get_audit_store", lambda: _FailingAuditSink())
    caplog.set_level(logging.ERROR, logger=agents_api.__name__)

    response = client.post(
        "/api/v1/agents/run/stream",
        headers={"Authorization": "Bearer test-token"},
        json={"task": "summarize this workspace"},
    )

    final = _completed_frames(response.text)
    assert response.status_code == 200
    assert len(final) == 1
    assert final[0]["result"]["status"] == "failed"
    assert final[0]["result"]["error_code"] == "agent_execution_failed"
    assert "SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK" not in response.text
    assert "SENSITIVE_AUDIT_DETAIL_DO_NOT_LEAK" not in response.text
    assert "SENSITIVE_INTERNAL_DETAIL_DO_NOT_LEAK" not in caplog.text
    assert "SENSITIVE_AUDIT_DETAIL_DO_NOT_LEAK" not in caplog.text
