#!/usr/bin/env python3
"""Build an owner-facing runbook for explicit commercial delivery staging.

The runbook reads existing ready reports and packages the exact sequence an
owner should follow: pre-stage checks, explicit stage commands, post-stage
verification, and commit preview. It does not execute any command, stage files,
create commits, push, call network services, or run agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_PRE_STAGE_GATE = REPORT_DIR / "commercial-delivery-owner-pre-stage-readiness-gate.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-runbook.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-runbook.md"


@dataclass(frozen=True)
class OwnerStagingRunbookCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStagingRunbookSection:
    name: str
    title: str
    commands: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OwnerStagingRunbook:
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
    reports: dict[str, str]
    summary: dict[str, Any]
    sections: list[OwnerStagingRunbookSection]
    checks: list[OwnerStagingRunbookCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sections"] = [asdict(section) for section in self.sections]
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
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


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStagingRunbookCheck:
    return OwnerStagingRunbookCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _has_broad_stage_command(commands: list[str]) -> bool:
    normalized = {" ".join(command.strip().lower().split()) for command in commands}
    return bool(normalized.intersection({"git add .", "git add -a", "git add --all", "git add -- ."}))


def build_owner_staging_runbook(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    pre_stage_gate_path: Path = DEFAULT_PRE_STAGE_GATE,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerStagingRunbook:
    report_paths = {
        "owner_packet": owner_packet_path,
        "pre_stage_gate": pre_stage_gate_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    owner_packet = reports["owner_packet"]
    pre_stage_gate = reports["pre_stage_gate"]
    task_board = reports["task_board"]
    task_summary = _summary(task_board)
    pre_stage_commands = _list(owner_packet.get("pre_stage_verification_commands"))
    stage_commands = _list(owner_packet.get("stage_commands"))
    post_stage_commands = _list(owner_packet.get("post_stage_verification_commands"))
    verification_commands = _list(owner_packet.get("verification_commands"))
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_summary = _summary(owner_packet)
    pre_gate_summary = _summary(pre_stage_gate)
    stage_count = owner_packet.get("stage_include_count")
    owner_eligible_stage_count = owner_packet.get("eligible_stage_count")
    pre_gate_stage_count = pre_gate_summary.get("stage_include_count")
    stage_command_count = len(stage_commands)
    pre_gate_stage_command_count = pre_gate_summary.get("stage_command_count")
    owner_unchanged_stage_count = owner_packet.get("unchanged_stage_count", owner_summary.get("unchanged_stage_count"))
    post_commit_noop_accounted_for = (
        stage_command_count == 0
        and owner_summary.get("post_commit_noop_accounted_for") is True
        and pre_gate_summary.get("post_commit_noop_accounted_for") is True
        and pre_gate_summary.get("post_commit_noop_stage_counts_agree") is True
        and stage_count == pre_gate_stage_count
        and pre_gate_stage_command_count == 0
        and owner_packet.get("eligible_stage_count") == 0
        and owner_packet.get("blocked_stage_count") == 0
        and owner_unchanged_stage_count == stage_count
    )
    active_stage_count_matches_gate = (
        stage_count == pre_gate_stage_count
        and (
            stage_command_count == stage_count
            or (
                owner_eligible_stage_count is not None
                and stage_command_count == owner_eligible_stage_count
                and stage_command_count == pre_gate_stage_command_count
                and isinstance(stage_count, int)
                and stage_command_count <= stage_count
            )
        )
    )
    stage_command_count_matches_gate = (
        active_stage_count_matches_gate
        or post_commit_noop_accounted_for
    )
    commands_are_split = (
        bool(pre_stage_commands)
        and bool(post_stage_commands)
        and verification_commands == post_stage_commands
        and "python scripts\\commercial_delivery_owner_staging_preflight.py" not in post_stage_commands
    )
    stage_commands_are_explicit = (
        post_commit_noop_accounted_for
        or (
            bool(stage_commands)
            and all(command.startswith("git add -- '") and command.endswith("'") for command in stage_commands)
            and not _has_broad_stage_command(stage_commands)
        )
    )
    owner_stage_notes = [
        "Run only these exact commands after explicit owner approval.",
        "Do not use git add ., git add -A, or git add --all.",
    ]
    if post_commit_noop_accounted_for:
        owner_stage_notes = [
            "No stage commands are required because this post-commit/noop state is already accounted for.",
            "Do not run broad staging commands or stage additional paths.",
        ]

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more owner staging runbook inputs are missing or unreadable",
        ),
        _check(
            "owner_packet_ready",
            _status(owner_packet) == "owner_staging_packet_ready",
            details={"status": _status(owner_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "pre_stage_gate_ready",
            _status(pre_stage_gate) == "owner_pre_stage_readiness_ready",
            details={"status": _status(pre_stage_gate)},
            error="owner pre-stage readiness gate is not ready",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={
                "status": _status(task_board),
                "owner_pre_stage_readiness_gate_status": task_summary.get("owner_pre_stage_readiness_gate_status"),
            },
            error="commercial delivery task board is not ready",
        ),
        _check(
            "stage_command_count_matches_gate",
            stage_command_count_matches_gate,
            details={
                "stage_command_count": stage_command_count,
                "owner_packet_stage_include_count": stage_count,
                "owner_packet_eligible_stage_count": owner_eligible_stage_count,
                "pre_stage_gate_stage_include_count": pre_gate_stage_count,
                "pre_stage_gate_stage_command_count": pre_gate_stage_command_count,
                "owner_packet_unchanged_stage_count": owner_unchanged_stage_count,
                "active_stage_count_matches_gate": active_stage_count_matches_gate,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="stage command count does not match owner packet and pre-stage gate counts",
        ),
        _check(
            "verification_commands_are_split",
            commands_are_split,
            details={
                "pre_stage_verification_command_count": len(pre_stage_commands),
                "post_stage_verification_command_count": len(post_stage_commands),
                "verification_alias_matches_post": verification_commands == post_stage_commands,
                "post_stage_contains_preflight": "python scripts\\commercial_delivery_owner_staging_preflight.py" in post_stage_commands,
            },
            error="owner packet does not cleanly split pre-stage and post-stage verification commands",
        ),
        _check(
            "stage_commands_are_explicit_path_adds",
            stage_commands_are_explicit,
            details={
                "stage_command_count": stage_command_count,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="stage commands must be explicit git add -- '<path>' commands",
        ),
        _check(
            "owner_gate_present",
            owner_packet.get("owner_gated") is True and pre_stage_gate.get("owner_gated") is True,
            details={
                "owner_packet_owner_gated": owner_packet.get("owner_gated"),
                "pre_stage_gate_owner_gated": pre_stage_gate.get("owner_gated"),
            },
            error="owner gate marker is missing",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more runbook inputs claim full Codex parity",
        ),
        _check(
            "no_runbook_mutation",
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
    status = "owner_staging_runbook_ready" if ready else "owner_staging_runbook_blocked"

    sections = [
        OwnerStagingRunbookSection(
            name="pre_stage_verification",
            title="Pre-stage verification",
            commands=pre_stage_commands,
            notes=[
                "Run these immediately before owner-approved staging.",
                "Stop if any command fails or if the git index is not empty.",
            ],
        ),
        OwnerStagingRunbookSection(
            name="owner_stage_commands",
            title="Owner-approved stage commands",
            commands=stage_commands,
            notes=owner_stage_notes,
        ),
        OwnerStagingRunbookSection(
            name="post_stage_verification",
            title="Post-stage verification",
            commands=post_stage_commands,
            notes=[
                "Run these after staging and before commit.",
                "Post-stage verification intentionally excludes preflight because the git index should no longer be empty.",
            ],
        ),
        OwnerStagingRunbookSection(
            name="commit_preview",
            title="Commit preview",
            commands=[str(owner_packet.get("commit_command_preview") or "")],
            notes=["Commit only after post-stage verification is ready."],
        ),
    ]

    return OwnerStagingRunbook(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_staging_runbook",
        owner_gated=owner_packet.get("owner_gated") is True and pre_stage_gate.get("owner_gated") is True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        summary={
            "stage_command_count": stage_command_count,
            "pre_stage_verification_command_count": len(pre_stage_commands),
            "post_stage_verification_command_count": len(post_stage_commands),
            "verification_alias_matches_post": verification_commands == post_stage_commands,
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "owner_packet_eligible_stage_count": owner_eligible_stage_count,
            "owner_packet_unchanged_stage_count": owner_unchanged_stage_count,
            "pre_stage_gate_stage_command_count": pre_gate_stage_command_count,
            "pre_stage_gate_status": _status(pre_stage_gate),
            "task_board_status": _status(task_board),
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "commit_command_preview": owner_packet.get("commit_command_preview"),
        },
        sections=sections,
        checks=checks,
        next_actions=[
            "Review this runbook with the owner before any staging.",
            "Run pre-stage verification first; do not stage if pre-stage verification is not ready.",
            "Run only the exact owner stage commands after explicit approval.",
            "Run post-stage verification before commit.",
        ],
        known_limits=[
            "This runbook is read-only and never executes commands.",
            "It does not stage, commit, push, run tests, call network services, or execute agents.",
            "It describes owner-gated local staging only; it does not claim full Codex parity.",
        ],
    )


def render_markdown_runbook(runbook: OwnerStagingRunbook) -> str:
    lines = [
        "# Commercial Delivery Owner Staging Runbook",
        "",
        f"- Status: `{runbook.status}`",
        f"- Generated at: `{runbook.generated_at}`",
        f"- Owner gated: `{str(runbook.owner_gated).lower()}`",
        f"- Stage command count: `{runbook.summary.get('stage_command_count')}`",
        f"- Secondary handoff next queue: `{', '.join(runbook.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{runbook.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{runbook.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Pre-stage verification commands: `{runbook.summary.get('pre_stage_verification_command_count')}`",
        f"- Post-stage verification commands: `{runbook.summary.get('post_stage_verification_command_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in runbook.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    for section in runbook.sections:
        lines.extend(["", f"## {section.title}", ""])
        lines.extend(f"- `{command}`" for command in section.commands if command)
        if section.notes:
            lines.append("")
            lines.extend(f"- {note}" for note in section.notes)
    lines.append("")
    return "\n".join(lines)


def write_report(runbook: OwnerStagingRunbook, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(runbook.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_runbook(runbook: OwnerStagingRunbook, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_runbook(runbook), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--pre-stage-gate", type=Path, default=DEFAULT_PRE_STAGE_GATE)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runbook = build_owner_staging_runbook(
        owner_packet_path=args.owner_packet,
        pre_stage_gate_path=args.pre_stage_gate,
        task_board_path=args.task_board,
    )
    write_report(runbook, args.output)
    write_markdown_runbook(runbook, args.markdown_output)
    print(f"Commercial delivery owner staging runbook status: {runbook.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage commands: {runbook.summary.get('stage_command_count')}")
    for check in runbook.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if runbook.status == "owner_staging_runbook_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
