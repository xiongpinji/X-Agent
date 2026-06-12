#!/usr/bin/env python3
"""Build a read-only owner stage approval readiness brief.

The brief consolidates the approval request, approval gate, delivery packet,
and stage execution plan into one owner-facing artifact. It never creates the
real owner approval payload, stages files, creates commits, pushes, calls
network services, executes tests, or runs agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_OWNER_STAGE_APPROVAL_REQUEST = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_REFRESH_CHAIN = REPORT_DIR / "commercial-delivery-refresh-chain-receipt.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-brief.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-brief.md"


@dataclass(frozen=True)
class OwnerStageApprovalBriefCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStageApprovalBrief:
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
    real_owner_approval_written: bool
    full_codex_parity_claimed: bool
    approval_ready: bool
    approval_required: bool
    stage_allowed: bool
    stage_execution_ready: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    owner_action_payload_template: dict[str, Any]
    checks: list[OwnerStageApprovalBriefCheck]
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


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _failed_step_names(payload: dict[str, Any]) -> list[str]:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return []
    names: list[str] = []
    for step in steps:
        if isinstance(step, dict) and step.get("status") == "failed" and step.get("name") is not None:
            names.append(str(step.get("name")))
    return names


REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS = {
    "owner_decision_brief",
    "owner_pre_stage_readiness_gate",
    "owner_staging_runbook",
    "owner_delivery_packet_before_owner_approval",
    "owner_delivery_packet",
    "owner_stage_approval_request",
    "owner_approval_payload_audit",
    "owner_stage_approval_gate",
    "owner_stage_approval_brief",
    "owner_stage_execution_plan",
    "closure_snapshot",
    "owner_approval_handoff",
    "pre_approval_drift_guard",
    "owner_approval_resume_packet",
    "owner_post_approval_operator_checklist",
    "task_board_after_owner_decision",
}


def _refresh_receipt_ready_or_bootstrap(refresh_chain: dict[str, Any]) -> bool:
    refresh_summary = _summary(refresh_chain)
    if _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_ready":
        return True
    failed_steps = _failed_step_names(refresh_chain)
    failed_step_count = int(refresh_summary.get("failed_step_count") or 0)
    return (
        _status(refresh_chain) == "commercial_delivery_refresh_chain_receipt_blocked"
        and failed_step_count > 0
        and len(failed_steps) == failed_step_count
        and set(failed_steps).issubset(REFRESH_RECEIPT_SELF_BOOTSTRAP_STEPS)
    )


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStageApprovalBriefCheck:
    return OwnerStageApprovalBriefCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _expected_stage_execution_blocked(stage_execution_plan: dict[str, Any]) -> bool:
    return (
        _status(stage_execution_plan) == "owner_stage_execution_blocked"
        and stage_execution_plan.get("stage_allowed") is not True
    )


def build_owner_stage_approval_brief(
    *,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_stage_approval_request_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_REQUEST,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    refresh_chain_path: Path = DEFAULT_REFRESH_CHAIN,
    task_board_path: Path = DEFAULT_TASK_BOARD,
) -> OwnerStageApprovalBrief:
    report_paths = {
        "owner_delivery_packet": owner_delivery_packet_path,
        "owner_stage_approval_request": owner_stage_approval_request_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "refresh_chain": refresh_chain_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    delivery_packet = reports["owner_delivery_packet"]
    approval_request = reports["owner_stage_approval_request"]
    approval_gate = reports["owner_stage_approval_gate"]
    stage_execution_plan = reports["owner_stage_execution_plan"]
    refresh_chain = reports["refresh_chain"]
    task_board = reports["task_board"]
    delivery_summary = _summary(delivery_packet)
    request_summary = _summary(approval_request)
    task_summary = _summary(task_board)

    stage_include_count = delivery_summary.get("stage_include_count")
    owner_stage_command_count = delivery_summary.get("owner_stage_command_count")
    requested_stage_count = request_summary.get("stage_include_count")
    requested_stage_command_count = request_summary.get("owner_stage_command_count")
    stage_path_digest = delivery_summary.get("stage_path_digest")
    request_stage_path_digest = request_summary.get("stage_path_digest")
    stage_command_digest = delivery_summary.get("stage_command_digest")
    request_stage_command_digest = request_summary.get("stage_command_digest")
    expected_stage_path_set_digest = delivery_summary.get("expected_stage_path_set_digest")
    request_expected_stage_path_set_digest = request_summary.get("expected_stage_path_set_digest")
    post_commit_noop_accounted_for = delivery_summary.get("post_commit_noop_accounted_for") is True
    stage_allowed = approval_gate.get("stage_allowed") is True
    approval_ready = _status(approval_gate) == "owner_stage_approval_ready" and stage_allowed
    approval_required = delivery_packet.get("owner_approval_required") is True
    stage_execution_ready = _status(stage_execution_plan) == "owner_stage_execution_ready"
    expected_execution_blocked = _expected_stage_execution_blocked(stage_execution_plan)
    suggested_payload = approval_request.get("suggested_owner_approval_payload")
    if not isinstance(suggested_payload, dict):
        suggested_payload = {}
    template_expected_stage_path_set_digest = suggested_payload.get("expected_stage_path_set_digest")
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = (
        delivery_packet.get("owner_gated") is True
        and approval_request.get("owner_gated") is True
        and approval_gate.get("owner_gated") is True
        and stage_execution_plan.get("owner_gated") is True
    )

    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more owner approval brief inputs are missing or unreadable",
        ),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready",
            details={"status": _status(delivery_packet), "stage_ready": delivery_packet.get("stage_ready")},
            error="owner delivery packet is not ready",
        ),
        _check(
            "owner_stage_approval_request_ready",
            _status(approval_request) == "owner_stage_approval_request_ready",
            details={"status": _status(approval_request)},
            error="owner stage approval request is not ready",
        ),
        _check(
            "approval_request_counts_match_delivery_packet",
            stage_include_count == requested_stage_count
            and owner_stage_command_count == requested_stage_command_count
            and (int(owner_stage_command_count or 0) > 0 or post_commit_noop_accounted_for)
            and int(owner_stage_command_count or 0) <= int(stage_include_count or -1),
            details={
                "stage_include_count": stage_include_count,
                "owner_stage_command_count": owner_stage_command_count,
                "request_stage_include_count": requested_stage_count,
                "request_owner_stage_command_count": requested_stage_command_count,
            },
            error="owner approval request stage counts do not match the owner delivery packet",
        ),
        _check(
            "approval_request_digests_match_delivery_packet",
            isinstance(stage_path_digest, str)
            and stage_path_digest == request_stage_path_digest
            and isinstance(stage_command_digest, str)
            and stage_command_digest == request_stage_command_digest
            and isinstance(expected_stage_path_set_digest, str)
            and expected_stage_path_set_digest == request_expected_stage_path_set_digest
            and expected_stage_path_set_digest == template_expected_stage_path_set_digest,
            details={
                "stage_path_digest": stage_path_digest,
                "request_stage_path_digest": request_stage_path_digest,
                "stage_command_digest": stage_command_digest,
                "request_stage_command_digest": request_stage_command_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "request_expected_stage_path_set_digest": request_expected_stage_path_set_digest,
                "template_expected_stage_path_set_digest": template_expected_stage_path_set_digest,
            },
            error="owner approval request digests do not match the owner delivery packet",
        ),
        _check(
            "owner_stage_approval_gate_accounted_for",
            approval_ready or (
                _status(approval_gate) == "owner_stage_approval_blocked"
                and approval_gate.get("stage_allowed") is not True
            ),
            details={
                "owner_stage_approval_gate_status": _status(approval_gate),
                "stage_allowed": approval_gate.get("stage_allowed"),
            },
            error="owner stage approval gate is missing or in an unknown state",
        ),
        _check(
            "owner_stage_execution_plan_accounted_for",
            stage_execution_ready or expected_execution_blocked,
            details={
                "owner_stage_execution_plan_status": _status(stage_execution_plan),
                "stage_allowed": stage_execution_plan.get("stage_allowed"),
            },
            error="owner stage execution plan is neither ready nor in the expected pre-approval blocked state",
        ),
        _check(
            "owner_action_payload_template_ready",
            suggested_payload.get("decision") == "approve_owner_stage"
            and suggested_payload.get("approve_stage") is True
            and suggested_payload.get("stage_include_count") == stage_include_count,
            details={
                "decision": suggested_payload.get("decision"),
                "approve_stage": suggested_payload.get("approve_stage"),
                "template_stage_include_count": suggested_payload.get("stage_include_count"),
                "template_stage_path_digest": suggested_payload.get("stage_path_digest"),
                "template_stage_command_digest": suggested_payload.get("stage_command_digest"),
            },
            error="owner approval request does not include a usable suggested owner payload",
        ),
        _check(
            "task_board_ready_for_owner_review",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={
                "task_board_status": _status(task_board),
                "secondary_pending_count": task_summary.get("secondary_pending_count"),
            },
            error="commercial delivery task board is not ready for owner staging review",
        ),
        _check(
            "refresh_chain_ready",
            _refresh_receipt_ready_or_bootstrap(refresh_chain),
            details={
                "refresh_chain_status": _status(refresh_chain),
                "expected_nonzero_steps": _summary(refresh_chain).get("expected_nonzero_steps"),
                "failed_step_count": _summary(refresh_chain).get("failed_step_count"),
                "failed_steps": _failed_step_names(refresh_chain),
            },
            error="commercial delivery refresh chain is not ready",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_delivery_packet_owner_gated": delivery_packet.get("owner_gated"),
                "owner_stage_approval_request_owner_gated": approval_request.get("owner_gated"),
                "owner_stage_approval_gate_owner_gated": approval_gate.get("owner_gated"),
                "owner_stage_execution_plan_owner_gated": stage_execution_plan.get("owner_gated"),
            },
            error="one or more owner approval brief inputs are missing owner-gated markers",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more owner approval brief inputs claim full Codex parity",
        ),
        _check(
            "no_approval_brief_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
                "real_owner_approval_written": False,
            },
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    status = "owner_stage_approval_brief_ready" if ready else "owner_stage_approval_brief_blocked"

    return OwnerStageApprovalBrief(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_stage_approval_brief",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        real_owner_approval_written=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        approval_ready=approval_ready,
        approval_required=approval_required,
        stage_allowed=stage_allowed,
        stage_execution_ready=stage_execution_ready,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "stage_include_count": stage_include_count,
            "owner_stage_command_count": owner_stage_command_count,
            "owner_stage_approval_request_status": _status(approval_request),
            "owner_stage_approval_gate_status": _status(approval_gate),
            "owner_stage_execution_plan_status": _status(stage_execution_plan),
            "stage_allowed": approval_gate.get("stage_allowed"),
            "approval_required": approval_required,
            "approval_payload_path": approval_request.get("approval_payload_path"),
            "template_output_path": approval_request.get("template_output_path"),
            "commit_command_preview": delivery_summary.get("commit_command_preview"),
            "stage_path_digest": stage_path_digest,
            "request_stage_path_digest": request_stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "request_stage_command_digest": request_stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "request_expected_stage_path_set_digest": request_expected_stage_path_set_digest,
            "template_expected_stage_path_set_digest": template_expected_stage_path_set_digest,
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "request_secondary_handoff_completed_count": request_summary.get("secondary_handoff_completed_count"),
            "request_secondary_handoff_latest_completed_candidate": request_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "control_modes_preservation_status": delivery_summary.get("control_modes_preservation_status"),
            "control_modes_plan_only_default": delivery_summary.get("control_modes_plan_only_default"),
            "control_modes_loop_phases": delivery_summary.get("control_modes_loop_phases"),
            "control_modes_surface_file_count": delivery_summary.get("control_modes_surface_file_count"),
        },
        owner_action_payload_template=suggested_payload,
        checks=checks,
        next_actions=[
            "Owner reviews this brief, the delivery packet, and the approval request.",
            "If approved, create the real owner approval payload at approval_payload_path with concrete owner fields.",
            "Rerun commercial_delivery_owner_stage_approval_gate.py after the real approval payload exists.",
            "Rerun commercial_delivery_owner_stage_execution_plan.py and stage only when it reports owner_stage_execution_ready.",
        ],
        known_limits=[
            "This brief is read-only except writing local evidence files.",
            "It does not write the real owner approval payload.",
            "It does not stage, commit, push, call network services, run tests, or execute agents.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_brief(brief: OwnerStageApprovalBrief) -> str:
    lines = [
        "# Commercial Delivery Owner Stage Approval Brief",
        "",
        f"- Status: `{brief.status}`",
        f"- Generated at: `{brief.generated_at}`",
        f"- Approval ready: `{str(brief.approval_ready).lower()}`",
        f"- Stage allowed: `{str(brief.stage_allowed).lower()}`",
        f"- Stage execution ready: `{str(brief.stage_execution_ready).lower()}`",
        f"- Stage include count: `{brief.summary.get('stage_include_count')}`",
        f"- Owner stage command count: `{brief.summary.get('owner_stage_command_count')}`",
        f"- Approval payload path: `{brief.summary.get('approval_payload_path')}`",
        f"- Secondary handoff next queue: `{', '.join(brief.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{brief.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{brief.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Control modes preservation: `{brief.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{brief.summary.get('control_modes_plan_only_default')}`",
        "",
        "## Checks",
        "",
    ]
    for check in brief.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Owner Action Payload Template", "", "```json"])
    lines.append(json.dumps(brief.owner_action_payload_template, ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in brief.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(brief: OwnerStageApprovalBrief, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_brief(
    brief: OwnerStageApprovalBrief,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_brief(brief), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-stage-approval-request", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_REQUEST)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--refresh-chain", type=Path, default=DEFAULT_REFRESH_CHAIN)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brief = build_owner_stage_approval_brief(
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_stage_approval_request_path=args.owner_stage_approval_request,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        refresh_chain_path=args.refresh_chain,
        task_board_path=args.task_board,
    )
    write_report(brief, args.output)
    write_markdown_brief(brief, args.markdown_output)
    print(f"Commercial delivery owner stage approval brief status: {brief.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Approval ready: {brief.approval_ready}")
    print(f"Stage allowed: {brief.stage_allowed}")
    print(f"Stage execution ready: {brief.stage_execution_ready}")
    for check in brief.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if brief.status == "owner_stage_approval_brief_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
