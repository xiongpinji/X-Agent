from __future__ import annotations

import json

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


def test_cli_sdk_turn_run_execute_flag_only_marks_envelope_intent() -> None:
    set_current_config(CLIConfig(api_base_url="http://localhost:8000", output_format="json"))
    result = CliRunner().invoke(
        app,
        ["sdk", "turn-run", "thread-1", "next instruction", "--execute", "--idempotency-key", "idem-2"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["operation"] == "turn_start"
    assert payload["request"]["dry_run"] is False
    assert payload["request"]["idempotency_key"] == "idem-2"
    assert payload["request"]["mutation_performed"] is False
    assert payload["owner_gate"]["mutation_performed"] is False
