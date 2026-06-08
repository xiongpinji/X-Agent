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

    assert report.status == "sdk_http_dry_run_adapter_ready"
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

    assert methods == ["thread/start", "thread/resume", "turn/start", "thread/read"]
    assert command_methods == methods
    assert all(item["request"]["context"]["non_interactive"] is True for item in report.sdk_contracts)
    assert all(item["request"]["mutation_performed"] is False for item in report.sdk_contracts)
    assert all(item["execute_starts_agent"] is False for item in report.cli_commands)


def test_sdk_noninteractive_report_covers_owner_gated_backend_stub() -> None:
    stub = build_sdk_noninteractive_report().backend_stub

    assert stub["endpoint"] == "/api/v1/control-plane/sdk/invoke"
    assert stub["normalizes_to"] == "/api/v1/control-plane/invoke"
    assert stub["approval_subject_type"] == "command"
    assert stub["owner_gate_required"] is True
    assert stub["admin_policy_required"] is True
    assert stub["audit_required"] is True
    assert stub["adapter_execution_enabled"] is False
    assert stub["mutation_performed"] is False


def test_sdk_noninteractive_report_covers_cli_http_dry_run_adapter() -> None:
    adapter = build_sdk_noninteractive_report().http_client_adapter

    assert adapter["cli_method"] == "HTTPClient.invoke_sdk_contract"
    assert adapter["endpoint"] == "/api/v1/control-plane/sdk/invoke"
    assert adapter["trigger"] == "xagent sdk <command> --execute"
    assert adapter["default_without_execute"] == "local_envelope_only"
    assert adapter["starts_agent_execution"] is False
    assert adapter["adapter_execution_enabled"] is False
    assert adapter["mutation_performed"] is False


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
    assert payload["status"] == "sdk_http_dry_run_adapter_ready"
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
