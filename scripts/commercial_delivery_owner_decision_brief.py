#!/usr/bin/env python3
"""Build a read-only owner decision brief for commercial delivery.

The brief summarizes the current owner-gated staging decision point. It reads
existing delivery reports only; it does not stage files, create commits, push,
run agents, execute tests, call network services, or mutate release gates.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now
from scripts.commercial_delivery_task_board import _display_path

DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_PREFLIGHT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_OWNER_POST_STAGING = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_COMMAND_AUDIT = REPORT_DIR / "commercial-delivery-owner-command-audit.json"
DEFAULT_OWNER_PRE_STAGE_READINESS_GATE = REPORT_DIR / "commercial-delivery-owner-pre-stage-readiness-gate.json"
DEFAULT_OWNER_APPROVAL_HANDOFF = REPORT_DIR / "commercial-delivery-owner-approval-handoff.json"
DEFAULT_OWNER_APPROVAL_RESUME_PACKET = REPORT_DIR / "commercial-delivery-owner-approval-resume-packet.json"
DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST = (
    REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
)
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-decision-brief.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-decision-brief.md"


@dataclass(frozen=True)
class OwnerDecisionBriefCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerDecisionBrief:
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
    decision: str
    reports: dict[str, str]
    summary: dict[str, Any]
    pending_secondary_paths: list[str]
    checks: list[OwnerDecisionBriefCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerDecisionBriefCheck:
    return OwnerDecisionBriefCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _pending_paths(manifest: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in manifest.get("excluded_dirty_paths") or []:
        if isinstance(item, dict) and item.get("scope") == "secondary_pending_candidate":
            path = str(item.get("path") or "").replace("\\", "/").strip()
            if path:
                paths.append(path)
    return sorted(paths)


def build_owner_decision_brief(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    owner_preflight_path: Path = DEFAULT_OWNER_PREFLIGHT,
    owner_post_staging_path: Path = DEFAULT_OWNER_POST_STAGING,
    owner_command_audit_path: Path = DEFAULT_OWNER_COMMAND_AUDIT,
    owner_pre_stage_readiness_gate_path: Path = DEFAULT_OWNER_PRE_STAGE_READINESS_GATE,
    owner_approval_handoff_path: Path = DEFAULT_OWNER_APPROVAL_HANDOFF,
    owner_approval_resume_packet_path: Path = DEFAULT_OWNER_APPROVAL_RESUME_PACKET,
    owner_post_approval_operator_checklist_path: Path = DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerDecisionBrief:
    report_paths = {
        "manifest": manifest_path,
        "staging_review": staging_review_path,
        "owner_packet": owner_packet_path,
        "owner_preflight": owner_preflight_path,
        "owner_post_staging": owner_post_staging_path,
        "owner_command_audit": owner_command_audit_path,
        "owner_pre_stage_readiness_gate": owner_pre_stage_readiness_gate_path,
        "owner_approval_handoff": owner_approval_handoff_path,
        "owner_approval_resume_packet": owner_approval_resume_packet_path,
        "owner_post_approval_operator_checklist": owner_post_approval_operator_checklist_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    manifest = reports["manifest"]
    staging_review = reports["staging_review"]
    owner_packet = reports["owner_packet"]
    owner_preflight = reports["owner_preflight"]
    owner_post_staging = reports["owner_post_staging"]
    owner_command_audit = reports["owner_command_audit"]
    owner_pre_stage_readiness_gate = reports["owner_pre_stage_readiness_gate"]
    owner_approval_handoff = reports["owner_approval_handoff"]
    owner_approval_resume_packet = reports["owner_approval_resume_packet"]
    operator_checklist = reports["owner_post_approval_operator_checklist"]
    task_board = reports["task_board"]
    task_summary = task_board.get("summary") if isinstance(task_board.get("summary"), dict) else {}
    readiness_summary = owner_pre_stage_readiness_gate.get("summary") if isinstance(
        owner_pre_stage_readiness_gate.get("summary"),
        dict,
    ) else {}
    pending_paths = _pending_paths(manifest)
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    stage_include_count = manifest.get("stage_include_count")
    owner_stage_command_count = len(owner_packet.get("stage_commands") or [])
    command_audit_count = owner_command_audit.get("command_count")
    command_audit_expected_path_count = owner_command_audit.get("expected_path_count")
    staging_review_eligible_count = staging_review.get("eligible_stage_count")
    post_commit_noop_accounted_for = (
        isinstance(stage_include_count, int)
        and stage_include_count > 0
        and staging_review_eligible_count == 0
        and owner_stage_command_count == 0
        and command_audit_count == 0
        and command_audit_expected_path_count == 0
        and _status(owner_post_staging) == "owner_post_staging_verification_ready"
        and int(owner_post_staging.get("cached_staged_path_count") or 0) == 0
        and readiness_summary.get("post_commit_noop_accounted_for") is True
        and readiness_summary.get("post_commit_noop_stage_counts_agree") is True
    )
    post_staging_ready = (
        _status(owner_post_staging) == "owner_post_staging_verification_ready"
        and int(owner_post_staging.get("cached_staged_path_count") or 0) > 0
    )
    owner_gated = (
        staging_review.get("owner_gated") is True
        and owner_packet.get("owner_gated") is True
        and owner_pre_stage_readiness_gate.get("owner_gated") is True
        and owner_approval_handoff.get("owner_gated") is True
        and owner_approval_resume_packet.get("owner_gated") is True
        and operator_checklist.get("owner_gated") is True
    )
    owner_boundary_accounted_for = (
        _status(owner_approval_handoff) == "owner_approval_handoff_ready"
        and _status(owner_pre_stage_readiness_gate) == "owner_pre_stage_readiness_ready"
        and _status(owner_approval_resume_packet)
        in {"owner_approval_resume_packet_waiting_for_owner", "owner_approval_resume_packet_ready"}
        and _status(operator_checklist)
        in {"owner_post_approval_operator_checklist_waiting_for_owner", "owner_post_approval_operator_checklist_ready"}
    )
    owner_boundary_post_staging_accounted_for = post_staging_ready and (
        owner_approval_resume_packet.get("real_owner_approval_present") is True
        or _status(owner_approval_resume_packet) == "owner_approval_resume_packet_waiting_for_owner"
    )
    owner_boundary_ready_for_brief = owner_boundary_accounted_for or owner_boundary_post_staging_accounted_for
    pre_stage_readiness_ready_for_brief = (
        _status(owner_pre_stage_readiness_gate) == "owner_pre_stage_readiness_ready"
        or post_staging_ready
    )
    stage_commands_match_manifest = (
        stage_include_count == owner_stage_command_count
        and stage_include_count == command_audit_count
        and stage_include_count == command_audit_expected_path_count
    )
    stage_commands_subset_accounted_for = (
        isinstance(stage_include_count, int)
        and isinstance(owner_stage_command_count, int)
        and isinstance(command_audit_count, int)
        and isinstance(command_audit_expected_path_count, int)
        and owner_stage_command_count == command_audit_count == command_audit_expected_path_count
        and 0 < owner_stage_command_count <= stage_include_count
    )
    post_staging_state_accounted_for = (
        (
            _status(owner_post_staging) == "owner_post_staging_verification_blocked"
            and int(owner_post_staging.get("cached_staged_path_count") or 0) == 0
        )
        or post_staging_ready
        or post_commit_noop_accounted_for
    )
    owner_preflight_ready_for_brief = _status(owner_preflight) == "owner_staging_preflight_ready" or post_staging_ready

    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="required reports are missing or unreadable"),
        _check(
            "manifest_ready",
            _status(manifest) == "original_kernel_delivery_manifest_ready",
            details={"status": _status(manifest)},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "staging_review_ready",
            _status(staging_review) == "staging_review_ready",
            details={"status": _status(staging_review)},
            error="commercial delivery staging review is not ready",
        ),
        _check(
            "owner_packet_ready",
            _status(owner_packet) == "owner_staging_packet_ready",
            details={"status": _status(owner_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "owner_preflight_ready",
            owner_preflight_ready_for_brief,
            details={"status": _status(owner_preflight), "post_staging_ready": post_staging_ready},
            error="owner staging preflight is not ready",
        ),
        _check(
            "owner_command_audit_ready",
            _status(owner_command_audit) == "owner_command_audit_ready",
            details={"status": _status(owner_command_audit)},
            error="owner command audit is not ready",
        ),
        _check(
            "owner_pre_stage_readiness_gate_ready",
            pre_stage_readiness_ready_for_brief,
            details={
                "status": _status(owner_pre_stage_readiness_gate),
                "post_staging_ready": post_staging_ready,
                "owner_approval_resume_packet_status": readiness_summary.get(
                    "owner_approval_resume_packet_status"
                ),
                "owner_post_approval_operator_checklist_status": readiness_summary.get(
                    "owner_post_approval_operator_checklist_status"
                ),
            },
            error="owner pre-stage readiness gate is not ready",
        ),
        _check(
            "owner_approval_boundary_accounted_for",
            owner_boundary_ready_for_brief,
            details={
                "owner_approval_handoff_status": _status(owner_approval_handoff),
                "owner_pre_stage_readiness_gate_status": _status(owner_pre_stage_readiness_gate),
                "post_staging_ready": post_staging_ready,
                "owner_boundary_post_staging_accounted_for": owner_boundary_post_staging_accounted_for,
                "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
                "owner_approval_resume_packet_waiting_for_owner": owner_approval_resume_packet.get(
                    "waiting_for_owner"
                ),
                "owner_approval_resume_packet_resume_ready": owner_approval_resume_packet.get("resume_ready"),
                "owner_post_approval_operator_checklist_status": _status(operator_checklist),
                "owner_post_approval_operator_checklist_waiting_for_owner": operator_checklist.get(
                    "waiting_for_owner"
                ),
                "owner_post_approval_operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
            },
            error="owner approval boundary reports are not ready or waiting for owner",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={"status": _status(task_board)},
            error="commercial delivery task board is not ready for owner staging review",
        ),
        _check(
            "stage_commands_match_manifest",
            stage_commands_match_manifest
            or stage_commands_subset_accounted_for
            or post_commit_noop_accounted_for,
            details={
                "stage_include_count": stage_include_count,
                "staging_review_eligible_count": staging_review_eligible_count,
                "owner_stage_command_count": owner_stage_command_count,
                "owner_command_audit_command_count": command_audit_count,
                "owner_command_audit_expected_path_count": command_audit_expected_path_count,
                "stage_commands_subset_accounted_for": stage_commands_subset_accounted_for,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner stage command or command-audit counts do not match manifest stage include count",
        ),
        _check(
            "post_staging_not_yet_applied",
            post_staging_state_accounted_for,
            details={
                "status": _status(owner_post_staging),
                "cached_staged_path_count": owner_post_staging.get("cached_staged_path_count"),
                "post_staging_ready": post_staging_ready,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="post-staging verifier is not in the expected pre-owner-staging state",
        ),
        _check(
            "secondary_pending_does_not_block_owner_review",
            task_summary.get("secondary_pending_blocks_owner_staging") is False,
            details={
                "secondary_pending_count": task_summary.get("secondary_pending_count"),
                "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            },
            error="secondary pending candidates are blocking owner staging review",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="delivery reports claim full Codex parity",
        ),
        _check(
            "no_decision_brief_mutation",
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
    decision = "ready_for_owner_staging_decision" if ready else "blocked_before_owner_staging_decision"

    return OwnerDecisionBrief(
        status=decision,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_decision_brief",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        decision=decision,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        summary={
            "stage_include_count": stage_include_count,
            "owner_stage_command_count": owner_stage_command_count,
            "owner_command_audit_command_count": command_audit_count,
            "owner_command_audit_expected_path_count": command_audit_expected_path_count,
            "post_staging_ready": post_staging_ready,
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "owner_boundary_post_staging_accounted_for": owner_boundary_post_staging_accounted_for,
            "stage_commands_subset_accounted_for": stage_commands_subset_accounted_for,
            "staging_review_eligible_count": staging_review_eligible_count,
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "secondary_pending_blocks_owner_staging": task_summary.get("secondary_pending_blocks_owner_staging"),
            "cached_staged_path_count": owner_post_staging.get("cached_staged_path_count"),
            "post_staging_status": _status(owner_post_staging),
            "owner_command_audit_status": _status(owner_command_audit),
            "owner_pre_stage_readiness_gate_status": _status(owner_pre_stage_readiness_gate),
            "owner_approval_handoff_status": _status(owner_approval_handoff),
            "owner_approval_handoff_owner_action_required": owner_approval_handoff.get("owner_action_required"),
            "owner_approval_resume_packet_status": _status(owner_approval_resume_packet),
            "owner_approval_resume_packet_waiting_for_owner": owner_approval_resume_packet.get("waiting_for_owner"),
            "owner_approval_resume_packet_resume_ready": owner_approval_resume_packet.get("resume_ready"),
            "owner_post_approval_operator_checklist_status": _status(operator_checklist),
            "owner_post_approval_operator_checklist_waiting_for_owner": operator_checklist.get("waiting_for_owner"),
            "owner_post_approval_operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
            "task_board_status": _status(task_board),
        },
        pending_secondary_paths=pending_paths,
        checks=checks,
        next_actions=[
            "Review this brief and the owner staging packet before any git staging.",
            "If the brief is ready, rerun owner staging preflight immediately before owner-approved staging.",
            "After explicit owner-approved staging, rerun owner post-staging verifier and this decision brief.",
            "Keep secondary_pending_candidate paths out of stage_include_paths until the secondary handoff records validation.",
        ],
        known_limits=[
            "This brief is read-only and does not perform staging, commits, pushes, tests, network calls, or agent execution.",
            "A blocked post-staging verifier is expected before owner staging because the git index should be empty.",
            "Pending secondary candidates do not block owner staging review but require validation before promotion.",
        ],
    )


def render_markdown_brief(brief: OwnerDecisionBrief) -> str:
    lines = [
        "# Commercial Delivery Owner Decision Brief",
        "",
        f"- Status: `{brief.status}`",
        f"- Generated at: `{brief.generated_at}`",
        f"- Owner gated: `{str(brief.owner_gated).lower()}`",
        f"- Stage include count: `{brief.summary.get('stage_include_count')}`",
        f"- Owner stage command count: `{brief.summary.get('owner_stage_command_count')}`",
        f"- Secondary pending count: `{brief.summary.get('secondary_pending_count')}`",
        f"- Secondary handoff next queue: `{', '.join(brief.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{brief.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{brief.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Owner command audit command count: `{brief.summary.get('owner_command_audit_command_count')}`",
        f"- Owner command audit expected path count: `{brief.summary.get('owner_command_audit_expected_path_count')}`",
        f"- Owner pre-stage readiness gate: `{brief.summary.get('owner_pre_stage_readiness_gate_status')}`",
        f"- Owner approval resume packet: `{brief.summary.get('owner_approval_resume_packet_status')}`",
        f"- Owner post-approval operator checklist: `{brief.summary.get('owner_post_approval_operator_checklist_status')}`",
        f"- Post-staging verifier status: `{brief.summary.get('post_staging_status')}`",
        "",
        "## Pending Secondary Paths",
        "",
    ]
    if brief.pending_secondary_paths:
        lines.extend(f"- `{path}`" for path in brief.pending_secondary_paths)
    else:
        lines.append("- None")
    lines.extend(["", "## Checks", ""])
    for check in brief.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in brief.next_actions)
    return "\n".join(lines)


def write_report(brief: OwnerDecisionBrief, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown_brief(brief: OwnerDecisionBrief, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_brief(brief), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--staging-review", type=Path, default=DEFAULT_STAGING_REVIEW)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--owner-preflight", type=Path, default=DEFAULT_OWNER_PREFLIGHT)
    parser.add_argument("--owner-post-staging", type=Path, default=DEFAULT_OWNER_POST_STAGING)
    parser.add_argument("--owner-command-audit", type=Path, default=DEFAULT_OWNER_COMMAND_AUDIT)
    parser.add_argument("--owner-pre-stage-readiness-gate", type=Path, default=DEFAULT_OWNER_PRE_STAGE_READINESS_GATE)
    parser.add_argument("--owner-approval-handoff", type=Path, default=DEFAULT_OWNER_APPROVAL_HANDOFF)
    parser.add_argument("--owner-approval-resume-packet", type=Path, default=DEFAULT_OWNER_APPROVAL_RESUME_PACKET)
    parser.add_argument(
        "--owner-post-approval-operator-checklist",
        type=Path,
        default=DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    )
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brief = build_owner_decision_brief(
        manifest_path=args.manifest,
        staging_review_path=args.staging_review,
        owner_packet_path=args.owner_packet,
        owner_preflight_path=args.owner_preflight,
        owner_post_staging_path=args.owner_post_staging,
        owner_command_audit_path=args.owner_command_audit,
        owner_pre_stage_readiness_gate_path=args.owner_pre_stage_readiness_gate,
        owner_approval_handoff_path=args.owner_approval_handoff,
        owner_approval_resume_packet_path=args.owner_approval_resume_packet,
        owner_post_approval_operator_checklist_path=args.owner_post_approval_operator_checklist,
        task_board_path=args.task_board,
    )
    write_report(brief, args.output)
    write_markdown_brief(brief, args.markdown_output)
    print(f"Commercial delivery owner decision brief status: {brief.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage include count: {brief.summary.get('stage_include_count')}")
    print(f"Secondary pending: {brief.summary.get('secondary_pending_count')}")
    for check in brief.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if brief.status == "ready_for_owner_staging_decision" else 1


if __name__ == "__main__":
    raise SystemExit(main())
