#!/usr/bin/env python3
"""Verify plan mode and loop-engineering control surfaces are preserved.

This read-only report covers the user-requested control mode delivery surface:
plan-only drafts, approval-gated goal advancement, execute=true as the explicit
agent execution boundary, fixed coding-loop phases, API wiring, CLI wiring, and
JSON store configuration. It does not create plans or goals, run agents, stage
files, commit, push, call network services, or mutate runtime state.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-control-modes-preservation.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-control-modes-preservation.md"
EXPECTED_LOOP_PHASES = ["explore", "plan", "edit", "verify", "deliver"]
EXPECTED_API_ROUTES = [
    ("POST", "/plans"),
    ("GET", "/plans"),
    ("GET", "/plans/{plan_id}"),
    ("POST", "/plans/{plan_id}/approve"),
    ("POST", "/plans/{plan_id}/reject"),
    ("POST", "/goals"),
    ("GET", "/goals"),
    ("GET", "/goals/{goal_id}"),
    ("POST", "/goals/{goal_id}/advance"),
    ("POST", "/goals/{goal_id}/cancel"),
]
EXPECTED_CLI_MARKERS = [
    'control_app.add_typer(plan_app, name="plan")',
    'control_app.add_typer(goal_app, name="goal")',
    '@plan_app.command("draft")',
    '@plan_app.command("approve")',
    '@plan_app.command("reject")',
    '@goal_app.command("create")',
    '@goal_app.command("advance")',
    '@goal_app.command("show")',
    '@goal_app.command("list")',
    '@goal_app.command("cancel")',
]
CONTROL_SURFACE_FILES = [
    "backend/app/core/control_modes.py",
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


@dataclass(frozen=True)
class ControlModesPreservationCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ControlModesPreservationReport:
    status: str
    generated_at: str
    evidence_type: str
    owner_gated: bool
    mutation_performed: bool
    git_stage_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    agent_execution_enabled: bool
    full_codex_parity_claimed: bool
    control_surface_files: list[str]
    expected_api_routes: list[str]
    expected_cli_commands: list[str]
    summary: dict[str, Any]
    checks: list[ControlModesPreservationCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
        return payload


def _read_text(path: Path) -> tuple[str, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except FileNotFoundError:
        return "", f"file not found: {_display_path(path)}"
    except OSError as exc:
        return "", f"could not read {_display_path(path)}: {exc}"


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> ControlModesPreservationCheck:
    return ControlModesPreservationCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _contains_all(text: str, markers: list[str]) -> tuple[bool, list[str]]:
    missing = [marker for marker in markers if marker not in text]
    return not missing, missing


def _api_route_markers(api_text: str) -> list[str]:
    found: list[str] = []
    for method, path in EXPECTED_API_ROUTES:
        marker = f'@router.{method.lower()}("{path}"'
        if marker in api_text:
            found.append(f"{method} /api/v1/control{path}")
    return found


def _route_functions(api_text: str) -> list[str]:
    return re.findall(r"^async def ([a-zA-Z0-9_]+)\(", api_text, flags=re.MULTILINE)


def _loop_phase_order_present(coding_loop_text: str) -> bool:
    return bool(
        re.search(
            r"CODING_LOOP_PHASES[^=]*=\s*\(\s*"
            r'"explore",\s*"plan",\s*"edit",\s*"verify",\s*"deliver"\s*\)',
            coding_loop_text,
            flags=re.DOTALL,
        )
    )


def _path_statuses(workspace_root: Path) -> dict[str, bool]:
    return {
        path: (workspace_root / path).exists()
        for path in CONTROL_SURFACE_FILES
    }


def build_report(*, workspace_root: str | Path = ROOT) -> ControlModesPreservationReport:
    workspace = Path(workspace_root).resolve()
    path_statuses = _path_statuses(workspace)
    texts: dict[str, str] = {}
    errors: dict[str, str] = {}
    for path in CONTROL_SURFACE_FILES:
        text, error = _read_text(workspace / path)
        texts[path] = text
        if error:
            errors[path] = error

    core_text = texts.get("backend/app/core/control_modes.py", "")
    coding_loop_text = _read_text(workspace / "backend/app/core/coding_loop.py")[0]
    api_text = texts.get("backend/app/api/control_modes.py", "")
    main_text = texts.get("backend/app/main.py", "")
    settings_text = texts.get("backend/app/settings.py", "")
    dependencies_text = texts.get("backend/app/dependencies.py", "")
    cli_client_text = texts.get("cli/client.py", "")
    cli_command_text = texts.get("cli/commands/control_cmd.py", "")
    cli_init_text = texts.get("cli/commands/__init__.py", "")
    cli_main_text = texts.get("cli/main.py", "")
    unit_test_text = texts.get("tests/test_control_modes.py", "")
    api_test_text = texts.get("tests/test_control_modes_api.py", "")
    cli_test_text = texts.get("tests/test_control_cli.py", "")

    route_markers = _api_route_markers(api_text)
    missing_api_routes = [
        f"{method} /api/v1/control{path}"
        for method, path in EXPECTED_API_ROUTES
        if f"{method} /api/v1/control{path}" not in route_markers
    ]
    cli_markers_ok, missing_cli_markers = _contains_all(cli_command_text, EXPECTED_CLI_MARKERS)
    loop_phase_literal = 'CODING_LOOP_PHASES: tuple[str, ...] = ("explore", "plan", "edit", "verify", "deliver")'
    core_markers = [
        "class PlanModeService",
        "class GoalLoopService",
        "class ControlModeStore",
        "class GoalAdvanceRequest",
        "execute: bool = False",
        "require_plan_approval: bool = True",
        "auto_execute: bool = False",
        "requires_execution\": False",
        "mode\": \"plan_only",
        "Set execute=true to run it.",
    ]
    core_markers_ok, missing_core_markers = _contains_all(core_text, core_markers)
    api_execution_markers = [
        "if not request.execute:",
        "service.advance_without_execution",
        "result = await agent.run(",
        '"loop_engineering": True',
        '"phase_order": ["explore", "plan", "edit", "verify", "deliver"]',
    ]
    api_execution_ok, missing_api_execution = _contains_all(api_text, api_execution_markers)
    test_markers = [
        "test_plan_mode_draft_requires_approval_and_contains_loop_contract",
        "test_goal_advance_plan_only_blocks_until_approved",
        "test_goal_advance_plan_only_adds_next_iteration_after_approval",
        "test_control_goal_api_execute_advance_records_agent_result",
        "test_control_cli_group_is_registered",
    ]
    all_tests_text = "\n".join([unit_test_text, api_test_text, cli_test_text])
    tests_ok, missing_test_markers = _contains_all(all_tests_text, test_markers)

    checks = [
        _check(
            "control_surface_files_exist",
            all(path_statuses.values()) and not errors,
            details={"paths": path_statuses, "errors": errors},
            error="one or more plan mode or goal-loop control surface files are missing",
        ),
        _check(
            "loop_phase_order_preserved",
            _loop_phase_order_present(coding_loop_text)
            and "from backend.app.core.coding_loop import CODING_LOOP_PHASES" in core_text
            and "list(CODING_LOOP_PHASES)" in core_text,
            details={
                "expected_phases": EXPECTED_LOOP_PHASES,
                "literal": loop_phase_literal,
                "core_imports_phase_contract": "from backend.app.core.coding_loop import CODING_LOOP_PHASES" in core_text,
                "core_serializes_phase_contract": "list(CODING_LOOP_PHASES)" in core_text,
            },
            error="coding loop phases are missing or not fixed to explore -> plan -> edit -> verify -> deliver",
        ),
        _check(
            "plan_mode_core_contract_preserved",
            core_markers_ok,
            details={"missing_markers": missing_core_markers},
            error="plan mode or goal loop core contract markers are missing",
        ),
        _check(
            "api_routes_preserved",
            not missing_api_routes and 'router = APIRouter(prefix="/api/v1/control"' in api_text,
            details={"routes": route_markers, "missing_routes": missing_api_routes, "route_functions": _route_functions(api_text)},
            error="one or more control mode API routes are missing",
        ),
        _check(
            "api_execution_boundary_preserved",
            api_execution_ok,
            details={"missing_markers": missing_api_execution},
            error="control goal API no longer preserves the plan-only default or execute=true boundary",
        ),
        _check(
            "api_router_mounted",
            "from backend.app.api.control_modes import router as control_modes_router" in main_text
            and "app.include_router(control_modes_router)" in main_text,
            details={"main_py": "backend/app/main.py"},
            error="control mode API router is not mounted in backend/app/main.py",
        ),
        _check(
            "store_dependency_configured",
            "control_mode_store_path" in settings_text
            and "def get_control_mode_store()" in dependencies_text
            and "ControlModeStore(storage_path=settings.control_mode_store_path)" in dependencies_text,
            details={"settings": "backend/app/settings.py", "dependencies": "backend/app/dependencies.py"},
            error="control mode JSON store setting or dependency factory is missing",
        ),
        _check(
            "cli_surface_preserved",
            cli_markers_ok
            and "from cli.commands.control_cmd import control_app" in cli_init_text
            and 'app.add_typer(control_app, name="control"' in cli_main_text,
            details={"missing_markers": missing_cli_markers},
            error="control CLI command surface or registration is missing",
        ),
        _check(
            "cli_client_routes_preserved",
            all(route in cli_client_text for route in [
                "/api/v1/control/plans",
                "/api/v1/control/goals",
                "/api/v1/control/goals/{goal_id}",
                "/advance",
                '"execute": execute',
            ]),
            details={"client": "cli/client.py"},
            error="CLI client control API methods are missing expected route markers",
        ),
        _check(
            "tests_cover_control_contract",
            tests_ok,
            details={"missing_markers": missing_test_markers},
            error="control mode preservation tests do not cover plan mode, API, and CLI surfaces",
        ),
        _check(
            "no_preservation_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
            },
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    return ControlModesPreservationReport(
        status="control_modes_preservation_ready" if ready else "control_modes_preservation_blocked",
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_control_modes_preservation",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=False,
        control_surface_files=CONTROL_SURFACE_FILES,
        expected_api_routes=route_markers,
        expected_cli_commands=[
            "xagent control plan draft",
            "xagent control plan approve",
            "xagent control plan reject",
            "xagent control goal create",
            "xagent control goal advance",
            "xagent control goal advance --execute",
            "xagent control goal show",
            "xagent control goal list",
            "xagent control goal cancel",
        ],
        summary={
            "control_surface_file_count": len(CONTROL_SURFACE_FILES),
            "api_route_count": len(route_markers),
            "cli_command_count": 9,
            "loop_phases": EXPECTED_LOOP_PHASES,
            "plan_only_default": True,
            "execute_true_required_for_agent_run": True,
            "owner_gated_mainline_surface": True,
            "stage_in_original_kernel_manifest": False,
        },
        checks=checks,
        next_actions=[
            "Keep this control surface out of original-kernel staging unless the owner approves API/router/entrypoint inclusion.",
            "Run the targeted control mode unit, API, and CLI tests before any owner-gated mainline integration commit.",
            "Do not enable automatic agent execution; goal advance remains plan-only unless execute=true is supplied.",
            "Preserve the coding loop order: explore -> plan -> edit -> verify -> deliver.",
        ],
        known_limits=[
            "This report is read-only except writing local evidence files.",
            "It checks source-level preservation and does not create live plans, goals, approvals, or agent runs.",
            "It does not stage API router, main.py, settings, dependencies, CLI, or test files.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_report(report: ControlModesPreservationReport) -> str:
    lines = [
        "# Commercial Delivery Control Modes Preservation",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Owner gated: `{str(report.owner_gated).lower()}`",
        f"- Control surface files: `{report.summary['control_surface_file_count']}`",
        f"- API routes: `{report.summary['api_route_count']}`",
        f"- CLI commands: `{report.summary['cli_command_count']}`",
        f"- Plan-only default: `{str(report.summary['plan_only_default']).lower()}`",
        f"- Execute=true required for agent run: `{str(report.summary['execute_true_required_for_agent_run']).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## API Routes", ""])
    lines.extend(f"- `{route}`" for route in report.expected_api_routes)
    lines.extend(["", "## CLI Commands", ""])
    lines.extend(f"- `{command}`" for command in report.expected_cli_commands)
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(report: ControlModesPreservationReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: ControlModesPreservationReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_report(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(workspace_root=args.workspace_root)
    write_report(report, args.output)
    write_markdown_report(report, args.markdown_output)
    print(f"Commercial delivery control modes preservation status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "control_modes_preservation_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
