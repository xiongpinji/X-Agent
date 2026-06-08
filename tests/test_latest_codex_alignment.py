from __future__ import annotations

import json
from pathlib import Path

from scripts.latest_codex_alignment import (
    AlignmentEvidenceSpec,
    build_latest_codex_alignment_report,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, value: str = "alignment evidence\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _customer_pack_payload(
    *,
    status: str = "customer_acceptance_pack_ready",
    parity: bool = False,
    mutation: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "evidence_type": "commercial_pilot_customer_acceptance_pack",
        "pilot_channel": "feishu",
        "full_codex_parity_claimed": parity,
        "mutation_performed": mutation,
        "outbound_message_sent": mutation,
    }


def _github_review_action_payload(
    *,
    status: str = "github_review_action_report_ready",
    parity: bool = False,
    mutation: bool = False,
) -> dict[str, object]:
    return {
        "status": status,
        "evidence_type": "github_review_action",
        "full_codex_parity_claimed": parity,
        "mutation_performed": mutation,
        "network_mutation_performed": mutation,
    }


def _write_default_evidence(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "customer_pack": tmp_path / "reports" / "commercial-pilot-customer-acceptance-pack.json",
        "github_report": tmp_path / "reports" / "github-review-action-report.json",
        "control_plane": tmp_path / "docs" / "specs" / "xagent-control-plane-protocol.md",
        "control_plane_api": tmp_path / "backend" / "app" / "api" / "control_plane.py",
        "control_plane_tests": tmp_path / "tests" / "test_control_plane_protocol.py",
        "delivery_doc": tmp_path / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md",
        "mcp": tmp_path / "tests" / "test_mcp_manager.py",
        "hooks": tmp_path / "tests" / "test_hooks_manager.py",
        "cli": tmp_path / "tests" / "test_cli_commands.py",
        "workbench": tmp_path / "tests" / "test_workbench_thread_loop.py",
        "commercial_workbench": tmp_path / "tests" / "test_commercial_pilot_workbench_thread.py",
        "cloud_task_spec": tmp_path / "docs" / "specs" / "xagent-cloud-task-environment.md",
        "cloud_task_tests": tmp_path / "tests" / "test_cloud_task_environment_contract.py",
        "skill": tmp_path / "tests" / "test_skill_curator_api.py",
        "approvals": tmp_path / "tests" / "test_approvals.py",
        "sandbox": tmp_path / "tests" / "test_security_sandbox.py",
        "github_report_script": tmp_path / "scripts" / "github_review_action_report.py",
        "github_report_tests": tmp_path / "tests" / "test_github_review_action_report.py",
        "github_api": tmp_path / "tests" / "test_issue_to_pr_api.py",
        "github_cli": tmp_path / "tests" / "test_cli_github.py",
        "workflow": tmp_path / ".github" / "workflows" / "commercial-rc.yml",
        "plan": tmp_path
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-06-08-latest-codex-alignment-execution.md",
    }
    _write_json(paths["customer_pack"], _customer_pack_payload())
    _write_json(paths["github_report"], _github_review_action_payload())
    for key, path in paths.items():
        if key not in {"customer_pack", "github_report"}:
            _write_text(path)
    return paths


def _evidence_specs(paths: dict[str, Path]) -> tuple[AlignmentEvidenceSpec, ...]:
    return (
        AlignmentEvidenceSpec(
            "feishu_customer_acceptance_pack",
            paths["customer_pack"],
            "runtime_report",
            expected_statuses=frozenset({"customer_acceptance_pack_ready"}),
            expected_evidence_type="commercial_pilot_customer_acceptance_pack",
        ),
        AlignmentEvidenceSpec(
            "github_review_action_report",
            paths["github_report"],
            "runtime_report",
            expected_statuses=frozenset({"github_review_action_report_ready"}),
            expected_evidence_type="github_review_action",
        ),
        AlignmentEvidenceSpec("control_plane_protocol", paths["control_plane"], "source_doc"),
        AlignmentEvidenceSpec("control_plane_api", paths["control_plane_api"], "source_api"),
        AlignmentEvidenceSpec("control_plane_protocol_tests", paths["control_plane_tests"], "source_test"),
        AlignmentEvidenceSpec("feishu_delivery_pack_doc", paths["delivery_doc"], "source_doc"),
        AlignmentEvidenceSpec("mcp_manager_tests", paths["mcp"], "source_test"),
        AlignmentEvidenceSpec("hooks_manager_tests", paths["hooks"], "source_test"),
        AlignmentEvidenceSpec("cli_commands_tests", paths["cli"], "source_test"),
        AlignmentEvidenceSpec("workbench_thread_tests", paths["workbench"], "source_test"),
        AlignmentEvidenceSpec(
            "commercial_workbench_evidence_tests",
            paths["commercial_workbench"],
            "source_test",
        ),
        AlignmentEvidenceSpec("cloud_task_environment_spec", paths["cloud_task_spec"], "source_doc"),
        AlignmentEvidenceSpec("cloud_task_environment_tests", paths["cloud_task_tests"], "source_test"),
        AlignmentEvidenceSpec("skill_curator_api_tests", paths["skill"], "source_test"),
        AlignmentEvidenceSpec("approval_tests", paths["approvals"], "source_test"),
        AlignmentEvidenceSpec("sandbox_security_tests", paths["sandbox"], "source_test"),
        AlignmentEvidenceSpec("github_review_action_script", paths["github_report_script"], "source_script"),
        AlignmentEvidenceSpec(
            "github_review_action_report_tests",
            paths["github_report_tests"],
            "source_test",
        ),
        AlignmentEvidenceSpec("github_issue_to_pr_tests", paths["github_api"], "source_test"),
        AlignmentEvidenceSpec("github_cli_tests", paths["github_cli"], "source_test"),
        AlignmentEvidenceSpec("commercial_rc_workflow", paths["workflow"], "source_workflow"),
        AlignmentEvidenceSpec("latest_alignment_plan", paths["plan"], "source_doc"),
    )


def test_latest_codex_alignment_ready_with_current_evidence(tmp_path: Path) -> None:
    paths = _write_default_evidence(tmp_path)

    report = build_latest_codex_alignment_report(
        root=tmp_path,
        report_dir=tmp_path / "reports",
        evidence_specs=_evidence_specs(paths),
    )

    assert report.status == "latest_codex_alignment_plan_ready"
    assert report.evidence_type == "latest_codex_alignment"
    assert report.pilot_delivery_status == "customer_acceptance_pack_ready"
    assert report.full_codex_parity_claimed is False
    assert report.p0_ready_count == report.p0_total_count
    assert not any("app_server_control_plane" in item for item in report.next_p0_tasks)
    assert not any("threads_worktrees_and_automations" in item for item in report.next_p0_tasks)
    assert not any("cloud_task_environment" in item for item in report.next_p0_tasks)
    assert not any("github_review_and_action_workflows" in item for item in report.next_p0_tasks)
    assert any("skills_plugins_and_mcp" in item for item in report.next_p0_tasks)
    assert any("approval_sandbox_and_enterprise_admin" in item for item in report.next_p0_tasks)
    control_plane = next(item for item in report.capabilities if item.capability == "app_server_control_plane")
    assert control_plane.xagent_status == "contract_first_ready"
    assert {
        "control_plane_protocol",
        "control_plane_api",
        "control_plane_protocol_tests",
    }.issubset(set(control_plane.evidence))
    threads = next(item for item in report.capabilities if item.capability == "threads_worktrees_and_automations")
    assert threads.xagent_status == "durable_thread_contract_ready"
    assert {
        "control_plane_api",
        "control_plane_protocol_tests",
        "workbench_thread_tests",
        "commercial_workbench_evidence_tests",
    }.issubset(set(threads.evidence))
    cloud = next(item for item in report.capabilities if item.capability == "cloud_task_environment")
    assert cloud.xagent_status == "cloud_task_contract_ready"
    assert {
        "cloud_task_environment_spec",
        "cloud_task_environment_tests",
        "commercial_rc_workflow",
    }.issubset(set(cloud.evidence))
    github = next(item for item in report.capabilities if item.capability == "github_review_and_action_workflows")
    assert github.xagent_status == "github_review_action_report_ready"
    assert {
        "github_review_action_report",
        "github_review_action_script",
        "github_review_action_report_tests",
        "github_issue_to_pr_tests",
        "github_cli_tests",
        "commercial_rc_workflow",
    }.issubset(set(github.evidence))
    assert {check.status for check in report.checks} == {"passed"}
    assert all(item.official_sources for item in report.capabilities)


def test_latest_codex_alignment_action_required_when_customer_pack_missing(tmp_path: Path) -> None:
    paths = _write_default_evidence(tmp_path)
    paths["customer_pack"].unlink()

    report = build_latest_codex_alignment_report(
        root=tmp_path,
        report_dir=tmp_path / "reports",
        evidence_specs=_evidence_specs(paths),
    )

    assert report.status == "latest_codex_alignment_action_required"
    required = next(check for check in report.checks if check.name == "required_alignment_evidence")
    pack = next(check for check in report.checks if check.name == "feishu_customer_acceptance_pack_ready")
    mutation = next(check for check in report.checks if check.name == "commercial_pilot_no_mutation_boundary")
    assert required.status == "action_required"
    assert pack.status == "action_required"
    assert mutation.status == "action_required"


def test_latest_codex_alignment_blocks_full_parity_claim(tmp_path: Path) -> None:
    paths = _write_default_evidence(tmp_path)
    _write_json(paths["customer_pack"], _customer_pack_payload(parity=True))

    report = build_latest_codex_alignment_report(
        root=tmp_path,
        report_dir=tmp_path / "reports",
        evidence_specs=_evidence_specs(paths),
    )

    assert report.status == "latest_codex_alignment_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "feishu_customer_acceptance_pack" in parity.details["claiming_evidence"]


def test_latest_codex_alignment_blocks_mutation_boundary_break(tmp_path: Path) -> None:
    paths = _write_default_evidence(tmp_path)
    _write_json(paths["customer_pack"], _customer_pack_payload(mutation=True))

    report = build_latest_codex_alignment_report(
        root=tmp_path,
        report_dir=tmp_path / "reports",
        evidence_specs=_evidence_specs(paths),
    )

    assert report.status == "latest_codex_alignment_blocked"
    mutation = next(check for check in report.checks if check.name == "commercial_pilot_no_mutation_boundary")
    assert mutation.status == "failed"
    assert "mutation_performed" in mutation.details["offenders"]


def test_write_latest_codex_alignment_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_default_evidence(tmp_path)
    report = build_latest_codex_alignment_report(
        root=tmp_path,
        report_dir=tmp_path / "reports",
        evidence_specs=_evidence_specs(paths),
    )
    json_output = tmp_path / "latest-codex-alignment.json"
    markdown_output = tmp_path / "latest-codex-alignment.md"

    write_report(report, json_output)
    write_markdown_report(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "latest_codex_alignment_plan_ready"
    assert payload["full_codex_parity_claimed"] is False
    assert "# X-Agent Latest Codex Alignment Report" in markdown
    assert "cloud_task_environment" in render_markdown_report(report)
