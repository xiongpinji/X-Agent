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


def test_sdk_resume_run_and_read_thread_methods_are_stable() -> None:
    sdk = ControlPlaneSDK()
    resume = sdk.resume_thread("thread-1", input_text="continue", dry_run=False).to_dict()
    turn = sdk.run_turn("thread-1", "next").to_dict()
    read = sdk.read_thread("thread-1").to_dict()

    assert resume["operation"] == "thread_resume"
    assert resume["request"]["method"] == "thread/resume"
    assert resume["request"]["dry_run"] is False
    assert resume["owner_gate"]["mutation_performed"] is False
    assert turn["operation"] == "turn_start"
    assert turn["request"]["method"] == "turn/start"
    assert read["operation"] == "thread_read"
    assert read["request"]["method"] == "thread/read"
    assert read["request"]["dry_run"] is True
    assert read["owner_gate"]["required_for_write_methods"] is False


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
        "status": "sdk_approval_handoff_ready",
        "sdk": {
            "status": "sdk_approval_handoff_ready",
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
        },
        "control_plane": {
            "ok": False,
            "error": {"code": "adapter_pending"},
        },
    }

    with patch("cli.commands.sdk_cmd.create_client", return_value=mock_client):
        result = CliRunner().invoke(
            app,
            ["sdk", "turn-run", "thread-1", "next instruction", "--execute", "--idempotency-key", "idem-2"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "sdk_approval_handoff_ready"
    assert payload["sdk"]["status"] == "sdk_approval_handoff_ready"
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
    assert payload["control_plane"]["error"]["code"] == "adapter_pending"

    mock_client.invoke_sdk_contract.assert_awaited_once()
    contract = mock_client.invoke_sdk_contract.await_args.args[0]
    assert contract["operation"] == "turn_start"
    assert contract["request"]["dry_run"] is False
    assert contract["request"]["idempotency_key"] == "idem-2"
    assert contract["request"]["mutation_performed"] is False
