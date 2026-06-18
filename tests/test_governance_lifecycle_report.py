from __future__ import annotations

import json
from pathlib import Path

from scripts.governance_lifecycle_report import (
    GOVERNED_DOMAINS,
    LIFECYCLE_STATES,
    build_governance_lifecycle_report,
    main,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def test_governance_lifecycle_report_default_is_read_only() -> None:
    report = build_governance_lifecycle_report()
    payload = report.to_dict()

    assert report.status == "governance_lifecycle_report_ready"
    assert report.evidence_type == "skills_plugins_mcp_hooks_governance"
    assert report.full_codex_parity_claimed is False
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.owner_gate_required is True
    assert report.lifecycle_states == list(LIFECYCLE_STATES)
    assert sorted(report.governed_domains) == sorted(GOVERNED_DOMAINS)
    assert {check["status"] for check in payload["checks"]} == {"passed"}


def test_governance_lifecycle_report_covers_all_governed_domains() -> None:
    report = build_governance_lifecycle_report()
    domains = {item.domain for item in report.governed_items}
    names = {item.name for item in report.governed_items}

    assert domains == set(GOVERNED_DOMAINS)
    assert "skill_curator_staged_skill" in names
    assert "plugin_contract_preview" in names
    assert "mcp_server_registration" in names
    assert "hook_policy_registration" in names


def test_governed_items_include_required_metadata_and_owner_gates() -> None:
    report = build_governance_lifecycle_report()

    for item in report.governed_items:
        assert item.lifecycle_states == list(LIFECYCLE_STATES)
        assert item.permission_scopes
        assert "classification" in item.data_access
        assert item.data_access["secret_material_allowed"] is False
        assert item.test_command.startswith("python -m pytest")
        assert item.rollback["owner_approval_required"] is True
        assert item.rollback["mutation_performed"] is False
        assert item.approvals["promote"] == "owner_required"
        assert item.approvals["rollback"] == "owner_required"
        assert item.execution_adapter["mutation_enabled"] is False
        assert item.source_refs

    assert report.promotion_gate["owner_approval_required"] is True
    assert report.promotion_gate["mutation_enabled"] is False
    assert report.rollback_gate["owner_approval_required"] is True
    assert report.rollback_gate["mutation_enabled"] is False


def test_governance_lifecycle_report_blocks_mutating_adapter() -> None:
    report = build_governance_lifecycle_report(
        [
            {
                "domain": "skill",
                "name": "unsafe_skill",
                "current_state": "promote",
                "lifecycle_states": list(LIFECYCLE_STATES),
                "permission_scopes": ["filesystem:write"],
                "mcp_dependencies": [],
                "data_access": {"classification": "internal_metadata", "secret_material_allowed": False},
                "test_command": "python -m pytest tests/test_skill_curator_api.py -q",
                "rollback": {"owner_approval_required": True, "mutation_performed": False},
                "approvals": {"promote": "owner_required", "rollback": "owner_required"},
                "execution_adapter": {"state": "execute", "mutation_enabled": True},
                "source_refs": ["tests/test_skill_curator_api.py"],
            }
        ]
    )

    assert report.status == "governance_lifecycle_report_blocked"
    adapter = next(check for check in report.checks if check.name == "no_mutating_adapters")
    domains = next(check for check in report.checks if check.name == "governed_domains_complete")
    assert adapter.status == "failed"
    assert "unsafe_skill" in adapter.details["mutation_enabled"]
    assert domains.status == "failed"


def test_governance_lifecycle_report_redacts_secret_like_metadata() -> None:
    report = build_governance_lifecycle_report(
        [
            {
                "domain": "skill",
                "name": "secret_skill",
                "current_state": "review",
                "lifecycle_states": list(LIFECYCLE_STATES),
                "permission_scopes": ["skill:inspect"],
                "mcp_dependencies": [],
                "data_access": {
                    "classification": "internal_metadata",
                    "secret_material_allowed": False,
                    "sample": "Bearer abcdefghijklmnopqrstuvwxyz",
                },
                "test_command": "python -m pytest tests/test_skill_curator_api.py -q",
                "rollback": {
                    "plan": "Remove " + "sk-" + "test1234567890abcdef" + " from metadata.",
                    "owner_approval_required": True,
                    "mutation_performed": False,
                },
                "approvals": {"promote": "owner_required", "rollback": "owner_required"},
                "execution_adapter": {"state": "metadata_only", "mutation_enabled": False},
                "source_refs": ["tests/test_skill_curator_api.py"],
            }
        ]
    )
    rendered = json.dumps(report.to_dict(), ensure_ascii=False)

    assert "sk-test" not in rendered
    assert "Bearer abcdef" not in rendered
    assert "<redacted>" in rendered


def test_write_governance_lifecycle_report_json_and_markdown(tmp_path: Path) -> None:
    report = build_governance_lifecycle_report()
    json_output = tmp_path / "governance-lifecycle-report.json"
    markdown_output = tmp_path / "governance-lifecycle-report.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "governance_lifecycle_report_ready"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["mutation_performed"] is False
    assert "# X-Agent Governance Lifecycle Report" in markdown
    assert "skill_curator_staged_skill" in render_markdown_report(report)


def test_governance_lifecycle_report_cli_writes_report(tmp_path: Path, monkeypatch) -> None:
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "governance_lifecycle_report.py",
            "--output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ],
    )

    assert main() == 0
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["evidence_type"] == "skills_plugins_mcp_hooks_governance"
    assert payload["mutation_performed"] is False
    assert markdown_output.exists()
