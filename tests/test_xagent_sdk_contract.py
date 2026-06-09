from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from backend.app.sdk import ControlPlaneSDK
from cli.config import CLIConfig
from cli.main import app, set_current_config


def test_sdk_start_thread_builds_control_plane_envelope() -> None:
    contract = ControlPlaneSDK(default_tenant_id="tenant-a", default_user_id="operator").start_thread(
        "ship the pilot",
        permission_scope=["tools:read"],
        idempotency_key="idem-1",
    )
    payload = contract.to_dict()

    assert payload["operation"] == "thread_start"
    assert payload["request"]["method"] == "thread/start"
    assert payload["request"]["params"]["task"] == "ship the pilot"
    assert payload["request"]["context"]["tenant_id"] == "tenant-a"
    assert payload["request"]["context"]["user_id"] == "operator"
    assert payload["request"]["context"]["non_interactive"] is True
    assert payload["request"]["dry_run"] is True
    assert payload["request"]["mutation_performed"] is False
    assert payload["request"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["required_for_write_methods"] is True
    assert payload["owner_gate"]["write_runner_safety_contract"] is True
    assert payload["owner_gate"]["write_runner_execute_gate_contract"] is True
    assert payload["owner_gate"]["write_runner_adapter_review_contract"] is True
    assert payload["owner_gate"]["write_runner_adapter_review_enabled"] is False
    assert payload["owner_gate"]["write_runner_runtime_flag_contract"] is True
    assert payload["owner_gate"]["owner_acceptance_evidence_required"] is True
    assert payload["owner_gate"]["owner_acceptance_recording_contract"] is True
    assert payload["owner_gate"]["owner_acceptance_readback_contract"] is True
    assert payload["owner_gate"]["owner_acceptance_record_present"] is False
    assert payload["owner_gate"]["runtime_enablement_review_contract"] is True
    assert payload["owner_gate"]["runtime_enablement_review_enabled"] is False
    assert payload["owner_gate"]["write_runner_implementation_plan_contract"] is True
    assert payload["owner_gate"]["write_runner_implementation_plan_enabled"] is False
    assert payload["owner_gate"]["runtime_smoke_runbook_contract"] is True
    assert payload["owner_gate"]["runtime_smoke_runbook_enabled"] is False
    assert payload["owner_gate"]["runtime_enablement_receipt_contract"] is True
    assert payload["owner_gate"]["runtime_enablement_receipt_enabled"] is False
    assert payload["owner_gate"]["runtime_implementation_preflight_contract"] is True
    assert payload["owner_gate"]["runtime_implementation_preflight_enabled"] is False
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["mark_executed"] is False


def test_sdk_resume_run_and_read_thread_methods_are_stable() -> None:
    sdk = ControlPlaneSDK()
    resume = sdk.resume_thread("thread-1", input_text="continue", dry_run=False).to_dict()
    turn = sdk.run_turn("thread-1", "next", approved_approval_id="approval-1").to_dict()
    read = sdk.read_thread("thread-1").to_dict()
    evidence = sdk.read_runtime_evidence("latest-codex-alignment.json").to_dict()
    receipt_evidence = sdk.read_runtime_evidence(
        "sdk-dry-run-executor-stub.json",
        evidence_type="sdk_dry_run_executor_stub",
        approval_id="approval-1",
        method="turn/start",
    ).to_dict()

    assert resume["operation"] == "thread_resume"
    assert resume["request"]["method"] == "thread/resume"
    assert resume["request"]["dry_run"] is False
    assert resume["owner_gate"]["mutation_performed"] is False
    assert turn["operation"] == "turn_start"
    assert turn["request"]["method"] == "turn/start"
    assert turn["approved_approval_id"] == "approval-1"
    assert turn["owner_approved"] is True
    assert turn["owner_gate"]["approved_approval_id"] == "approval-1"
    assert turn["owner_gate"]["execution_adapter_contract"] == "owner_approved_preflight"
    assert turn["owner_gate"]["write_runner_safety_contract"] is True
    assert turn["owner_gate"]["write_runner_adapter_review_contract"] is True
    assert turn["owner_gate"]["write_runner_adapter_review_enabled"] is False
    assert turn["owner_gate"]["write_runner_runtime_flag_contract"] is True
    assert turn["owner_gate"]["owner_acceptance_evidence_required"] is True
    assert turn["owner_gate"]["owner_acceptance_recording_contract"] is True
    assert turn["owner_gate"]["owner_acceptance_readback_contract"] is True
    assert turn["owner_gate"]["runtime_enablement_review_contract"] is True
    assert turn["owner_gate"]["runtime_enablement_review_enabled"] is False
    assert turn["owner_gate"]["write_runner_implementation_plan_contract"] is True
    assert turn["owner_gate"]["write_runner_implementation_plan_enabled"] is False
    assert turn["owner_gate"]["runtime_smoke_runbook_contract"] is True
    assert turn["owner_gate"]["runtime_smoke_runbook_enabled"] is False
    assert turn["owner_gate"]["runtime_enablement_receipt_contract"] is True
    assert turn["owner_gate"]["runtime_enablement_receipt_enabled"] is False
    assert turn["owner_gate"]["runtime_implementation_preflight_contract"] is True
    assert turn["owner_gate"]["runtime_implementation_preflight_enabled"] is False
    assert turn["owner_gate"]["runtime_flag_enabled"] is False
    assert turn["owner_gate"]["runner_invoked"] is False
    assert turn["owner_gate"]["adapter_execution_enabled"] is False
    assert read["operation"] == "thread_read"
    assert read["request"]["method"] == "thread/read"
    assert read["request"]["dry_run"] is True
    assert read["owner_gate"]["required_for_write_methods"] is False
    assert read["owner_gate"]["read_only_runner_contract"] is True
    assert read["owner_gate"]["write_runner_adapter_review_contract"] is False
    assert read["owner_gate"]["write_runner_runtime_flag_contract"] is False
    assert read["owner_gate"]["owner_acceptance_evidence_required"] is False
    assert read["owner_gate"]["owner_acceptance_recording_contract"] is False
    assert read["owner_gate"]["owner_acceptance_readback_contract"] is False
    assert read["owner_gate"]["runtime_enablement_review_contract"] is False
    assert read["owner_gate"]["write_runner_implementation_plan_contract"] is False
    assert read["owner_gate"]["runtime_smoke_runbook_contract"] is False
    assert read["owner_gate"]["runtime_enablement_receipt_contract"] is False
    assert read["owner_gate"]["runtime_implementation_preflight_contract"] is False
    assert evidence["operation"] == "runtime_evidence_read"
    assert evidence["request"]["method"] == "runtime/evidence/read"
    assert evidence["request"]["params"]["report_name"] == "latest-codex-alignment.json"
    assert evidence["owner_gate"]["required_for_write_methods"] is False
    assert receipt_evidence["request"]["params"]["evidence_type"] == "sdk_dry_run_executor_stub"
    assert receipt_evidence["request"]["params"]["approval_id"] == "approval-1"
    assert receipt_evidence["request"]["params"]["method"] == "turn/start"
    acceptance_evidence = sdk.read_runtime_evidence(
        "sdk-write-runner-owner-acceptance.json",
        evidence_type="sdk_write_runner_owner_acceptance",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id="audit-1",
    ).to_dict()
    assert acceptance_evidence["request"]["params"]["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert acceptance_evidence["request"]["params"]["owner_acceptance_id"] == "acceptance-1"
    assert acceptance_evidence["request"]["params"]["audit_id"] == "audit-1"
    readiness_evidence = sdk.read_runtime_evidence(
        "sdk-write-runner-runtime-enable-readiness.json",
        evidence_type="sdk_write_runner_runtime_enablement_readiness",
        readiness_receipt_id="readiness-1",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        audit_id="audit-readiness-1",
    ).to_dict()
    assert (
        readiness_evidence["request"]["params"]["evidence_type"]
        == "sdk_write_runner_runtime_enablement_readiness"
    )
    assert readiness_evidence["request"]["params"]["readiness_receipt_id"] == "readiness-1"
    assert readiness_evidence["request"]["params"]["owner_acceptance_id"] == "acceptance-1"
    assert readiness_evidence["request"]["params"]["audit_id"] == "audit-readiness-1"
    lock_evidence = sdk.read_runtime_evidence(
        "sdk-write-runner-runtime-implementation-readiness-lock.json",
        evidence_type="sdk_write_runner_runtime_implementation_readiness_lock",
        implementation_lock_id="lock-1",
        approval_id="approval-1",
        readiness_receipt_id="readiness-1",
        owner_pack_decision_id="decision-1",
        audit_id="audit-lock-1",
    ).to_dict()
    assert (
        lock_evidence["request"]["params"]["evidence_type"]
        == "sdk_write_runner_runtime_implementation_readiness_lock"
    )
    assert lock_evidence["request"]["params"]["implementation_lock_id"] == "lock-1"
    assert lock_evidence["request"]["params"]["owner_pack_decision_id"] == "decision-1"
    assert lock_evidence["request"]["params"]["audit_id"] == "audit-lock-1"
    acceptance_record = sdk.record_owner_acceptance(
        owner_acceptance_id="acceptance-1",
        approval_id="approval-1",
        accepted_by="owner",
        accepted_at="2026-06-08T00:00:00Z",
        runbook_acknowledged=True,
        rollback_plan_acknowledged=True,
        acceptance_hash="hash-1",
    ).to_dict()
    assert acceptance_record["operation"] == "owner_acceptance_record"
    assert acceptance_record["endpoint"] == "/api/v1/control-plane/sdk/owner-acceptance/record"
    assert acceptance_record["request"]["approval_id"] == "approval-1"
    assert acceptance_record["request"]["acceptance_hash"] == "hash-1"
    assert acceptance_record["owner_gate"]["requires_approved_sdk_approval"] is True
    assert acceptance_record["owner_gate"]["marks_approval_executed"] is False
    assert acceptance_record["owner_gate"]["write_runner_enabled"] is False
    assert acceptance_record["mutation_performed"] is False
    readiness_record = sdk.record_runtime_enablement_receipt(
        readiness_receipt_id="readiness-1",
        approval_id="approval-1",
        owner_acceptance_id="acceptance-1",
        owner_acceptance_audit_id="audit-acceptance-1",
        smoke_runbook_version="v1",
        rollback_runbook_version="v1",
        accepted_by="owner",
        accepted_at="2026-06-08T00:00:00Z",
        expires_at="2026-06-09T00:00:00Z",
        smoke_runbook_acknowledged=True,
        rollback_runbook_acknowledged=True,
        failure_receipt_reviewed=True,
        acceptance_hash="hash-readiness-1",
    ).to_dict()
    assert readiness_record["operation"] == "runtime_enablement_receipt_record"
    assert readiness_record["endpoint"] == "/api/v1/control-plane/sdk/runtime-enablement/receipt/record"
    assert readiness_record["request"]["readiness_receipt_id"] == "readiness-1"
    assert readiness_record["request"]["owner_acceptance_audit_id"] == "audit-acceptance-1"
    assert readiness_record["owner_gate"]["requires_owner_acceptance_audit_record"] is True
    assert readiness_record["owner_gate"]["marks_approval_executed"] is False
    assert readiness_record["owner_gate"]["write_runner_enabled"] is False
    assert readiness_record["owner_gate"]["runner_invoked"] is False
    assert readiness_record["mutation_performed"] is False
    owner_pack_decision = sdk.record_runtime_enablement_owner_pack_decision(
        owner_pack_decision_id="decision-1",
        decision="accepted",
        approval_id="approval-1",
        readiness_receipt_id="readiness-1",
        readiness_receipt_audit_id="audit-readiness-1",
        owner_acceptance_id="acceptance-1",
        owner_acceptance_audit_id="audit-acceptance-1",
        decided_by="owner",
        decided_at="2026-06-08T00:00:00Z",
        reason="owner accepted pack",
        decision_hash="hash-decision-1",
    ).to_dict()
    assert owner_pack_decision["operation"] == "runtime_enablement_owner_pack_decision_record"
    assert (
        owner_pack_decision["endpoint"]
        == "/api/v1/control-plane/sdk/runtime-enablement/owner-pack/decision/record"
    )
    assert owner_pack_decision["request"]["decision"] == "accepted"
    assert owner_pack_decision["request"]["decision_hash"] == "hash-decision-1"
    assert owner_pack_decision["owner_gate"]["requires_runtime_enablement_readiness_receipt"] is True
    assert owner_pack_decision["owner_gate"]["marks_approval_executed"] is False
    assert owner_pack_decision["owner_gate"]["write_runner_enabled"] is False
    assert owner_pack_decision["owner_gate"]["runner_invoked"] is False
    assert owner_pack_decision["mutation_performed"] is False
    readiness_lock = sdk.record_runtime_implementation_readiness_lock(
        implementation_lock_id="lock-1",
        idempotency_key="sdk-write-runner-lock-1",
        idempotency_hash="hash-idempotency-1",
        approval_id="approval-1",
        readiness_receipt_id="readiness-1",
        readiness_receipt_audit_id="audit-readiness-1",
        owner_pack_decision_id="decision-1",
        owner_pack_decision_audit_id="audit-decision-1",
        operator_id="operator",
        locked_at="2026-06-08T00:00:00Z",
        lock_reason="owner accepted readiness lock",
        lock_hash="hash-lock-1",
    ).to_dict()
    assert readiness_lock["operation"] == "runtime_implementation_readiness_lock_record"
    assert (
        readiness_lock["endpoint"]
        == "/api/v1/control-plane/sdk/runtime-implementation/readiness-lock/record"
    )
    assert readiness_lock["request"]["implementation_lock_id"] == "lock-1"
    assert readiness_lock["request"]["idempotency_key"] == "sdk-write-runner-lock-1"
    assert readiness_lock["request"]["owner_pack_decision_audit_id"] == "audit-decision-1"
    assert readiness_lock["owner_gate"]["requires_accepted_owner_pack_decision"] is True
    assert readiness_lock["owner_gate"]["requires_idempotency_key"] is True
    assert readiness_lock["owner_gate"]["requires_idempotency_hash"] is True
    assert readiness_lock["owner_gate"]["marks_approval_executed"] is False
    assert readiness_lock["owner_gate"]["write_runner_enabled"] is False
    assert readiness_lock["owner_gate"]["runner_invoked"] is False
    assert readiness_lock["mutation_performed"] is False
    final_decision = sdk.record_runtime_implementation_final_decision(
        final_decision_id="final-decision-1",
        decision="accepted",
        approval_id="approval-1",
        implementation_lock_id="lock-1",
        implementation_lock_audit_id="audit-lock-1",
        readiness_receipt_id="readiness-1",
        owner_pack_decision_id="decision-1",
        decided_by="owner",
        decided_at="2026-06-08T00:00:00Z",
        reason="owner accepted final decision",
        decision_hash="hash-final-decision-1",
    ).to_dict()
    assert final_decision["operation"] == "runtime_implementation_final_decision_record"
    assert (
        final_decision["endpoint"]
        == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
    )
    assert final_decision["request"]["implementation_lock_audit_id"] == "audit-lock-1"
    assert final_decision["request"]["decision_hash"] == "hash-final-decision-1"
    assert final_decision["owner_gate"]["requires_runtime_implementation_readiness_lock"] is True
    assert final_decision["owner_gate"]["requires_decision_accept_or_reject"] is True
    assert final_decision["owner_gate"]["marks_approval_executed"] is False
    assert final_decision["owner_gate"]["runtime_flag_enabled"] is False
    assert final_decision["owner_gate"]["implementation_enabled"] is False
    assert final_decision["owner_gate"]["write_runner_enabled"] is False
    assert final_decision["owner_gate"]["runner_invoked"] is False
    assert final_decision["mutation_performed"] is False
    runtime_flag_enablement = sdk.record_runtime_flag_enablement(
        runtime_flag_enablement_id="flag-enable-1",
        approval_id="approval-1",
        final_decision_id="final-decision-1",
        final_decision_audit_id="audit-final-decision-1",
        implementation_lock_id="lock-1",
        readiness_receipt_id="readiness-1",
        requested_by="owner",
        requested_at="2026-06-08T00:00:00Z",
        enablement_reason="owner explicitly requested runtime flag enablement",
        enablement_hash="hash-flag-enable-1",
    ).to_dict()
    assert runtime_flag_enablement["operation"] == "runtime_flag_enablement_record"
    assert runtime_flag_enablement["endpoint"] == "/api/v1/control-plane/sdk/runtime-flag/enablement/record"
    assert runtime_flag_enablement["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert runtime_flag_enablement["request"]["final_decision_audit_id"] == "audit-final-decision-1"
    assert runtime_flag_enablement["owner_gate"]["requires_runtime_implementation_final_decision"] is True
    assert runtime_flag_enablement["owner_gate"]["requires_final_decision_accepted"] is True
    assert runtime_flag_enablement["owner_gate"]["marks_approval_executed"] is False
    assert runtime_flag_enablement["owner_gate"]["runtime_flag_enabled"] is False
    assert runtime_flag_enablement["owner_gate"]["implementation_enabled"] is False
    assert runtime_flag_enablement["owner_gate"]["write_runner_enabled"] is False
    assert runtime_flag_enablement["owner_gate"]["runner_invoked"] is False
    assert runtime_flag_enablement["mutation_performed"] is False
    runtime_flag_preflight = sdk.record_runtime_flag_application_preflight(
        runtime_flag_preflight_id="flag-preflight-1",
        approval_id="approval-1",
        runtime_flag_enablement_id="flag-enable-1",
        runtime_flag_enablement_audit_id="audit-flag-enable-1",
        final_decision_id="final-decision-1",
        requested_by="owner",
        requested_at="2026-06-08T00:00:00Z",
        preflight_reason="owner requested live runtime flag application preflight",
        rollback_plan_ref="runbooks/sdk-write-runner-rollback.md",
        smoke_runbook_ref="runbooks/sdk-write-runner-smoke.md",
        preflight_hash="hash-flag-preflight-1",
    ).to_dict()
    assert runtime_flag_preflight["operation"] == "runtime_flag_application_preflight_record"
    assert (
        runtime_flag_preflight["endpoint"]
        == "/api/v1/control-plane/sdk/runtime-flag/application-preflight/record"
    )
    assert runtime_flag_preflight["request"]["target_state"] == "enabled"
    assert runtime_flag_preflight["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert runtime_flag_preflight["owner_gate"]["requires_runtime_flag_enablement_intent"] is True
    assert runtime_flag_preflight["owner_gate"]["requires_rollback_plan"] is True
    assert runtime_flag_preflight["owner_gate"]["requires_smoke_runbook"] is True
    assert runtime_flag_preflight["owner_gate"]["marks_approval_executed"] is False
    assert runtime_flag_preflight["owner_gate"]["runtime_flag_enabled"] is False
    assert runtime_flag_preflight["owner_gate"]["flag_application_performed"] is False
    assert runtime_flag_preflight["owner_gate"]["write_runner_enabled"] is False
    assert runtime_flag_preflight["owner_gate"]["runner_invoked"] is False
    assert runtime_flag_preflight["mutation_performed"] is False


def test_sdk_contract_keeps_feishu_domestic_v1_primary() -> None:
    contract = ControlPlaneSDK().start_thread("domestic pilot").to_dict()
    strategy = contract["channel_strategy"]

    assert strategy["pilot_channel"] == "feishu"
    assert strategy["domestic_v1_primary"] == "feishu"
    assert strategy["telegram_required"] is False
    assert strategy["slack_blocking"] is False
    assert strategy["dingtalk_or_wechat_work_next"] == "after_feishu_pilot_acceptance"


def test_cli_sdk_thread_start_outputs_non_interactive_json() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    result = CliRunner().invoke(
        app,
        [
            "sdk",
            "thread-start",
            "pilot task",
            "--tenant-id",
            "tenant-a",
            "--user-id",
            "operator",
            "--scope",
            "tools:read",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"] == "thread_start"
    assert payload["request"]["method"] == "thread/start"
    assert payload["request"]["context"]["tenant_id"] == "tenant-a"
    assert payload["request"]["dry_run"] is True


def test_cli_sdk_turn_run_execute_flag_calls_backend_stub_without_agent_execution() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "turn/start",
            "dry_run": False,
            "adapter_execution_enabled": False,
            "mutation_performed": False,
            "network_mutation_performed": False,
            "approval_intent": {
                "required": True,
                "created": True,
                "approval_id": "approval-1",
                "status": "pending",
                "mutation_performed": False,
            },
            "approval_handoff": {
                "available": True,
                "approval_id": "approval-1",
                "next_commands": [
                    "xagent approvals show approval-1",
                    "xagent approvals approve approval-1 --by <owner> --reason <reason>",
                ],
                "blocked_command": "xagent approvals execute approval-1",
                "execute_disabled": True,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            "execution_adapter_contract": {
                "approved_approval_id": "approval-1",
                "preflight_status": "approved_ready",
                "ready_for_owner_approved_adapter": True,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "execute_disabled": True,
                "mark_executed": False,
                "mutation_performed": False,
                "network_mutation_performed": False,
            },
            "read_only_runner_contract": {
                "available": False,
                "read_only_runner_enabled": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "mutation_performed": False,
            },
            "write_runner_safety_contract": {
                "ready_for_runner_contract": True,
                "runner_plan": {"approval_id": "approval-1", "idempotency_key_present": True},
                "receipt_template": {"status": "planned_not_executed", "runner_invoked": False},
                "runner_invoked": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "dry_run_executor_stub": {
                "available": True,
                "audit_event_recorded": True,
                "audit_action": "sdk.write_runner.dry_run_planned",
                "receipt": {"status": "dry_run_planned", "runner_invoked": False},
                "runner_invoked": False,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "write_runner_execute_gate": {
                "stage": "owner_approved_write_runner_execute_gate",
                "gate_status": "ready_but_disabled",
                "checks": {
                    "approved_preflight_ready": True,
                    "runner_contract_ready": True,
                    "receipt_persisted": True,
                    "dry_run_receipt_planned": True,
                    "runner_not_invoked": True,
                    "mark_executed_false": True,
                    "mutation_false": True,
                    "idempotency_key_present": True,
                },
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "write_runner_adapter_review": {
                "stage": "owner_approved_write_runner_adapter_implementation_review",
                "review_status": "ready_but_disabled",
                "adapter_target": {"callable": "AgentCoordinator.run"},
                "implementation_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "adapter_execution_enabled": False,
                "agent_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "write_runner_runtime_flag": {
                "flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED",
                "flag_status": "declared_disabled",
                "runtime_flag_enabled": False,
                "implementation_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "mutation_performed": False,
            },
            "owner_acceptance_evidence": {
                "evidence_status": "recording_contract_ready_not_provided",
                "recording_contract_ready": True,
                "evidence_type": "sdk_write_runner_owner_acceptance",
                "recording_contract": {"created_by_sdk_invoke": False},
                "required_fields": ["owner_acceptance_id"],
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_enablement_review": {
                "review_status": "ready_but_disabled",
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "write_runner_implementation_plan": {
                "stage": "owner_approved_write_runner_concrete_implementation_plan",
                "plan_status": "ready_but_disabled",
                "adapter_target": {"callable": "AgentCoordinator.run"},
                "idempotency_contract": {"required": True},
                "rollback_plan": {"disable_runtime_flag": True},
                "audit_result_shape": {"planned_action": "sdk.write_runner.implementation_plan_ready"},
                "implementation_enabled": False,
                "runtime_flag_enabled": False,
                "execute_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_smoke_runbook": {
                "stage": "owner_approved_write_runner_runtime_smoke_runbook",
                "contract_status": "ready_but_disabled",
                "smoke_plan": {"requires_runtime_flag": "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"},
                "rollback_plan": {"failure_receipt_required": True},
                "failure_receipt_contract": {
                    "audit_action": "sdk.write_runner.failed",
                    "mark_executed_must_be_false_on_failure": True,
                },
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_enablement_receipt": {
                "stage": "owner_approved_write_runner_runtime_enablement_receipt",
                "receipt_status": "ready_but_disabled",
                "receipt_type": "sdk_write_runner_runtime_enablement_readiness",
                "receipt_schema": {"runtime_flag_name": "XAGENT_SDK_WRITE_RUNNER_ENABLED"},
                "review_readback": {
                    "query_keys": ["readiness_receipt_id", "approval_id", "owner_acceptance_id"]
                },
                "owner_review_policy": {"requires_expiry": True},
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_implementation_preflight": {
                "stage": "owner_approved_write_runner_runtime_implementation_preflight",
                "preflight_status": "ready_but_disabled",
                "adapter_module_boundary": {
                    "module": "backend.app.core.agent.coordinator",
                    "callable": "AgentCoordinator.run",
                    "import_allowed": False,
                },
                "dependency_injection_contract": {"required": True, "default_factory_enabled": False},
                "idempotency_lock_contract": {"required": True, "lock_enabled": False},
                "receipt_persistence_interface": {"required": True, "persistence_enabled": False},
                "approval_postcondition_contract": {"mark_executed_enabled": False},
                "failure_handling_contract": {"mark_executed_on_failure": False},
                "implementation_enabled": False,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_enablement_owner_pack": {
                "stage": "runtime_enablement_owner_acceptance_pack",
                "pack_status": "ready_but_disabled",
                "pack_type": "sdk_write_runner_runtime_enablement_owner_review_pack",
                "readback_contract": {
                    "query_keys": [
                        "readiness_receipt_id",
                        "approval_id",
                        "owner_acceptance_id",
                        "audit_id",
                    ]
                },
                "owner_decision_policy": {
                    "manual_review_required": True,
                    "can_enable_runtime_flag_after_pack": False,
                },
                "audit_contract": {"audit_event_recorded_now": False},
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_implementation_readiness_lock_workflow": {
                "stage": "runtime_implementation_readiness_lock_record_workflow",
                "workflow_status": "ready_but_disabled",
                "requires_accepted_owner_pack_decision": True,
                "requires_idempotency_key": True,
                "requires_idempotency_hash": True,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_implementation_owner_pack": {
                "stage": "runtime_implementation_owner_acceptance_pack",
                "pack_status": "ready_but_disabled",
                "pack_type": "sdk_write_runner_runtime_implementation_owner_review_pack",
                "readback_contract": {
                    "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
                    "query_keys": [
                        "implementation_lock_id",
                        "approval_id",
                        "readiness_receipt_id",
                        "owner_pack_decision_id",
                        "audit_id",
                    ],
                },
                "owner_decision_policy": {
                    "can_enable_runtime_flag_after_pack": False,
                    "can_invoke_write_runner_after_pack": False,
                },
                "implementation_enabled": False,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
            "runtime_implementation_final_decision_workflow": {
                "stage": "runtime_implementation_final_decision_record_workflow",
                "workflow_status": "ready_but_disabled",
                "endpoint": "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record",
                "audit_action": "sdk.write_runner.runtime_implementation_final_decision_recorded",
                "decision_effect": {
                    "enables_runtime_flag": False,
                    "starts_agent_execution": False,
                    "marks_approval_executed": False,
                },
                "next_gate": "owner_explicit_runtime_flag_enablement_and_live_runner_implementation",
                "implementation_enabled": False,
                "runtime_flag_enabled": False,
                "write_runner_enabled": False,
                "agent_execution_enabled": False,
                "runner_invoked": False,
                "mark_executed": False,
                "mutation_performed": False,
            },
        },
        "control_plane": {
            "ok": False,
            "error": {"code": "adapter_pending"},
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "turn-run",
                "thread-1",
                "next instruction",
                "--execute",
                "--approved-approval-id",
                "approval-1",
                "--idempotency-key",
                "idem-2",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    assert payload["sdk"]["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    assert payload["sdk"]["method"] == "turn/start"
    assert payload["sdk"]["dry_run"] is False
    assert payload["sdk"]["adapter_execution_enabled"] is False
    assert payload["sdk"]["mutation_performed"] is False
    assert payload["sdk"]["approval_intent"]["created"] is True
    assert payload["sdk"]["approval_intent"]["status"] == "pending"
    assert payload["sdk"]["approval_handoff"]["available"] is True
    assert payload["sdk"]["approval_handoff"]["next_commands"][0] == "xagent approvals show approval-1"
    assert payload["sdk"]["approval_handoff"]["execute_disabled"] is True
    assert payload["sdk"]["approval_handoff"]["mark_executed"] is False
    assert payload["sdk"]["approval_handoff"]["network_mutation_performed"] is False
    assert payload["sdk"]["execution_adapter_contract"]["preflight_status"] == "approved_ready"
    assert payload["sdk"]["execution_adapter_contract"]["ready_for_owner_approved_adapter"] is True
    assert payload["sdk"]["execution_adapter_contract"]["adapter_execution_enabled"] is False
    assert payload["sdk"]["read_only_runner_contract"]["available"] is False
    assert payload["sdk"]["read_only_runner_contract"]["write_execution_enabled"] is False
    assert payload["sdk"]["write_runner_safety_contract"]["ready_for_runner_contract"] is True
    assert payload["sdk"]["write_runner_safety_contract"]["runner_invoked"] is False
    assert payload["sdk"]["write_runner_safety_contract"]["mark_executed"] is False
    assert payload["sdk"]["dry_run_executor_stub"]["audit_event_recorded"] is True
    assert payload["sdk"]["dry_run_executor_stub"]["runner_invoked"] is False
    assert payload["sdk"]["dry_run_executor_stub"]["mutation_performed"] is False
    assert payload["sdk"]["write_runner_execute_gate"]["gate_status"] == "ready_but_disabled"
    assert payload["sdk"]["write_runner_execute_gate"]["execute_enabled"] is False
    assert payload["sdk"]["write_runner_execute_gate"]["write_runner_enabled"] is False
    assert payload["sdk"]["write_runner_execute_gate"]["agent_execution_enabled"] is False
    assert payload["sdk"]["write_runner_execute_gate"]["mutation_performed"] is False
    assert payload["sdk"]["write_runner_adapter_review"]["review_status"] == "ready_but_disabled"
    assert payload["sdk"]["write_runner_adapter_review"]["adapter_target"]["callable"] == "AgentCoordinator.run"
    assert payload["sdk"]["write_runner_adapter_review"]["implementation_enabled"] is False
    assert payload["sdk"]["write_runner_adapter_review"]["mark_executed"] is False
    assert payload["sdk"]["write_runner_adapter_review"]["mutation_performed"] is False
    assert payload["sdk"]["write_runner_runtime_flag"]["runtime_flag_enabled"] is False
    assert payload["sdk"]["write_runner_runtime_flag"]["write_runner_enabled"] is False
    assert payload["sdk"]["owner_acceptance_evidence"]["evidence_status"] == "recording_contract_ready_not_provided"
    assert payload["sdk"]["owner_acceptance_evidence"]["recording_contract_ready"] is True
    assert payload["sdk"]["owner_acceptance_evidence"]["recording_contract"]["created_by_sdk_invoke"] is False
    assert payload["sdk"]["owner_acceptance_evidence"]["execute_enabled"] is False
    assert payload["sdk"]["owner_acceptance_evidence"]["mutation_performed"] is False
    assert payload["sdk"]["runtime_enablement_review"]["review_status"] == "ready_but_disabled"
    assert payload["sdk"]["runtime_enablement_review"]["runtime_flag_enabled"] is False
    assert payload["sdk"]["runtime_enablement_review"]["write_runner_enabled"] is False
    assert payload["sdk"]["runtime_enablement_review"]["agent_execution_enabled"] is False
    assert payload["sdk"]["runtime_enablement_review"]["mutation_performed"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["plan_status"] == "ready_but_disabled"
    assert (
        payload["sdk"]["write_runner_implementation_plan"]["adapter_target"]["callable"]
        == "AgentCoordinator.run"
    )
    assert payload["sdk"]["write_runner_implementation_plan"]["idempotency_contract"]["required"] is True
    assert payload["sdk"]["write_runner_implementation_plan"]["rollback_plan"]["disable_runtime_flag"] is True
    assert payload["sdk"]["write_runner_implementation_plan"]["implementation_enabled"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["runtime_flag_enabled"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["write_runner_enabled"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["agent_execution_enabled"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["runner_invoked"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["mark_executed"] is False
    assert payload["sdk"]["write_runner_implementation_plan"]["mutation_performed"] is False
    assert payload["sdk"]["runtime_smoke_runbook"]["contract_status"] == "ready_but_disabled"
    assert (
        payload["sdk"]["runtime_smoke_runbook"]["smoke_plan"]["requires_runtime_flag"]
        == "XAGENT_SDK_WRITE_RUNNER_ENABLED=true"
    )
    assert payload["sdk"]["runtime_smoke_runbook"]["rollback_plan"]["failure_receipt_required"] is True
    assert payload["sdk"]["runtime_smoke_runbook"]["write_runner_enabled"] is False
    assert payload["sdk"]["runtime_smoke_runbook"]["agent_execution_enabled"] is False
    assert payload["sdk"]["runtime_smoke_runbook"]["runner_invoked"] is False
    assert payload["sdk"]["runtime_smoke_runbook"]["mark_executed"] is False
    assert payload["sdk"]["runtime_smoke_runbook"]["mutation_performed"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["receipt_status"] == "ready_but_disabled"
    assert payload["sdk"]["runtime_enablement_receipt"]["receipt_type"] == "sdk_write_runner_runtime_enablement_readiness"
    assert (
        payload["sdk"]["runtime_enablement_receipt"]["receipt_schema"]["runtime_flag_name"]
        == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    )
    assert payload["sdk"]["runtime_enablement_receipt"]["owner_review_policy"]["requires_expiry"] is True
    assert payload["sdk"]["runtime_enablement_receipt"]["runtime_flag_enabled"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["write_runner_enabled"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["agent_execution_enabled"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["runner_invoked"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["mark_executed"] is False
    assert payload["sdk"]["runtime_enablement_receipt"]["mutation_performed"] is False
    preflight = payload["sdk"]["runtime_implementation_preflight"]
    assert preflight["preflight_status"] == "ready_but_disabled"
    assert preflight["adapter_module_boundary"]["module"] == "backend.app.core.agent.coordinator"
    assert preflight["adapter_module_boundary"]["callable"] == "AgentCoordinator.run"
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
    owner_pack = payload["sdk"]["runtime_enablement_owner_pack"]
    assert owner_pack["pack_status"] == "ready_but_disabled"
    assert owner_pack["pack_type"] == "sdk_write_runner_runtime_enablement_owner_review_pack"
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
    readiness_lock = payload["sdk"]["runtime_implementation_readiness_lock_workflow"]
    assert readiness_lock["workflow_status"] == "ready_but_disabled"
    assert readiness_lock["requires_accepted_owner_pack_decision"] is True
    assert readiness_lock["requires_idempotency_key"] is True
    assert readiness_lock["requires_idempotency_hash"] is True
    assert readiness_lock["write_runner_enabled"] is False
    assert readiness_lock["runner_invoked"] is False
    assert readiness_lock["mutation_performed"] is False
    implementation_pack = payload["sdk"]["runtime_implementation_owner_pack"]
    assert implementation_pack["pack_status"] == "ready_but_disabled"
    assert (
        implementation_pack["readback_contract"]["evidence_type"]
        == "sdk_write_runner_runtime_implementation_readiness_lock"
    )
    assert implementation_pack["owner_decision_policy"]["can_enable_runtime_flag_after_pack"] is False
    assert implementation_pack["owner_decision_policy"]["can_invoke_write_runner_after_pack"] is False
    assert implementation_pack["write_runner_enabled"] is False
    assert implementation_pack["runner_invoked"] is False
    assert implementation_pack["mutation_performed"] is False
    final_decision = payload["sdk"]["runtime_implementation_final_decision_workflow"]
    assert final_decision["workflow_status"] == "ready_but_disabled"
    assert final_decision["endpoint"] == "/api/v1/control-plane/sdk/runtime-implementation/final-decision/record"
    assert final_decision["audit_action"] == "sdk.write_runner.runtime_implementation_final_decision_recorded"
    assert final_decision["decision_effect"]["enables_runtime_flag"] is False
    assert final_decision["decision_effect"]["starts_agent_execution"] is False
    assert final_decision["decision_effect"]["marks_approval_executed"] is False
    assert final_decision["next_gate"] == "owner_explicit_runtime_flag_enablement_and_live_runner_implementation"
    assert final_decision["implementation_enabled"] is False
    assert final_decision["runtime_flag_enabled"] is False
    assert final_decision["write_runner_enabled"] is False
    assert final_decision["agent_execution_enabled"] is False
    assert final_decision["runner_invoked"] is False
    assert final_decision["mark_executed"] is False
    assert final_decision["mutation_performed"] is False
    assert payload["control_plane"]["error"]["code"] == "adapter_pending"

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "turn_start"
    assert contract["approved_approval_id"] == "approval-1"
    assert contract["owner_approved"] is True
    assert contract["request"]["dry_run"] is False
    assert contract["request"]["idempotency_key"] == "idem-2"
    assert contract["request"]["mutation_performed"] is False


def test_cli_sdk_thread_read_execute_flag_calls_read_only_runner_contract() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "thread/read",
            "read_only_runner_contract": {
                "available": True,
                "read_only_runner_enabled": True,
                "agent_execution_enabled": False,
                "write_execution_enabled": False,
                "mutation_performed": False,
            },
        },
        "control_plane": {
            "ok": True,
            "result": {"thread": {"status": "not_found", "thread_id": "thread-1"}},
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(app, ["sdk", "thread-read", "thread-1", "--execute"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    assert payload["sdk"]["method"] == "thread/read"
    assert payload["sdk"]["read_only_runner_contract"]["available"] is True
    assert payload["sdk"]["read_only_runner_contract"]["agent_execution_enabled"] is False
    assert payload["sdk"]["read_only_runner_contract"]["write_execution_enabled"] is False
    assert payload["control_plane"]["ok"] is True

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "thread_read"
    assert contract["request"]["method"] == "thread/read"
    assert contract["request"]["dry_run"] is True
    assert contract["owner_gate"]["read_only_runner_contract"] is True


def test_cli_sdk_evidence_read_execute_flag_supports_dry_run_receipt_readback() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "runtime/evidence/read",
            "read_only_runner_contract": {"available": True, "read_only_runner_enabled": True},
        },
        "control_plane": {
            "ok": True,
            "result": {
                "evidence": {
                    "evidence_type": "sdk_dry_run_executor_stub",
                    "available": True,
                    "receipt_schema": {"status": "dry_run_planned"},
                }
            },
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "evidence-read",
                "sdk-dry-run-executor-stub.json",
                "--evidence-type",
                "sdk_dry_run_executor_stub",
                "--approval-id",
                "approval-1",
                "--method",
                "turn/start",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    assert payload["control_plane"]["result"]["evidence"]["evidence_type"] == "sdk_dry_run_executor_stub"

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "runtime_evidence_read"
    assert contract["request"]["params"]["evidence_type"] == "sdk_dry_run_executor_stub"
    assert contract["request"]["params"]["approval_id"] == "approval-1"
    assert contract["request"]["params"]["method"] == "turn/start"


def test_cli_sdk_evidence_read_execute_flag_supports_owner_acceptance_readback() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "runtime/evidence/read",
            "read_only_runner_contract": {"available": True, "read_only_runner_enabled": True},
        },
        "control_plane": {
            "ok": True,
            "result": {
                "evidence": {
                    "evidence_type": "sdk_write_runner_owner_acceptance",
                    "acceptance_record_present": False,
                    "recording_contract_ready": True,
                    "safety": {"write_runner_enabled": False, "mutation_performed": False},
                }
            },
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "evidence-read",
                "sdk-write-runner-owner-acceptance.json",
                "--evidence-type",
                "sdk_write_runner_owner_acceptance",
                "--approval-id",
                "approval-1",
                "--acceptance-id",
                "acceptance-1",
                "--audit-id",
                "audit-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert evidence["acceptance_record_present"] is False
    assert evidence["safety"]["write_runner_enabled"] is False

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "runtime_evidence_read"
    assert contract["request"]["params"]["evidence_type"] == "sdk_write_runner_owner_acceptance"
    assert contract["request"]["params"]["approval_id"] == "approval-1"
    assert contract["request"]["params"]["owner_acceptance_id"] == "acceptance-1"
    assert contract["request"]["params"]["audit_id"] == "audit-1"


def test_cli_sdk_evidence_read_execute_flag_supports_runtime_enablement_readiness_readback() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "runtime/evidence/read",
            "read_only_runner_contract": {"available": True, "read_only_runner_enabled": True},
        },
        "control_plane": {
            "ok": True,
            "result": {
                "evidence": {
                    "evidence_type": "sdk_write_runner_runtime_enablement_readiness",
                    "readiness_receipt_present": False,
                    "safety": {"write_runner_enabled": False},
                }
            },
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "evidence-read",
                "sdk-write-runner-runtime-enable-readiness.json",
                "--evidence-type",
                "sdk_write_runner_runtime_enablement_readiness",
                "--readiness-receipt-id",
                "readiness-1",
                "--approval-id",
                "approval-1",
                "--acceptance-id",
                "acceptance-1",
                "--audit-id",
                "audit-readiness-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_write_runner_runtime_enablement_readiness"
    assert evidence["readiness_receipt_present"] is False

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "runtime_evidence_read"
    assert (
        contract["request"]["params"]["evidence_type"]
        == "sdk_write_runner_runtime_enablement_readiness"
    )
    assert contract["request"]["params"]["readiness_receipt_id"] == "readiness-1"
    assert contract["request"]["params"]["owner_acceptance_id"] == "acceptance-1"
    assert contract["request"]["params"]["audit_id"] == "audit-readiness-1"


def test_cli_sdk_evidence_read_execute_flag_supports_runtime_implementation_lock_readback() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.invoke_sdk_contract.return_value = {
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "sdk": {
            "status": "sdk_runtime_implementation_final_decision_workflow_ready",
            "method": "runtime/evidence/read",
            "read_only_runner_contract": {"available": True, "read_only_runner_enabled": True},
        },
        "control_plane": {
            "ok": True,
            "result": {
                "evidence": {
                    "evidence_type": "sdk_write_runner_runtime_implementation_readiness_lock",
                    "implementation_lock_present": False,
                    "safety": {"write_runner_enabled": False},
                }
            },
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "evidence-read",
                "sdk-write-runner-runtime-implementation-readiness-lock.json",
                "--evidence-type",
                "sdk_write_runner_runtime_implementation_readiness_lock",
                "--implementation-lock-id",
                "lock-1",
                "--approval-id",
                "approval-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--decision-id",
                "decision-1",
                "--audit-id",
                "audit-lock-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    evidence = payload["control_plane"]["result"]["evidence"]
    assert evidence["evidence_type"] == "sdk_write_runner_runtime_implementation_readiness_lock"
    assert evidence["implementation_lock_present"] is False

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "runtime_evidence_read"
    assert (
        contract["request"]["params"]["evidence_type"]
        == "sdk_write_runner_runtime_implementation_readiness_lock"
    )
    assert contract["request"]["params"]["implementation_lock_id"] == "lock-1"
    assert contract["request"]["params"]["readiness_receipt_id"] == "readiness-1"
    assert contract["request"]["params"]["owner_pack_decision_id"] == "decision-1"
    assert contract["request"]["params"]["audit_id"] == "audit-lock-1"


def test_cli_sdk_acceptance_record_execute_flag_records_owner_evidence_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_owner_acceptance.return_value = {
        "ok": True,
        "status": "sdk_owner_acceptance_record_workflow_ready",
        "owner_acceptance": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "acceptance-record",
                "--approval-id",
                "approval-1",
                "--acceptance-id",
                "acceptance-1",
                "--accepted-by",
                "owner",
                "--accepted-at",
                "2026-06-08T00:00:00Z",
                "--acceptance-hash",
                "hash-1",
                "--runbook-acknowledged",
                "--rollback-plan-acknowledged",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_owner_acceptance_record_workflow_ready"
    assert payload["owner_acceptance"]["record_status"] == "recorded"
    assert payload["owner_acceptance"]["write_runner_enabled"] is False
    assert payload["owner_acceptance"]["mutation_performed"] is False

    mock_client.record_sdk_owner_acceptance.assert_awaited_once()
    request = mock_client.record_sdk_owner_acceptance.await_args.args[0]
    assert request["approval_id"] == "approval-1"
    assert request["owner_acceptance_id"] == "acceptance-1"
    assert request["acceptance_hash"] == "hash-1"
    assert request["runbook_acknowledged"] is True
    assert request["rollback_plan_acknowledged"] is True
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_enablement_receipt_record_execute_flag_records_receipt_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_enablement_receipt.return_value = {
        "ok": True,
        "status": "sdk_runtime_enablement_receipt_record_workflow_ready",
        "runtime_enablement_receipt": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-enable-receipt-record",
                "--approval-id",
                "approval-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--acceptance-id",
                "acceptance-1",
                "--acceptance-audit-id",
                "audit-acceptance-1",
                "--accepted-by",
                "owner",
                "--accepted-at",
                "2026-06-08T00:00:00Z",
                "--expires-at",
                "2026-06-09T00:00:00Z",
                "--smoke-runbook-version",
                "v1",
                "--rollback-runbook-version",
                "v1",
                "--smoke-runbook-acknowledged",
                "--rollback-runbook-acknowledged",
                "--failure-receipt-reviewed",
                "--acceptance-hash",
                "hash-readiness-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_enablement_receipt_record_workflow_ready"
    assert payload["runtime_enablement_receipt"]["record_status"] == "recorded"
    assert payload["runtime_enablement_receipt"]["write_runner_enabled"] is False
    assert payload["runtime_enablement_receipt"]["runner_invoked"] is False
    assert payload["runtime_enablement_receipt"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_enablement_receipt.assert_awaited_once()
    request = mock_client.record_sdk_runtime_enablement_receipt.await_args.args[0]
    assert request["approval_id"] == "approval-1"
    assert request["readiness_receipt_id"] == "readiness-1"
    assert request["owner_acceptance_id"] == "acceptance-1"
    assert request["owner_acceptance_audit_id"] == "audit-acceptance-1"
    assert request["smoke_runbook_acknowledged"] is True
    assert request["rollback_runbook_acknowledged"] is True
    assert request["failure_receipt_reviewed"] is True
    assert request["acceptance_hash"] == "hash-readiness-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_enablement_owner_pack_decision_execute_flag_records_decision_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_enablement_owner_pack_decision.return_value = {
        "ok": True,
        "status": "sdk_runtime_enablement_owner_pack_decision_workflow_ready",
        "owner_pack_decision": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "decision": "accepted",
            "runtime_flag_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-enable-owner-pack-decision-record",
                "--decision-id",
                "decision-1",
                "--decision",
                "accepted",
                "--approval-id",
                "approval-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--readiness-receipt-audit-id",
                "audit-readiness-1",
                "--acceptance-id",
                "acceptance-1",
                "--acceptance-audit-id",
                "audit-acceptance-1",
                "--decided-by",
                "owner",
                "--decided-at",
                "2026-06-08T00:00:00Z",
                "--reason",
                "owner accepted pack",
                "--decision-hash",
                "hash-decision-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_enablement_owner_pack_decision_workflow_ready"
    assert payload["owner_pack_decision"]["record_status"] == "recorded"
    assert payload["owner_pack_decision"]["write_runner_enabled"] is False
    assert payload["owner_pack_decision"]["runner_invoked"] is False
    assert payload["owner_pack_decision"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_enablement_owner_pack_decision.assert_awaited_once()
    request = mock_client.record_sdk_runtime_enablement_owner_pack_decision.await_args.args[0]
    assert request["owner_pack_decision_id"] == "decision-1"
    assert request["decision"] == "accepted"
    assert request["approval_id"] == "approval-1"
    assert request["readiness_receipt_id"] == "readiness-1"
    assert request["readiness_receipt_audit_id"] == "audit-readiness-1"
    assert request["owner_acceptance_id"] == "acceptance-1"
    assert request["owner_acceptance_audit_id"] == "audit-acceptance-1"
    assert request["decision_hash"] == "hash-decision-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_implementation_readiness_lock_execute_flag_records_lock_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_implementation_readiness_lock.return_value = {
        "ok": True,
        "status": "sdk_runtime_implementation_readiness_lock_workflow_ready",
        "readiness_lock": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-implementation-readiness-lock-record",
                "--implementation-lock-id",
                "lock-1",
                "--idempotency-key",
                "sdk-write-runner-lock-1",
                "--idempotency-hash",
                "hash-idempotency-1",
                "--approval-id",
                "approval-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--readiness-receipt-audit-id",
                "audit-readiness-1",
                "--decision-id",
                "decision-1",
                "--decision-audit-id",
                "audit-decision-1",
                "--operator-id",
                "operator",
                "--locked-at",
                "2026-06-08T00:00:00Z",
                "--lock-reason",
                "owner accepted readiness lock",
                "--lock-hash",
                "hash-lock-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_readiness_lock_workflow_ready"
    assert payload["readiness_lock"]["record_status"] == "recorded"
    assert payload["readiness_lock"]["write_runner_enabled"] is False
    assert payload["readiness_lock"]["runner_invoked"] is False
    assert payload["readiness_lock"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_implementation_readiness_lock.assert_awaited_once()
    request = mock_client.record_sdk_runtime_implementation_readiness_lock.await_args.args[0]
    assert request["implementation_lock_id"] == "lock-1"
    assert request["idempotency_key"] == "sdk-write-runner-lock-1"
    assert request["idempotency_hash"] == "hash-idempotency-1"
    assert request["approval_id"] == "approval-1"
    assert request["readiness_receipt_id"] == "readiness-1"
    assert request["readiness_receipt_audit_id"] == "audit-readiness-1"
    assert request["owner_pack_decision_id"] == "decision-1"
    assert request["owner_pack_decision_audit_id"] == "audit-decision-1"
    assert request["lock_hash"] == "hash-lock-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_implementation_final_decision_execute_flag_records_decision_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_implementation_final_decision.return_value = {
        "ok": True,
        "status": "sdk_runtime_implementation_final_decision_workflow_ready",
        "final_decision": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "implementation_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-implementation-final-decision-record",
                "--final-decision-id",
                "final-decision-1",
                "--decision",
                "accepted",
                "--approval-id",
                "approval-1",
                "--implementation-lock-id",
                "lock-1",
                "--implementation-lock-audit-id",
                "audit-lock-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--decision-id",
                "decision-1",
                "--decided-by",
                "owner",
                "--decided-at",
                "2026-06-08T00:00:00Z",
                "--reason",
                "owner accepted final decision",
                "--decision-hash",
                "hash-final-decision-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_implementation_final_decision_workflow_ready"
    assert payload["final_decision"]["record_status"] == "recorded"
    assert payload["final_decision"]["runtime_flag_enabled"] is False
    assert payload["final_decision"]["write_runner_enabled"] is False
    assert payload["final_decision"]["runner_invoked"] is False
    assert payload["final_decision"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_implementation_final_decision.assert_awaited_once()
    request = mock_client.record_sdk_runtime_implementation_final_decision.await_args.args[0]
    assert request["final_decision_id"] == "final-decision-1"
    assert request["decision"] == "accepted"
    assert request["approval_id"] == "approval-1"
    assert request["implementation_lock_id"] == "lock-1"
    assert request["implementation_lock_audit_id"] == "audit-lock-1"
    assert request["readiness_receipt_id"] == "readiness-1"
    assert request["owner_pack_decision_id"] == "decision-1"
    assert request["decision_hash"] == "hash-final-decision-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_enable_execute_flag_records_intent_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_enablement.return_value = {
        "ok": True,
        "status": "sdk_runtime_flag_enablement_record_workflow_ready",
        "runtime_flag_enablement": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "implementation_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-enable-record",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--approval-id",
                "approval-1",
                "--final-decision-id",
                "final-decision-1",
                "--final-decision-audit-id",
                "audit-final-decision-1",
                "--implementation-lock-id",
                "lock-1",
                "--readiness-receipt-id",
                "readiness-1",
                "--requested-by",
                "owner",
                "--requested-at",
                "2026-06-08T00:00:00Z",
                "--enablement-reason",
                "owner requested runtime flag enablement",
                "--enablement-hash",
                "hash-flag-enable-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_flag_enablement_record_workflow_ready"
    assert payload["runtime_flag_enablement"]["record_status"] == "recorded"
    assert payload["runtime_flag_enablement"]["runtime_flag_enabled"] is False
    assert payload["runtime_flag_enablement"]["write_runner_enabled"] is False
    assert payload["runtime_flag_enablement"]["runner_invoked"] is False
    assert payload["runtime_flag_enablement"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_flag_enablement.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_enablement.await_args.args[0]
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["approval_id"] == "approval-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["final_decision_audit_id"] == "audit-final-decision-1"
    assert request["implementation_lock_id"] == "lock-1"
    assert request["readiness_receipt_id"] == "readiness-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["enablement_hash"] == "hash-flag-enable-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_preflight_execute_flag_records_preflight_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_preflight.return_value = {
        "ok": True,
        "status": "sdk_runtime_flag_application_preflight_workflow_ready",
        "runtime_flag_preflight": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-preflight-record",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--approval-id",
                "approval-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--runtime-flag-enablement-audit-id",
                "audit-flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--requested-by",
                "owner",
                "--requested-at",
                "2026-06-08T00:00:00Z",
                "--preflight-reason",
                "owner requested runtime flag application preflight",
                "--rollback-plan-ref",
                "runbooks/sdk-write-runner-rollback.md",
                "--smoke-runbook-ref",
                "runbooks/sdk-write-runner-smoke.md",
                "--preflight-hash",
                "hash-flag-preflight-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_flag_application_preflight_workflow_ready"
    assert payload["runtime_flag_preflight"]["record_status"] == "recorded"
    assert payload["runtime_flag_preflight"]["runtime_flag_enabled"] is False
    assert payload["runtime_flag_preflight"]["flag_application_performed"] is False
    assert payload["runtime_flag_preflight"]["write_runner_enabled"] is False
    assert payload["runtime_flag_preflight"]["runner_invoked"] is False
    assert payload["runtime_flag_preflight"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_flag_application_preflight.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_preflight.await_args.args[0]
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["approval_id"] == "approval-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["runtime_flag_enablement_audit_id"] == "audit-flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["target_state"] == "enabled"
    assert request["preflight_hash"] == "hash-flag-preflight-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_sdk_runtime_flag_application_owner_approval_contract_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_owner_approval(
        runtime_flag_approval_id="flag-approval-1",
        approval_id="approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_preflight_audit_id="audit-flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        decision="accepted",
        decided_by="owner",
        decided_at="2026-06-08T00:00:00Z",
        approval_reason="owner approved runtime flag application preflight",
        approval_hash="hash-flag-approval-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_owner_approval_record"
    assert payload["endpoint"] == "/api/v1/control-plane/sdk/runtime-flag/application-approval/record"
    assert payload["request"]["runtime_flag_approval_id"] == "flag-approval-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert payload["request"]["runtime_flag_preflight_audit_id"] == "audit-flag-preflight-1"
    assert payload["request"]["runtime_flag_enablement_id"] == "flag-enable-1"
    assert payload["request"]["decision"] == "accepted"
    assert payload["request"]["approval_hash"] == "hash-flag-approval-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_runtime_flag_application_preflight"] is True
    assert payload["owner_gate"]["requires_decision_accept_or_reject"] is True
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_sdk_runtime_flag_application_execute_contract_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_execute_contract(
        runtime_flag_execute_contract_id="flag-execute-contract-1",
        approval_id="approval-1",
        runtime_flag_approval_id="flag-approval-1",
        runtime_flag_approval_audit_id="audit-flag-approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        operator_id="operator",
        locked_at="2026-06-08T00:00:00Z",
        execute_contract_reason="owner requested live runtime flag application contract",
        idempotency_key="idem-flag-execute-1",
        idempotency_hash="hash-idem-flag-execute-1",
        rollback_plan_ref="runbooks/sdk-write-runner-rollback.md",
        smoke_runbook_ref="runbooks/sdk-write-runner-smoke.md",
        execute_contract_hash="hash-flag-execute-contract-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_execute_contract_record"
    assert payload["endpoint"] == "/api/v1/control-plane/sdk/runtime-flag/application-execute-contract/record"
    assert payload["request"]["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["runtime_flag_approval_id"] == "flag-approval-1"
    assert payload["request"]["runtime_flag_approval_audit_id"] == "audit-flag-approval-1"
    assert payload["request"]["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert payload["request"]["runtime_flag_enablement_id"] == "flag-enable-1"
    assert payload["request"]["final_decision_id"] == "final-decision-1"
    assert payload["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["request"]["idempotency_key"] == "idem-flag-execute-1"
    assert payload["request"]["idempotency_hash"] == "hash-idem-flag-execute-1"
    assert payload["request"]["execute_contract_hash"] == "hash-flag-execute-contract-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_runtime_flag_application_owner_approval"] is True
    assert payload["owner_gate"]["requires_owner_approval_decision"] == "accepted"
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_idempotency_key"] is True
    assert payload["owner_gate"]["requires_idempotency_hash"] is True
    assert payload["owner_gate"]["requires_rollback_plan"] is True
    assert payload["owner_gate"]["requires_smoke_runbook"] is True
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["execute_enabled"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["owner_gate"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["file_mutation_performed"] is False
    assert payload["owner_gate"]["channel_mutation_performed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_sdk_runtime_flag_application_readiness_plan_decision_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_readiness_plan_decision(
        readiness_plan_decision_id="readiness-plan-decision-1",
        approval_id="approval-1",
        runtime_flag_execute_contract_id="flag-execute-contract-1",
        runtime_flag_execute_contract_audit_id="audit-flag-execute-contract-1",
        runtime_flag_approval_id="flag-approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        decision="accepted",
        decided_by="owner",
        decided_at="2026-06-08T00:00:00Z",
        reason="owner accepted readiness plan",
        decision_hash="hash-readiness-plan-decision-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_readiness_plan_decision_record"
    assert payload["endpoint"] == (
        "/api/v1/control-plane/sdk/runtime-flag/application-readiness-plan/decision/record"
    )
    assert payload["request"]["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert payload["request"]["runtime_flag_execute_contract_audit_id"] == "audit-flag-execute-contract-1"
    assert payload["request"]["runtime_flag_approval_id"] == "flag-approval-1"
    assert payload["request"]["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert payload["request"]["runtime_flag_enablement_id"] == "flag-enable-1"
    assert payload["request"]["final_decision_id"] == "final-decision-1"
    assert payload["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["request"]["decision"] == "accepted"
    assert payload["request"]["decision_hash"] == "hash-readiness-plan-decision-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_runtime_flag_application_execute_contract"] is True
    assert payload["owner_gate"]["requires_readiness_plan_review"] is True
    assert payload["owner_gate"]["requires_decision_accept_or_reject"] is True
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["implementation_enabled"] is False
    assert payload["owner_gate"]["execute_enabled"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["owner_gate"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["file_mutation_performed"] is False
    assert payload["owner_gate"]["channel_mutation_performed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_sdk_runtime_flag_application_adapter_implementation_request_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_adapter_implementation_request(
        adapter_implementation_request_id="adapter-implementation-request-1",
        approval_id="approval-1",
        readiness_plan_decision_id="readiness-plan-decision-1",
        readiness_plan_decision_audit_id="audit-readiness-plan-decision-1",
        runtime_flag_execute_contract_id="flag-execute-contract-1",
        runtime_flag_approval_id="flag-approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        requested_by="owner",
        requested_at="2026-06-08T00:00:00Z",
        implementation_request_reason="owner explicitly requested adapter implementation",
        adapter_design_ref="docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
        rollback_plan_ref="docs/runbooks/sdk-write-runner-rollback.md",
        smoke_runbook_ref="docs/runbooks/sdk-write-runner-smoke.md",
        request_hash="hash-adapter-implementation-request-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_adapter_implementation_request_record"
    assert payload["endpoint"] == (
        "/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-request/record"
    )
    assert payload["request"]["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert payload["request"]["readiness_plan_decision_audit_id"] == "audit-readiness-plan-decision-1"
    assert payload["request"]["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert payload["request"]["runtime_flag_approval_id"] == "flag-approval-1"
    assert payload["request"]["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert payload["request"]["runtime_flag_enablement_id"] == "flag-enable-1"
    assert payload["request"]["final_decision_id"] == "final-decision-1"
    assert payload["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["request"]["adapter_design_ref"] == (
        "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md"
    )
    assert payload["request"]["rollback_plan_ref"] == "docs/runbooks/sdk-write-runner-rollback.md"
    assert payload["request"]["smoke_runbook_ref"] == "docs/runbooks/sdk-write-runner-smoke.md"
    assert payload["request"]["request_hash"] == "hash-adapter-implementation-request-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_accepted_readiness_plan_decision"] is True
    assert payload["owner_gate"]["requires_readiness_plan_decision_audit"] is True
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_adapter_design_ref"] is True
    assert payload["owner_gate"]["requires_rollback_plan_ref"] is True
    assert payload["owner_gate"]["requires_smoke_runbook_ref"] is True
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["implementation_enabled"] is False
    assert payload["owner_gate"]["execute_enabled"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["owner_gate"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["file_mutation_performed"] is False
    assert payload["owner_gate"]["channel_mutation_performed"] is False
    assert payload["owner_gate"]["runtime_flag_writer_enabled"] is False
    assert payload["owner_gate"]["adapter_import_allowed"] is False
    assert payload["owner_gate"]["adapter_execution_allowed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_sdk_runtime_flag_application_adapter_design_review_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_adapter_design_review(
        adapter_design_review_id="adapter-design-review-1",
        approval_id="approval-1",
        adapter_implementation_request_id="adapter-implementation-request-1",
        adapter_implementation_request_audit_id="audit-adapter-implementation-request-1",
        readiness_plan_decision_id="readiness-plan-decision-1",
        runtime_flag_execute_contract_id="flag-execute-contract-1",
        runtime_flag_approval_id="flag-approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        review_decision="accepted",
        reviewed_by="owner",
        reviewed_at="2026-06-08T00:00:00Z",
        review_reason="owner accepted adapter design",
        adapter_design_ref="docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
        security_review_ref="docs/security/sdk-write-runner-runtime-flag-adapter-review.md",
        test_plan_ref="tests/test_control_plane_protocol.py",
        rollback_plan_ref="docs/runbooks/sdk-write-runner-rollback.md",
        smoke_runbook_ref="docs/runbooks/sdk-write-runner-smoke.md",
        review_hash="hash-adapter-design-review-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_adapter_design_review_record"
    assert payload["endpoint"] == (
        "/api/v1/control-plane/sdk/runtime-flag/application-adapter/design-review/record"
    )
    assert payload["request"]["adapter_design_review_id"] == "adapter-design-review-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert payload["request"]["adapter_implementation_request_audit_id"] == (
        "audit-adapter-implementation-request-1"
    )
    assert payload["request"]["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert payload["request"]["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert payload["request"]["runtime_flag_approval_id"] == "flag-approval-1"
    assert payload["request"]["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert payload["request"]["runtime_flag_enablement_id"] == "flag-enable-1"
    assert payload["request"]["final_decision_id"] == "final-decision-1"
    assert payload["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["request"]["review_decision"] == "accepted"
    assert payload["request"]["security_review_ref"] == (
        "docs/security/sdk-write-runner-runtime-flag-adapter-review.md"
    )
    assert payload["request"]["test_plan_ref"] == "tests/test_control_plane_protocol.py"
    assert payload["request"]["review_hash"] == "hash-adapter-design-review-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_accepted_adapter_implementation_request"] is True
    assert payload["owner_gate"]["requires_adapter_implementation_request_audit"] is True
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_review_decision_accept_or_reject"] is True
    assert payload["owner_gate"]["requires_adapter_design_ref"] is True
    assert payload["owner_gate"]["requires_security_review_ref"] is True
    assert payload["owner_gate"]["requires_test_plan_ref"] is True
    assert payload["owner_gate"]["requires_rollback_plan_ref"] is True
    assert payload["owner_gate"]["requires_smoke_runbook_ref"] is True
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["implementation_enabled"] is False
    assert payload["owner_gate"]["execute_enabled"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["owner_gate"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["file_mutation_performed"] is False
    assert payload["owner_gate"]["channel_mutation_performed"] is False
    assert payload["owner_gate"]["runtime_flag_writer_enabled"] is False
    assert payload["owner_gate"]["adapter_import_allowed"] is False
    assert payload["owner_gate"]["adapter_execution_allowed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_sdk_runtime_flag_application_adapter_implementation_preflight_is_safe() -> None:
    payload = ControlPlaneSDK().record_runtime_flag_application_adapter_implementation_preflight(
        adapter_implementation_preflight_id="adapter-implementation-preflight-1",
        approval_id="approval-1",
        adapter_design_review_id="adapter-design-review-1",
        adapter_design_review_audit_id="audit-adapter-design-review-1",
        adapter_implementation_request_id="adapter-implementation-request-1",
        readiness_plan_decision_id="readiness-plan-decision-1",
        runtime_flag_execute_contract_id="flag-execute-contract-1",
        runtime_flag_approval_id="flag-approval-1",
        runtime_flag_preflight_id="flag-preflight-1",
        runtime_flag_enablement_id="flag-enable-1",
        final_decision_id="final-decision-1",
        operator_id="operator",
        locked_at="2026-06-08T00:00:00Z",
        implementation_branch_ref="codex/runtime-flag-adapter-preflight",
        implementation_plan_ref="docs/runbooks/sdk-write-runner-runtime-flag-adapter-implementation.md",
        adapter_design_ref="docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
        security_review_ref="docs/security/sdk-write-runner-runtime-flag-adapter-review.md",
        test_plan_ref="tests/test_control_plane_protocol.py",
        rollback_plan_ref="docs/runbooks/sdk-write-runner-rollback.md",
        smoke_runbook_ref="docs/runbooks/sdk-write-runner-smoke.md",
        idempotency_key="adapter-implementation-preflight-1",
        idempotency_hash="hash-idempotency-preflight-1",
        preflight_hash="hash-adapter-implementation-preflight-1",
    ).to_dict()

    assert payload["operation"] == "runtime_flag_application_adapter_implementation_preflight_record"
    assert payload["endpoint"] == (
        "/api/v1/control-plane/sdk/runtime-flag/application-adapter/implementation-preflight/record"
    )
    assert payload["request"]["adapter_implementation_preflight_id"] == "adapter-implementation-preflight-1"
    assert payload["request"]["approval_id"] == "approval-1"
    assert payload["request"]["adapter_design_review_id"] == "adapter-design-review-1"
    assert payload["request"]["adapter_design_review_audit_id"] == "audit-adapter-design-review-1"
    assert payload["request"]["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert payload["request"]["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["request"]["implementation_branch_ref"] == "codex/runtime-flag-adapter-preflight"
    assert payload["request"]["implementation_plan_ref"] == (
        "docs/runbooks/sdk-write-runner-runtime-flag-adapter-implementation.md"
    )
    assert payload["request"]["idempotency_key"] == "adapter-implementation-preflight-1"
    assert payload["request"]["idempotency_hash"] == "hash-idempotency-preflight-1"
    assert payload["request"]["preflight_hash"] == "hash-adapter-implementation-preflight-1"
    assert payload["request"]["dry_run"] is True
    assert payload["owner_gate"]["requires_approved_sdk_approval"] is True
    assert payload["owner_gate"]["requires_accepted_adapter_design_review"] is True
    assert payload["owner_gate"]["requires_adapter_design_review_audit"] is True
    assert payload["owner_gate"]["requires_runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert payload["owner_gate"]["requires_implementation_branch_ref"] is True
    assert payload["owner_gate"]["requires_implementation_plan_ref"] is True
    assert payload["owner_gate"]["requires_adapter_design_ref"] is True
    assert payload["owner_gate"]["requires_security_review_ref"] is True
    assert payload["owner_gate"]["requires_test_plan_ref"] is True
    assert payload["owner_gate"]["requires_rollback_plan_ref"] is True
    assert payload["owner_gate"]["requires_smoke_runbook_ref"] is True
    assert payload["owner_gate"]["requires_idempotency_key"] is True
    assert payload["owner_gate"]["requires_idempotency_hash"] is True
    assert payload["owner_gate"]["requires_signature_or_hash"] is True
    assert payload["owner_gate"]["runtime_flag_enabled"] is False
    assert payload["owner_gate"]["flag_application_performed"] is False
    assert payload["owner_gate"]["implementation_enabled"] is False
    assert payload["owner_gate"]["execute_enabled"] is False
    assert payload["owner_gate"]["write_runner_enabled"] is False
    assert payload["owner_gate"]["adapter_execution_enabled"] is False
    assert payload["owner_gate"]["agent_execution_enabled"] is False
    assert payload["owner_gate"]["write_execution_enabled"] is False
    assert payload["owner_gate"]["runner_invoked"] is False
    assert payload["owner_gate"]["mark_executed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
    assert payload["owner_gate"]["network_mutation_performed"] is False
    assert payload["owner_gate"]["file_mutation_performed"] is False
    assert payload["owner_gate"]["channel_mutation_performed"] is False
    assert payload["owner_gate"]["runtime_flag_writer_enabled"] is False
    assert payload["owner_gate"]["adapter_import_allowed"] is False
    assert payload["owner_gate"]["adapter_execution_allowed"] is False
    assert payload["mutation_performed"] is False
    assert payload["network_mutation_performed"] is False


def test_cli_sdk_runtime_flag_application_owner_approval_execute_flag_records_approval_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_owner_approval.return_value = {
        "ok": True,
        "status": "sdk_runtime_flag_application_owner_approval_workflow_ready",
        "runtime_flag_approval": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "write_runner_enabled": False,
            "agent_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-approval-record",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--approval-id",
                "approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-preflight-audit-id",
                "audit-flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--decision",
                "accepted",
                "--decided-by",
                "owner",
                "--decided-at",
                "2026-06-08T00:00:00Z",
                "--approval-reason",
                "owner approved runtime flag application preflight",
                "--approval-hash",
                "hash-flag-approval-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_flag_application_owner_approval_workflow_ready"
    assert payload["runtime_flag_approval"]["record_status"] == "recorded"
    assert payload["runtime_flag_approval"]["runtime_flag_enabled"] is False
    assert payload["runtime_flag_approval"]["flag_application_performed"] is False
    assert payload["runtime_flag_approval"]["write_runner_enabled"] is False
    assert payload["runtime_flag_approval"]["runner_invoked"] is False
    assert payload["runtime_flag_approval"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_flag_application_owner_approval.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_owner_approval.await_args.args[0]
    assert request["runtime_flag_approval_id"] == "flag-approval-1"
    assert request["approval_id"] == "approval-1"
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["runtime_flag_preflight_audit_id"] == "audit-flag-preflight-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["decision"] == "accepted"
    assert request["approval_hash"] == "hash-flag-approval-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_readiness_plan_decision_execute_flag_records_decision_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_readiness_plan_decision.return_value = {
        "ok": True,
        "status": "sdk_live_runtime_flag_application_readiness_plan_decision_workflow_ready",
        "readiness_plan_decision": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-readiness-plan-decision-record",
                "--readiness-plan-decision-id",
                "readiness-plan-decision-1",
                "--approval-id",
                "approval-1",
                "--runtime-flag-execute-contract-id",
                "flag-execute-contract-1",
                "--runtime-flag-execute-contract-audit-id",
                "audit-flag-execute-contract-1",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--decision",
                "accepted",
                "--decided-by",
                "owner",
                "--decided-at",
                "2026-06-08T00:00:00Z",
                "--reason",
                "owner accepted readiness plan",
                "--decision-hash",
                "hash-readiness-plan-decision-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_live_runtime_flag_application_readiness_plan_decision_workflow_ready"
    assert payload["readiness_plan_decision"]["record_status"] == "recorded"
    assert payload["readiness_plan_decision"]["runtime_flag_enabled"] is False
    assert payload["readiness_plan_decision"]["flag_application_performed"] is False
    assert payload["readiness_plan_decision"]["write_runner_enabled"] is False
    assert payload["readiness_plan_decision"]["runner_invoked"] is False
    assert payload["readiness_plan_decision"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_flag_application_readiness_plan_decision.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_readiness_plan_decision.await_args.args[0]
    assert request["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert request["approval_id"] == "approval-1"
    assert request["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert request["runtime_flag_execute_contract_audit_id"] == "audit-flag-execute-contract-1"
    assert request["runtime_flag_approval_id"] == "flag-approval-1"
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["decision"] == "accepted"
    assert request["decision_hash"] == "hash-readiness-plan-decision-1"
    assert request["dry_run"] is True
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_adapter_implementation_request_execute_flag_records_request_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_adapter_implementation_request.return_value = {
        "ok": True,
        "status": "sdk_live_runtime_flag_application_adapter_implementation_request_workflow_ready",
        "adapter_implementation_request": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "adapter_import_allowed": False,
            "adapter_execution_allowed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-adapter-implementation-request-record",
                "--adapter-implementation-request-id",
                "adapter-implementation-request-1",
                "--approval-id",
                "approval-1",
                "--readiness-plan-decision-id",
                "readiness-plan-decision-1",
                "--readiness-plan-decision-audit-id",
                "audit-readiness-plan-decision-1",
                "--runtime-flag-execute-contract-id",
                "flag-execute-contract-1",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--requested-by",
                "owner",
                "--requested-at",
                "2026-06-08T00:00:00Z",
                "--implementation-request-reason",
                "owner requested adapter implementation",
                "--adapter-design-ref",
                "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
                "--rollback-plan-ref",
                "docs/runbooks/sdk-write-runner-rollback.md",
                "--smoke-runbook-ref",
                "docs/runbooks/sdk-write-runner-smoke.md",
                "--request-hash",
                "hash-adapter-implementation-request-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == (
        "sdk_live_runtime_flag_application_adapter_implementation_request_workflow_ready"
    )
    assert payload["adapter_implementation_request"]["record_status"] == "recorded"
    assert payload["adapter_implementation_request"]["runtime_flag_enabled"] is False
    assert payload["adapter_implementation_request"]["flag_application_performed"] is False
    assert payload["adapter_implementation_request"]["implementation_enabled"] is False
    assert payload["adapter_implementation_request"]["write_runner_enabled"] is False
    assert payload["adapter_implementation_request"]["adapter_execution_enabled"] is False
    assert payload["adapter_implementation_request"]["runner_invoked"] is False
    assert payload["adapter_implementation_request"]["mutation_performed"] is False
    assert payload["adapter_implementation_request"]["adapter_import_allowed"] is False
    assert payload["adapter_implementation_request"]["adapter_execution_allowed"] is False

    mock_client.record_sdk_runtime_flag_application_adapter_implementation_request.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_adapter_implementation_request.await_args.args[0]
    assert request["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert request["approval_id"] == "approval-1"
    assert request["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert request["readiness_plan_decision_audit_id"] == "audit-readiness-plan-decision-1"
    assert request["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert request["runtime_flag_approval_id"] == "flag-approval-1"
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["adapter_design_ref"] == (
        "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md"
    )
    assert request["rollback_plan_ref"] == "docs/runbooks/sdk-write-runner-rollback.md"
    assert request["smoke_runbook_ref"] == "docs/runbooks/sdk-write-runner-smoke.md"
    assert request["request_hash"] == "hash-adapter-implementation-request-1"
    assert request["dry_run"] is True
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_adapter_design_review_execute_flag_records_review_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_adapter_design_review.return_value = {
        "ok": True,
        "status": "sdk_live_runtime_flag_application_adapter_design_review_workflow_ready",
        "adapter_design_review": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "adapter_import_allowed": False,
            "adapter_execution_allowed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-adapter-design-review-record",
                "--adapter-design-review-id",
                "adapter-design-review-1",
                "--approval-id",
                "approval-1",
                "--adapter-implementation-request-id",
                "adapter-implementation-request-1",
                "--adapter-implementation-request-audit-id",
                "audit-adapter-implementation-request-1",
                "--readiness-plan-decision-id",
                "readiness-plan-decision-1",
                "--runtime-flag-execute-contract-id",
                "flag-execute-contract-1",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--review-decision",
                "accepted",
                "--reviewed-by",
                "owner",
                "--reviewed-at",
                "2026-06-08T00:00:00Z",
                "--review-reason",
                "owner accepted adapter design",
                "--adapter-design-ref",
                "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
                "--security-review-ref",
                "docs/security/sdk-write-runner-runtime-flag-adapter-review.md",
                "--test-plan-ref",
                "tests/test_control_plane_protocol.py",
                "--rollback-plan-ref",
                "docs/runbooks/sdk-write-runner-rollback.md",
                "--smoke-runbook-ref",
                "docs/runbooks/sdk-write-runner-smoke.md",
                "--review-hash",
                "hash-adapter-design-review-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_live_runtime_flag_application_adapter_design_review_workflow_ready"
    assert payload["adapter_design_review"]["record_status"] == "recorded"
    assert payload["adapter_design_review"]["runtime_flag_enabled"] is False
    assert payload["adapter_design_review"]["flag_application_performed"] is False
    assert payload["adapter_design_review"]["implementation_enabled"] is False
    assert payload["adapter_design_review"]["write_runner_enabled"] is False
    assert payload["adapter_design_review"]["adapter_execution_enabled"] is False
    assert payload["adapter_design_review"]["runner_invoked"] is False
    assert payload["adapter_design_review"]["mutation_performed"] is False
    assert payload["adapter_design_review"]["adapter_import_allowed"] is False
    assert payload["adapter_design_review"]["adapter_execution_allowed"] is False

    mock_client.record_sdk_runtime_flag_application_adapter_design_review.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_adapter_design_review.await_args.args[0]
    assert request["adapter_design_review_id"] == "adapter-design-review-1"
    assert request["approval_id"] == "approval-1"
    assert request["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert request["adapter_implementation_request_audit_id"] == "audit-adapter-implementation-request-1"
    assert request["readiness_plan_decision_id"] == "readiness-plan-decision-1"
    assert request["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert request["runtime_flag_approval_id"] == "flag-approval-1"
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["review_decision"] == "accepted"
    assert request["security_review_ref"] == (
        "docs/security/sdk-write-runner-runtime-flag-adapter-review.md"
    )
    assert request["test_plan_ref"] == "tests/test_control_plane_protocol.py"
    assert request["review_hash"] == "hash-adapter-design-review-1"
    assert request["dry_run"] is True
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_adapter_implementation_preflight_execute_flag_records_preflight_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_adapter_implementation_preflight.return_value = {
        "ok": True,
        "status": "sdk_live_runtime_flag_application_adapter_implementation_preflight_workflow_ready",
        "adapter_implementation_preflight": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
            "adapter_import_allowed": False,
            "adapter_execution_allowed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-adapter-implementation-preflight-record",
                "--adapter-implementation-preflight-id",
                "adapter-implementation-preflight-1",
                "--approval-id",
                "approval-1",
                "--adapter-design-review-id",
                "adapter-design-review-1",
                "--adapter-design-review-audit-id",
                "audit-adapter-design-review-1",
                "--adapter-implementation-request-id",
                "adapter-implementation-request-1",
                "--readiness-plan-decision-id",
                "readiness-plan-decision-1",
                "--runtime-flag-execute-contract-id",
                "flag-execute-contract-1",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--operator-id",
                "operator",
                "--locked-at",
                "2026-06-08T00:00:00Z",
                "--implementation-branch-ref",
                "codex/runtime-flag-adapter-preflight",
                "--implementation-plan-ref",
                "docs/runbooks/sdk-write-runner-runtime-flag-adapter-implementation.md",
                "--adapter-design-ref",
                "docs/runbooks/sdk-write-runner-runtime-flag-adapter-design.md",
                "--security-review-ref",
                "docs/security/sdk-write-runner-runtime-flag-adapter-review.md",
                "--test-plan-ref",
                "tests/test_control_plane_protocol.py",
                "--rollback-plan-ref",
                "docs/runbooks/sdk-write-runner-rollback.md",
                "--smoke-runbook-ref",
                "docs/runbooks/sdk-write-runner-smoke.md",
                "--idempotency-key",
                "adapter-implementation-preflight-1",
                "--idempotency-hash",
                "hash-idempotency-preflight-1",
                "--preflight-hash",
                "hash-adapter-implementation-preflight-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_live_runtime_flag_application_adapter_implementation_preflight_workflow_ready"
    assert payload["adapter_implementation_preflight"]["record_status"] == "recorded"
    assert payload["adapter_implementation_preflight"]["runtime_flag_enabled"] is False
    assert payload["adapter_implementation_preflight"]["flag_application_performed"] is False
    assert payload["adapter_implementation_preflight"]["implementation_enabled"] is False
    assert payload["adapter_implementation_preflight"]["write_runner_enabled"] is False
    assert payload["adapter_implementation_preflight"]["adapter_execution_enabled"] is False
    assert payload["adapter_implementation_preflight"]["runner_invoked"] is False
    assert payload["adapter_implementation_preflight"]["mutation_performed"] is False
    assert payload["adapter_implementation_preflight"]["adapter_import_allowed"] is False
    assert payload["adapter_implementation_preflight"]["adapter_execution_allowed"] is False

    mock_client.record_sdk_runtime_flag_application_adapter_implementation_preflight.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_adapter_implementation_preflight.await_args.args[0]
    assert request["adapter_implementation_preflight_id"] == "adapter-implementation-preflight-1"
    assert request["approval_id"] == "approval-1"
    assert request["adapter_design_review_id"] == "adapter-design-review-1"
    assert request["adapter_design_review_audit_id"] == "audit-adapter-design-review-1"
    assert request["adapter_implementation_request_id"] == "adapter-implementation-request-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["implementation_branch_ref"] == "codex/runtime-flag-adapter-preflight"
    assert request["implementation_plan_ref"] == (
        "docs/runbooks/sdk-write-runner-runtime-flag-adapter-implementation.md"
    )
    assert request["idempotency_key"] == "adapter-implementation-preflight-1"
    assert request["idempotency_hash"] == "hash-idempotency-preflight-1"
    assert request["preflight_hash"] == "hash-adapter-implementation-preflight-1"
    assert request["dry_run"] is True
    mock_client.invoke_sdk_contract.assert_not_called()


def test_cli_sdk_runtime_flag_application_execute_contract_execute_flag_records_contract_only() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    mock_client = AsyncMock()
    mock_client.record_sdk_runtime_flag_application_execute_contract.return_value = {
        "ok": True,
        "status": "sdk_runtime_flag_application_execute_contract_workflow_ready",
        "runtime_flag_execute_contract": {
            "record_status": "recorded",
            "audit_event_recorded": True,
            "runtime_flag_enabled": False,
            "flag_application_performed": False,
            "implementation_enabled": False,
            "execute_enabled": False,
            "write_runner_enabled": False,
            "adapter_execution_enabled": False,
            "agent_execution_enabled": False,
            "write_execution_enabled": False,
            "runner_invoked": False,
            "mark_executed": False,
            "mutation_performed": False,
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            [
                "sdk",
                "runtime-flag-application-execute-contract-record",
                "--runtime-flag-execute-contract-id",
                "flag-execute-contract-1",
                "--approval-id",
                "approval-1",
                "--runtime-flag-approval-id",
                "flag-approval-1",
                "--runtime-flag-approval-audit-id",
                "audit-flag-approval-1",
                "--runtime-flag-preflight-id",
                "flag-preflight-1",
                "--runtime-flag-enablement-id",
                "flag-enable-1",
                "--final-decision-id",
                "final-decision-1",
                "--operator-id",
                "operator",
                "--locked-at",
                "2026-06-08T00:00:00Z",
                "--execute-contract-reason",
                "owner requested live runtime flag application contract",
                "--idempotency-key",
                "idem-flag-execute-1",
                "--idempotency-hash",
                "hash-idem-flag-execute-1",
                "--rollback-plan-ref",
                "runbooks/sdk-write-runner-rollback.md",
                "--smoke-runbook-ref",
                "runbooks/sdk-write-runner-smoke.md",
                "--execute-contract-hash",
                "hash-flag-execute-contract-1",
                "--execute",
            ],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_runtime_flag_application_execute_contract_workflow_ready"
    assert payload["runtime_flag_execute_contract"]["record_status"] == "recorded"
    assert payload["runtime_flag_execute_contract"]["runtime_flag_enabled"] is False
    assert payload["runtime_flag_execute_contract"]["flag_application_performed"] is False
    assert payload["runtime_flag_execute_contract"]["execute_enabled"] is False
    assert payload["runtime_flag_execute_contract"]["write_runner_enabled"] is False
    assert payload["runtime_flag_execute_contract"]["runner_invoked"] is False
    assert payload["runtime_flag_execute_contract"]["mutation_performed"] is False

    mock_client.record_sdk_runtime_flag_application_execute_contract.assert_awaited_once()
    request = mock_client.record_sdk_runtime_flag_application_execute_contract.await_args.args[0]
    assert request["runtime_flag_execute_contract_id"] == "flag-execute-contract-1"
    assert request["approval_id"] == "approval-1"
    assert request["runtime_flag_approval_id"] == "flag-approval-1"
    assert request["runtime_flag_approval_audit_id"] == "audit-flag-approval-1"
    assert request["runtime_flag_preflight_id"] == "flag-preflight-1"
    assert request["runtime_flag_enablement_id"] == "flag-enable-1"
    assert request["final_decision_id"] == "final-decision-1"
    assert request["runtime_flag_name"] == "XAGENT_SDK_WRITE_RUNNER_ENABLED"
    assert request["idempotency_key"] == "idem-flag-execute-1"
    assert request["idempotency_hash"] == "hash-idem-flag-execute-1"
    assert request["execute_contract_hash"] == "hash-flag-execute-contract-1"
    assert request["dry_run"] is False
    mock_client.invoke_sdk_contract.assert_not_called()
