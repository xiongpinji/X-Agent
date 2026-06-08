from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from backend.app.core.approvals import ApprovalStore
from backend.app.core.contracts import AgentRunResponse, RiskLevel, RunContext, RunStatus
from backend.app.core.runs import RunStore
from backend.app.core.tracing import TraceStore
from backend.app.dependencies import get_approval_store, get_run_store, get_trace_store
from backend.app.main import app
from backend.app.sdk import ControlPlaneSDK


def _client() -> TestClient:
    return TestClient(app, headers={"x-api-key": "bootstrap"})


@contextmanager
def _client_with_stores(
    run_store: RunStore,
    trace_store: TraceStore,
    approval_store: ApprovalStore,
):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_run_store] = lambda: run_store
    app.dependency_overrides[get_trace_store] = lambda: trace_store
    app.dependency_overrides[get_approval_store] = lambda: approval_store
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
    assert payload["status"] == "sdk_approval_intent_ready"
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
    assert payload["status"] == "sdk_approval_intent_ready"
    assert payload["sdk"]["method"] == "thread/read"
    assert payload["sdk"]["owner_gate_required"] is False
    assert payload["sdk"]["approval_intent"]["required"] is False
    assert payload["sdk"]["approval_intent"]["created"] is False
    assert payload["sdk"]["mutation_performed"] is False
    assert payload["control_plane"]["result"]["contract"]["dry_run"] is True
    assert payload["control_plane"]["result"]["compatibility"]["sdk_surface"] == "python"
    assert payload["control_plane"]["result"]["compatibility"]["non_interactive"] is True
    assert approval_store.pending_count() == 0


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
