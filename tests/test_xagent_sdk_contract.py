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
        "status": "sdk_write_runner_implementation_plan_ready",
        "sdk": {
            "status": "sdk_write_runner_implementation_plan_ready",
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
    assert payload["status"] == "sdk_write_runner_implementation_plan_ready"
    assert payload["sdk"]["status"] == "sdk_write_runner_implementation_plan_ready"
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
        "status": "sdk_write_runner_implementation_plan_ready",
        "sdk": {
            "status": "sdk_write_runner_implementation_plan_ready",
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
    assert payload["status"] == "sdk_write_runner_implementation_plan_ready"
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
        "status": "sdk_write_runner_implementation_plan_ready",
        "sdk": {
            "status": "sdk_write_runner_implementation_plan_ready",
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
    assert payload["status"] == "sdk_write_runner_implementation_plan_ready"
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
        "status": "sdk_write_runner_implementation_plan_ready",
        "sdk": {
            "status": "sdk_write_runner_implementation_plan_ready",
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
    assert payload["status"] == "sdk_write_runner_implementation_plan_ready"
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
