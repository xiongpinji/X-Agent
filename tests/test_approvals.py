from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.core.approvals import ApprovalDecisionRequest, ApprovalStore
from backend.app.core.approvals import (
    ApprovalDecisionType,
    ApprovalStatus,
    ApprovalSubjectRequest,
    ApprovalSubjectType,
    infer_approval_subject_type,
)
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


def test_approval_store_normalizes_safety_subjects_and_decisions(tmp_path) -> None:
    store = ApprovalStore(storage_path=tmp_path / "approvals.json")
    record = store.create_subject_approval(
        context=RunContext(user_id="u1", tenant_id="t1", trace_id="trace-subject"),
        subject=ApprovalSubjectRequest(
            subject_type=ApprovalSubjectType.NETWORK_REQUEST,
            resource_id="https://example.com/api",
            risk_level=RiskLevel.HIGH,
            reason="external network requires owner gate",
            arguments_preview={"method": "POST", "host": "example.com"},
            sandbox_profile="network_default_deny",
            policy_snapshot={"policy": "default-deny"},
        ),
    )
    approved = store.approve(
        record.id,
        ApprovalDecisionRequest(
            decided_by="admin",
            reason="allow for this run",
            decision_type=ApprovalDecisionType.APPROVE_FOR_RUN,
        ),
    )
    reloaded = ApprovalStore(storage_path=tmp_path / "approvals.json").get(record.id)

    assert record.subject_type == ApprovalSubjectType.NETWORK_REQUEST
    assert record.resource_type == "network_request"
    assert record.action == "network.request"
    assert record.owner_gate_required is True
    assert record.audit_required is True
    assert record.sandbox_profile == "network_default_deny"
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.decision_type == ApprovalDecisionType.APPROVE_FOR_RUN
    assert approved.decision_scope == "run"
    assert reloaded.subject_type == ApprovalSubjectType.NETWORK_REQUEST
    assert reloaded.policy_snapshot == {"policy": "default-deny"}


def test_approval_store_supports_deny_and_abort_decisions() -> None:
    store = ApprovalStore()
    denied = store.create_subject_approval(
        context=RunContext(),
        subject=ApprovalSubjectRequest(
            subject_type=ApprovalSubjectType.CHANNEL_SEND,
            resource_id="feishu:chat:oc_123",
            risk_level=RiskLevel.MEDIUM,
            reason="channel send requires owner gate",
        ),
    )
    aborted = store.create_subject_approval(
        context=RunContext(),
        subject=ApprovalSubjectRequest(
            subject_type=ApprovalSubjectType.ISSUE_TO_PR_EXECUTE,
            resource_id="github:xiongpinji/X-Agent#1",
            risk_level=RiskLevel.HIGH,
            reason="GitHub mutation requires owner gate",
        ),
    )

    rejected = store.reject(denied.id, ApprovalDecisionRequest(decided_by="admin", reason="no send"))
    stopped = store.abort(aborted.id, ApprovalDecisionRequest(decided_by="admin", reason="stop task"))

    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.decision_type == ApprovalDecisionType.DENY
    assert rejected.decision_scope == "deny"
    assert stopped.status == ApprovalStatus.ABORTED
    assert stopped.decision_type == ApprovalDecisionType.ABORT
    assert stopped.decision_scope == "abort"


def test_infer_approval_subject_type_keeps_legacy_tool_and_workflow_compatible() -> None:
    assert infer_approval_subject_type("tool", "tool.execute") == ApprovalSubjectType.TOOL
    assert infer_approval_subject_type("workflow", "workflow.node.approve") == ApprovalSubjectType.WORKFLOW
    assert infer_approval_subject_type("file_change", "file_change.apply") == ApprovalSubjectType.FILE_CHANGE


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
