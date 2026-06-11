from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.core.audit import AuditStore
from backend.app.core.contracts import AgentRunResponse, RunStatus
from backend.app.core.control_modes import ControlModeStore
from backend.app.core.runs import RunStore
from backend.app.dependencies import get_agent, get_audit_store, get_control_mode_store, get_run_store
from backend.app.main import app


def test_control_plan_api_draft_and_approve(tmp_path) -> None:
    store = ControlModeStore(tmp_path / "control.json")
    audit_store = AuditStore(tmp_path / "audit.jsonl", hmac_secret="test-secret")
    app.dependency_overrides[get_control_mode_store] = lambda: store
    app.dependency_overrides[get_audit_store] = lambda: audit_store
    try:
        client = TestClient(app, headers={"x-api-key": "bootstrap"})

        response = client.post(
            "/api/v1/control/plans",
            json={"task": "add plan mode", "context": {"inspected_files": ["backend/app/main.py"]}},
        )
        assert response.status_code == 200
        plan = response.json()
        assert plan["status"] == "waiting_approval"
        assert plan["coding_loop"]["phases"] == ["explore", "plan", "edit", "verify", "deliver"]

        approved = client.post(
            f"/api/v1/control/plans/{plan['plan_id']}/approve",
            json={"reason": "looks good"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert sorted(item.action for item in audit_store.list(limit=10)) == [
            "control.plan.approve",
            "control.plan.draft",
        ]
    finally:
        app.dependency_overrides.pop(get_control_mode_store, None)
        app.dependency_overrides.pop(get_audit_store, None)


def test_control_goal_api_create_and_plan_only_advance(tmp_path) -> None:
    store = ControlModeStore(tmp_path / "control.json")
    audit_store = AuditStore(tmp_path / "audit.jsonl", hmac_secret="test-secret")
    app.dependency_overrides[get_control_mode_store] = lambda: store
    app.dependency_overrides[get_audit_store] = lambda: audit_store
    try:
        client = TestClient(app, headers={"x-api-key": "bootstrap"})

        created = client.post(
            "/api/v1/control/goals",
            json={
                "objective": "ship loop engineering mode",
                "policy": {"require_plan_approval": False, "max_iterations": 3},
            },
        )
        assert created.status_code == 200
        goal = created.json()
        assert goal["status"] == "active"
        assert goal["snapshot"]["loop"] == "engineering"

        advanced = client.post(
            f"/api/v1/control/goals/{goal['goal_id']}/advance",
            json={"execute": False, "user_feedback": "continue"},
        )
        assert advanced.status_code == 200
        payload = advanced.json()
        assert payload["status"] == "active"
        assert payload["iterations"][0]["status"] == "planned"
        assert payload["snapshot"]["next_action"] == "execute_iteration"
    finally:
        app.dependency_overrides.pop(get_control_mode_store, None)
        app.dependency_overrides.pop(get_audit_store, None)


def test_control_goal_api_execute_advance_records_agent_result(tmp_path) -> None:
    store = ControlModeStore(tmp_path / "control.json")
    run_store = RunStore(tmp_path / "runs.jsonl")
    audit_store = AuditStore(tmp_path / "audit.jsonl", hmac_secret="test-secret")

    class FakeAgent:
        async def run(self, context, task, extra_context):
            return AgentRunResponse(
                trace_id="trace-exec",
                agent_id=context.agent_id,
                status=RunStatus.COMPLETED,
                answer="goal achieved and completed",
                iterations=1,
                memory_hits=0,
                execution_summary={"goal_id": extra_context["goal_id"]},
            )

    app.dependency_overrides[get_control_mode_store] = lambda: store
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_agent] = lambda: FakeAgent()
    app.dependency_overrides[get_audit_store] = lambda: audit_store
    try:
        client = TestClient(app, headers={"x-api-key": "bootstrap"})
        created = client.post(
            "/api/v1/control/goals",
            json={
                "objective": "execute one loop iteration",
                "policy": {"require_plan_approval": False, "max_iterations": 3},
            },
        ).json()

        advanced = client.post(
            f"/api/v1/control/goals/{created['goal_id']}/advance",
            json={"execute": True},
        )

        assert advanced.status_code == 200
        payload = advanced.json()
        assert payload["status"] == "completed"
        assert payload["stop_reason"] == "completion_reported"
        assert payload["active_trace_id"] == "trace-exec"
        assert payload["iterations"][0]["trace_id"] == "trace-exec"
        assert run_store.get("trace-exec") is not None
    finally:
        app.dependency_overrides.pop(get_control_mode_store, None)
        app.dependency_overrides.pop(get_run_store, None)
        app.dependency_overrides.pop(get_agent, None)
        app.dependency_overrides.pop(get_audit_store, None)
