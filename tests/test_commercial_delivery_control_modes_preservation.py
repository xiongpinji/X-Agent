from __future__ import annotations

from pathlib import Path

from scripts.commercial_delivery_control_modes_preservation import (
    build_report,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def test_control_modes_preservation_ready_on_current_workspace() -> None:
    report = build_report()

    assert report.status == "control_modes_preservation_ready"
    assert report.evidence_type == "commercial_delivery_control_modes_preservation"
    assert report.owner_gated is True
    assert report.mutation_performed is False
    assert report.git_stage_performed is False
    assert report.git_commit_performed is False
    assert report.git_push_performed is False
    assert report.network_mutation_performed is False
    assert report.agent_execution_enabled is False
    assert report.full_codex_parity_claimed is False
    assert report.summary["loop_phases"] == ["explore", "plan", "edit", "verify", "deliver"]
    assert report.summary["plan_only_default"] is True
    assert report.summary["execute_true_required_for_agent_run"] is True
    assert report.summary["stage_in_original_kernel_manifest"] is False
    assert "POST /api/v1/control/plans" in report.expected_api_routes
    assert "POST /api/v1/control/goals/{goal_id}/advance" in report.expected_api_routes
    assert "xagent control goal advance --execute" in report.expected_cli_commands
    assert {check.status for check in report.checks} == {"passed"}


def test_control_modes_preservation_blocks_missing_api_route(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = Path.cwd()
    files = [
        "backend/app/core/control_modes.py",
        "backend/app/core/coding_loop.py",
        "backend/app/api/control_modes.py",
        "backend/app/settings.py",
        "backend/app/dependencies.py",
        "backend/app/main.py",
        "cli/client.py",
        "cli/commands/control_cmd.py",
        "cli/commands/__init__.py",
        "cli/main.py",
        "tests/test_control_modes.py",
        "tests/test_control_modes_api.py",
        "tests/test_control_cli.py",
    ]
    for relative in files:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (source / relative).read_text(encoding="utf-8")
        if relative == "backend/app/api/control_modes.py":
            text = text.replace('@router.post("/goals/{goal_id}/advance", response_model=GoalRecord)', "")
        target.write_text(text, encoding="utf-8")

    report = build_report(workspace_root=workspace)

    assert report.status == "control_modes_preservation_blocked"
    check = next(check for check in report.checks if check.name == "api_routes_preserved")
    assert check.status == "failed"
    assert "POST /api/v1/control/goals/{goal_id}/advance" in check.details["missing_routes"]


def test_control_modes_preservation_blocks_loop_phase_drift(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    source = Path.cwd()
    files = [
        "backend/app/core/control_modes.py",
        "backend/app/core/coding_loop.py",
        "backend/app/api/control_modes.py",
        "backend/app/settings.py",
        "backend/app/dependencies.py",
        "backend/app/main.py",
        "cli/client.py",
        "cli/commands/control_cmd.py",
        "cli/commands/__init__.py",
        "cli/main.py",
        "tests/test_control_modes.py",
        "tests/test_control_modes_api.py",
        "tests/test_control_cli.py",
    ]
    for relative in files:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        text = (source / relative).read_text(encoding="utf-8")
        if relative == "backend/app/core/coding_loop.py":
            text = text.replace('("explore", "plan", "edit", "verify", "deliver")', '("plan", "edit", "verify")')
        target.write_text(text, encoding="utf-8")

    report = build_report(workspace_root=workspace)

    assert report.status == "control_modes_preservation_blocked"
    assert next(check for check in report.checks if check.name == "loop_phase_order_preserved").status == "failed"


def test_control_modes_preservation_writes_json_and_markdown(tmp_path: Path) -> None:
    report = build_report()
    json_output = tmp_path / "control-modes.json"
    md_output = tmp_path / "control-modes.md"

    write_report(report, json_output)
    write_markdown_report(report, md_output)

    assert "control_modes_preservation_ready" in json_output.read_text(encoding="utf-8")
    markdown = md_output.read_text(encoding="utf-8")
    assert "Commercial Delivery Control Modes Preservation" in markdown
    assert "xagent control goal advance --execute" in render_markdown_report(report)
