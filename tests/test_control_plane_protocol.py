from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.core.approvals import ApprovalDecisionRequest, ApprovalStore
from backend.app.core.audit import AuditStore
from backend.app.core.contracts import AgentRunResponse, RiskLevel, RunContext, RunStatus
from backend.app.core.runs import RunStore
from backend.app.core.tracing import TraceStore
from backend.app.dependencies import get_approval_store, get_audit_store, get_run_store, get_trace_store
from backend.app.main import app
from backend.app.sdk import ControlPlaneSDK


def _client() -> TestClient:
    return TestClient(app, headers={"x-api-key": "bootstrap"})


@contextmanager
def _client_with_stores(
    run_store: RunStore,
    trace_store: TraceStore,
    approval_store: ApprovalStore,
    audit_store: AuditStore | None = None,
):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_trace_store] = lambda: trace_store
    app.dependency_overrides[get_approval_store] = lambda: approval_store
    if audit_store is not None:
        app.dependency_overrides[get_audit_store] = lambda: audit_store
    try:
        yield TestClient(app, headers={"x-api-key": "bootstrap"})
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.fixture()
def durable_thread_state() -> tuple[RunStore, TraceStore, ApprovalStore, str]:
    trace_id = "trace-control-thread"
    run_store = RunStore()
    trace_store = TraceStore()
    approval_store = ApprovalStore()
    context = RunContext(
        trace_id=trace_id,
        tenant_id="default",
        user_id="bootstrap-admin",
        agent_id="agent-control",
        request_id="req-control",
    )
    trace_store.record(context, "agent.started", task="inspect durable thread")
    trace_store.record(context, "tool.called", tool_name="search", status="ok")
    trace_store.record(context, "agent.completed", status="completed")
    approval_store.create_approval(
        context=context,
        resource_type="thread",
        resource_id=trace_id,
        action="thread.rollback",
        risk_level=RiskLevel.MEDIUM,
        reason="rollback metadata must remain owner gated",
        arguments_preview={"thread_id": trace_id},
    )
    response = AgentRunResponse(
        trace_id=trace_id,
        agent_id="agent-control",
        status=RunStatus.COMPLETED,
        answer="durable thread inspected",
        iterations=2,
        memory_hits=1,
        tool_calls=[],
        events=[],
        plan=[],
        execution_summary={
            "affected_files": ["backend/app/api/control_plane.py"],
            "worktree": {"branch": "codex/codex-hermes-gap-closure"},
        },
        snapshot={"stage": "finalizing"},
    )
    run_store.save(context, "inspect durable thread", response)
    return run_store, trace_store, approval_store, trace_id


def test_control_plane_method_catalog_covers_p0_groups() -> None:
    response = _client().get("/api/v1/control-plane/methods")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "control_plane_contract_ready"
    assert payload["implementation_stage"] == "contract_first"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["safety"]["raw_secret_payloads_rejected"] is True
    assert payload["safety"]["mutation_performed"] is False

    groups = set(payload["method_groups"])
    assert {
        "thread",
        "turn",
        "tool",
        "approval",
        "plugin",
        "skill",
        "mcp",
        "channel",
        "runtime/evidence",
    }.issubset(groups)

    methods = {method["method"]: method for method in payload["methods"]}
    assert methods["thread/read"]["implementation_state"] == "read_only_contract"
    assert methods["tool/call"]["requires_approval"] is True
    assert methods["channel/send"]["requires_approval"] is True
    assert methods["runtime/evidence/read"]["operation_kind"] == "read"


def test_control_plane_read_method_returns_envelope_and_audit_evidence() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-thread-read",
            "method": "thread/read",
            "params": {"trace_id": "trace-demo"},
            "context": {
                "tenant_id": "default",
                "actor_id": "owner",
                "workspace_id": "workspace-demo",
                "trace_id": "trace-demo",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "req-thread-read"
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["evidence"]["trace_id"] == "trace-demo"
    assert payload["evidence"]["audit_id"]
    assert payload["result"]["method"] == "thread/read"
    assert payload["result"]["contract"]["mutation_performed"] is False
    assert payload["result"]["compatibility"]["thread_id"] == "trace-demo"


def test_control_plane_mutating_method_is_adapter_gated_without_mutation() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-tool-call",
            "method": "tool/call",
            "params": {"tool_name": "file_write", "arguments": {"path": "demo.txt"}},
            "context": {"trace_id": "trace-tool-call"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "approval_required"
    assert payload["error"]["retryable"] is True
    assert payload["error"]["details"]["requires_approval"] is True
    assert payload["error"]["details"]["mutation_performed"] is False
    assert payload["evidence"]["audit_id"]


def test_sdk_control_plane_stub_accepts_thread_start_envelope_without_mutation() -> None:
    approval_store = ApprovalStore()
    contract = ControlPlaneSDK(default_tenant_id="tenant-a", default_user_id="operator").start_thread(
        "ship sdk backend stub",
        idempotency_key="sdk-stub-1",
        dry_run=False,
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["method"] == "thread/start"
    assert payload["sdk"]["dry_run"] is False
    assert payload["sdk"]["idempotency_key_present"] is True
    assert payload["sdk"]["mutation_performed"] is False
    assert payload["sdk"]["network_mutation_performed"] is False
    assert payload["sdk"]["adapter_execution_enabled"] is False
    assert payload["sdk"]["approval_intent"]["required"] is True
    assert payload["sdk"]["approval_intent"]["created"] is True
    assert payload["sdk"]["approval_intent"]["status"] == "pending"
    assert payload["sdk"]["approval_intent"]["subject_type"] == "command"
    assert payload["sdk"]["approval_intent"]["resource_id"] == "sdk:thread/start"
    assert payload["sdk"]["approval_intent"]["mutation_performed"] is False
    assert payload["sdk"]["execution_adapter_contract"]["preflight_status"] == "approval_id_required"
    readiness_lock = payload["sdk"]["runtime_implementation_readiness_lock_workflow"]
    assert readiness_lock["workflow_status"] == "blocked"
    assert readiness_lock["requires_accepted_owner_pack_decision"] is True
    assert readiness_lock["requires_idempotency_key"] is True
    assert readiness_lock["write_runner_enabled"] is False
    assert readiness_lock["runner_invoked"] is False
    assert readiness_lock["mutation_performed"] is False
    implementation_pack = payload["sdk"]["runtime_implementation_owner_pack"]
    assert implementation_pack["pack_status"] == "blocked"
    assert implementation_pack["readback_contract"]["evidence_type"] == (
        "sdk_write_runner_runtime_implementation_readiness_lock"
    )
    assert implementation_pack["owner_decision_policy"]["can_enable_runtime_flag_after_pack"] is False
    assert implementation_pack["owner_decision_policy"]["can_invoke_write_runner_after_pack"] is False
    assert implementation_pack["write_runner_enabled"] is False
    assert implementation_pack["runner_invoked"] is False
    assert implementation_pack["mutation_performed"] is False
    final_decision = payload["sdk"]["runtime_implementation_final_decision_workflow"]
    assert final_decision["workflow_status"] == "blocked"
    assert final_decision["endpoint"] == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
    assert final_decision["requires_runtime_implementation_readiness_lock"] is True
    assert final_decision["requires_decision_accept_or_reject"] is True
    assert final_decision["decision_effect"]["enables_runtime_flag"] is False
    assert final_decision["decision_effect"]["starts_agent_execution"] is False
    assert final_decision["decision_effect"]["marks_approval_executed"] is False
    assert final_decision["write_runner_enabled"] is False
    assert final_decision["runner_invoked"] is False
    assert final_decision["mutation_performed"] is False
    assert payload["sdk"]["execution_adapter_contract"]["ready_for_owner_approved_adapter"] is False
    assert payload["sdk"]["execution_adapter_contract"]["adapter_execution_enabled"] is False
    assert payload["sdk"]["read_only_runner_contract"]["available"] is False
    assert payload["sdk"]["read_only_runner_contract"]["write_execution_enabled"] is False
    safety = payload["sdk"]["write_runner_safety_contract"]
    assert safety["available"] is True
    assert safety["ready_for_runner_contract"] is False
    assert safety["runner_invoked"] is False
    assert safety["agent_execution_enabled"] is False
    assert safety["mark_executed"] is False
    stub = payload["sdk"]["dry_run_executor_stub"]
    assert stub["available"] is False
    assert stub["audit_event_recorded"] is False
    assert stub["runner_invoked"] is False
    assert stub["mutation_performed"] is False
    gate = payload["sdk"]["write_runner_execute_gate"]
    assert gate["stage"] == "owner_approved_write_runner_execute_gate"
    assert gate["gate_status"] == "blocked"
    assert gate["checks"]["write_method"] is True
    assert gate["checks"]["approved_preflight_ready"] is False
    assert gate["checks"]["receipt_persisted"] is False
    assert gate["execute_enabled"] is False
    assert gate["write_runner_enabled"] is False
    assert gate["agent_execution_enabled"] is False
    assert gate["adapter_execution_enabled"] is False
    assert gate["mark_executed"] is False
    assert gate["mutation_performed"] is False
    review = payload["sdk"]["write_runner_adapter_review"]
    assert review["stage"] == "owner_approved_write_runner_adapter_implementation_review"
    assert review["review_status"] == "blocked"
    assert review["checks"]["execute_gate_ready_but_disabled"] is False
    assert review["implementation_enabled"] is False
    assert review["write_runner_enabled"] is False
    assert review["agent_execution_enabled"] is False
    assert review["mark_executed"] is False
    assert review["mutation_performed"] is False
    runtime_flag = payload["sdk"]["write_runner_runtime_flag"]
    assert runtime_flag["flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert runtime_flag["flag_status"] == "declared_disabled"
    assert runtime_flag["runtime_flag_enabled"] is False
    assert runtime_flag["implementation_enabled"] is False
    assert runtime_flag["write_runner_enabled"] is False
    owner_evidence = payload["sdk"]["owner_acceptance_evidence"]
    assert owner_evidence["evidence_status"] == "recording_contract_ready_not_provided"
    assert owner_evidence["recording_contract_ready"] is True
    assert owner_evidence["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert owner_evidence["readback_contract"]["returns_record_if_present"] is True
    assert owner_evidence["recording_contract"]["created_by_sdk_invoke"] is False
    assert owner_evidence["execute_enabled"] is False
    assert owner_evidence["mutation_performed"] is False
    enablement = payload["sdk"]["runtime_enablement_review"]
    assert enablement["stage"] == "owner_approved_write_runner_runtime_enablement_review"
    assert enablement["review_status"] == "blocked"
    assert enablement["checks"]["execute_gate_ready_but_disabled"] is False
    assert enablement["checks"]["adapter_review_ready_but_disabled"] is False
    assert enablement["runtime_flag_enabled"] is False
    assert enablement["write_runner_enabled"] is False
    assert enablement["agent_execution_enabled"] is False
    assert enablement["mark_executed"] is False
    assert enablement["mutation_performed"] is False
    plan = payload["sdk"]["write_runner_implementation_plan"]
    assert plan["stage"] == "owner_approved_write_runner_concrete_implementation_plan"
    assert plan["plan_status"] == "blocked"
    assert plan["checks"]["runtime_enablement_ready_but_disabled"] is False
    assert plan["implementation_enabled"] is False
    assert plan["runtime_flag_enabled"] is False
    assert plan["write_runner_enabled"] is False
    assert plan["agent_execution_enabled"] is False
    assert plan["runner_invoked"] is False
    assert plan["mark_executed"] is False
    assert plan["mutation_performed"] is False
    smoke = payload["sdk"]["runtime_smoke_runbook"]
    assert smoke["stage"] == "owner_approved_write_runner_runtime_smoke_runbook"
    assert smoke["contract_status"] == "blocked"
    assert smoke["checks"]["implementation_plan_ready_but_disabled"] is False
    assert smoke["runtime_flag_enabled"] is False
    assert smoke["write_runner_enabled"] is False
    assert smoke["agent_execution_enabled"] is False
    assert smoke["runner_invoked"] is False
    assert smoke["mark_executed"] is False
    assert smoke["mutation_performed"] is False
    receipt = payload["sdk"]["runtime_enablement_receipt"]
    assert receipt["stage"] == "owner_approved_write_runner_runtime_enablement_receipt"
    assert receipt["receipt_status"] == "blocked"
    assert receipt["checks"]["runtime_smoke_runbook_ready_but_disabled"] is False
    assert receipt["runtime_flag_enabled"] is False
    assert receipt["write_runner_enabled"] is False
    assert receipt["agent_execution_enabled"] is False
    assert receipt["runner_invoked"] is False
    assert receipt["mark_executed"] is False
    assert receipt["mutation_performed"] is False
    preflight = payload["sdk"]["runtime_implementation_preflight"]
    assert preflight["stage"] == "owner_approved_write_runner_runtime_implementation_preflight"
    assert preflight["preflight_status"] == "blocked"
    assert preflight["checks"]["readiness_receipt_ready_but_disabled"] is False
    assert preflight["adapter_module_boundary"]["import_allowed"] is False
    assert preflight["dependency_injection_contract"]["required"] is True
    assert preflight["idempotency_lock_contract"]["lock_enabled"] is False
    assert preflight["receipt_persistence_interface"]["persistence_enabled"] is False
    assert preflight["approval_postcondition_contract"]["mark_executed_enabled"] is False
    assert preflight["failure_handling_contract"]["mark_executed_on_failure"] is False
    assert preflight["write_runner_enabled"] is False
    assert preflight["agent_execution_enabled"] is False
    assert preflight["runner_invoked"] is False
    assert preflight["mark_executed"] is False
    assert preflight["mutation_performed"] is False
    execute_contract = payload["sdk"]["runtime_flag_application_execute_contract_workflow"]
    assert execute_contract["stage"] == "runtime_flag_application_execute_contract_record_workflow"
    assert execute_contract["workflow_status"] == "blocked"
    assert execute_contract["endpoint"] == "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record"
    assert execute_contract["requires_runtime_flag_application_owner_approval"] is True
    assert execute_contract["requires_owner_approval_decision"] == "accepted"
    assert execute_contract["requires_idempotency_key"] is True
    assert execute_contract["requires_idempotency_hash"] is True
    assert execute_contract["decision_effect"]["applies_runtime_flag"] is False
    assert execute_contract["decision_effect"]["invokes_write_runner"] is False
    assert execute_contract["runtime_flag_enabled"] is False
    assert execute_contract["flag_application_performed"] is False
    assert execute_contract["execute_enabled"] is False
    assert execute_contract["write_runner_enabled"] is False
    assert execute_contract["adapter_execution_enabled"] is False
    assert execute_contract["agent_execution_enabled"] is False
    assert execute_contract["runner_invoked"] is False
    assert execute_contract["mark_executed"] is False
    assert execute_contract["mutation_performed"] is False
    execute_contract_review = payload["sdk"]["runtime_flag_application_execute_contract_owner_review"]
    assert execute_contract_review["stage"] == "runtime_flag_application_execute_contract_owner_review"
    assert execute_contract_review["review_status"] == "blocked"
    assert execute_contract_review["review_pack_type"] == (
        "sdk_write_runner_runtime_flag_application_execute_contract_owner_review"
    )
    assert execute_contract_review["owner_review_policy"]["manual_review_required"] is True
    assert execute_contract_review["owner_review_policy"]["independent_review_required"] is True
    assert execute_contract_review["owner_review_policy"]["requires_live_application_request"] is True
    assert execute_contract_review["owner_review_policy"]["can_apply_runtime_flag_after_review"] is False
    assert execute_contract_review["owner_review_policy"]["can_invoke_write_runner_after_review"] is False
    assert execute_contract_review["review_readback"]["method"] == "runtime/evidence/read"
    assert execute_contract_review["runtime_flag_enabled"] is False
    assert execute_contract_review["flag_application_performed"] is False
    assert execute_contract_review["execute_enabled"] is False
    assert execute_contract_review["write_runner_enabled"] is False
    assert execute_contract_review["adapter_execution_enabled"] is False
    assert execute_contract_review["agent_execution_enabled"] is False
    assert execute_contract_review["runner_invoked"] is False
    assert execute_contract_review["mark_executed"] is False
    assert execute_contract_review["mutation_performed"] is False
    handoff = payload["sdk"]["approval_handoff"]
    assert handoff["available"] is True
    assert handoff["approval_id"] == payload["sdk"]["approval_intent"]["approval_id"]
    assert handoff["next_commands"][0] == f"xagent approvals show {handoff['approval_id']}"
    assert handoff["next_commands"][1].startswith(f"xagent approvals approve {handoff['approval_id']}")
    assert handoff["blocked_command"] == f"xagent approvals execute {handoff['approval_id']}"
    assert handoff["execute_disabled"] is True
    assert handoff["mark_executed"] is False
    assert handoff["api_links"]["show"] == f"/api/v1/approvals/{handoff['approval_id']}"
    assert handoff["readback"]["method"] == "approval/read"
    assert handoff["mutation_performed"] is False
    assert handoff["network_mutation_performed"] is False
    assert payload["sdk"]["approval_sandbox_admin"]["subject_type"] == "command"
    assert payload["sdk"]["approval_sandbox_admin"]["owner_gate_required"] is True
    assert payload["control_plane"]["error"]["code"] == "adapter_pending"
    assert payload["control_plane"]["error"]["details"]["sdk"]["non_interactive"] is True
    assert payload["control_plane"]["error"]["details"]["thread_operation"]["operation"] == "start"
    assert payload["evidence"]["audit_id"]
    record = approval_store.get(payload["sdk"]["approval_intent"]["approval_id"])
    assert record is not None
    assert record.status == "pending"
    assert record.resource_type == "command"
    assert record.resource_id == "sdk:thread/start"
    assert record.arguments_preview["adapter_execution_enabled"] is False
    assert approval_store.pending_count() == 1


def test_sdk_control_plane_stub_reads_approved_execution_adapter_contract_without_mutation() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-sdk-approved",
        tenant_id="default",
        user_id="operator",
        request_id="req-sdk-approved",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner approved SDK turn preflight.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="preflight accepted"),
    )
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").run_turn(
        "thread-1",
        "continue",
        idempotency_key="sdk-approved-1",
        approved_approval_id=approval.id,
        dry_run=False,
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["approval_intent"]["created"] is False
    assert payload["sdk"]["approval_intent"]["approval_id"] == approval.id
    adapter = payload["sdk"]["execution_adapter_contract"]
    assert adapter["approved_approval_id"] == approval.id
    assert adapter["preflight_status"] == "approved_ready"
    assert adapter["ready_for_owner_approved_adapter"] is True
    assert adapter["approval_status"] == "approved"
    assert adapter["resource_id_ok"] is True
    assert adapter["tenant_ok"] is True
    assert adapter["adapter_execution_enabled"] is False
    assert adapter["agent_execution_enabled"] is False
    assert adapter["execute_disabled"] is True
    assert adapter["mark_executed"] is False
    assert adapter["mutation_performed"] is False
    final_decision = payload["sdk"]["runtime_implementation_final_decision_workflow"]
    assert final_decision["workflow_status"] == "ready_but_disabled"
    assert final_decision["audit_action"] == "sdk.write_runner.runtime_implementation_final_decision_recorded"
    assert final_decision["decision_effect"]["enables_runtime_flag"] is False
    assert final_decision["decision_effect"]["starts_agent_execution"] is False
    assert final_decision["decision_effect"]["marks_approval_executed"] is False
    assert final_decision["implementation_enabled"] is False
    assert final_decision["write_runner_enabled"] is False
    assert final_decision["runner_invoked"] is False
    assert final_decision["mutation_performed"] is False
    assert adapter["network_mutation_performed"] is False
    assert payload["sdk"]["read_only_runner_contract"]["available"] is False
    assert payload["sdk"]["read_only_runner_contract"]["write_execution_enabled"] is False
    safety = payload["sdk"]["write_runner_safety_contract"]
    assert safety["ready_for_runner_contract"] is True
    assert safety["runner_plan"]["approval_id"] == approval.id
    assert safety["runner_plan"]["idempotency_key_present"] is True
    assert safety["receipt_template"]["status"] == "planned_not_executed"
    assert safety["receipt_template"]["runner_invoked"] is False
    assert safety["runner_invoked"] is False
    assert safety["agent_execution_enabled"] is False
    assert safety["mark_executed"] is False
    assert safety["mutation_performed"] is False
    stub = payload["sdk"]["dry_run_executor_stub"]
    assert stub["available"] is True
    assert stub["audit_event_recorded"] is True
    assert stub["audit_action"] == "sdk.write_runner.dry_run_planned"
    assert stub["receipt_persisted"] is True
    assert stub["receipt_readback_method"] == "runtime/evidence/read"
    assert stub["receipt"]["status"] == "dry_run_planned"
    assert stub["receipt"]["audit_id"] == stub["audit_id"]
    assert stub["receipt"]["audit_hash"] == stub["audit_hash"]
    assert stub["receipt"]["audit_signature_present"] is True
    assert stub["receipt"]["receipt_persisted"] is True
    assert stub["receipt"]["runner_invoked"] is False
    assert stub["receipt"]["mark_executed"] is False
    assert stub["mutation_performed"] is False
    gate = payload["sdk"]["write_runner_execute_gate"]
    assert gate["stage"] == "owner_approved_write_runner_execute_gate"
    assert gate["gate_status"] == "ready_but_disabled"
    assert gate["approved_approval_id"] == approval.id
    assert gate["checks"]["write_method"] is True
    assert gate["checks"]["approved_preflight_ready"] is True
    assert gate["checks"]["runner_contract_ready"] is True
    assert gate["checks"]["receipt_persisted"] is True
    assert gate["checks"]["dry_run_receipt_planned"] is True
    assert gate["checks"]["audit_event_recorded"] is True
    assert gate["checks"]["audit_hash_present"] is True
    assert gate["checks"]["audit_signature_present"] is True
    assert gate["checks"]["safety_review_passed"] is True
    assert gate["checks"]["runner_not_invoked"] is True
    assert gate["checks"]["mark_executed_false"] is True
    assert gate["checks"]["mutation_false"] is True
    assert gate["checks"]["idempotency_key_present"] is True
    assert gate["execute_enabled"] is False
    assert gate["write_runner_enabled"] is False
    assert gate["agent_execution_enabled"] is False
    assert gate["adapter_execution_enabled"] is False
    assert gate["mark_executed"] is False
    assert gate["mutation_performed"] is False
    assert gate["network_mutation_performed"] is False
    assert gate["next_gate"] == "owner_approved_write_runner_adapter_implementation"
    review = payload["sdk"]["write_runner_adapter_review"]
    assert review["stage"] == "owner_approved_write_runner_adapter_implementation_review"
    assert review["review_status"] == "ready_but_disabled"
    assert review["adapter_target"]["callable"] == "AgentCoordinator.run"
    assert review["checks"]["execute_gate_ready_but_disabled"] is True
    assert review["checks"]["approval_id_bound"] is True
    assert review["checks"]["idempotency_key_present"] is True
    assert review["checks"]["receipt_persisted"] is True
    assert review["checks"]["safety_review_passed"] is True
    assert review["approval_execution_policy"]["mark_executed_allowed_after_runner_success"] is True
    assert review["approval_execution_policy"]["mark_executed_called_now"] is False
    assert review["audit_contract"]["future_execute_action"] == "sdk.write_runner.executed"
    assert review["implementation_enabled"] is False
    assert review["execute_enabled"] is False
    assert review["write_runner_enabled"] is False
    assert review["agent_execution_enabled"] is False
    assert review["adapter_execution_enabled"] is False
    assert review["mark_executed"] is False
    assert review["mutation_performed"] is False
    runtime_flag = payload["sdk"]["write_runner_runtime_flag"]
    assert runtime_flag["stage"] == "owner_approved_write_runner_runtime_feature_flag"
    assert runtime_flag["flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert runtime_flag["flag_status"] == "declared_disabled"
    assert runtime_flag["checks"]["adapter_review_ready_but_disabled"] is True
    assert runtime_flag["owner_acceptance_evidence_required"] is True
    assert "owner_acceptance_evidence_present" in runtime_flag["required_runtime_guards"]
    assert runtime_flag["runtime_flag_enabled"] is False
    assert runtime_flag["implementation_enabled"] is False
    assert runtime_flag["write_runner_enabled"] is False
    assert runtime_flag["agent_execution_enabled"] is False
    assert runtime_flag["mark_executed"] is False
    assert runtime_flag["mutation_performed"] is False
    owner_evidence = payload["sdk"]["owner_acceptance_evidence"]
    assert owner_evidence["stage"] == "owner_acceptance_evidence_record"
    assert owner_evidence["evidence_status"] == "recording_contract_ready_not_provided"
    assert owner_evidence["recording_contract_ready"] is True
    assert owner_evidence["recording_action"] == "sdk.write_runner.owner_acceptance_recorded"
    assert owner_evidence["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert "owner_acceptance_id" in owner_evidence["required_fields"]
    assert owner_evidence["acceptance_report_name"] == "sdk-write-runner-owner-acceptance.json"
    assert owner_evidence["readback_contract"]["method"] == "runtime/evidence/read"
    assert owner_evidence["readback_contract"]["returns_schema"] is True
    assert owner_evidence["recording_contract"]["created_by_sdk_invoke"] is False
    assert owner_evidence["checks"]["runtime_flag_disabled"] is True
    assert owner_evidence["checks"]["recording_contract_declared"] is True
    assert owner_evidence["checks"]["readback_contract_declared"] is True
    assert owner_evidence["checks"]["acceptance_record_present"] is False
    assert owner_evidence["runtime_flag_enabled"] is False
    assert owner_evidence["execute_enabled"] is False
    assert owner_evidence["write_runner_enabled"] is False
    assert owner_evidence["agent_execution_enabled"] is False
    assert owner_evidence["mark_executed"] is False
    assert owner_evidence["mutation_performed"] is False
    enablement = payload["sdk"]["runtime_enablement_review"]
    assert enablement["stage"] == "owner_approved_write_runner_runtime_enablement_review"
    assert enablement["review_status"] == "ready_but_disabled"
    assert enablement["checks"]["execute_gate_ready_but_disabled"] is True
    assert enablement["checks"]["adapter_review_ready_but_disabled"] is True
    assert enablement["checks"]["runtime_flag_declared_disabled"] is True
    assert enablement["checks"]["owner_acceptance_recording_contract_ready"] is True
    assert enablement["checks"]["strict_acceptance_readback_keys_required"] is True
    assert enablement["required_evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert enablement["runtime_flag_enabled"] is False
    assert enablement["execute_enabled"] is False
    assert enablement["write_runner_enabled"] is False
    assert enablement["agent_execution_enabled"] is False
    assert enablement["mark_executed"] is False
    assert enablement["mutation_performed"] is False
    plan = payload["sdk"]["write_runner_implementation_plan"]
    assert plan["stage"] == "owner_approved_write_runner_concrete_implementation_plan"
    assert plan["plan_status"] == "ready_but_disabled"
    assert plan["adapter_target"]["callable"] == "AgentCoordinator.run"
    assert plan["checks"]["runtime_enablement_ready_but_disabled"] is True
    assert plan["checks"]["execute_gate_ready_but_disabled"] is True
    assert plan["idempotency_contract"]["required"] is True
    assert plan["rollback_plan"]["disable_runtime_flag"] is True
    assert plan["audit_result_shape"]["planned_action"] == "sdk.write_runner.implementation_plan_ready"
    assert "mark_approval_executed_after_runner_success" in plan["implementation_steps"]
    assert plan["implementation_enabled"] is False
    assert plan["runtime_flag_enabled"] is False
    assert plan["execute_enabled"] is False
    assert plan["write_runner_enabled"] is False
    assert plan["agent_execution_enabled"] is False
    assert plan["runner_invoked"] is False
    assert plan["mark_executed"] is False
    assert plan["mutation_performed"] is False
    smoke = payload["sdk"]["runtime_smoke_runbook"]
    assert smoke["stage"] == "owner_approved_write_runner_runtime_smoke_runbook"
    assert smoke["contract_status"] == "ready_but_disabled"
    assert smoke["smoke_plan"]["requires_runtime_flag"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"
    assert smoke["rollback_plan"]["failure_receipt_required"] is True
    assert smoke["failure_receipt_contract"]["audit_action"] == "sdk.write_runner.failed"
    assert smoke["failure_receipt_contract"]["mark_executed_must_be_false_on_failure"] is True
    assert "disable_runtime_flag_after_smoke" in smoke["owner_checklist"]
    assert smoke["implementation_enabled"] is False
    assert smoke["runtime_flag_enabled"] is False
    assert smoke["execute_enabled"] is False
    assert smoke["write_runner_enabled"] is False
    assert smoke["agent_execution_enabled"] is False
    assert smoke["runner_invoked"] is False
    assert smoke["mark_executed"] is False
    assert smoke["mutation_performed"] is False
    receipt = payload["sdk"]["runtime_enablement_receipt"]
    assert receipt["stage"] == "owner_approved_write_runner_runtime_enablement_receipt"
    assert receipt["receipt_status"] == "ready_but_disabled"
    assert receipt["receipt_type"] == "sdk_write_runner_runtime_enablement_readiness"
    assert receipt["receipt_schema"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert receipt["review_readback"]["query_keys"] == [
        "readiness_receipt_id",
        "approval_id",
        "owner_acceptance_id",
    ]
    assert receipt["owner_review_policy"]["requires_expiry"] is True
    assert receipt["audit_contract"]["planned_action"] == "sdk.write_runner.runtime_enablement_receipt_ready"
    assert receipt["implementation_enabled"] is False
    assert receipt["runtime_flag_enabled"] is False
    assert receipt["execute_enabled"] is False
    assert receipt["write_runner_enabled"] is False
    assert receipt["agent_execution_enabled"] is False
    assert receipt["runner_invoked"] is False
    assert receipt["mark_executed"] is False
    assert receipt["mutation_performed"] is False
    preflight = payload["sdk"]["runtime_implementation_preflight"]
    assert preflight["stage"] == "owner_approved_write_runner_runtime_implementation_preflight"
    assert preflight["preflight_status"] == "ready_but_disabled"
    assert preflight["checks"]["readiness_receipt_ready_but_disabled"] is True
    assert preflight["checks"]["implementation_plan_ready_but_disabled"] is True
    assert preflight["adapter_module_boundary"]["module"] == "backend.app.core.agent.coordinator"
    assert preflight["adapter_module_boundary"]["callable"] == "AgentCoordinator.run"
    assert preflight["adapter_module_boundary"]["import_allowed"] is False
    assert preflight["dependency_injection_contract"]["required"] is True
    assert preflight["dependency_injection_contract"]["default_factory_enabled"] is False
    assert preflight["idempotency_lock_contract"]["required"] is True
    assert preflight["idempotency_lock_contract"]["lock_enabled"] is False
    assert preflight["receipt_persistence_interface"]["required"] is True
    assert preflight["receipt_persistence_interface"]["persistence_enabled"] is False
    assert preflight["approval_postcondition_contract"]["mark_executed_enabled"] is False
    assert preflight["failure_handling_contract"]["mark_executed_on_failure"] is False
    assert preflight["implementation_enabled"] is False
    assert preflight["runtime_flag_enabled"] is False
    assert preflight["execute_enabled"] is False
    assert preflight["write_runner_enabled"] is False
    assert preflight["agent_execution_enabled"] is False
    assert preflight["runner_invoked"] is False
    assert preflight["mark_executed"] is False
    assert preflight["mutation_performed"] is False
    owner_pack = payload["sdk"]["runtime_enablement_owner_pack"]
    assert owner_pack["stage"] == "runtime_enablement_owner_acceptance_pack"
    assert owner_pack["pack_status"] == "ready_but_disabled"
    assert owner_pack["readback_contract"]["query_keys"] == [
        "readiness_receipt_id",
        "approval_id",
        "owner_acceptance_id",
        "audit_id",
    ]
    assert owner_pack["owner_decision_policy"]["manual_review_required"] is True
    assert owner_pack["owner_decision_policy"]["can_enable_runtime_flag_after_pack"] is False
    assert owner_pack["audit_contract"]["audit_event_recorded_now"] is False
    assert owner_pack["runtime_flag_enabled"] is False
    assert owner_pack["write_runner_enabled"] is False
    assert owner_pack["runner_invoked"] is False
    assert owner_pack["mark_executed"] is False
    assert owner_pack["mutation_performed"] is False
    assert approval_store.pending_count() == 0
    assert approval_store.get(approval.id).status == "approved"
    audit_records = audit_store.list(action="sdk.write_runner.dry_run_planned")
    assert len(audit_records) == 1
    assert audit_records[0].details["approval_id"] == approval.id
    assert audit_records[0].details["receipt_persisted"] is True
    assert audit_records[0].details["receipt"]["audit_id"] == audit_records[0].id


def test_sdk_control_plane_stub_can_read_thread_through_existing_contract() -> None:
    approval_store = ApprovalStore()
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_thread(
        "trace-demo"
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["method"] == "thread/read"
    assert payload["sdk"]["owner_gate_required"] is False
    assert payload["sdk"]["approval_intent"]["required"] is False
    assert payload["sdk"]["approval_intent"]["created"] is False
    assert payload["sdk"]["approval_handoff"]["available"] is False
    assert payload["sdk"]["approval_handoff"]["execute_disabled"] is True
    assert payload["sdk"]["approval_handoff"]["mark_executed"] is False
    assert payload["sdk"]["approval_handoff"]["network_mutation_performed"] is False
    assert payload["sdk"]["execution_adapter_contract"]["preflight_status"] == "not_required_for_read"
    assert payload["sdk"]["execution_adapter_contract"]["adapter_execution_enabled"] is False
    runner = payload["sdk"]["read_only_runner_contract"]
    assert runner["available"] is True
    assert runner["read_only_runner_enabled"] is True
    assert runner["adapter_execution_enabled"] is False
    assert runner["agent_execution_enabled"] is False
    assert runner["write_execution_enabled"] is False
    assert "thread/read" in runner["supported_methods"]
    gate = payload["sdk"]["write_runner_execute_gate"]
    assert gate["available"] is False
    assert gate["gate_status"] == "blocked"
    assert gate["execute_enabled"] is False
    assert gate["mutation_performed"] is False
    assert payload["sdk"]["write_runner_adapter_review"]["available"] is False
    assert payload["sdk"]["write_runner_adapter_review"]["implementation_enabled"] is False
    assert payload["sdk"]["mutation_performed"] is False
    assert payload["control_plane"]["result"]["contract"]["dry_run"] is True
    assert payload["control_plane"]["result"]["compatibility"]["sdk_surface"] == "python"
    assert payload["control_plane"]["result"]["compatibility"]["non_interactive"] is True
    assert approval_store.pending_count() == 0


def test_sdk_control_plane_stub_reads_runtime_evidence_through_read_only_runner() -> None:
    approval_store = ApprovalStore()
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_runtime_evidence(
        "latest-codex-alignment.json"
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    assert payload["sdk"]["method"] == "runtime/evidence/read"
    runner = payload["sdk"]["read_only_runner_contract"]
    assert runner["available"] is True
    assert runner["runner_kind"] == "read_only_control_plane"
    assert runner["read_only_runner_enabled"] is True
    assert runner["agent_execution_enabled"] is False
    assert runner["write_execution_enabled"] is False
    assert runner["mutation_performed"] is False
    assert payload["control_plane"]["result"]["evidence"]["report_name"] == "latest-codex-alignment.json"
    assert approval_store.pending_count() == 0


def test_sdk_control_plane_stub_reads_persisted_dry_run_executor_runtime_evidence() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-sdk-receipt-readback",
        tenant_id="default",
        user_id="operator",
        request_id="req-sdk-receipt-readback",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner approved SDK dry-run receipt persistence.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="receipt readback accepted"),
    )
    write_contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").run_turn(
        "thread-1",
        "continue",
        idempotency_key="sdk-receipt-1",
        approved_approval_id=approval.id,
        dry_run=False,
    )
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_runtime_evidence(
        "sdk-dry-run-executor-stub.json",
        evidence_type="sdk_dry_run_executor_stub",
        approval_id=approval.id,
        method="turn/start",
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        write_response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=write_contract.to_dict(),
        )
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert write_response.status_code == 200
    write_payload = write_response.json()
    assert write_payload["sdk"]["dry_run_executor_stub"]["receipt_persisted"] is True
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_dry_run_executor_stub"
    assert evidence["available"] is True
    assert evidence["approval_id"] == approval.id
    assert evidence["method"] == "turn/start"
    assert evidence["receipt_available"] is True
    assert evidence["receipt_persisted"] is True
    assert evidence["receipt"]["approval_id"] == approval.id
    assert evidence["receipt"]["method"] == "turn/start"
    assert evidence["receipt"]["status"] == "dry_run_planned"
    assert evidence["receipt"]["runner_invoked"] is False
    assert evidence["receipt"]["mutation_performed"] is False
    assert evidence["receipt"]["receipt_persisted"] is True
    assert evidence["receipt"]["audit_signature_present"] is True
    assert evidence["receipt_schema"]["status"] == "dry_run_planned"
    assert evidence["audit_readback"]["action"] == "sdk.write_runner.dry_run_planned"
    assert evidence["audit_readback"]["receipt_persisted"] is True
    review = evidence["runner_safety_review"]
    assert review["stage"] == "persisted_dry_run_receipt_safety_review"
    assert review["status"] == "passed"
    assert review["checks"]["receipt_persisted"] is True
    assert review["checks"]["runner_not_invoked"] is True
    assert review["checks"]["mutation_false"] is True
    assert review["write_runner_enabled"] is False
    assert review["agent_execution_enabled"] is False
    assert review["mark_executed"] is False
    assert evidence["safety"]["runner_invoked"] is False
    assert evidence["safety"]["mutation_performed"] is False


def test_sdk_control_plane_stub_reads_owner_acceptance_runtime_evidence_contract_without_mutation() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_runtime_evidence(
        "sdk-write-runner-owner-acceptance.json",
        evidence_type="sdk_write_runner_owner_acceptance",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id="audit-1",
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert evidence["available"] is True
    assert evidence["evidence_status"] == "required_not_provided"
    assert evidence["recording_contract_ready"] is True
    assert evidence["readback_contract_ready"] is True
    assert evidence["acceptance_record_present"] is False
    assert evidence["validation"]["status"] == "invalid"
    assert evidence["validation"]["checks"]["record_present"] is False
    assert evidence["validation"]["checks"]["accepted_at_rfc3339"] is False
    assert evidence["validation"]["checks"]["signature_or_hash_present"] is False
    assert evidence["missing_required_query_keys"] == []
    assert evidence["report_preview_only"] is True
    assert evidence["schema"]["required"] == [
        "owner_acceptance_id",
        "accepted_by",
        "accepted_at",
        "approval_id",
        "runbook_acknowledged",
        "rollback_plan_acknowledged",
    ]
    assert evidence["audit_readback"]["action"] == "sdk.write_runner.owner_acceptance_recorded"
    assert evidence["audit_readback"]["record_persisted"] is False
    assert evidence["control_plane_readback"]["params"]["owner_acceptance_id"] == "acceptance-1"
    assert evidence["safety"]["runtime_flag_enabled"] is False
    assert evidence["safety"]["execute_enabled"] is False
    assert evidence["safety"]["write_runner_enabled"] is False
    assert evidence["safety"]["agent_execution_enabled"] is False
    assert evidence["safety"]["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.owner_acceptance_recorded") == []


def test_owner_acceptance_readback_treats_json_report_as_preview_only(tmp_path, monkeypatch) -> None:
    import backend.app.api.control_plane as control_plane

    monkeypatch.setattr(control_plane, "REPORT_DIR", tmp_path)
    (tmp_path / "sdk-write-runner-owner-acceptance.json").write_text(
        json.dumps(
            {
                "owner_acceptance_id": "acceptance-1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "approval_id": "approval-1",
                "runbook_acknowledged": True,
                "rollback_plan_acknowledged": True,
                "acceptance_hash": "hash-preview-only",
            }
        ),
        encoding="utf-8",
    )
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_runtime_evidence(
        "sdk-write-runner-owner-acceptance.json",
        evidence_type="sdk_write_runner_owner_acceptance",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id="audit-1",
    )

    with _client_with_stores(RunStore(), TraceStore(), ApprovalStore(), AuditStore(hmac_secret="test-secret")) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    evidence = response.json()["control_plane"]["result"]["evidence"]
    assert evidence["report"]["available"] is True
    assert evidence["report_preview_only"] is True
    assert evidence["acceptance_record_present"] is False
    assert evidence["evidence_status"] == "required_not_provided"
    assert evidence["validation"]["status"] == "invalid"
    assert evidence["validation"]["checks"]["record_present"] is False
    assert evidence["safety"]["write_runner_enabled"] is False
    assert evidence["safety"]["mutation_performed"] is False


def test_owner_acceptance_readback_requires_strict_audit_query_keys() -> None:
    audit_store = AuditStore(hmac_secret="test-secret")
    audit = audit_store.record(
        action="sdk.write_runner.owner_acceptance_recorded",
        resource_type="sdk_write_runner_owner_acceptance",
        resource_id="acceptance-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": "approval-1",
            "owner_acceptance_evidence": {
                "owner_acceptance_id": "acceptance-1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "approval_id": "approval-1",
                "runbook_acknowledged": True,
                "rollback_plan_acknowledged": True,
                "acceptance_hash": "hash-audit-backed",
            },
        },
    )
    sdk = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator")
    missing_key_contract = sdk.read_runtime_evidence(
        "sdk-write-runner-owner-acceptance.json",
        evidence_type="sdk_write_runner_owner_acceptance",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
    )
    strict_contract = sdk.read_runtime_evidence(
        "sdk-write-runner-owner-acceptance.json",
        evidence_type="sdk_write_runner_owner_acceptance",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id=audit.id,
    )

    with _client_with_stores(RunStore(), TraceStore(), ApprovalStore(), audit_store) as client:
        missing_response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=missing_key_contract.to_dict(),
        )
        strict_response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=strict_contract.to_dict(),
        )

    assert missing_response.status_code == 200
    missing_evidence = missing_response.json()["control_plane"]["result"]["evidence"]
    assert missing_evidence["missing_required_query_keys"] == ["audit_id"]
    assert missing_evidence["acceptance_record_present"] is False
    assert missing_evidence["evidence_status"] == "required_not_provided"

    assert strict_response.status_code == 200
    strict_evidence = strict_response.json()["control_plane"]["result"]["evidence"]
    assert strict_evidence["missing_required_query_keys"] == []
    assert strict_evidence["acceptance_record_present"] is True
    assert strict_evidence["evidence_status"] == "provided"
    assert strict_evidence["record"]["owner_acceptance_id"] == "acceptance-1"
    assert strict_evidence["record"]["audit_id"] == audit.id
    assert strict_evidence["record"]["audit_signature_present"] is True
    assert strict_evidence["validation"]["status"] == "valid"
    assert strict_evidence["safety"]["write_runner_enabled"] is False
    assert strict_evidence["safety"]["mutation_performed"] is False


def test_runtime_enablement_readiness_readback_requires_strict_audit_query_keys() -> None:
    audit_store = AuditStore(hmac_secret="test-secret")
    audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_receipt_recorded",
        resource_type="sdk_write_runner_runtime_enablement_readiness",
        resource_id="readiness-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": "approval-1",
            "owner_acceptance_id": "acceptance-1",
            "runtime_enablement_receipt": {
                "readiness_receipt_id": "readiness-1",
                "approval_id": "approval-1",
                "owner_acceptance_id": "acceptance-1",
                "owner_acceptance_audit_id": "audit-acceptance-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "smoke_runbook_version": "v1",
                "rollback_runbook_version": "v1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "expires_at": "2026-06-09T00:00:00Z",
                "smoke_runbook_acknowledged": True,
                "rollback_runbook_acknowledged": True,
                "failure_receipt_reviewed": True,
                "acceptance_hash": "hash-readiness",
            },
        },
    )
    sdk = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator")
    missing_key_contract = sdk.read_runtime_evidence(
        "sdk-write-runner-runtime-enable-readiness.json",
        evidence_type="sdk_write_runner_runtime_enablement_readiness",
        readiness_receipt_id="readiness-1",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
    )
    strict_contract = sdk.read_runtime_evidence(
        "sdk-write-runner-runtime-enable-readiness.json",
        evidence_type="sdk_write_runner_runtime_enablement_readiness",
        readiness_receipt_id="readiness-1",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id=audit.id,
    )

    with _client_with_stores(RunStore(), TraceStore(), ApprovalStore(), audit_store) as client:
        missing_response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=missing_key_contract.to_dict(),
        )
        strict_response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=strict_contract.to_dict(),
        )

    assert missing_response.status_code == 200
    missing_evidence = missing_response.json()["control_plane"]["result"]["evidence"]
    assert missing_evidence["missing_required_query_keys"] == ["audit_id"]
    assert missing_evidence["readiness_receipt_present"] is False
    assert missing_evidence["evidence_status"] == "required_not_provided"

    assert strict_response.status_code == 200
    strict_evidence = strict_response.json()["control_plane"]["result"]["evidence"]
    assert strict_evidence["missing_required_query_keys"] == []
    assert strict_evidence["readiness_receipt_present"] is True
    assert strict_evidence["evidence_status"] == "provided"
    assert strict_evidence["record"]["readiness_receipt_id"] == "readiness-1"
    assert strict_evidence["record"]["audit_id"] == audit.id
    assert strict_evidence["record"]["audit_signature_present"] is True
    assert strict_evidence["validation"]["status"] == "valid"
    assert strict_evidence["safety"]["runtime_flag_enabled"] is False
    assert strict_evidence["safety"]["write_runner_enabled"] is False
    assert strict_evidence["safety"]["runner_invoked"] is False
    assert strict_evidence["safety"]["mark_executed"] is False
    assert strict_evidence["safety"]["mutation_performed"] is False


def test_sdk_owner_acceptance_record_workflow_records_audit_without_execution() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-acceptance-record",
        tenant_id="default",
        user_id="operator",
        request_id="req-acceptance-record",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK write preflight.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for owner acceptance"),
    )
    request_payload = {
        "owner_acceptance_id": "acceptance-record-1",
        "approval_id": approval.id,
        "accepted_by": "owner",
        "accepted_at": "2026-06-08T00:00:00Z",
        "runbook_acknowledged": True,
        "rollback_plan_acknowledged": True,
        "acceptance_hash": "hash-audit-backed",
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/owner-acceptance/record",
            json=request_payload,
        )
        readback = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=ControlPlaneSDK(default_tenant_id="default", default_user_id="operator")
            .read_runtime_evidence(
                "sdk-write-runner-owner-acceptance.json",
                evidence_type="sdk_write_runner_owner_acceptance",
                approval_id=approval.id,
                owner_acceptance_id="acceptance-record-1",
                audit_id=response.json()["evidence"]["audit_id"],
            )
            .to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_owner_acceptance_record_workflow_ready"
    record = payload["owner_acceptance"]
    assert record["record_status"] == "recorded"
    assert record["audit_event_recorded"] is True
    assert record["audit_action"] == "sdk.write_runner.owner_acceptance_recorded"
    assert record["checks"]["approval_status_approved"] is True
    assert record["checks"]["evidence_valid"] is True
    assert record["runtime_flag_enabled"] is False
    assert record["write_runner_enabled"] is False
    assert record["agent_execution_enabled"] is False
    assert record["mark_executed"] is False
    assert record["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None

    evidence = readback.json()["control_plane"]["result"]["evidence"]
    assert evidence["acceptance_record_present"] is True
    assert evidence["evidence_status"] == "provided"
    assert evidence["record"]["owner_acceptance_id"] == "acceptance-record-1"
    assert evidence["record"]["approval_id"] == approval.id
    assert evidence["validation"]["status"] == "valid"
    assert evidence["safety"]["write_runner_enabled"] is False
    assert evidence["safety"]["mutation_performed"] is False


def test_sdk_owner_acceptance_record_workflow_rejects_unapproved_or_unsigned_evidence() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-acceptance-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-acceptance-reject",
    )
    pending = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Pending SDK write preflight.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    request_payload = {
        "owner_acceptance_id": "acceptance-reject-1",
        "approval_id": pending.id,
        "accepted_by": "owner",
        "accepted_at": "2026-06-08T00:00:00Z",
        "runbook_acknowledged": True,
        "rollback_plan_acknowledged": True,
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/owner-acceptance/record",
            json=request_payload,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["owner_acceptance"]["record_status"] == "rejected"
    assert payload["owner_acceptance"]["checks"]["approval_status_approved"] is False
    assert payload["owner_acceptance"]["validation"]["checks"]["signature_or_hash_present"] is False
    assert payload["owner_acceptance"]["audit_event_recorded"] is False
    assert payload["owner_acceptance"]["write_runner_enabled"] is False
    assert payload["owner_acceptance"]["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.owner_acceptance_recorded") == []


def test_sdk_runtime_enablement_receipt_record_workflow_records_audit_without_execution() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-readiness-record",
        tenant_id="default",
        user_id="operator",
        request_id="req-readiness-record",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime readiness.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime readiness"),
    )
    owner_acceptance_audit = audit_store.record(
        action="sdk.write_runner.owner_acceptance_recorded",
        resource_type="sdk_write_runner_owner_acceptance",
        resource_id="acceptance-record-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_evidence": {
                "owner_acceptance_id": "acceptance-record-1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "approval_id": approval.id,
                "runbook_acknowledged": True,
                "rollback_plan_acknowledged": True,
                "acceptance_hash": "hash-owner-acceptance",
            },
        },
    )
    request_payload = {
        "readiness_receipt_id": "readiness-record-1",
        "approval_id": approval.id,
        "owner_acceptance_id": "acceptance-record-1",
        "owner_acceptance_audit_id": owner_acceptance_audit.id,
        "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        "smoke_runbook_version": "v1",
        "rollback_runbook_version": "v1",
        "accepted_by": "owner",
        "accepted_at": "2026-06-08T00:00:00Z",
        "expires_at": "2026-06-09T00:00:00Z",
        "smoke_runbook_acknowledged": True,
        "rollback_runbook_acknowledged": True,
        "failure_receipt_reviewed": True,
        "acceptance_hash": "hash-readiness",
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            json=request_payload,
        )
        readback = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=ControlPlaneSDK(default_tenant_id="default", default_user_id="operator")
            .read_runtime_evidence(
                "sdk-write-runner-runtime-enable-readiness.json",
                evidence_type="sdk_write_runner_runtime_enablement_readiness",
                readiness_receipt_id="readiness-record-1",
                approval_id=approval.id,
                owner_acceptance_id="acceptance-record-1",
                audit_id=response.json()["evidence"]["audit_id"],
            )
            .to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_enablement_receipt_record_workflow_ready"
    record = payload["runtime_enablement_receipt"]
    assert record["record_status"] == "recorded"
    assert record["audit_event_recorded"] is True
    assert record["audit_action"] == "sdk.write_runner.runtime_enablement_receipt_recorded"
    assert record["checks"]["approval_status_approved"] is True
    assert record["checks"]["owner_acceptance_audit_record_present"] is True
    assert record["checks"]["receipt_valid"] is True
    assert record["runtime_flag_enabled"] is False
    assert record["write_runner_enabled"] is False
    assert record["agent_execution_enabled"] is False
    assert record["runner_invoked"] is False
    assert record["mark_executed"] is False
    assert record["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None

    evidence = readback.json()["control_plane"]["result"]["evidence"]
    assert evidence["readiness_receipt_present"] is True
    assert evidence["evidence_status"] == "provided"
    assert evidence["record"]["readiness_receipt_id"] == "readiness-record-1"
    assert evidence["record"]["approval_id"] == approval.id
    assert evidence["validation"]["status"] == "valid"
    assert evidence["safety"]["runtime_flag_enabled"] is False
    assert evidence["safety"]["write_runner_enabled"] is False
    assert evidence["safety"]["runner_invoked"] is False
    assert evidence["safety"]["mark_executed"] is False
    assert evidence["safety"]["mutation_performed"] is False


def test_sdk_runtime_enablement_receipt_record_workflow_rejects_missing_owner_acceptance_or_hash() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-readiness-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-readiness-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime readiness.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime readiness"),
    )
    request_payload = {
        "readiness_receipt_id": "readiness-reject-1",
        "approval_id": approval.id,
        "owner_acceptance_id": "acceptance-missing-1",
        "owner_acceptance_audit_id": "audit-missing-1",
        "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
        "smoke_runbook_version": "v1",
        "rollback_runbook_version": "v1",
        "accepted_by": "owner",
        "accepted_at": "2026-06-08T00:00:00Z",
        "expires_at": "2026-06-09T00:00:00Z",
        "smoke_runbook_acknowledged": True,
        "rollback_runbook_acknowledged": True,
        "failure_receipt_reviewed": True,
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-enablement/receipt/record",
            json=request_payload,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["runtime_enablement_receipt"]["record_status"] == "rejected"
    assert (
        payload["runtime_enablement_receipt"]["checks"]["owner_acceptance_audit_record_present"]
        is False
    )
    assert (
        payload["runtime_enablement_receipt"]["validation"]["checks"]["signature_or_hash_present"]
        is False
    )
    assert payload["runtime_enablement_receipt"]["audit_event_recorded"] is False
    assert payload["runtime_enablement_receipt"]["write_runner_enabled"] is False
    assert payload["runtime_enablement_receipt"]["runner_invoked"] is False
    assert payload["runtime_enablement_receipt"]["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_enablement_receipt_recorded") == []


def test_sdk_runtime_enablement_owner_pack_decision_records_audit_without_execution() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-owner-pack-decision",
        tenant_id="default",
        user_id="operator",
        request_id="req-owner-pack-decision",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK owner pack decision.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for owner pack decision"),
    )
    owner_acceptance_audit = audit_store.record(
        action="sdk.write_runner.owner_acceptance_recorded",
        resource_type="sdk_write_runner_owner_acceptance",
        resource_id="acceptance-decision-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_evidence": {
                "owner_acceptance_id": "acceptance-decision-1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "approval_id": approval.id,
                "runbook_acknowledged": True,
                "rollback_plan_acknowledged": True,
                "acceptance_hash": "hash-owner-acceptance",
            },
        },
    )
    readiness_receipt_audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_receipt_recorded",
        resource_type="sdk_write_runner_runtime_enablement_readiness",
        resource_id="readiness-decision-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_id": "acceptance-decision-1",
            "owner_acceptance_audit_id": owner_acceptance_audit.id,
            "runtime_enablement_receipt": {
                "readiness_receipt_id": "readiness-decision-1",
                "approval_id": approval.id,
                "owner_acceptance_id": "acceptance-decision-1",
                "owner_acceptance_audit_id": owner_acceptance_audit.id,
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "smoke_runbook_version": "v1",
                "rollback_runbook_version": "v1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "expires_at": "2026-06-09T00:00:00Z",
                "smoke_runbook_acknowledged": True,
                "rollback_runbook_acknowledged": True,
                "failure_receipt_reviewed": True,
                "acceptance_hash": "hash-readiness",
            },
        },
    )
    request_payload = {
        "owner_pack_decision_id": "decision-record-1",
        "decision": "accepted",
        "approval_id": approval.id,
        "readiness_receipt_id": "readiness-decision-1",
        "readiness_receipt_audit_id": readiness_receipt_audit.id,
        "owner_acceptance_id": "acceptance-decision-1",
        "owner_acceptance_audit_id": owner_acceptance_audit.id,
        "decided_by": "owner",
        "decided_at": "2026-06-08T01:00:00Z",
        "reason": "owner accepted pack",
        "decision_hash": "hash-decision",
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record",
            json=request_payload,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_enablement_owner_pack_decision_workflow_ready"
    decision = payload["owner_pack_decision"]
    assert decision["record_status"] == "recorded"
    assert decision["decision"] == "accepted"
    assert decision["audit_event_recorded"] is True
    assert decision["audit_action"] == "sdk.write_runner.runtime_enablement_owner_pack_decision_recorded"
    assert decision["checks"]["approval_status_approved"] is True
    assert decision["checks"]["readiness_receipt_audit_record_present"] is True
    assert decision["checks"]["decision_valid"] is True
    assert decision["runtime_flag_enabled"] is False
    assert decision["write_runner_enabled"] is False
    assert decision["agent_execution_enabled"] is False
    assert decision["runner_invoked"] is False
    assert decision["mark_executed"] is False
    assert decision["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_implementation_readiness_lock_records_audit_without_execution() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-readiness-lock",
        tenant_id="default",
        user_id="operator",
        request_id="req-readiness-lock",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK readiness lock.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for readiness lock"),
    )
    owner_acceptance_audit = audit_store.record(
        action="sdk.write_runner.owner_acceptance_recorded",
        resource_type="sdk_write_runner_owner_acceptance",
        resource_id="acceptance-lock-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_evidence": {
                "owner_acceptance_id": "acceptance-lock-1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "approval_id": approval.id,
                "runbook_acknowledged": True,
                "rollback_plan_acknowledged": True,
                "acceptance_hash": "hash-owner-acceptance",
            },
        },
    )
    readiness_receipt_audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_receipt_recorded",
        resource_type="sdk_write_runner_runtime_enablement_readiness",
        resource_id="readiness-lock-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_id": "acceptance-lock-1",
            "owner_acceptance_audit_id": owner_acceptance_audit.id,
            "runtime_enablement_receipt": {
                "readiness_receipt_id": "readiness-lock-1",
                "approval_id": approval.id,
                "owner_acceptance_id": "acceptance-lock-1",
                "owner_acceptance_audit_id": owner_acceptance_audit.id,
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "smoke_runbook_version": "v1",
                "rollback_runbook_version": "v1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "expires_at": "2026-06-09T00:00:00Z",
                "smoke_runbook_acknowledged": True,
                "rollback_runbook_acknowledged": True,
                "failure_receipt_reviewed": True,
                "acceptance_hash": "hash-readiness",
            },
        },
    )
    owner_pack_decision_audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
        resource_type="sdk_write_runner_runtime_enablement_owner_review_pack",
        resource_id="decision-lock-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "readiness_receipt_id": "readiness-lock-1",
            "readiness_receipt_audit_id": readiness_receipt_audit.id,
            "owner_acceptance_id": "acceptance-lock-1",
            "owner_acceptance_audit_id": owner_acceptance_audit.id,
            "owner_pack_decision": {
                "owner_pack_decision_id": "decision-lock-1",
                "decision": "accepted",
                "approval_id": approval.id,
                "readiness_receipt_id": "readiness-lock-1",
                "readiness_receipt_audit_id": readiness_receipt_audit.id,
                "owner_acceptance_id": "acceptance-lock-1",
                "owner_acceptance_audit_id": owner_acceptance_audit.id,
                "decided_by": "owner",
                "decided_at": "2026-06-08T01:00:00Z",
                "reason": "owner accepted pack",
                "decision_hash": "hash-decision",
            },
        },
    )
    request_payload = {
        "implementation_lock_id": "lock-record-1",
        "idempotency_key": "sdk-write-runner-lock-1",
        "idempotency_hash": "hash-idempotency",
        "approval_id": approval.id,
        "readiness_receipt_id": "readiness-lock-1",
        "readiness_receipt_audit_id": readiness_receipt_audit.id,
        "owner_pack_decision_id": "decision-lock-1",
        "owner_pack_decision_audit_id": owner_pack_decision_audit.id,
        "operator_id": "operator",
        "locked_at": "2026-06-08T02:00:00Z",
        "lock_reason": "owner accepted readiness lock",
        "lock_hash": "hash-lock",
        "dry_run": True,
    }

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            json=request_payload,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_implementation_readiness_lock_workflow_ready"
    readiness_lock = payload["readiness_lock"]
    assert readiness_lock["record_status"] == "recorded"
    assert readiness_lock["audit_event_recorded"] is True
    assert readiness_lock["audit_action"] == "sdk.write_runner.runtime_implementation_readiness_lock_recorded"
    assert readiness_lock["checks"]["approval_status_approved"] is True
    assert readiness_lock["checks"]["readiness_receipt_audit_record_present"] is True
    assert readiness_lock["checks"]["owner_pack_decision_audit_record_present"] is True
    assert readiness_lock["checks"]["owner_pack_decision_accepted"] is True
    assert readiness_lock["checks"]["readiness_lock_valid"] is True
    assert readiness_lock["runtime_flag_enabled"] is False
    assert readiness_lock["write_runner_enabled"] is False
    assert readiness_lock["agent_execution_enabled"] is False
    assert readiness_lock["runner_invoked"] is False
    assert readiness_lock["mark_executed"] is False
    assert readiness_lock["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_runtime_implementation_readiness_lock_readback_requires_strict_audit_query_keys() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    lock_audit = audit_store.record(
        action="sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        resource_type="sdk_write_runner_runtime_implementation_readiness_lock",
        resource_id="lock-readback-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": "approval-lock-readback",
            "readiness_receipt_id": "readiness-lock-readback",
            "owner_pack_decision_id": "decision-lock-readback",
            "readiness_lock": {
                "implementation_lock_id": "lock-readback-1",
                "idempotency_key": "sdk-write-runner-lock-readback",
                "idempotency_hash": "hash-idempotency",
                "approval_id": "approval-lock-readback",
                "readiness_receipt_id": "readiness-lock-readback",
                "readiness_receipt_audit_id": "audit-readiness-lock-readback",
                "owner_pack_decision_id": "decision-lock-readback",
                "owner_pack_decision_audit_id": "audit-decision-lock-readback",
                "operator_id": "operator",
                "locked_at": "2026-06-08T02:00:00Z",
                "lock_reason": "readback test",
                "lock_hash": "hash-lock",
            },
        },
    )
    contract = ControlPlaneSDK(default_tenant_id="default", default_user_id="operator").read_runtime_evidence(
        "sdk-write-runner-runtime-implementation-readiness-lock.json",
        evidence_type="sdk_write_runner_runtime_implementation_readiness_lock",
        implementation_lock_id="lock-readback-1",
        approval_id="approval-lock-readback",
        readiness_receipt_id="readiness-lock-readback",
        owner_pack_decision_id="decision-lock-readback",
        audit_id=lock_audit.id,
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/invoke",
            json=contract.to_dict(),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_owner_review_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_write_runner_runtime_implementation_readiness_lock"
    assert evidence["implementation_lock_present"] is True
    assert evidence["missing_required_query_keys"] == []
    assert evidence["record"]["implementation_lock_id"] == "lock-readback-1"
    assert evidence["record"]["audit_signature_present"] is True
    assert evidence["validation"]["status"] == "valid"
    assert evidence["audit_readback"]["record_persisted"] is True
    assert evidence["control_plane_readback"]["params"]["implementation_lock_id"] == "lock-readback-1"
    assert evidence["safety"]["write_runner_enabled"] is False
    assert evidence["safety"]["runner_invoked"] is False
    assert evidence["safety"]["mutation_performed"] is False


def test_sdk_runtime_implementation_readiness_lock_rejects_rejected_owner_pack_decision() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-readiness-lock-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-readiness-lock-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK readiness lock reject case.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for rejected decision test"),
    )
    readiness_receipt_audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_receipt_recorded",
        resource_type="sdk_write_runner_runtime_enablement_readiness",
        resource_id="readiness-lock-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "owner_acceptance_id": "acceptance-lock-reject",
            "owner_acceptance_audit_id": "audit-acceptance-lock-reject",
            "runtime_enablement_receipt": {
                "readiness_receipt_id": "readiness-lock-reject",
                "approval_id": approval.id,
                "owner_acceptance_id": "acceptance-lock-reject",
                "owner_acceptance_audit_id": "audit-acceptance-lock-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "smoke_runbook_version": "v1",
                "rollback_runbook_version": "v1",
                "accepted_by": "owner",
                "accepted_at": "2026-06-08T00:00:00Z",
                "expires_at": "2026-06-09T00:00:00Z",
                "smoke_runbook_acknowledged": True,
                "rollback_runbook_acknowledged": True,
                "failure_receipt_reviewed": True,
                "acceptance_hash": "hash-readiness",
            },
        },
    )
    owner_pack_decision_audit = audit_store.record(
        action="sdk.write_runner.runtime_enablement_owner_pack_decision_recorded",
        resource_type="sdk_write_runner_runtime_enablement_owner_review_pack",
        resource_id="decision-lock-reject",
        outcome="rejected",
        tenant_id="default",
        actor_id="owner",
        details={
            "approval_id": approval.id,
            "readiness_receipt_id": "readiness-lock-reject",
            "readiness_receipt_audit_id": readiness_receipt_audit.id,
            "owner_pack_decision": {
                "owner_pack_decision_id": "decision-lock-reject",
                "decision": "rejected",
                "approval_id": approval.id,
                "readiness_receipt_id": "readiness-lock-reject",
                "readiness_receipt_audit_id": readiness_receipt_audit.id,
                "owner_acceptance_id": "acceptance-lock-reject",
                "owner_acceptance_audit_id": "audit-acceptance-lock-reject",
                "decided_by": "owner",
                "decided_at": "2026-06-08T01:00:00Z",
                "reason": "owner rejected pack",
                "decision_hash": "hash-decision",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record",
            json={
                "implementation_lock_id": "lock-rejected-1",
                "idempotency_key": "sdk-write-runner-lock-rejected",
                "idempotency_hash": "hash-idempotency",
                "approval_id": approval.id,
                "readiness_receipt_id": "readiness-lock-reject",
                "readiness_receipt_audit_id": readiness_receipt_audit.id,
                "owner_pack_decision_id": "decision-lock-reject",
                "owner_pack_decision_audit_id": owner_pack_decision_audit.id,
                "operator_id": "operator",
                "locked_at": "2026-06-08T02:00:00Z",
                "lock_reason": "should not lock after rejected owner decision",
                "lock_hash": "hash-lock",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    readiness_lock = payload["readiness_lock"]
    assert readiness_lock["record_status"] == "rejected"
    assert readiness_lock["checks"]["owner_pack_decision_audit_record_present"] is False
    assert readiness_lock["checks"]["owner_pack_decision_accepted"] is False
    assert readiness_lock["audit_event_recorded"] is False
    assert readiness_lock["write_runner_enabled"] is False
    assert readiness_lock["runner_invoked"] is False
    assert readiness_lock["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_implementation_readiness_lock_recorded") == []


def test_sdk_runtime_implementation_final_decision_records_audit_without_execution() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-final-decision",
        tenant_id="default",
        user_id="operator",
        request_id="req-final-decision",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK final decision.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for final decision"),
    )
    readiness_lock_audit = audit_store.record(
        action="sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        resource_type="sdk_write_runner_runtime_implementation_readiness_lock",
        resource_id="lock-final-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "readiness_receipt_id": "readiness-final-1",
            "owner_pack_decision_id": "decision-final-1",
            "readiness_lock": {
                "implementation_lock_id": "lock-final-1",
                "idempotency_key": "sdk-write-runner-lock-final",
                "idempotency_hash": "hash-idempotency-final",
                "approval_id": approval.id,
                "readiness_receipt_id": "readiness-final-1",
                "readiness_receipt_audit_id": "audit-readiness-final-1",
                "owner_pack_decision_id": "decision-final-1",
                "owner_pack_decision_audit_id": "audit-decision-final-1",
                "operator_id": "operator",
                "locked_at": "2026-06-08T02:00:00Z",
                "lock_reason": "owner accepted readiness lock",
                "lock_hash": "hash-lock-final",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            json={
                "final_decision_id": "final-decision-record-1",
                "decision": "accepted",
                "approval_id": approval.id,
                "implementation_lock_id": "lock-final-1",
                "implementation_lock_audit_id": readiness_lock_audit.id,
                "readiness_receipt_id": "readiness-final-1",
                "owner_pack_decision_id": "decision-final-1",
                "decided_by": "owner",
                "decided_at": "2026-06-08T03:00:00Z",
                "reason": "owner accepted final implementation decision",
                "decision_hash": "hash-final-decision",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    final_decision = payload["final_decision"]
    assert final_decision["record_status"] == "recorded"
    assert final_decision["decision"] == "accepted"
    assert final_decision["audit_event_recorded"] is True
    assert final_decision["audit_action"] == "sdk.write_runner.runtime_implementation_final_decision_recorded"
    assert final_decision["checks"]["approval_status_approved"] is True
    assert final_decision["checks"]["readiness_lock_audit_record_present"] is True
    assert final_decision["checks"]["readiness_lock_validation_valid"] is True
    assert final_decision["checks"]["decision_valid"] is True
    assert final_decision["runtime_flag_enabled"] is False
    assert final_decision["implementation_enabled"] is False
    assert final_decision["write_runner_enabled"] is False
    assert final_decision["agent_execution_enabled"] is False
    assert final_decision["runner_invoked"] is False
    assert final_decision["mark_executed"] is False
    assert final_decision["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_implementation_final_decision_rejects_without_dry_run_guard() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-final-decision-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-final-decision-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK final decision reject.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for final decision reject"),
    )
    readiness_lock_audit = audit_store.record(
        action="sdk.write_runner.runtime_implementation_readiness_lock_recorded",
        resource_type="sdk_write_runner_runtime_implementation_readiness_lock",
        resource_id="lock-final-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "readiness_receipt_id": "readiness-final-reject",
            "owner_pack_decision_id": "decision-final-reject",
            "readiness_lock": {
                "implementation_lock_id": "lock-final-reject",
                "idempotency_key": "sdk-write-runner-lock-final-reject",
                "idempotency_hash": "hash-idempotency-final-reject",
                "approval_id": approval.id,
                "readiness_receipt_id": "readiness-final-reject",
                "readiness_receipt_audit_id": "audit-readiness-final-reject",
                "owner_pack_decision_id": "decision-final-reject",
                "owner_pack_decision_audit_id": "audit-decision-final-reject",
                "operator_id": "operator",
                "locked_at": "2026-06-08T02:00:00Z",
                "lock_reason": "owner accepted readiness lock",
                "lock_hash": "hash-lock-final-reject",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
            json={
                "final_decision_id": "final-decision-rejected-1",
                "decision": "accepted",
                "approval_id": approval.id,
                "implementation_lock_id": "lock-final-reject",
                "implementation_lock_audit_id": readiness_lock_audit.id,
                "readiness_receipt_id": "readiness-final-reject",
                "owner_pack_decision_id": "decision-final-reject",
                "decided_by": "owner",
                "decided_at": "2026-06-08T03:00:00Z",
                "reason": "should not record without dry-run guard",
                "decision_hash": "hash-final-decision-reject",
                "dry_run": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    final_decision = payload["final_decision"]
    assert final_decision["record_status"] == "rejected"
    assert final_decision["checks"]["dry_run_does_not_execute"] is False
    assert final_decision["audit_event_recorded"] is False
    assert final_decision["runtime_flag_enabled"] is False
    assert final_decision["write_runner_enabled"] is False
    assert final_decision["runner_invoked"] is False
    assert final_decision["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_implementation_final_decision_recorded") == []


def test_sdk_runtime_flag_enablement_records_intent_without_enabling_flag() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-enable",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-enable",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag enablement.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag enablement intent"),
    )
    final_decision_audit = audit_store.record(
        action="sdk.write_runner.runtime_implementation_final_decision_recorded",
        resource_type="sdk_write_runner_runtime_implementation_final_decision",
        resource_id="final-decision-flag-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "implementation_lock_id": "lock-flag-1",
            "readiness_receipt_id": "readiness-flag-1",
            "owner_pack_decision_id": "decision-flag-1",
            "final_decision": {
                "final_decision_id": "final-decision-flag-1",
                "decision": "accepted",
                "approval_id": approval.id,
                "implementation_lock_id": "lock-flag-1",
                "implementation_lock_audit_id": "audit-lock-flag-1",
                "readiness_receipt_id": "readiness-flag-1",
                "owner_pack_decision_id": "decision-flag-1",
                "decided_by": "owner",
                "decided_at": "2026-06-08T03:00:00Z",
                "reason": "owner accepted final implementation decision",
                "decision_hash": "hash-final-decision-flag",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            json={
                "runtime_flag_enablement_id": "flag-enable-record-1",
                "approval_id": approval.id,
                "final_decision_id": "final-decision-flag-1",
                "final_decision_audit_id": final_decision_audit.id,
                "implementation_lock_id": "lock-flag-1",
                "readiness_receipt_id": "readiness-flag-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requested_by": "owner",
                "requested_at": "2026-06-08T04:00:00Z",
                "enablement_reason": "owner requested explicit runtime flag enablement",
                "enablement_hash": "hash-flag-enable",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_enablement_record_workflow_ready"
    enablement = payload["runtime_flag_enablement"]
    assert enablement["record_status"] == "recorded"
    assert enablement["audit_event_recorded"] is True
    assert enablement["audit_action"] == "sdk.write_runner.runtime_flag_enablement_requested"
    assert enablement["checks"]["approval_status_approved"] is True
    assert enablement["checks"]["final_decision_audit_record_present"] is True
    assert enablement["checks"]["final_decision_accepted"] is True
    assert enablement["checks"]["runtime_flag_enablement_valid"] is True
    assert enablement["runtime_flag_enabled"] is False
    assert enablement["implementation_enabled"] is False
    assert enablement["write_runner_enabled"] is False
    assert enablement["agent_execution_enabled"] is False
    assert enablement["runner_invoked"] is False
    assert enablement["mark_executed"] is False
    assert enablement["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_flag_enablement_rejects_without_dry_run_guard() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-enable-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-enable-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag enablement reject.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag enablement reject"),
    )
    final_decision_audit = audit_store.record(
        action="sdk.write_runner.runtime_implementation_final_decision_recorded",
        resource_type="sdk_write_runner_runtime_implementation_final_decision",
        resource_id="final-decision-flag-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "implementation_lock_id": "lock-flag-reject",
            "readiness_receipt_id": "readiness-flag-reject",
            "owner_pack_decision_id": "decision-flag-reject",
            "final_decision": {
                "final_decision_id": "final-decision-flag-reject",
                "decision": "accepted",
                "approval_id": approval.id,
                "implementation_lock_id": "lock-flag-reject",
                "implementation_lock_audit_id": "audit-lock-flag-reject",
                "readiness_receipt_id": "readiness-flag-reject",
                "owner_pack_decision_id": "decision-flag-reject",
                "decided_by": "owner",
                "decided_at": "2026-06-08T03:00:00Z",
                "reason": "owner accepted final implementation decision",
                "decision_hash": "hash-final-decision-flag-reject",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/enablement/record",
            json={
                "runtime_flag_enablement_id": "flag-enable-rejected-1",
                "approval_id": approval.id,
                "final_decision_id": "final-decision-flag-reject",
                "final_decision_audit_id": final_decision_audit.id,
                "implementation_lock_id": "lock-flag-reject",
                "readiness_receipt_id": "readiness-flag-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requested_by": "owner",
                "requested_at": "2026-06-08T04:00:00Z",
                "enablement_reason": "should not record without dry-run guard",
                "enablement_hash": "hash-flag-enable-reject",
                "dry_run": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    enablement = payload["runtime_flag_enablement"]
    assert enablement["record_status"] == "rejected"
    assert enablement["checks"]["dry_run_does_not_enable_runtime"] is False
    assert enablement["audit_event_recorded"] is False
    assert enablement["runtime_flag_enabled"] is False
    assert enablement["write_runner_enabled"] is False
    assert enablement["runner_invoked"] is False
    assert enablement["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_flag_enablement_requested") == []


def test_sdk_runtime_flag_application_preflight_records_without_applying_flag() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-preflight",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-preflight",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag application preflight.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag preflight"),
    )
    enablement_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_enablement_requested",
        resource_type="sdk_write_runner_runtime_flag_enablement_request",
        resource_id="flag-enable-preflight-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "final_decision_id": "final-decision-preflight-1",
            "runtime_flag_enablement": {
                "runtime_flag_enablement_id": "flag-enable-preflight-1",
                "approval_id": approval.id,
                "final_decision_id": "final-decision-preflight-1",
                "final_decision_audit_id": "audit-final-decision-preflight-1",
                "implementation_lock_id": "lock-preflight-1",
                "readiness_receipt_id": "readiness-preflight-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requested_by": "owner",
                "requested_at": "2026-06-08T04:00:00Z",
                "enablement_reason": "owner requested explicit runtime flag enablement",
                "enablement_hash": "hash-flag-enable-preflight",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            json={
                "runtime_flag_preflight_id": "flag-preflight-record-1",
                "approval_id": approval.id,
                "runtime_flag_enablement_id": "flag-enable-preflight-1",
                "runtime_flag_enablement_audit_id": enablement_audit.id,
                "final_decision_id": "final-decision-preflight-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "target_state": "enabled",
                "requested_by": "owner",
                "requested_at": "2026-06-08T05:00:00Z",
                "preflight_reason": "owner requested runtime flag application preflight",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "preflight_hash": "hash-flag-preflight",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_preflight_workflow_ready"
    preflight = payload["runtime_flag_preflight"]
    assert preflight["record_status"] == "recorded"
    assert preflight["audit_event_recorded"] is True
    assert preflight["audit_action"] == "sdk.write_runner.runtime_flag_application_preflight_recorded"
    assert preflight["checks"]["approval_status_approved"] is True
    assert preflight["checks"]["runtime_flag_enablement_audit_record_present"] is True
    assert preflight["checks"]["runtime_flag_enablement_validation_valid"] is True
    assert preflight["checks"]["runtime_flag_preflight_valid"] is True
    assert preflight["runtime_flag_enabled"] is False
    assert preflight["flag_application_performed"] is False
    assert preflight["implementation_enabled"] is False
    assert preflight["write_runner_enabled"] is False
    assert preflight["agent_execution_enabled"] is False
    assert preflight["runner_invoked"] is False
    assert preflight["mark_executed"] is False
    assert preflight["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_flag_application_preflight_rejects_without_dry_run_guard() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-preflight-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-preflight-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag preflight reject.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag preflight reject"),
    )
    enablement_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_enablement_requested",
        resource_type="sdk_write_runner_runtime_flag_enablement_request",
        resource_id="flag-enable-preflight-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "final_decision_id": "final-decision-preflight-reject",
            "runtime_flag_enablement": {
                "runtime_flag_enablement_id": "flag-enable-preflight-reject",
                "approval_id": approval.id,
                "final_decision_id": "final-decision-preflight-reject",
                "final_decision_audit_id": "audit-final-decision-preflight-reject",
                "implementation_lock_id": "lock-preflight-reject",
                "readiness_receipt_id": "readiness-preflight-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "requested_by": "owner",
                "requested_at": "2026-06-08T04:00:00Z",
                "enablement_reason": "owner requested explicit runtime flag enablement",
                "enablement_hash": "hash-flag-enable-preflight-reject",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record",
            json={
                "runtime_flag_preflight_id": "flag-preflight-rejected-1",
                "approval_id": approval.id,
                "runtime_flag_enablement_id": "flag-enable-preflight-reject",
                "runtime_flag_enablement_audit_id": enablement_audit.id,
                "final_decision_id": "final-decision-preflight-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "target_state": "enabled",
                "requested_by": "owner",
                "requested_at": "2026-06-08T05:00:00Z",
                "preflight_reason": "should not apply runtime flag without dry-run guard",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "preflight_hash": "hash-flag-preflight-reject",
                "dry_run": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    preflight = payload["runtime_flag_preflight"]
    assert preflight["record_status"] == "rejected"
    assert preflight["checks"]["dry_run_does_not_apply_flag"] is False
    assert preflight["audit_event_recorded"] is False
    assert preflight["runtime_flag_enabled"] is False
    assert preflight["flag_application_performed"] is False
    assert preflight["write_runner_enabled"] is False
    assert preflight["runner_invoked"] is False
    assert preflight["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_flag_application_preflight_recorded") == []


def test_sdk_runtime_flag_application_owner_approval_records_without_applying_flag() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-approval",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-approval",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag application approval.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag owner approval"),
    )
    preflight_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_application_preflight_recorded",
        resource_type="sdk_write_runner_runtime_flag_application_preflight",
        resource_id="flag-preflight-approval-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "runtime_flag_enablement_id": "flag-enable-approval-1",
            "final_decision_id": "final-decision-approval-1",
            "runtime_flag_preflight": {
                "runtime_flag_preflight_id": "flag-preflight-approval-1",
                "approval_id": approval.id,
                "runtime_flag_enablement_id": "flag-enable-approval-1",
                "runtime_flag_enablement_audit_id": "audit-flag-enable-approval-1",
                "final_decision_id": "final-decision-approval-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "target_state": "enabled",
                "requested_by": "owner",
                "requested_at": "2026-06-08T05:00:00Z",
                "preflight_reason": "owner reviewed runtime flag preflight",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "preflight_hash": "hash-flag-preflight-approval",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            json={
                "runtime_flag_approval_id": "flag-approval-record-1",
                "approval_id": approval.id,
                "runtime_flag_preflight_id": "flag-preflight-approval-1",
                "runtime_flag_preflight_audit_id": preflight_audit.id,
                "runtime_flag_enablement_id": "flag-enable-approval-1",
                "final_decision_id": "final-decision-approval-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "decision": "accepted",
                "decided_by": "owner",
                "decided_at": "2026-06-08T06:00:00Z",
                "approval_reason": "owner accepted runtime flag application preflight",
                "approval_hash": "hash-flag-approval",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_owner_approval_workflow_ready"
    runtime_flag_approval = payload["runtime_flag_approval"]
    assert runtime_flag_approval["record_status"] == "recorded"
    assert runtime_flag_approval["audit_event_recorded"] is True
    assert runtime_flag_approval["audit_action"] == (
        "sdk.write_runner.runtime_flag_application_owner_approval_recorded"
    )
    assert runtime_flag_approval["checks"]["approval_status_approved"] is True
    assert runtime_flag_approval["checks"]["runtime_flag_preflight_audit_record_present"] is True
    assert runtime_flag_approval["checks"]["runtime_flag_preflight_validation_valid"] is True
    assert runtime_flag_approval["checks"]["runtime_flag_owner_approval_valid"] is True
    assert runtime_flag_approval["runtime_flag_enabled"] is False
    assert runtime_flag_approval["flag_application_performed"] is False
    assert runtime_flag_approval["implementation_enabled"] is False
    assert runtime_flag_approval["write_runner_enabled"] is False
    assert runtime_flag_approval["agent_execution_enabled"] is False
    assert runtime_flag_approval["runner_invoked"] is False
    assert runtime_flag_approval["mark_executed"] is False
    assert runtime_flag_approval["mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_flag_application_owner_approval_rejects_without_dry_run_guard() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-approval-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-approval-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag application approval reject.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag owner approval reject"),
    )
    preflight_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_application_preflight_recorded",
        resource_type="sdk_write_runner_runtime_flag_application_preflight",
        resource_id="flag-preflight-approval-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "runtime_flag_enablement_id": "flag-enable-approval-reject",
            "final_decision_id": "final-decision-approval-reject",
            "runtime_flag_preflight": {
                "runtime_flag_preflight_id": "flag-preflight-approval-reject",
                "approval_id": approval.id,
                "runtime_flag_enablement_id": "flag-enable-approval-reject",
                "runtime_flag_enablement_audit_id": "audit-flag-enable-approval-reject",
                "final_decision_id": "final-decision-approval-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "target_state": "enabled",
                "requested_by": "owner",
                "requested_at": "2026-06-08T05:00:00Z",
                "preflight_reason": "owner reviewed runtime flag preflight reject",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "preflight_hash": "hash-flag-preflight-approval-reject",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-approval/record",
            json={
                "runtime_flag_approval_id": "flag-approval-rejected-1",
                "approval_id": approval.id,
                "runtime_flag_preflight_id": "flag-preflight-approval-reject",
                "runtime_flag_preflight_audit_id": preflight_audit.id,
                "runtime_flag_enablement_id": "flag-enable-approval-reject",
                "final_decision_id": "final-decision-approval-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "decision": "accepted",
                "decided_by": "owner",
                "decided_at": "2026-06-08T06:00:00Z",
                "approval_reason": "should not record without dry-run guard",
                "approval_hash": "hash-flag-approval-reject",
                "dry_run": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    runtime_flag_approval = payload["runtime_flag_approval"]
    assert runtime_flag_approval["record_status"] == "rejected"
    assert runtime_flag_approval["checks"]["dry_run_does_not_apply_flag"] is False
    assert runtime_flag_approval["audit_event_recorded"] is False
    assert runtime_flag_approval["runtime_flag_enabled"] is False
    assert runtime_flag_approval["flag_application_performed"] is False
    assert runtime_flag_approval["write_runner_enabled"] is False
    assert runtime_flag_approval["runner_invoked"] is False
    assert runtime_flag_approval["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_flag_application_owner_approval_recorded") == []


def test_sdk_runtime_flag_application_execute_contract_records_without_applying_flag() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-execute-contract",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-execute-contract",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag application execute contract.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag execute contract"),
    )
    owner_approval_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_application_owner_approval_recorded",
        resource_type="sdk_write_runner_runtime_flag_application_owner_approval",
        resource_id="flag-approval-execute-1",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "runtime_flag_preflight_id": "flag-preflight-execute-1",
            "runtime_flag_enablement_id": "flag-enable-execute-1",
            "final_decision_id": "final-decision-execute-1",
            "runtime_flag_owner_approval": {
                "runtime_flag_approval_id": "flag-approval-execute-1",
                "approval_id": approval.id,
                "runtime_flag_preflight_id": "flag-preflight-execute-1",
                "runtime_flag_preflight_audit_id": "audit-flag-preflight-execute-1",
                "runtime_flag_enablement_id": "flag-enable-execute-1",
                "final_decision_id": "final-decision-execute-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "decision": "accepted",
                "decided_by": "owner",
                "decided_at": "2026-06-08T06:00:00Z",
                "approval_reason": "owner accepted runtime flag application preflight",
                "approval_hash": "hash-flag-approval-execute",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
            json={
                "runtime_flag_execute_contract_id": "flag-execute-contract-record-1",
                "approval_id": approval.id,
                "runtime_flag_approval_id": "flag-approval-execute-1",
                "runtime_flag_approval_audit_id": owner_approval_audit.id,
                "runtime_flag_preflight_id": "flag-preflight-execute-1",
                "runtime_flag_enablement_id": "flag-enable-execute-1",
                "final_decision_id": "final-decision-execute-1",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "operator_id": "operator",
                "locked_at": "2026-06-08T07:00:00Z",
                "execute_contract_reason": "owner requested live runtime flag application contract",
                "idempotency_key": "idem-flag-execute-contract-1",
                "idempotency_hash": "hash-idem-flag-execute-contract-1",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "execute_contract_hash": "hash-flag-execute-contract",
                "dry_run": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_workflow_ready"
    execute_contract = payload["runtime_flag_execute_contract"]
    assert execute_contract["record_status"] == "recorded"
    assert execute_contract["audit_event_recorded"] is True
    assert execute_contract["audit_action"] == (
        "sdk.write_runner.runtime_flag_application_execute_contract_recorded"
    )
    assert execute_contract["checks"]["approval_status_approved"] is True
    assert execute_contract["checks"]["runtime_flag_owner_approval_audit_record_present"] is True
    assert execute_contract["checks"]["runtime_flag_owner_approval_validation_valid"] is True
    assert execute_contract["checks"]["runtime_flag_owner_approval_accepted"] is True
    assert execute_contract["checks"]["runtime_flag_execute_contract_valid"] is True
    assert execute_contract["runtime_flag_enabled"] is False
    assert execute_contract["flag_application_performed"] is False
    assert execute_contract["implementation_enabled"] is False
    assert execute_contract["execute_enabled"] is False
    assert execute_contract["write_runner_enabled"] is False
    assert execute_contract["adapter_execution_enabled"] is False
    assert execute_contract["agent_execution_enabled"] is False
    assert execute_contract["write_execution_enabled"] is False
    assert execute_contract["runner_invoked"] is False
    assert execute_contract["mark_executed"] is False
    assert execute_contract["mutation_performed"] is False
    assert execute_contract["network_mutation_performed"] is False
    assert execute_contract["file_mutation_performed"] is False
    assert execute_contract["channel_mutation_performed"] is False
    assert approval_store.get(approval.id).status == "approved"
    assert approval_store.get(approval.id).executed_at is None


def test_sdk_runtime_flag_application_execute_contract_rejects_without_dry_run_guard() -> None:
    approval_store = ApprovalStore()
    audit_store = AuditStore(hmac_secret="test-secret")
    context = RunContext(
        trace_id="trace-flag-execute-contract-reject",
        tenant_id="default",
        user_id="operator",
        request_id="req-flag-execute-contract-reject",
    )
    approval = approval_store.create_approval(
        context=context,
        resource_type="command",
        resource_id="sdk:turn/start",
        action="command.execute",
        risk_level=RiskLevel.HIGH,
        reason="Owner-approved SDK runtime flag application execute contract reject.",
        arguments_preview={"method": "turn/start", "adapter_execution_enabled": False},
    )
    approval_store.approve(
        approval.id,
        ApprovalDecisionRequest(decided_by="owner", reason="ready for runtime flag execute contract reject"),
    )
    owner_approval_audit = audit_store.record(
        action="sdk.write_runner.runtime_flag_application_owner_approval_recorded",
        resource_type="sdk_write_runner_runtime_flag_application_owner_approval",
        resource_id="flag-approval-execute-reject",
        outcome="accepted",
        tenant_id="default",
        actor_id="operator",
        details={
            "approval_id": approval.id,
            "runtime_flag_preflight_id": "flag-preflight-execute-reject",
            "runtime_flag_enablement_id": "flag-enable-execute-reject",
            "final_decision_id": "final-decision-execute-reject",
            "runtime_flag_owner_approval": {
                "runtime_flag_approval_id": "flag-approval-execute-reject",
                "approval_id": approval.id,
                "runtime_flag_preflight_id": "flag-preflight-execute-reject",
                "runtime_flag_preflight_audit_id": "audit-flag-preflight-execute-reject",
                "runtime_flag_enablement_id": "flag-enable-execute-reject",
                "final_decision_id": "final-decision-execute-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "decision": "accepted",
                "decided_by": "owner",
                "decided_at": "2026-06-08T06:00:00Z",
                "approval_reason": "owner accepted runtime flag application preflight reject",
                "approval_hash": "hash-flag-approval-execute-reject",
            },
        },
    )

    with _client_with_stores(RunStore(), TraceStore(), approval_store, audit_store) as client:
        response = client.post(
            "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record",
            json={
                "runtime_flag_execute_contract_id": "flag-execute-contract-rejected-1",
                "approval_id": approval.id,
                "runtime_flag_approval_id": "flag-approval-execute-reject",
                "runtime_flag_approval_audit_id": owner_approval_audit.id,
                "runtime_flag_preflight_id": "flag-preflight-execute-reject",
                "runtime_flag_enablement_id": "flag-enable-execute-reject",
                "final_decision_id": "final-decision-execute-reject",
                "runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "operator_id": "operator",
                "locked_at": "2026-06-08T07:00:00Z",
                "execute_contract_reason": "should not apply runtime flag without dry-run guard",
                "idempotency_key": "idem-flag-execute-contract-reject",
                "idempotency_hash": "hash-idem-flag-execute-contract-reject",
                "rollback_plan_ref": "runbooks/sdk-write-runner-rollback.md",
                "smoke_runbook_ref": "runbooks/sdk-write-runner-smoke.md",
                "execute_contract_hash": "hash-flag-execute-contract-reject",
                "dry_run": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    execute_contract = payload["runtime_flag_execute_contract"]
    assert execute_contract["record_status"] == "rejected"
    assert execute_contract["checks"]["dry_run_does_not_apply_flag"] is False
    assert execute_contract["audit_event_recorded"] is False
    assert execute_contract["runtime_flag_enabled"] is False
    assert execute_contract["flag_application_performed"] is False
    assert execute_contract["write_runner_enabled"] is False
    assert execute_contract["runner_invoked"] is False
    assert execute_contract["mutation_performed"] is False
    assert audit_store.list(action="sdk.write_runner.runtime_flag_application_execute_contract_recorded") == []


def test_control_plane_rejects_raw_secret_payloads() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-secret",
            "method": "thread/read",
            "params": {"openai_api_key": "sk-test1234567890abcdef"},
            "context": {"trace_id": "trace-secret"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "raw_secret_payload_rejected"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["details"]["secret_paths"] == ["$.params.openai_api_key"]
    assert "sk-test" not in response.text


def test_control_plane_accepts_secret_references() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-secret-ref",
            "method": "runtime/evidence/read",
            "params": {
                "report_name": "latest-codex-alignment.json",
                "openai_api_key": "secret://openai/default",
            },
            "context": {"trace_id": "trace-secret-ref"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["result"]["method"] == "runtime/evidence/read"
    assert payload["result"]["contract"]["mutation_performed"] is False
    assert payload["result"]["evidence"]["report_name"] == "latest-codex-alignment.json"


def test_control_plane_unknown_method_uses_protocol_error_envelope() -> None:
    response = _client().post(
        "/api/v1/control-plane/invoke",
        json={
            "id": "req-unknown",
            "method": "missing/method",
            "params": {},
            "context": {"trace_id": "trace-unknown"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["result"] is None
    assert payload["error"]["code"] == "method_not_found"
    assert payload["evidence"]["trace_id"] == "trace-unknown"
    assert payload["evidence"]["audit_id"]


def test_control_plane_thread_read_returns_durable_run_state(
    durable_thread_state: tuple[RunStore, TraceStore, ApprovalStore, str],
) -> None:
    run_store, trace_store, approval_store, trace_id = durable_thread_state

    with _client_with_stores(run_store, trace_store, approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/invoke",
            json={
                "id": "req-durable-read",
                "method": "thread/read",
                "params": {"thread_id": trace_id},
                "context": {"trace_id": trace_id, "workspace_id": "workspace-control"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    thread = payload["result"]["thread"]
    assert payload["ok"] is True
    assert thread["thread_id"] == trace_id
    assert thread["status"] == "completed"
    assert thread["turns"][0]["event_count"] == 3
    assert [item["role"] for item in thread["items"]] == ["user", "assistant"]
    assert thread["tool_calls"]["count"] == 0
    assert thread["approval_summary"]["pending"] == 1
    assert thread["evidence_links"]["run"] == f"/api/v1/runs/{trace_id}"
    assert thread["rollback"]["requires_approval"] is True
    assert thread["rollback"]["file_system_rollback"] is False
    assert thread["worktree"]["file_mutation_performed"] is False
    assert thread["automations"]["scheduled_runs_supported"] is False


def test_control_plane_thread_search_lists_thread_worktree_and_automation_state(
    durable_thread_state: tuple[RunStore, TraceStore, ApprovalStore, str],
) -> None:
    run_store, trace_store, approval_store, trace_id = durable_thread_state

    with _client_with_stores(run_store, trace_store, approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/invoke",
            json={
                "id": "req-thread-search",
                "method": "thread/search",
                "params": {"limit": 5, "status": "completed"},
                "context": {"trace_id": "trace-search"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    threads = payload["result"]["threads"]
    assert threads["count"] == 1
    assert threads["items"][0]["thread_id"] == trace_id
    assert threads["items"][0]["approval_summary"]["pending"] == 1
    assert threads["worktree"]["mode"] == "metadata_only"
    assert threads["worktree"]["file_mutation_performed"] is False
    assert threads["automations"]["evidence_only"] is True


def test_control_plane_turn_events_list_normalizes_trace_events(
    durable_thread_state: tuple[RunStore, TraceStore, ApprovalStore, str],
) -> None:
    run_store, trace_store, approval_store, trace_id = durable_thread_state

    with _client_with_stores(run_store, trace_store, approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/invoke",
            json={
                "id": "req-turn-events",
                "method": "turn/events/list",
                "params": {"thread_id": trace_id, "limit": 2},
                "context": {"trace_id": trace_id},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    events = payload["result"]["events"]
    assert events["thread_id"] == trace_id
    assert events["count"] == 2
    assert events["items"][0]["event_id"] == f"{trace_id}:event:1"
    assert events["items"][0]["type"] == "agent.started"
    assert events["items"][0]["item_id"] == f"{trace_id}:item:1"
    assert events["items"][0]["payload"]["task"] == "inspect durable thread"
    assert events["items"][0]["created_at"]


def test_control_plane_thread_rollback_is_metadata_only_and_owner_gated(
    durable_thread_state: tuple[RunStore, TraceStore, ApprovalStore, str],
) -> None:
    run_store, trace_store, approval_store, trace_id = durable_thread_state

    with _client_with_stores(run_store, trace_store, approval_store) as client:
        response = client.post(
            "/api/v1/control-plane/invoke",
            json={
                "id": "req-thread-rollback",
                "method": "thread/rollback",
                "params": {"thread_id": trace_id},
                "context": {"trace_id": trace_id},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    operation = payload["error"]["details"]["thread_operation"]
    assert payload["ok"] is False
    assert payload["error"]["code"] == "approval_required"
    assert payload["error"]["details"]["mutation_performed"] is False
    assert operation["operation"] == "rollback"
    assert operation["source_exists"] is True
    assert operation["metadata_only"] is True
    assert operation["file_system_rollback"] is False
    assert operation["file_rollback_claimed"] is False
    assert operation["approval_summary"]["pending"] == 1
    assert operation["trace_event_count"] == 3
