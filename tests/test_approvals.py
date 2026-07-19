from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.core.approvals import ApprovalDecisionRequest, ApprovalStore
from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import ToolRegistry
from backend.app.main import app


async def high_risk_tool(target: str) -> str:
    return f"deleted:{target}"


def test_approval_store_persists_and_decides(tmp_path) -> None:
    store = ApprovalStore(storage_path=tmp_path / "approvals.json")
    record = store.create_tool_approval(
        context=RunContext(user_id="u1", tenant_id="t1"),
        tool_name="danger",
        risk_level=RiskLevel.HIGH,
        reason="needs approval",
        arguments_preview={"target": "/tmp"},
        arguments={"target": "/tmp"},
    )

    approved = store.approve(record.id, ApprovalDecisionRequest(decided_by="admin"))
    reloaded = ApprovalStore(storage_path=tmp_path / "approvals.json")

    assert approved is not None
    assert approved.status == "approved"
    assert reloaded.get(record.id).status == "approved"
    assert reloaded.get(record.id).arguments == {"target": "/tmp"}


async def test_high_risk_tool_creates_approval_request() -> None:
    store = ApprovalStore()
    registry = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=False), approval_store=store)
    registry.register("danger", "Dangerous operation", high_risk_tool, RiskLevel.HIGH)

    result = await registry.execute(RunContext(), "danger", {"target": "/tmp"})

    approvals = store.list()
    assert result.success is False
    assert result.policy.requires_approval is True
    assert len(approvals) == 1
    assert approvals[0].resource_id == "danger"
    assert approvals[0].status == "pending"
    assert approvals[0].id in result.error
    assert approvals[0].arguments == {"target": "/tmp"}


async def test_approved_tool_executes_once() -> None:
    store = ApprovalStore()
    registry = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=False), approval_store=store)
    registry.register("danger", "Dangerous operation", high_risk_tool, RiskLevel.HIGH)
    context = RunContext(tenant_id="tenant-a", user_id="operator")

    blocked = await registry.execute(context, "danger", {"target": "/tmp"})
    approval = store.list()[0]
    store.approve(approval.id, ApprovalDecisionRequest(decided_by="admin", reason="ok"))

    executed = await registry.execute_approved(
        RunContext(tenant_id="tenant-a", user_id="admin"),
        approval.id,
    )
    replay = await registry.execute_approved(
        RunContext(tenant_id="tenant-a", user_id="admin"),
        approval.id,
    )

    assert blocked.success is False
    assert executed.success is True
    assert executed.output == "deleted:/tmp"
    assert store.get(approval.id).status == "executed"
    assert replay.success is False
    assert "executed" in replay.error


def test_approvals_api_flow() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    store = ApprovalStore()
    record = store.create_tool_approval(
        context=RunContext(),
        tool_name="manual",
        risk_level=RiskLevel.HIGH,
        reason="manual test",
        arguments_preview={},
    )
    from backend.app.dependencies import get_approval_store

    app.dependency_overrides[get_approval_store] = lambda: store
    try:
        listed = client.get("/api/v1/approvals")
        approved = client.post(
            f"/api/v1/approvals/{record.id}/approve",
            json={"decided_by": "admin", "reason": "ok"},
        )
    finally:
        app.dependency_overrides.pop(get_approval_store, None)

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == record.id
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_approvals_api_executes_approved_tool() -> None:
    client = TestClient(app, headers={"x-api-key": "bootstrap"})
    store = ApprovalStore()
    registry = ToolRegistry(ToolPolicyEngine(enable_high_risk_tools=False), approval_store=store)
    registry.register("danger", "Dangerous operation", high_risk_tool, RiskLevel.HIGH)
    record = store.create_tool_approval(
        context=RunContext(tenant_id="default"),
        tool_name="danger",
        risk_level=RiskLevel.HIGH,
        reason="manual test",
        arguments_preview={"target": "/tmp"},
        arguments={"target": "/tmp"},
    )
    store.approve(record.id, ApprovalDecisionRequest(decided_by="admin", reason="ok"))
    agent = SimpleNamespace(tools=registry)
    from backend.app.dependencies import get_agent, get_approval_store

    app.dependency_overrides[get_approval_store] = lambda: store
    app.dependency_overrides[get_agent] = lambda: agent
    try:
        executed = client.post(f"/api/v1/approvals/{record.id}/execute")
    finally:
        app.dependency_overrides.pop(get_approval_store, None)
        app.dependency_overrides.pop(get_agent, None)

    assert executed.status_code == 200
    assert executed.json()["success"] is True
    assert executed.json()["output"] == "deleted:/tmp"
    assert store.get(record.id).status == "executed"
