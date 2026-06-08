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
    assert turn["owner_gate"]["runner_invoked"] is False
    assert turn["owner_gate"]["adapter_execution_enabled"] is False
    assert read["operation"] == "thread_read"
    assert read["request"]["method"] == "thread/read"
    assert read["request"]["dry_run"] is True
    assert read["owner_gate"]["required_for_write_methods"] is False
    assert read["owner_gate"]["read_only_runner_contract"] is True
    assert evidence["operation"] == "runtime_evidence_read"
    assert evidence["request"]["method"] == "runtime/evidence/read"
    assert evidence["request"]["params"]["report_name"] == "latest-codex-alignment.json"
    assert evidence["owner_gate"]["required_for_write_methods"] is False
    assert receipt_evidence["request"]["params"]["evidence_type"] == "sdk_dry_run_executor_stub"
    assert receipt_evidence["request"]["params"]["approval_id"] == "approval-1"
    assert receipt_evidence["request"]["params"]["method"] == "turn/start"


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
        "status": "sdk_dry_run_receipt_persistence_ready",
        "sdk": {
            "status": "sdk_dry_run_receipt_persistence_ready",
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
    assert payload["status"] == "sdk_dry_run_receipt_persistence_ready"
    assert payload["sdk"]["status"] == "sdk_dry_run_receipt_persistence_ready"
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
        "status": "sdk_dry_run_receipt_persistence_ready",
        "sdk": {
            "status": "sdk_dry_run_receipt_persistence_ready",
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
    assert payload["status"] == "sdk_dry_run_receipt_persistence_ready"
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
        "status": "sdk_dry_run_receipt_persistence_ready",
        "sdk": {
            "status": "sdk_dry_run_receipt_persistence_ready",
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
    assert payload["status"] == "sdk_dry_run_receipt_persistence_ready"
    assert payload["control_plane"]["result"]["evidence"]["evidence_type"] == "sdk_dry_run_executor_stub"

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "runtime_evidence_read"
    assert contract["request"]["params"]["evidence_type"] == "sdk_dry_run_executor_stub"
    assert contract["request"]["params"]["approval_id"] == "approval-1"
    assert contract["request"]["params"]["method"] == "turn/start"
