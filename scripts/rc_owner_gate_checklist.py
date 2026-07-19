#!/usr/bin/env python3
"""Render a release-owner checklist for commercial RC external gates.

The owner gate plan is machine-readable, but deployment owners still need a
copyable handoff that explains which resources are missing and which command
must be run next. This script renders that handoff without printing or storing
secret values.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_PLAN = REPORT_DIR / "rc-owner-gate-plan.json"
DEFAULT_JSON_OUTPUT = REPORT_DIR / "rc-owner-gate-checklist.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "rc-owner-gate-checklist.md"
LOCAL_HANDOFF_PATH_RE = re.compile(
    r"(?i)(?:[A-Z]:[\\/]|/(?:home|Users|tmp|var)/)(?:(?![\"'\s`<>]).)*?"
    r"([\\/]\.xagent_runtime[\\/][^\"'\s`,)]+)"
)


@dataclass(frozen=True)
class ChecklistGate:
    name: str
    status: str
    complete: bool
    action_required: bool
    required_env_groups: list[list[str]]
    configured_env: list[str]
    missing: list[str]
    command: str
    evidence: list[str]
    completion_criteria: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerGateChecklist:
    status: str
    generated_at: str
    owner_gate_plan: str
    source_bundle_report: str | None
    external_smoke_report: str | None
    evidence_freshness: dict[str, Any]
    gates: list[ChecklistGate]
    next_commands: list[str]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gates"] = [asdict(gate) for gate in self.gates]
        return _handoff_value(payload)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _handoff_text(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return match.group(1).replace("\\", "/").lstrip("/")

    return LOCAL_HANDOFF_PATH_RE.sub(replace, value)


def _handoff_value(value: Any) -> Any:
    if isinstance(value, str):
        return _handoff_text(value)
    if isinstance(value, list):
        return [_handoff_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _handoff_value(item) for key, item in value.items()}
    return value


def _handoff_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)).as_posix()
    except ValueError:
        return _handoff_text(str(path))


def _read_plan(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"owner gate plan is missing: {path}"]
    except json.JSONDecodeError as exc:
        return None, [f"owner gate plan is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, ["owner gate plan must be a JSON object"]
    return payload, []


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _env_groups(value: Any) -> list[list[str]]:
    if not isinstance(value, list):
        return []
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list):
            continue
        names = [str(item) for item in group if str(item).strip()]
        if names:
            groups.append(names)
    return groups


EXTERNAL_CHECKS_BY_GATE = {
    "provider": ("provider",),
    "feishu_webhook_contract": ("feishu_webhook_contract",),
    "github_issue_to_pr_dry_run": ("github_issue_to_pr_dry_run",),
    "github_issue_to_pr_execute_preflight": ("github_issue_to_pr_dry_run", "github_issue_to_pr_execute_preflight"),
    "hosted_github_actions_commercial_rc": ("hosted_github_actions_run",),
}


def _external_checks_by_name(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    checks = payload.get("checks") if isinstance(payload, dict) else []
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name")): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }


def _external_notes(gate_name: str, checks_by_name: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for check_name in EXTERNAL_CHECKS_BY_GATE.get(gate_name, (gate_name,)):
        check = checks_by_name.get(check_name)
        if not check:
            continue
        status = str(check.get("status") or "unknown")
        if status == "passed":
            continue
        notes.append(f"External smoke {check_name} is {status}.")
        for item in _string_list(check.get("missing")):
            notes.append(f"External smoke {check_name} missing: {item}")
        error = str(check.get("error") or "")
        if error:
            notes.append(f"External smoke {check_name} error: {error}")
    return notes


def _gate_from_payload(payload: dict[str, Any], checks_by_name: dict[str, dict[str, Any]] | None = None) -> ChecklistGate:
    status = str(payload.get("status") or "unknown")
    name = str(payload.get("name") or "owner_gate")
    return ChecklistGate(
        name=name,
        status=status,
        complete=status == "verified",
        action_required=status != "verified",
        required_env_groups=_env_groups(payload.get("required_env_groups")),
        configured_env=_string_list(payload.get("configured_env")),
        missing=_string_list(payload.get("missing")),
        command=str(payload.get("command") or ""),
        evidence=_string_list(payload.get("evidence")),
        completion_criteria=_string_list(payload.get("completion_criteria")),
        notes=[
            *_string_list(payload.get("notes")),
            *_external_notes(name, checks_by_name or {}),
        ],
    )


def build_checklist(plan_path: Path = DEFAULT_PLAN) -> OwnerGateChecklist:
    plan, errors = _read_plan(plan_path)
    if plan is None:
        return OwnerGateChecklist(
            status="failed",
            generated_at=_utc_now(),
            owner_gate_plan=_handoff_path(plan_path),
            source_bundle_report=None,
            external_smoke_report=None,
            evidence_freshness={},
            gates=[],
            next_commands=[f"python scripts\\rc_owner_gate_plan.py --output {plan_path}"],
            errors=errors,
        )

    external_smoke_report = str(plan.get("external_smoke_report") or "")
    external_payload = _read_json_object(Path(external_smoke_report)) if external_smoke_report else None
    checks_by_name = _external_checks_by_name(external_payload)
    raw_gates = plan.get("gates")
    gates = (
        [_gate_from_payload(item, checks_by_name) for item in raw_gates if isinstance(item, dict)]
        if isinstance(raw_gates, list)
        else []
    )
    plan_status = str(plan.get("status") or "unknown")
    checklist_errors: list[str] = []
    if not isinstance(raw_gates, list) or not gates:
        checklist_errors.append("owner gate plan contains no gate entries")

    if checklist_errors:
        status = "failed"
    elif all(gate.complete for gate in gates) and plan_status == "verified":
        status = "verified"
    elif any(gate.status == "action_required" for gate in gates) or plan_status == "action_required":
        status = "action_required"
    else:
        status = "ready_to_run"

    freshness = plan.get("evidence_freshness")
    return OwnerGateChecklist(
        status=status,
        generated_at=_utc_now(),
        owner_gate_plan=_handoff_path(plan_path),
        source_bundle_report=(
            _handoff_text(str(plan.get("source_bundle_report"))) if plan.get("source_bundle_report") is not None else None
        ),
        external_smoke_report=_handoff_text(external_smoke_report),
        evidence_freshness=_handoff_value(freshness) if isinstance(freshness, dict) else {},
        gates=gates,
        next_commands=[_handoff_text(command) for command in _string_list(plan.get("next_commands"))],
        errors=checklist_errors,
    )


def _bullet_list(items: list[str], *, empty: str = "None") -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def _required_env_lines(groups: list[list[str]]) -> list[str]:
    if not groups:
        return ["- None"]
    lines: list[str] = []
    for group in groups:
        primary = group[0]
        aliases = group[1:]
        alias_text = f" (aliases: {', '.join(aliases)})" if aliases else ""
        lines.append(f"- {primary}{alias_text}")
    return lines


def _markdown_gate(gate: ChecklistGate) -> str:
    checkbox = "x" if gate.complete else " "
    lines = [
        f"## [{checkbox}] {gate.name}",
        "",
        f"- Status: `{gate.status}`",
        f"- Complete: `{str(gate.complete).lower()}`",
        "",
        "Required environment variable groups:",
        *_required_env_lines(gate.required_env_groups),
        "",
        "Configured environment variable names:",
        *_bullet_list(gate.configured_env),
        "",
        "Missing owner actions:",
        *_bullet_list(gate.missing, empty="No missing owner action recorded."),
        "",
        "Command:",
        "```powershell",
        gate.command or "# No command recorded",
        "```",
        "",
        "Required evidence:",
        *_bullet_list(gate.evidence),
        "",
        "Completion criteria:",
        *_bullet_list(gate.completion_criteria),
    ]
    if gate.notes:
        lines.extend(["", "Notes:", *_bullet_list(gate.notes)])
    return "\n".join(lines)


def render_markdown(checklist: OwnerGateChecklist) -> str:
    complete = sum(1 for gate in checklist.gates if gate.complete)
    total = len(checklist.gates)
    lines = [
        "# X-Agent Commercial RC Owner Gate Checklist",
        "",
        f"Generated at: `{checklist.generated_at}`",
        f"Status: `{checklist.status}`",
        f"Owner gate plan: `{checklist.owner_gate_plan}`",
        f"External smoke report: `{checklist.external_smoke_report or 'missing'}`",
        f"Source bundle report: `{checklist.source_bundle_report or 'not provided'}`",
        f"Gate completion: `{complete}/{total}`",
        "",
        "This checklist intentionally records environment variable names and",
        "commands only. It must not contain secret values, tokens, or API keys.",
        "",
    ]
    if checklist.evidence_freshness:
        lines.extend(
            [
                "## Evidence Freshness",
                "",
                f"- Fresh: `{str(checklist.evidence_freshness.get('fresh')).lower()}`",
                f"- External generated at: `{checklist.evidence_freshness.get('external_generated_at')}`",
                f"- Source bundle generated at: `{checklist.evidence_freshness.get('source_bundle_generated_at')}`",
                "",
                "Freshness problems:",
                *_bullet_list([str(item) for item in checklist.evidence_freshness.get("problems", [])]),
                "",
            ]
        )
    if checklist.errors:
        lines.extend(["## Errors", "", *_bullet_list(checklist.errors), ""])
    lines.extend(["## Next Commands", "", *_bullet_list(checklist.next_commands), ""])
    lines.extend(_markdown_gate(gate) + "\n" for gate in checklist.gates)
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(checklist: OwnerGateChecklist, *, json_output: Path, markdown_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(checklist.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(render_markdown(checklist), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the X-Agent commercial RC owner gate checklist")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument(
        "--fail-action-required",
        action="store_true",
        help="return non-zero unless every owner gate is verified",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checklist = build_checklist(args.plan)
    write_outputs(checklist, json_output=args.json_output, markdown_output=args.markdown_output)
    print(f"RC owner gate checklist status: {checklist.status}")
    print(f"JSON written to {args.json_output}")
    print(f"Markdown written to {args.markdown_output}")
    for gate in checklist.gates:
        print(f"- {gate.name}: {gate.status}")
    if checklist.status == "failed":
        return 1
    if args.fail_action_required and checklist.status != "verified":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
