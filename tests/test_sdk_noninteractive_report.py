from __future__ import annotations

import json
from pathlib import Path

from scripts.sdk_noninteractive_report import (
    build_sdk_noninteractive_report,
    main,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def test_sdk_noninteractive_report_default_is_read_only() -> None:
    report = build_sdk_noninteractive_report()
    payload = report.to_dict()

    assert report.status == "sdk_write_runner_adapter_review_ready"
    assert report.evidence_type == "sdk_noninteractive_cli_contract"
    assert report.full_codex_parity_claimed is False
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.owner_gate_required is True
    assert {check["status"] for check in payload["checks"]} == {"passed"}


def test_sdk_noninteractive_report_covers_sdk_and_cli_methods() -> None:
    report = build_sdk_noninteractive_report()
    methods = [item["request"]["method"] for item in report.sdk_contracts]
    command_methods = [item["method"] for item in report.cli_commands]

    assert methods == [
        "thread/start",
        "thread/resume",
        "turn/start",
        "thread/read",
        "runtime/evidence/read",
        "runtime/evidence/read",
    ]
    assert command_methods == methods
    assert all(item["request"]["context"]["non_interactive"] is True for item in report.sdk_contracts)
    assert all(item["request"]["mutation_performed"] is False for item in report.sdk_contracts)
    assert all(item["execute_starts_agent"] is False for item in report.cli_commands)


def test_sdk_noninteractive_report_covers_owner_gated_backend_stub() -> None:
    stub = build_sdk_noninteractive_report().backend_stub

    assert stub["endpoint"] == "/api/v1/control-plane/sdk/invoke"
    assert stub["normalizes_to"] == "/api/v1/control-plane/invoke"
    assert stub["approval_subject_type"] == "command"
    assert stub["approval_intent_created_for_write_methods"] is True
    assert stub["owner_gate_required"] is True
    assert stub["admin_policy_required"] is True
    assert stub["audit_required"] is True
    assert stub["adapter_execution_enabled"] is False
    assert stub["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_cli_http_dry_run_adapter() -> None:
    adapter = build_sdk_noninteractive_report().http_client_adapter

    assert adapter["cli_method"] == "HTTPClient.invoke_sdk_contract"
    assert adapter["endpoint"] == "/api/v1/control-plane/sdk/invoke"
    assert "--execute" in adapter["trigger"]
    assert "--approved-approval-id <approval_id>" in adapter["trigger"]
    assert adapter["default_without_execute"] == "local_envelope_only"
    assert adapter["read_only_execute_supported"] is True
    assert adapter["starts_agent_execution"] is False
    assert adapter["adapter_execution_enabled"] is False
    assert adapter["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_approval_intent_flow() -> None:
    flow = build_sdk_noninteractive_report().approval_intent_flow

    assert flow["write_methods_create_pending_approval"] is True
    assert flow["read_methods_create_approval"] is False
    assert flow["approval_subject_type"] == "command"
    assert flow["approval_resource_prefix"] == "sdk:"
    assert flow["mark_executed"] is False
    assert flow["starts_agent_execution"] is False
    assert flow["adapter_execution_enabled"] is False
    assert flow["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_approval_handoff() -> None:
    handoff = build_sdk_noninteractive_report().approval_handoff

    assert handoff["approval_id_returned"] is True
    assert handoff["show_command"] == "xagent approvals show <approval_id>"
    assert handoff["approve_command"] == "xagent approvals approve <approval_id> --by <owner> --reason <reason>"
    assert handoff["blocked_execute_command"] == "xagent approvals execute <approval_id>"
    assert handoff["execute_disabled"] is True
    assert handoff["readback_method"] == "approval/read"
    assert handoff["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_owner_approved_execution_preflight() -> None:
    contract = build_sdk_noninteractive_report().execution_adapter_contract

    assert contract["stage"] == "owner_approved_preflight"
    assert contract["approved_approval_id_supported"] is True
    assert contract["owner_approved_cli_flag"] == "--approved-approval-id <approval_id>"
    assert contract["approval_readback_method"] == "approval/read"
    assert contract["ready_status"] == "approved_ready"
    assert contract["adapter_execution_enabled"] is False
    assert contract["agent_execution_enabled"] is False
    assert contract["mark_executed"] is False
    assert contract["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_read_only_runner_contract() -> None:
    contract = build_sdk_noninteractive_report().read_only_runner_contract

    assert contract["stage"] == "read_only_runner"
    assert contract["enabled_for_read_methods"] is True
    assert {"thread/read", "runtime/evidence/read"}.issubset(set(contract["supported_methods"]))
    assert "xagent sdk thread-read <thread_id> --execute" in contract["cli_execute_commands"]
    assert contract["returns_control_plane_result"] is True
    assert contract["agent_execution_enabled"] is False
    assert contract["write_execution_enabled"] is False
    assert contract["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_write_runner_safety_contract() -> None:
    contract = build_sdk_noninteractive_report().write_runner_safety_contract

    assert contract["stage"] == "owner_approved_write_runner_safety"
    assert contract["approved_approval_id_required"] is True
    assert contract["ready_status"] == "planned_not_executed"
    assert "runner_kind" in contract["runner_plan_fields"]
    assert "runner_invoked" in contract["receipt_template_fields"]
    assert contract["requires_idempotency_key_for_write"] is True
    assert contract["runner_invoked"] is False
    assert contract["agent_execution_enabled"] is False
    assert contract["write_execution_enabled"] is False
    assert contract["mark_executed"] is False
    assert contract["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_dry_run_executor_stub() -> None:
    stub = build_sdk_noninteractive_report().dry_run_executor_stub

    assert stub["stub_stage"] == "owner_approved_write_dry_run_executor"
    assert stub["audit_event_recorded"] is True
    assert stub["audit_action"] == "sdk.write_runner.dry_run_planned"
    assert stub["receipt_status"] == "dry_run_planned"
    assert stub["receipt_includes_audit_id"] is True
    assert stub["receipt_persisted"] is True
    assert stub["receipt_readback_method"] == "runtime/evidence/read"
    assert stub["runner_invoked"] is False
    assert stub["agent_execution_enabled"] is False
    assert stub["mark_executed"] is False
    assert stub["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_runtime_evidence_readback() -> None:
    readback = build_sdk_noninteractive_report().runtime_evidence_readback

    assert readback["evidence_type"] == "sdk_dry_run_executor_stub"
    assert readback["readback_method"] == "runtime/evidence/read"
    assert readback["receipt_schema_available"] is True
    assert readback["receipt_readback_supported"] is True
    assert readback["receipt_persisted"] is True
    assert "audit_id" in readback["receipt_filter_keys"]
    assert readback["audit_readback_action"] == "sdk.write_runner.dry_run_planned"
    assert "--evidence-type sdk_dry_run_executor_stub" in readback["sdk_command"]
    assert readback["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_persisted_receipt_safety_review() -> None:
    review = build_sdk_noninteractive_report().runner_safety_review

    assert review["stage"] == "persisted_dry_run_receipt_safety_review"
    assert review["review_status"] == "passed"
    assert "receipt_persisted" in review["required_receipt_checks"]
    assert review["next_gate"] == "owner_approved_write_runner_implementation_review"
    assert review["write_runner_enabled"] is False
    assert review["agent_execution_enabled"] is False
    assert review["mark_executed"] is False
    assert review["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_write_runner_execute_gate() -> None:
    gate = build_sdk_noninteractive_report().write_runner_execute_gate

    assert gate["stage"] == "owner_approved_write_runner_execute_gate"
    assert gate["gate_status"] == "ready_but_disabled"
    assert "approved_preflight_ready" in gate["required_checks"]
    assert "receipt_persisted" in gate["required_checks"]
    assert "safety_review_passed" in gate["required_checks"]
    assert gate["next_gate"] == "owner_approved_write_runner_adapter_implementation"
    assert gate["execute_enabled"] is False
    assert gate["write_runner_enabled"] is False
    assert gate["adapter_execution_enabled"] is False
    assert gate["agent_execution_enabled"] is False
    assert gate["mark_executed"] is False
    assert gate["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_write_runner_adapter_review() -> None:
    review = build_sdk_noninteractive_report().write_runner_adapter_review

    assert review["stage"] == "owner_approved_write_runner_adapter_implementation_review"
    assert review["review_status"] == "ready_but_disabled"
    assert review["adapter_target"]["callable"] == "AgentCoordinator.run"
    assert review["approval_execution_policy"]["mark_executed_allowed_after_runner_success"] is True
    assert review["approval_execution_policy"]["mark_executed_called_now"] is False
    assert review["audit_contract"]["future_execute_action"] == "sdk.write_runner.executed"
    assert review["next_gate"] == "owner_approved_write_runner_runtime_feature_flag"
    assert review["implementation_enabled"] is False
    assert review["execute_enabled"] is False
    assert review["write_runner_enabled"] is False
    assert review["adapter_execution_enabled"] is False
    assert review["agent_execution_enabled"] is False
    assert review["mark_executed"] is False
    assert review["mutation_performed"] is False


def test_sdk_noninteractive_report_keeps_feishu_first_channel_strategy() -> None:
    strategy = build_sdk_noninteractive_report().channel_strategy

    assert strategy["pilot_channel"] == "feishu"
    assert strategy["domestic_v1_primary"] == "feishu"
    assert strategy["telegram_required"] is False
    assert strategy["slack_blocking"] is False
    assert strategy["channel_send_performed"] is False


def test_write_sdk_noninteractive_report_json_and_markdown(tmp_path: Path) -> None:
    report = build_sdk_noninteractive_report()
    json_output = tmp_path / "sdk-noninteractive-report.json"
    markdown_output = tmp_path / "sdk-noninteractive-report.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "sdk_write_runner_adapter_review_ready"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["mutation_performed"] is False
    assert "# X-Agent SDK Non-Interactive Report" in markdown
    assert "thread/start" in render_markdown_report(report)


def test_sdk_noninteractive_report_cli_writes_report(tmp_path: Path, monkeypatch) -> None:
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "sdk_noninteractive_report.py",
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    assert main() == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["evidence_type"] == "sdk_noninteractive_cli_contract"
    assert payload["network_mutation_performed"] is False
    assert markdown_output.exists()
