from __future__ import annotations

import json
from pathlib import Path

from scripts.approval_sandbox_admin_report import (
    build_approval_sandbox_admin_report,
    main,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def test_approval_sandbox_admin_report_default_is_read_only() -> None:
    report = build_approval_sandbox_admin_report()
    payload = report.to_dict()

    assert report.status == "approval_sandbox_admin_contract_ready"
    assert report.evidence_type == "approval_sandbox_enterprise_admin_contract"
    assert report.full_codex_parity_claimed is False
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.owner_gate_required is True
    assert {check["status"] for check in payload["checks"]} == {"passed"}


def test_approval_sandbox_admin_report_covers_required_subjects_and_decisions() -> None:
    report = build_approval_sandbox_admin_report()

    assert report.subjects == [
        "command",
        "file_change",
        "network_request",
        "mcp_elicitation",
        "browser_action",
        "channel_send",
        "issue_to_pr_execute",
    ]
    assert report.decision_types == [
        "approve_once",
        "approve_for_run",
        "approve_for_session",
        "deny",
        "abort",
    ]
    assert {contract.subject_type for contract in report.contracts} == set(report.subjects)


def test_approval_sandbox_admin_contracts_are_owner_admin_audit_gated() -> None:
    report = build_approval_sandbox_admin_report()

    for contract in report.contracts:
        assert contract.owner_gate_required is True
        assert contract.admin_policy_required is True
        assert contract.audit_required is True
        assert contract.blocked_without_approval is True
        assert contract.execution_adapter["mutation_enabled"] is False
        assert contract.execution_adapter["requires_explicit_execute"] is True
        assert contract.default_sandbox_profile
        assert "abort" in contract.decision_types


def test_write_approval_sandbox_admin_report_json_and_markdown(tmp_path: Path) -> None:
    report = build_approval_sandbox_admin_report()
    json_output = tmp_path / "approval-sandbox-admin-report.json"
    markdown_output = tmp_path / "approval-sandbox-admin-report.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "approval_sandbox_admin_contract_ready"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["mutation_performed"] is False
    assert "# X-Agent Approval Sandbox Admin Report" in markdown
    assert "network_request" in render_markdown_report(report)


def test_approval_sandbox_admin_report_cli_writes_report(tmp_path: Path, monkeypatch) -> None:
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "approval_sandbox_admin_report.py",
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    assert main() == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["evidence_type"] == "approval_sandbox_enterprise_admin_contract"
    assert payload["network_mutation_performed"] is False
    assert markdown_output.exists()
