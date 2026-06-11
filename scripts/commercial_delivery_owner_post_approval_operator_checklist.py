#!/usr/bin/env python3
"""Build a read-only post-approval operator checklist.

The checklist turns the owner approval resume packet into an operator-facing
status view for the exact handoff sequence after human approval exists. It does
not create approval evidence, stage files, commit, push, call network services,
run tests, or execute agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_APPROVAL_RESUME_PACKET = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_STAGING_PREFLIGHT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_OWNER_POST_STAGING_VERIFIER = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_OWNER_COMMIT_PACKET = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.md"


@dataclass(frozen=True)
class OperatorChecklistItem:
    id: str
    title: str
    status: str
    executable_now: bool
    commands: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OperatorChecklistCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PostApprovalOperatorChecklist:
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
    real_owner_approval_present: bool
    waiting_for_owner: bool
    operator_ready: bool
    stage_allowed: bool
    stage_execution_ready: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checklist: list[OperatorChecklistItem]
    checks: list[OperatorChecklistCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checklist"] = [asdict(item) for item in self.checklist]
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["checklist_count"] = len(self.checklist)
        payload["checks_count"] = len(self.checks)
        payload["next_actions_count"] = len(self.next_actions)
        payload["known_limits_count"] = len(self.known_limits)
        return payload


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _command_groups(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = payload.get("command_groups")
    if not isinstance(groups, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for group in groups:
        if isinstance(group, dict) and group.get("name"):
            result[str(group["name"])] = group
    return result


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OperatorChecklistCheck:
    return OperatorChecklistCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _group_item(
    *,
    group: dict[str, Any] | None,
    item_id: str,
    title: str,
    status: str,
    executable_now: bool,
    default_notes: list[str] | None = None,
) -> OperatorChecklistItem:
    group = group or {}
    return OperatorChecklistItem(
        id=item_id,
        title=str(group.get("title") or title),
        status=status,
        executable_now=executable_now,
        commands=_list(group.get("commands")),
        prerequisites=_list(group.get("prerequisites")),
        notes=_list(group.get("notes")) or (default_notes or []),
    )


def build_post_approval_operator_checklist(
    *,
    owner_approval_resume_packet_path: Path = DEFAULT_OWNER_APPROVAL_RESUME_PACKET,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_staging_preflight_path: Path = DEFAULT_OWNER_STAGING_PREFLIGHT,
    owner_post_staging_verifier_path: Path = DEFAULT_OWNER_POST_STAGING_VERIFIER,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    owner_commit_packet_path: Path = DEFAULT_OWNER_COMMIT_PACKET,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> PostApprovalOperatorChecklist:
    report_paths = {
        "owner_approval_resume_packet": owner_approval_resume_packet_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "owner_staging_preflight": owner_staging_preflight_path,
        "owner_post_staging_verifier": owner_post_staging_verifier_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "owner_commit_packet": owner_commit_packet_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    resume_packet = reports["owner_approval_resume_packet"]
    approval_gate = reports["owner_stage_approval_gate"]
    execution_plan = reports["owner_stage_execution_plan"]
    preflight = reports["owner_staging_preflight"]
    post_staging = reports["owner_post_staging_verifier"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    commit_packet = reports["owner_commit_packet"]
    resume_summary = _summary(resume_packet)
    groups = _command_groups(resume_packet)

    real_owner_approval_present = owner_approval_path.exists()
    waiting_for_owner = (
        _status(resume_packet) == "owner_approval_resume_packet_waiting_for_owner"
        and resume_packet.get("waiting_for_owner") is True
        and not real_owner_approval_present
    )
    resume_ready = (
        _status(resume_packet) == "owner_approval_resume_packet_ready"
        and resume_packet.get("resume_ready") is True
        and real_owner_approval_present
    )
    post_commit_noop_resume_ready = (
        resume_ready
        and resume_summary.get("post_commit_noop_resume_ready") is True
        and resume_summary.get("post_commit_noop_accounted_for") is True
    )
    stage_allowed = _status(approval_gate) == "owner_stage_approval_ready" and approval_gate.get("stage_allowed") is True
    stage_execution_ready = (
        _status(execution_plan) == "owner_stage_execution_ready"
        and execution_plan.get("stage_allowed") is True
    )
    preflight_ready = _status(preflight) == "owner_staging_preflight_ready"
    post_staging_ready = _status(post_staging) == "owner_post_staging_verification_ready"
    commit_gate_ready = _status(commit_gate) == "owner_post_stage_commit_gate_ready"
    commit_packet_ready = _status(commit_packet) == "owner_commit_packet_ready" and commit_packet.get("commit_allowed") is True
    post_stage_sequence_accounted_for = (
        resume_ready
        and stage_allowed
        and stage_execution_ready
        and _status(preflight) == "owner_staging_preflight_blocked"
        and int(preflight.get("cached_staged_path_count") or 0) > 0
        and post_staging_ready
        and commit_gate_ready
        and commit_packet_ready
    )
    post_commit_noop_sequence_accounted_for = (
        post_commit_noop_resume_ready
        and _status(preflight) == "owner_staging_preflight_ready"
        and int(preflight.get("cached_staged_path_count") or 0) == 0
        and post_staging_ready
        and commit_gate_ready
        and commit_packet_ready
    )
    pre_stage_ready = resume_ready and stage_allowed and stage_execution_ready and preflight_ready
    operator_ready = pre_stage_ready or post_stage_sequence_accounted_for or post_commit_noop_sequence_accounted_for

    checklist = [
        _group_item(
            group=groups.get("owner_create_approval_payload"),
            item_id="owner_create_approval_payload",
            title="Owner creates real approval payload",
            status="waiting" if waiting_for_owner else "complete" if real_owner_approval_present else "blocked",
            executable_now=waiting_for_owner,
            default_notes=["This checklist never writes the real owner approval payload."],
        ),
        _group_item(
            group=groups.get("approval_payload_audit"),
            item_id="approval_payload_audit",
            title="Audit the real approval payload",
            status="ready" if real_owner_approval_present else "waiting",
            executable_now=real_owner_approval_present,
        ),
        _group_item(
            group=groups.get("approval_gate"),
            item_id="approval_gate",
            title="Validate owner stage approval gate",
            status="ready" if stage_allowed else "waiting",
            executable_now=real_owner_approval_present,
        ),
        _group_item(
            group=groups.get("stage_execution_plan"),
            item_id="stage_execution_plan",
            title="Regenerate owner stage execution plan",
            status="ready" if stage_execution_ready else "waiting",
            executable_now=stage_allowed,
        ),
        _group_item(
            group=groups.get("pre_stage_verification"),
            item_id="pre_stage_verification",
            title="Run pre-stage verification",
            status=(
                "ready"
                if pre_stage_ready
                else "complete"
                if post_stage_sequence_accounted_for or post_commit_noop_sequence_accounted_for
                else "waiting"
            ),
            executable_now=pre_stage_ready,
            default_notes=["Run immediately before any git add command."],
        ),
        _group_item(
            group=groups.get("owner_stage_commands"),
            item_id="owner_stage_commands",
            title="Run owner-approved stage commands",
            status=(
                "ready"
                if pre_stage_ready
                else "complete"
                if post_stage_sequence_accounted_for or post_commit_noop_sequence_accounted_for
                else "waiting"
            ),
            executable_now=pre_stage_ready,
            default_notes=["Run only exact git add commands; never use git add ., git add -A, or git add --all."],
        ),
        _group_item(
            group=groups.get("post_stage_verification"),
            item_id="post_stage_verification",
            title="Run post-stage verification",
            status="ready" if post_staging_ready else "waiting",
            executable_now=False,
        ),
        _group_item(
            group=groups.get("commit_gate_and_packet"),
            item_id="commit_gate_and_packet",
            title="Regenerate commit gate and commit packet",
            status="ready" if commit_gate_ready and commit_packet_ready else "waiting",
            executable_now=post_staging_ready,
        ),
        _group_item(
            group=groups.get("post_commit_evidence_refresh"),
            item_id="post_commit_evidence_refresh",
            title="Refresh final delivery evidence",
            status="ready" if commit_packet_ready else "waiting",
            executable_now=commit_packet_ready,
        ),
    ]
    stage_command_count = len(next(item for item in checklist if item.id == "owner_stage_commands").commands)
    full_codex_parity_claimed = any(payload.get("full_codex_parity_claimed") is True for payload in reports.values())
    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="operator checklist inputs are missing"),
        _check(
            "resume_packet_accounted_for",
            waiting_for_owner or resume_ready,
            details={
                "resume_packet_status": _status(resume_packet),
                "waiting_for_owner": resume_packet.get("waiting_for_owner"),
                "resume_ready": resume_packet.get("resume_ready"),
                "real_owner_approval_present": real_owner_approval_present,
            },
            error="resume packet is neither waiting for owner nor ready",
        ),
        _check(
            "operator_sequence_present",
            bool(checklist) and (stage_command_count > 0 or post_commit_noop_sequence_accounted_for),
            details={
                "checklist_count": len(checklist),
                "stage_command_count": stage_command_count,
                "post_commit_noop_sequence_accounted_for": post_commit_noop_sequence_accounted_for,
            },
            error="operator checklist is missing stage commands",
        ),
        _check(
            "approval_gate_matches_resume",
            waiting_for_owner or stage_allowed or post_commit_noop_sequence_accounted_for,
            details={
                "owner_stage_approval_gate_status": _status(approval_gate),
                "stage_allowed": approval_gate.get("stage_allowed"),
                "post_commit_noop_sequence_accounted_for": post_commit_noop_sequence_accounted_for,
            },
            error="approval gate is not ready after resume readiness",
        ),
        _check(
            "stage_execution_matches_resume",
            waiting_for_owner or stage_execution_ready or post_commit_noop_sequence_accounted_for,
            details={
                "owner_stage_execution_plan_status": _status(execution_plan),
                "stage_allowed": execution_plan.get("stage_allowed"),
                "post_commit_noop_sequence_accounted_for": post_commit_noop_sequence_accounted_for,
            },
            error="stage execution plan is not ready after resume readiness",
        ),
        _check(
            "operator_state_accounted_for",
            waiting_for_owner
            or pre_stage_ready
            or post_stage_sequence_accounted_for
            or post_commit_noop_sequence_accounted_for,
            details={
                "pre_stage_ready": pre_stage_ready,
                "post_stage_sequence_accounted_for": post_stage_sequence_accounted_for,
                "post_commit_noop_sequence_accounted_for": post_commit_noop_sequence_accounted_for,
                "owner_staging_preflight_status": _status(preflight),
                "owner_staging_preflight_cached_staged_path_count": preflight.get("cached_staged_path_count"),
                "owner_post_staging_verifier_status": _status(post_staging),
                "owner_post_stage_commit_gate_status": _status(commit_gate),
                "owner_commit_packet_status": _status(commit_packet),
            },
            error="operator state is neither waiting, pre-stage ready, nor accounted for after staging",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more operator checklist inputs claim full Codex parity",
        ),
        _check(
            "no_operator_checklist_mutation",
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
    checks_passed = all(check.status == "passed" for check in checks)
    if checks_passed and operator_ready:
        status = "owner_post_approval_operator_checklist_ready"
    elif checks_passed and waiting_for_owner:
        status = "owner_post_approval_operator_checklist_waiting_for_owner"
    else:
        status = "owner_post_approval_operator_checklist_blocked"

    if status == "owner_post_approval_operator_checklist_ready":
        next_actions = [
            "Run the pre-stage verification checklist item immediately before staging.",
            "Run only the owner_stage_commands listed here and in the resume packet.",
            "After staging, rerun post-stage verification and commit gates.",
        ]
    elif status == "owner_post_approval_operator_checklist_waiting_for_owner":
        next_actions = [
            "Wait for the human owner to create the real owner approval payload.",
            "After approval exists, rerun the resume packet and this checklist.",
            "Do not stage while this checklist is waiting_for_owner.",
        ]
    else:
        next_actions = [
            "Refresh the owner approval resume packet and gate reports before operator handoff.",
            "Do not stage, commit, or push while this checklist is blocked.",
        ]

    return PostApprovalOperatorChecklist(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_post_approval_operator_checklist",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        real_owner_approval_present=real_owner_approval_present,
        waiting_for_owner=status == "owner_post_approval_operator_checklist_waiting_for_owner",
        operator_ready=status == "owner_post_approval_operator_checklist_ready",
        stage_allowed=stage_allowed,
        stage_execution_ready=stage_execution_ready,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "stage_include_count": resume_summary.get("stage_include_count"),
            "stage_command_count": stage_command_count,
            "pre_stage_verification_command_count": len(
                next(item for item in checklist if item.id == "pre_stage_verification").commands
            ),
            "post_stage_verification_command_count": len(
                next(item for item in checklist if item.id == "post_stage_verification").commands
            ),
            "owner_approval_resume_packet_status": _status(resume_packet),
            "owner_stage_approval_gate_status": _status(approval_gate),
            "owner_stage_execution_plan_status": _status(execution_plan),
            "owner_staging_preflight_status": _status(preflight),
            "owner_staging_preflight_cached_staged_path_count": preflight.get("cached_staged_path_count"),
            "owner_post_staging_verifier_status": _status(post_staging),
            "owner_post_stage_commit_gate_status": _status(commit_gate),
            "owner_commit_packet_status": _status(commit_packet),
            "pre_stage_ready": pre_stage_ready,
            "post_stage_sequence_accounted_for": post_stage_sequence_accounted_for,
            "post_commit_noop_sequence_accounted_for": post_commit_noop_sequence_accounted_for,
            "secondary_handoff_completed_count": resume_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": resume_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "secondary_handoff_next_queue": resume_summary.get("secondary_handoff_next_queue"),
            "control_modes_preservation_status": resume_summary.get("control_modes_preservation_status"),
            "control_modes_plan_only_default": resume_summary.get("control_modes_plan_only_default"),
            "control_modes_loop_phases": resume_summary.get("control_modes_loop_phases"),
            "blocking_reasons": [check.name for check in checks if check.status != "passed"],
        },
        checklist=checklist,
        checks=checks,
        next_actions=next_actions,
        known_limits=[
            "This checklist is read-only except writing local evidence files.",
            "It does not write or infer real owner approval evidence.",
            "It does not stage files, reset files, commit, push, call network services, run tests, or execute agents.",
            "It does not claim full Codex parity or commercial delivery completion.",
        ],
    )


def render_markdown_checklist(report: PostApprovalOperatorChecklist) -> str:
    lines = [
        "# Commercial Delivery Post-Approval Operator Checklist",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Waiting for owner: `{str(report.waiting_for_owner).lower()}`",
        f"- Operator ready: `{str(report.operator_ready).lower()}`",
        f"- Real owner approval present: `{str(report.real_owner_approval_present).lower()}`",
        f"- Stage allowed: `{str(report.stage_allowed).lower()}`",
        f"- Stage execution ready: `{str(report.stage_execution_ready).lower()}`",
        f"- Stage command count: `{report.summary.get('stage_command_count')}`",
        f"- Secondary latest completed candidate: `{report.summary.get('secondary_handoff_latest_completed_candidate')}`",
        "",
        "## Checklist",
        "",
    ]
    for item in report.checklist:
        lines.extend(
            [
                f"### {item.id}",
                "",
                f"- Title: {item.title}",
                f"- Status: `{item.status}`",
                f"- Executable now: `{str(item.executable_now).lower()}`",
                f"- Prerequisites: `{', '.join(item.prerequisites)}`",
            ]
        )
        if item.commands:
            lines.append("- Commands:")
            lines.extend(f"  - `{command}`" for command in item.commands)
        if item.notes:
            lines.append("- Notes:")
            lines.extend(f"  - {note}" for note in item.notes)
        lines.append("")
    lines.extend(["## Checks", ""])
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in report.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(report: PostApprovalOperatorChecklist, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_checklist(
    report: PostApprovalOperatorChecklist,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_checklist(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-approval-resume-packet", type=Path, default=DEFAULT_OWNER_APPROVAL_RESUME_PACKET)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--owner-staging-preflight", type=Path, default=DEFAULT_OWNER_STAGING_PREFLIGHT)
    parser.add_argument("--owner-post-staging-verifier", type=Path, default=DEFAULT_OWNER_POST_STAGING_VERIFIER)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--owner-commit-packet", type=Path, default=DEFAULT_OWNER_COMMIT_PACKET)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checklist = build_post_approval_operator_checklist(
        owner_approval_resume_packet_path=args.owner_approval_resume_packet,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_staging_preflight_path=args.owner_staging_preflight,
        owner_post_staging_verifier_path=args.owner_post_staging_verifier,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        owner_commit_packet_path=args.owner_commit_packet,
        owner_approval_path=args.owner_approval,
    )
    write_report(checklist, args.output)
    write_markdown_checklist(checklist, args.markdown_output)
    print(f"Commercial delivery post-approval operator checklist status: {checklist.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Waiting for owner: {checklist.waiting_for_owner}")
    print(f"Operator ready: {checklist.operator_ready}")
    for check in checklist.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if checklist.status in {
        "owner_post_approval_operator_checklist_ready",
        "owner_post_approval_operator_checklist_waiting_for_owner",
    } else 1


if __name__ == "__main__":
    raise SystemExit(main())
