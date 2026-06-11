#!/usr/bin/env python3
"""Build a read-only owner stage execution plan.

The plan turns the owner staging packet and approval gate state into an
auditable execution sequence. It does not run git add, create commits, push,
call network services, execute tests, or run agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_STAGING_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_STAGING_PREFLIGHT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.md"


@dataclass(frozen=True)
class OwnerStageExecutionPlanCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStageExecutionPlan:
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
    stage_allowed: bool
    stage_ready: bool
    stage_command_count: int
    stage_path_digest: str | None
    stage_command_digest: str | None
    planned_stage_commands: list[str]
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[OwnerStageExecutionPlanCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        payload["planned_stage_commands_count"] = len(self.planned_stage_commands)
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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _digest_values(values: list[str]) -> str | None:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str | None:
    return _digest_values(sorted(set(paths))) if paths else None


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStageExecutionPlanCheck:
    return OwnerStageExecutionPlanCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerStageExecutionPlanCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


def build_owner_stage_execution_plan(
    *,
    owner_staging_packet_path: Path = DEFAULT_OWNER_STAGING_PACKET,
    owner_staging_preflight_path: Path = DEFAULT_OWNER_STAGING_PREFLIGHT,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
) -> OwnerStageExecutionPlan:
    report_paths = {
        "owner_staging_packet": owner_staging_packet_path,
        "owner_staging_preflight": owner_staging_preflight_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_delivery_packet": owner_delivery_packet_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    staging_packet = reports["owner_staging_packet"]
    preflight = reports["owner_staging_preflight"]
    approval_gate = reports["owner_stage_approval_gate"]
    delivery_packet = reports["owner_delivery_packet"]
    delivery_summary = _summary(delivery_packet)
    approval_summary = _summary(approval_gate)
    stage_commands = _list(staging_packet.get("stage_commands"))
    stage_paths = _list(staging_packet.get("stage_paths"))
    computed_stage_path_digest = _digest_values(stage_paths)
    computed_stage_command_digest = _digest_values(stage_commands)
    computed_expected_stage_path_set_digest = _path_set_digest(stage_paths)
    delivery_post_commit_noop_accounted_for = (
        delivery_summary.get("post_commit_noop_accounted_for") is True
        and delivery_summary.get("post_commit_owner_gate_accounted_for") is True
        and delivery_summary.get("owner_stage_command_count") == 0
    )
    empty_digest = _digest_values([])
    if delivery_post_commit_noop_accounted_for and not stage_paths and not stage_commands:
        computed_expected_stage_path_set_digest = empty_digest
    packet_stage_path_digest = _optional_str(staging_packet.get("stage_path_digest"))
    packet_stage_command_digest = _optional_str(staging_packet.get("stage_command_digest"))
    delivery_stage_path_digest = _optional_str(delivery_summary.get("stage_path_digest"))
    delivery_stage_command_digest = _optional_str(delivery_summary.get("stage_command_digest"))
    approval_stage_path_digest = _optional_str(approval_summary.get("stage_path_digest"))
    approval_stage_command_digest = _optional_str(approval_summary.get("stage_command_digest"))
    delivery_expected_stage_path_set_digest = _optional_str(delivery_summary.get("expected_stage_path_set_digest"))
    approval_expected_stage_path_set_digest = _optional_str(approval_summary.get("expected_stage_path_set_digest"))
    stage_path_digests = [
        computed_stage_path_digest,
        packet_stage_path_digest,
        delivery_stage_path_digest,
        approval_stage_path_digest,
    ]
    stage_command_digests = [
        computed_stage_command_digest,
        packet_stage_command_digest,
        delivery_stage_command_digest,
        approval_stage_command_digest,
    ]
    expected_stage_path_set_digests = [
        computed_expected_stage_path_set_digest,
        delivery_expected_stage_path_set_digest,
        approval_expected_stage_path_set_digest,
    ]
    if delivery_post_commit_noop_accounted_for and not stage_paths and not stage_commands:
        stage_path_digests = [value or empty_digest for value in stage_path_digests]
        stage_command_digests = [value or empty_digest for value in stage_command_digests]
        expected_stage_path_set_digests = [value or empty_digest for value in expected_stage_path_set_digests]
    stage_path_digest_matches = all(stage_path_digests) and len(set(stage_path_digests)) == 1
    stage_command_digest_matches = all(stage_command_digests) and len(set(stage_command_digests)) == 1
    expected_stage_path_set_digest_matches = (
        all(expected_stage_path_set_digests) and len(set(expected_stage_path_set_digests)) == 1
    )
    preflight_stage_count = preflight.get("stage_command_count")
    delivery_stage_include_count = delivery_summary.get("stage_include_count")
    delivery_stage_command_count = delivery_summary.get("owner_stage_command_count")
    approval_stage_include_count = approval_summary.get("stage_include_count")
    approval_stage_command_count = approval_summary.get("owner_stage_command_count")
    preflight_stage_count_int = _int_or_none(preflight_stage_count)
    delivery_stage_command_count_int = _int_or_none(delivery_stage_command_count)
    approval_stage_command_count_int = _int_or_none(approval_stage_command_count)
    full_codex_parity_claimed = any(report.get("full_codex_parity_claimed") is True for report in reports.values())
    stage_allowed = (
        _status(approval_gate) == "owner_stage_approval_ready"
        and approval_gate.get("stage_allowed") is True
    )
    strict_stage_ready = (
        _status(staging_packet) == "owner_staging_packet_ready"
        and _status(preflight) == "owner_staging_preflight_ready"
        and _status(delivery_packet) == "owner_delivery_packet_ready"
    )
    command_counts_match = (
        len(stage_commands) == len(stage_paths)
        and (bool(stage_commands) or delivery_post_commit_noop_accounted_for)
        and len(stage_commands) == (preflight_stage_count_int if preflight_stage_count_int is not None else -1)
        and len(stage_commands) == (
            delivery_stage_command_count_int if delivery_stage_command_count_int is not None else -1
        )
    )
    approval_count_matches = (
        (
            approval_stage_include_count is None
            and approval_stage_command_count is None
        )
        or (
            int(approval_stage_include_count or -1) == int(delivery_stage_include_count or -2)
            and int(approval_stage_command_count or -1) == len(stage_commands)
        )
    )
    if delivery_post_commit_noop_accounted_for and len(stage_commands) == 0:
        command_counts_match = (
            len(stage_commands) == len(stage_paths)
            and (preflight_stage_count_int or 0) == 0
            and (delivery_stage_command_count_int or 0) == 0
        )
        approval_count_matches = (
            approval_stage_include_count in {None, delivery_stage_include_count}
            and (approval_stage_command_count_int or 0) == 0
        )
    cached_staged_path_count = int(preflight.get("cached_staged_path_count") or 0)
    post_stage_accounted_for = (
        _status(preflight) in {"owner_staging_preflight_blocked", "owner_staging_preflight_ready"}
        and _status(delivery_packet) == "owner_delivery_packet_ready"
        and delivery_packet.get("stage_ready") is True
        and (stage_allowed or delivery_post_commit_noop_accounted_for)
        and (bool(stage_commands) or delivery_post_commit_noop_accounted_for)
        and cached_staged_path_count == len(stage_commands)
        and stage_path_digest_matches
        and stage_command_digest_matches
        and expected_stage_path_set_digest_matches
        and command_counts_match
        and approval_count_matches
    )
    stage_ready = strict_stage_ready or post_stage_accounted_for

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more stage execution plan inputs are missing or unreadable",
        ),
        _check(
            "owner_staging_packet_ready",
            _status(staging_packet) == "owner_staging_packet_ready",
            details={"status": _status(staging_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "owner_staging_preflight_accounted_for",
            _status(preflight) == "owner_staging_preflight_ready" or post_stage_accounted_for,
            details={
                "status": _status(preflight),
                "cached_staged_path_count": cached_staged_path_count,
                "strict_stage_ready": strict_stage_ready,
                "post_stage_accounted_for": post_stage_accounted_for,
            },
            error="owner staging preflight is not ready or accounted for by post-stage evidence",
        ),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready",
            details={"status": _status(delivery_packet), "stage_ready": delivery_packet.get("stage_ready")},
            error="owner delivery packet is not ready",
        ),
        _check(
            "approval_gate_ready",
            stage_allowed or delivery_post_commit_noop_accounted_for,
            details={
                "owner_stage_approval_gate_status": _status(approval_gate),
                "stage_allowed": approval_gate.get("stage_allowed"),
                "delivery_post_commit_noop_accounted_for": delivery_post_commit_noop_accounted_for,
            },
            error="owner stage approval gate must be ready before staging",
        ),
        _check(
            "stage_command_counts_match",
            command_counts_match,
            details={
                "stage_command_count": len(stage_commands),
                "stage_path_count": len(stage_paths),
                "preflight_stage_command_count": preflight_stage_count,
                "delivery_stage_include_count": delivery_stage_include_count,
                "delivery_owner_stage_command_count": delivery_stage_command_count,
                "delivery_post_commit_noop_accounted_for": delivery_post_commit_noop_accounted_for,
            },
            error="stage command counts do not match staging packet, preflight, and delivery packet",
        ),
        _check(
            "approval_count_matches_stage_commands",
            approval_count_matches,
            details={
                "approval_stage_include_count": approval_stage_include_count,
                "approval_owner_stage_command_count": approval_stage_command_count,
                "delivery_stage_include_count": delivery_stage_include_count,
                "stage_command_count": len(stage_commands),
            },
            error="approval gate stage counts do not match delivery coverage and stage command count",
        ),
        _check(
            "stage_path_digest_matches_execution_surface",
            stage_path_digest_matches,
            details={
                "computed_stage_path_digest": computed_stage_path_digest,
                "packet_stage_path_digest": packet_stage_path_digest,
                "delivery_stage_path_digest": delivery_stage_path_digest,
                "approval_stage_path_digest": approval_stage_path_digest,
            },
            error="stage path digest does not match staging packet, delivery packet, and approval gate",
        ),
        _check(
            "stage_command_digest_matches_execution_surface",
            stage_command_digest_matches,
            details={
                "computed_stage_command_digest": computed_stage_command_digest,
                "packet_stage_command_digest": packet_stage_command_digest,
                "delivery_stage_command_digest": delivery_stage_command_digest,
                "approval_stage_command_digest": approval_stage_command_digest,
            },
            error="stage command digest does not match staging packet, delivery packet, and approval gate",
        ),
        _check(
            "expected_stage_path_set_digest_matches_execution_surface",
            expected_stage_path_set_digest_matches,
            details={
                "computed_expected_stage_path_set_digest": computed_expected_stage_path_set_digest,
                "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
                "approval_expected_stage_path_set_digest": approval_expected_stage_path_set_digest,
            },
            error="expected stage path set digest does not match delivery packet and approval gate",
        ),
        _check(
            "no_cached_staged_paths_before_stage_execution_or_accounted",
            cached_staged_path_count == 0 or post_stage_accounted_for,
            details={
                "cached_staged_path_count": cached_staged_path_count,
                "post_stage_accounted_for": post_stage_accounted_for,
            },
            error="git index is not empty before stage execution and is not accounted for by post-stage evidence",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="stage execution plan inputs claim full Codex parity",
        ),
        _check(
            "no_stage_execution_plan_mutation",
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
    status = "owner_stage_execution_ready" if ready else "owner_stage_execution_blocked"
    blocking_reasons = _failed_check_names(checks)

    return OwnerStageExecutionPlan(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_stage_execution_plan",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        stage_allowed=stage_allowed,
        stage_ready=stage_ready,
        stage_command_count=len(stage_commands),
        stage_path_digest=computed_stage_path_digest,
        stage_command_digest=computed_stage_command_digest,
        planned_stage_commands=stage_commands if ready else [],
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": not ready,
            "stage_command_count": len(stage_commands),
            "stage_path_count": len(stage_paths),
            "preflight_stage_command_count": preflight_stage_count,
            "delivery_stage_include_count": delivery_stage_include_count,
            "delivery_owner_stage_command_count": delivery_stage_command_count,
            "approval_stage_include_count": approval_stage_include_count,
            "approval_owner_stage_command_count": approval_stage_command_count,
            "secondary_pending_count": delivery_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": delivery_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": delivery_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": delivery_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": delivery_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "stage_path_digest": computed_stage_path_digest,
            "stage_command_digest": computed_stage_command_digest,
            "packet_stage_path_digest": packet_stage_path_digest,
            "packet_stage_command_digest": packet_stage_command_digest,
            "delivery_stage_path_digest": delivery_stage_path_digest,
            "delivery_stage_command_digest": delivery_stage_command_digest,
            "approval_stage_path_digest": approval_stage_path_digest,
            "approval_stage_command_digest": approval_stage_command_digest,
            "expected_stage_path_set_digest": computed_expected_stage_path_set_digest,
            "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
            "approval_expected_stage_path_set_digest": approval_expected_stage_path_set_digest,
            "owner_stage_approval_gate_status": _status(approval_gate),
            "stage_allowed": approval_gate.get("stage_allowed"),
            "cached_staged_path_count": cached_staged_path_count,
            "strict_stage_ready": strict_stage_ready,
            "post_stage_accounted_for": post_stage_accounted_for,
            "post_commit_noop_accounted_for": delivery_post_commit_noop_accounted_for,
        },
        checks=checks,
        next_actions=[
            "Do not run stage commands until this plan reports owner_stage_execution_ready.",
            "If blocked on approval_gate_ready, create owner approval evidence and rerun the approval gate.",
            "When ready, run only planned_stage_commands in order.",
            "After staging, run owner post-staging verifier before commit.",
        ],
        known_limits=[
            "This plan is read-only except writing local evidence files.",
            "It does not run git add, commit, push, tests, network calls, or agents.",
            "It does not create or modify owner approval evidence.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_plan(plan: OwnerStageExecutionPlan) -> str:
    lines = [
        "# Commercial Delivery Owner Stage Execution Plan",
        "",
        f"- Status: `{plan.status}`",
        f"- Generated at: `{plan.generated_at}`",
        f"- Stage allowed: `{str(plan.stage_allowed).lower()}`",
        f"- Stage ready: `{str(plan.stage_ready).lower()}`",
        f"- Stage command count: `{plan.stage_command_count}`",
        f"- Owner action required: `{str(plan.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(plan.summary.get('blocking_reasons') or [])}`",
        f"- Secondary handoff next queue: `{', '.join(plan.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{plan.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{plan.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Stage path digest: `{plan.stage_path_digest}`",
        f"- Stage command digest: `{plan.stage_command_digest}`",
        "",
        "## Checks",
        "",
    ]
    for check in plan.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Planned Stage Commands", ""])
    if plan.planned_stage_commands:
        lines.extend(f"- `{command}`" for command in plan.planned_stage_commands)
    else:
        lines.append("- No stage commands are executable until all checks pass.")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in plan.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(plan: OwnerStageExecutionPlan, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_plan(plan: OwnerStageExecutionPlan, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_plan(plan), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-staging-packet", type=Path, default=DEFAULT_OWNER_STAGING_PACKET)
    parser.add_argument("--owner-staging-preflight", type=Path, default=DEFAULT_OWNER_STAGING_PREFLIGHT)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_owner_stage_execution_plan(
        owner_staging_packet_path=args.owner_staging_packet,
        owner_staging_preflight_path=args.owner_staging_preflight,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_delivery_packet_path=args.owner_delivery_packet,
    )
    write_report(plan, args.output)
    write_markdown_plan(plan, args.markdown_output)
    print(f"Commercial delivery owner stage execution plan status: {plan.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage allowed: {plan.stage_allowed}")
    print(f"Stage command count: {plan.stage_command_count}")
    for check in plan.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if plan.status == "owner_stage_execution_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
