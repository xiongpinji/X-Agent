#!/usr/bin/env python3
"""Validate explicit owner approval before commercial delivery staging.

This gate is read-only. It expects an owner-provided approval payload and
verifies that it matches the current owner delivery packet before any
``git add`` command is run. It never stages files, commits, pushes, calls
external services, or executes agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.md"
PLACEHOLDER_VALUES = {
    "<owner-name-or-id>",
    "<approval-id>",
    "<ISO-8601 UTC timestamp>",
}


@dataclass(frozen=True)
class OwnerStageApprovalGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStageApprovalGate:
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
    stage_approved: bool
    stage_allowed: bool
    owner: str | None
    approval_id: str | None
    approved_at: str | None
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[OwnerStageApprovalGateCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
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


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStageApprovalGateCheck:
    return OwnerStageApprovalGateCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerStageApprovalGateCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


def _bool(value: object) -> bool:
    return value is True


def _non_placeholder_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(stripped) and stripped not in PLACEHOLDER_VALUES and not (
        stripped.startswith("<") and stripped.endswith(">")
    )


def _valid_approved_at(value: object) -> bool:
    if not _non_placeholder_text(value):
        return False
    text = str(value).strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _section_commands(packet: dict[str, Any], section_name: str) -> list[str]:
    sections = packet.get("sections")
    if not isinstance(sections, list):
        return []
    for section in sections:
        if isinstance(section, dict) and section.get("name") == section_name:
            commands = section.get("commands")
            if isinstance(commands, list):
                return [str(command) for command in commands if str(command).strip()]
    return []


def _digest_values(values: list[str]) -> str | None:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stage_command_digest(packet: dict[str, Any]) -> str | None:
    return _digest_values(_section_commands(packet, "owner_stage_commands"))


def build_owner_stage_approval_gate(
    *,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> OwnerStageApprovalGate:
    delivery_packet, delivery_error = _read_json(owner_delivery_packet_path)
    approval_audit, approval_audit_error = _read_json(owner_approval_payload_audit_path)
    approval, approval_error = _read_json(owner_approval_path)
    delivery_summary = _summary(delivery_packet)
    approval_audit_summary = _summary(approval_audit)
    owner = approval.get("owner")
    approval_id = approval.get("approval_id")
    approved_at = approval.get("approved_at")
    approval_stage_count = _int_or_none(approval.get("stage_include_count"))
    approval_stage_command_count = _int_or_none(approval.get("owner_stage_command_count"))
    expected_stage_count = _int_or_none(delivery_summary.get("stage_include_count"))
    expected_stage_command_count = _int_or_none(delivery_summary.get("owner_stage_command_count"))
    approval_commit_preview = approval.get("commit_command_preview")
    expected_commit_preview = delivery_summary.get("commit_command_preview")
    approval_stage_path_digest = approval.get("stage_path_digest")
    expected_stage_path_digest = delivery_summary.get("stage_path_digest")
    approval_stage_command_digest = approval.get("stage_command_digest")
    expected_summary_stage_command_digest = delivery_summary.get("stage_command_digest")
    expected_stage_command_digest = _stage_command_digest(delivery_packet)
    approval_expected_stage_path_set_digest = approval.get("expected_stage_path_set_digest")
    expected_stage_path_set_digest = delivery_summary.get("expected_stage_path_set_digest")
    full_codex_parity_claimed = (
        delivery_packet.get("full_codex_parity_claimed") is True
        or approval.get("full_codex_parity_claimed") is True
    )
    stage_approved = (
        _bool(approval.get("approve_stage"))
        and str(approval.get("decision") or "") == "approve_owner_stage"
    )
    stage_counts_match = (
        approval_stage_count is not None
        and expected_stage_count is not None
        and approval_stage_count == expected_stage_count
        and approval_stage_command_count == expected_stage_command_count
    )
    commit_preview_matches = (
        isinstance(approval_commit_preview, str)
        and approval_commit_preview == expected_commit_preview
        and approval_commit_preview.startswith("git commit ")
    )
    stage_command_digest_matches = (
        isinstance(approval_stage_command_digest, str)
        and isinstance(expected_stage_command_digest, str)
        and expected_stage_command_digest == expected_summary_stage_command_digest
        and approval_stage_command_digest == expected_stage_command_digest
    )
    stage_path_digest_matches = (
        isinstance(approval_stage_path_digest, str)
        and isinstance(expected_stage_path_digest, str)
        and approval_stage_path_digest == expected_stage_path_digest
    )
    expected_stage_path_set_digest_matches = (
        isinstance(approval_expected_stage_path_set_digest, str)
        and isinstance(expected_stage_path_set_digest, str)
        and approval_expected_stage_path_set_digest == expected_stage_path_set_digest
    )
    owner_identity_present = all(
        _non_placeholder_text(value)
        for value in (owner, approval_id, approval.get("rationale"))
    ) and _valid_approved_at(approved_at)
    approval_audit_ready = (
        _status(approval_audit) == "owner_approval_payload_ready"
        and approval_audit.get("approval_payload_valid") is True
        and approval_audit.get("ready_for_approval_gate") is True
        and approval_audit.get("owner") == owner
        and approval_audit.get("approval_id") == approval_id
        and approval_audit.get("approved_at") == approved_at
        and approval_audit_summary.get("stage_path_digest") == expected_stage_path_digest
        and approval_audit_summary.get("approval_stage_path_digest") == approval_stage_path_digest
        and approval_audit_summary.get("stage_command_digest") == expected_stage_command_digest
        and approval_audit_summary.get("approval_stage_command_digest") == approval_stage_command_digest
        and approval_audit_summary.get("expected_stage_path_set_digest") == expected_stage_path_set_digest
        and approval_audit_summary.get("approval_expected_stage_path_set_digest") == approval_expected_stage_path_set_digest
    )

    checks = [
        _check(
            "owner_delivery_packet_readable",
            delivery_error is None,
            details={"owner_delivery_packet_path": _display_path(owner_delivery_packet_path)},
            error=delivery_error,
        ),
        _check(
            "owner_approval_readable",
            approval_error is None,
            details={"owner_approval_path": _display_path(owner_approval_path)},
            error=approval_error,
        ),
        _check(
            "owner_approval_payload_audit_readable",
            approval_audit_error is None,
            details={"owner_approval_payload_audit_path": _display_path(owner_approval_payload_audit_path)},
            error=approval_audit_error,
        ),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready",
            details={"status": _status(delivery_packet)},
            error="owner delivery packet is not ready",
        ),
        _check(
            "owner_approval_decision_present",
            stage_approved,
            details={
                "decision": approval.get("decision"),
                "approve_stage": approval.get("approve_stage"),
            },
            error="owner approval does not explicitly approve staging",
        ),
        _check(
            "owner_identity_present",
            owner_identity_present,
            details={
                "owner": owner,
                "approval_id": approval_id,
                "approved_at": approved_at,
                "approved_at_iso8601": _valid_approved_at(approved_at),
                "rationale_present": bool(str(approval.get("rationale") or "").strip()),
                "placeholders_rejected": True,
            },
            error="owner approval must include concrete owner, approval_id, ISO approved_at, and rationale values",
        ),
        _check(
            "stage_counts_match_owner_delivery_packet",
            stage_counts_match,
            details={
                "approval_stage_include_count": approval_stage_count,
                "expected_stage_include_count": expected_stage_count,
                "approval_owner_stage_command_count": approval_stage_command_count,
                "expected_owner_stage_command_count": expected_stage_command_count,
            },
            error="owner approval stage counts do not match the owner delivery packet",
        ),
        _check(
            "commit_preview_matches_owner_delivery_packet",
            commit_preview_matches,
            details={
                "approval_commit_command_preview": approval_commit_preview,
                "expected_commit_command_preview": expected_commit_preview,
            },
            error="owner approval commit preview does not match the owner delivery packet",
        ),
        _check(
            "stage_path_digest_matches_owner_delivery_packet",
            stage_path_digest_matches,
            details={
                "approval_stage_path_digest": approval_stage_path_digest,
                "expected_stage_path_digest": expected_stage_path_digest,
            },
            error="owner approval stage path digest does not match the owner delivery packet",
        ),
        _check(
            "expected_stage_path_set_digest_matches_owner_delivery_packet",
            expected_stage_path_set_digest_matches,
            details={
                "approval_expected_stage_path_set_digest": approval_expected_stage_path_set_digest,
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
            },
            error="owner approval expected stage path set digest does not match the owner delivery packet",
        ),
        _check(
            "stage_command_digest_matches_owner_delivery_packet",
            stage_command_digest_matches,
            details={
                "approval_stage_command_digest": approval_stage_command_digest,
                "expected_stage_command_digest": expected_stage_command_digest,
                "expected_summary_stage_command_digest": expected_summary_stage_command_digest,
            },
            error="owner approval stage command digest does not match the owner delivery packet",
        ),
        _check(
            "owner_acknowledges_gates",
            approval.get("acknowledge_pre_stage_verification") is True
            and approval.get("acknowledge_post_stage_verification") is True
            and approval.get("acknowledge_no_broad_git_add") is True,
            details={
                "acknowledge_pre_stage_verification": approval.get("acknowledge_pre_stage_verification"),
                "acknowledge_post_stage_verification": approval.get("acknowledge_post_stage_verification"),
                "acknowledge_no_broad_git_add": approval.get("acknowledge_no_broad_git_add"),
            },
            error="owner approval must acknowledge pre-stage, post-stage, and no broad git add gates",
        ),
        _check(
            "owner_approval_payload_audit_ready",
            approval_audit_ready,
            details={
                "owner_approval_payload_audit_status": _status(approval_audit),
                "approval_payload_valid": approval_audit.get("approval_payload_valid"),
                "ready_for_approval_gate": approval_audit.get("ready_for_approval_gate"),
                "audit_owner": approval_audit.get("owner"),
                "approval_owner": owner,
                "audit_approval_id": approval_audit.get("approval_id"),
                "approval_id": approval_id,
                "audit_stage_path_digest": approval_audit_summary.get("stage_path_digest"),
                "audit_approval_stage_path_digest": approval_audit_summary.get("approval_stage_path_digest"),
                "expected_stage_path_digest": expected_stage_path_digest,
                "approval_stage_path_digest": approval_stage_path_digest,
                "audit_stage_command_digest": approval_audit_summary.get("stage_command_digest"),
                "audit_approval_stage_command_digest": approval_audit_summary.get("approval_stage_command_digest"),
                "expected_stage_command_digest": expected_stage_command_digest,
                "approval_stage_command_digest": approval_stage_command_digest,
                "audit_expected_stage_path_set_digest": approval_audit_summary.get("expected_stage_path_set_digest"),
                "audit_approval_expected_stage_path_set_digest": approval_audit_summary.get(
                    "approval_expected_stage_path_set_digest"
                ),
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "approval_expected_stage_path_set_digest": approval_expected_stage_path_set_digest,
            },
            error="owner approval payload audit is not ready or does not match approval and delivery packet evidence",
        ),
        _check(
            "owner_delivery_packet_pre_stage_ready",
            delivery_packet.get("stage_ready") is True and delivery_packet.get("owner_approval_required") is True,
            details={
                "stage_ready": delivery_packet.get("stage_ready"),
                "owner_approval_required": delivery_packet.get("owner_approval_required"),
            },
            error="owner delivery packet is not in pre-stage owner approval state",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="owner approval gate inputs claim full Codex parity",
        ),
        _check(
            "no_approval_gate_mutation",
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
    status = "owner_stage_approval_ready" if ready else "owner_stage_approval_blocked"
    blocking_reasons = _failed_check_names(checks)

    return OwnerStageApprovalGate(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_stage_approval_gate",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        stage_approved=stage_approved,
        stage_allowed=ready,
        owner=str(owner) if owner is not None else None,
        approval_id=str(approval_id) if approval_id is not None else None,
        approved_at=str(approved_at) if approved_at is not None else None,
        reports={
            "owner_delivery_packet": _display_path(owner_delivery_packet_path),
            "owner_approval_payload_audit": _display_path(owner_approval_payload_audit_path),
            "owner_approval": _display_path(owner_approval_path),
        },
        report_statuses={
            "owner_delivery_packet": _status(delivery_packet),
            "owner_approval_payload_audit": _status(approval_audit),
            "owner_approval": _status(approval),
        },
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": not ready,
            "stage_include_count": expected_stage_count,
            "owner_stage_command_count": expected_stage_command_count,
            "secondary_pending_count": delivery_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": delivery_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": delivery_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": delivery_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": delivery_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "approval_stage_include_count": approval_stage_count,
            "approval_owner_stage_command_count": approval_stage_command_count,
            "commit_command_preview": expected_commit_preview,
            "approval_commit_command_preview": approval_commit_preview,
            "stage_path_digest": expected_stage_path_digest,
            "approval_stage_path_digest": approval_stage_path_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "approval_expected_stage_path_set_digest": approval_expected_stage_path_set_digest,
            "stage_command_digest": expected_stage_command_digest,
            "approval_stage_command_digest": approval_stage_command_digest,
            "owner_delivery_packet_status": _status(delivery_packet),
            "owner_approval_payload_audit_status": _status(approval_audit),
            "owner_approval_payload_valid": approval_audit.get("approval_payload_valid"),
            "owner_approval_payload_ready_for_gate": approval_audit.get("ready_for_approval_gate"),
            "owner_approval_status": _status(approval),
        },
        checks=checks,
        next_actions=[
            "If ready, run owner staging preflight again immediately before executing the approved stage commands.",
            "If blocked, update the owner approval payload; do not stage until this gate is ready.",
            "After staging, rerun post-stage verifier, commit gate, commit packet, delivery packet, and task board.",
        ],
        known_limits=[
            "This gate validates explicit owner approval evidence only.",
            "It does not create approval evidence, stage files, commit, push, run tests, call network services, or execute agents.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_gate(gate: OwnerStageApprovalGate) -> str:
    lines = [
        "# Commercial Delivery Owner Stage Approval Gate",
        "",
        f"- Status: `{gate.status}`",
        f"- Generated at: `{gate.generated_at}`",
        f"- Stage approved: `{str(gate.stage_approved).lower()}`",
        f"- Stage allowed: `{str(gate.stage_allowed).lower()}`",
        f"- Owner: `{gate.owner}`",
        f"- Approval ID: `{gate.approval_id}`",
        f"- Owner action required: `{str(gate.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(gate.summary.get('blocking_reasons') or [])}`",
        f"- Secondary handoff next queue: `{', '.join(gate.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{gate.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{gate.summary.get('secondary_handoff_latest_completed_candidate')}`",
        "",
        "## Checks",
        "",
    ]
    for check in gate.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in gate.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(gate: OwnerStageApprovalGate, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_gate(gate: OwnerStageApprovalGate, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_gate(gate), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_owner_stage_approval_gate(
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_approval_path=args.owner_approval,
    )
    write_report(gate, args.output)
    write_markdown_gate(gate, args.markdown_output)
    print(f"Commercial delivery owner stage approval gate status: {gate.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage approved: {gate.stage_approved}")
    print(f"Stage allowed: {gate.stage_allowed}")
    for check in gate.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if gate.status == "owner_stage_approval_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
