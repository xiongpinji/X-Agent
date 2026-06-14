#!/usr/bin/env python3
"""Audit the owner stage approval payload before running the stage gate.

This report is read-only. It validates the owner-provided approval payload
against the current owner delivery packet and approval request template. It
does not create approval evidence, stage files, commit, push, call network
services, run tests, or execute agents.
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
DEFAULT_OWNER_STAGE_APPROVAL_REQUEST = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.md"
PLACEHOLDER_VALUES = {
    "<owner-name-or-id>",
    "<approval-id>",
    "<ISO-8601 UTC timestamp>",
}


@dataclass(frozen=True)
class OwnerApprovalPayloadAuditCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerApprovalPayloadAudit:
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
    approval_payload_present: bool
    approval_payload_valid: bool
    ready_for_approval_gate: bool
    owner: str | None
    approval_id: str | None
    approved_at: str | None
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[OwnerApprovalPayloadAuditCheck]
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
) -> OwnerApprovalPayloadAuditCheck:
    return OwnerApprovalPayloadAuditCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerApprovalPayloadAuditCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


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
    try:
        datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


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


def _failed_report_check_names(payload: dict[str, Any]) -> set[str]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return set()
    names: set[str] = set()
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "failed":
            name = check.get("name")
            if name is not None:
                names.add(str(name))
    return names


def build_owner_approval_payload_audit(
    *,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_stage_approval_request_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_REQUEST,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> OwnerApprovalPayloadAudit:
    report_paths = {
        "owner_delivery_packet": owner_delivery_packet_path,
        "owner_stage_approval_request": owner_stage_approval_request_path,
        "owner_approval": owner_approval_path,
    }
    delivery_packet, delivery_error = _read_json(owner_delivery_packet_path)
    approval_request, request_error = _read_json(owner_stage_approval_request_path)
    approval, approval_error = _read_json(owner_approval_path)
    delivery_summary = _summary(delivery_packet)
    request_summary = _summary(approval_request)
    template = approval_request.get("suggested_owner_approval_payload")
    if not isinstance(template, dict):
        template = {}

    expected_stage_count = delivery_summary.get("stage_include_count")
    expected_command_count = delivery_summary.get("owner_stage_command_count")
    expected_commit_preview = delivery_summary.get("commit_command_preview")
    expected_stage_path_digest = delivery_summary.get("stage_path_digest")
    expected_stage_command_digest = _stage_command_digest(delivery_packet)
    expected_summary_stage_command_digest = delivery_summary.get("stage_command_digest")
    expected_path_set_digest = delivery_summary.get("expected_stage_path_set_digest")
    post_commit_noop_accounted_for = (
        delivery_summary.get("post_commit_noop_accounted_for") is True
        and delivery_summary.get("post_commit_owner_gate_accounted_for") is True
        and delivery_summary.get("owner_stage_command_count") == 0
        and request_summary.get("owner_stage_command_count") == 0
    )
    empty_digest = _digest_values([])
    if post_commit_noop_accounted_for and not expected_stage_command_digest:
        expected_stage_command_digest = empty_digest
    if post_commit_noop_accounted_for and not isinstance(expected_path_set_digest, str):
        expected_path_set_digest = empty_digest

    owner = approval.get("owner")
    approval_id = approval.get("approval_id")
    approved_at = approval.get("approved_at")
    stage_approved = approval.get("approve_stage") is True and approval.get("decision") == "approve_owner_stage"
    owner_identity_present = all(
        _non_placeholder_text(value)
        for value in (owner, approval_id, approval.get("rationale"))
    ) and _valid_approved_at(approved_at)

    approval_payload_present = approval_error is None
    full_codex_parity_claimed = (
        delivery_packet.get("full_codex_parity_claimed") is True
        or approval_request.get("full_codex_parity_claimed") is True
        or approval.get("full_codex_parity_claimed") is True
    )
    counts_match = (
        approval.get("stage_include_count") == expected_stage_count
        and approval.get("owner_stage_command_count") == expected_command_count
        and template.get("stage_include_count") == expected_stage_count
        and template.get("owner_stage_command_count") == expected_command_count
        and request_summary.get("stage_include_count") == expected_stage_count
        and request_summary.get("owner_stage_command_count") == expected_command_count
    )
    digests_match = (
        isinstance(expected_stage_path_digest, str)
        and approval.get("stage_path_digest") == expected_stage_path_digest
        and template.get("stage_path_digest") == expected_stage_path_digest
        and request_summary.get("stage_path_digest") == expected_stage_path_digest
        and isinstance(expected_stage_command_digest, str)
        and expected_stage_command_digest == expected_summary_stage_command_digest
        and approval.get("stage_command_digest") == expected_stage_command_digest
        and template.get("stage_command_digest") == expected_stage_command_digest
        and request_summary.get("stage_command_digest") == expected_stage_command_digest
        and isinstance(expected_path_set_digest, str)
        and approval.get("expected_stage_path_set_digest") == expected_path_set_digest
        and template.get("expected_stage_path_set_digest") == expected_path_set_digest
        and request_summary.get("expected_stage_path_set_digest") == expected_path_set_digest
    )
    commit_preview_matches = (
        isinstance(expected_commit_preview, str)
        and expected_commit_preview.startswith("git commit ")
        and approval.get("commit_command_preview") == expected_commit_preview
        and template.get("commit_command_preview") == expected_commit_preview
        and request_summary.get("commit_command_preview") == expected_commit_preview
    )
    acknowledgements_present = (
        approval.get("acknowledge_pre_stage_verification") is True
        and approval.get("acknowledge_post_stage_verification") is True
        and approval.get("acknowledge_no_broad_git_add") is True
    )
    owner_gated = (
        delivery_packet.get("owner_gated") is True
        and approval_request.get("owner_gated") is True
    )
    delivery_failed_check_names = _failed_report_check_names(delivery_packet)
    request_failed_check_names = _failed_report_check_names(approval_request)
    payload_matches_current_request_and_delivery = (
        approval_payload_present
        and delivery_error is None
        and request_error is None
        and stage_approved
        and owner_identity_present
        and counts_match
        and digests_match
        and commit_preview_matches
        and acknowledgements_present
        and owner_gated
        and not full_codex_parity_claimed
    )
    delivery_packet_bootstrap_accounted_for = (
        _status(delivery_packet) == "owner_delivery_packet_blocked"
        and delivery_failed_check_names == {"owner_approval_payload_audit_accounted_for"}
        and payload_matches_current_request_and_delivery
    )
    request_bootstrap_accounted_for = (
        _status(approval_request) == "owner_stage_approval_request_blocked"
        and (
            request_failed_check_names == {"owner_delivery_packet_ready"}
            or request_failed_check_names
            == {
                "owner_delivery_packet_ready",
                "owner_delivery_packet_requires_approval",
            }
        )
        and payload_matches_current_request_and_delivery
    )
    delivery_packet_status_accounted_for = (
        _status(delivery_packet) == "owner_delivery_packet_ready" or delivery_packet_bootstrap_accounted_for
    )
    approval_request_status_accounted_for = (
        _status(approval_request) == "owner_stage_approval_request_ready" or request_bootstrap_accounted_for
    )

    checks = [
        _check(
            "owner_delivery_packet_readable",
            delivery_error is None,
            details={"owner_delivery_packet_path": _display_path(owner_delivery_packet_path)},
            error=delivery_error,
        ),
        _check(
            "owner_stage_approval_request_readable",
            request_error is None,
            details={"owner_stage_approval_request_path": _display_path(owner_stage_approval_request_path)},
            error=request_error,
        ),
        _check(
            "owner_approval_payload_readable",
            approval_error is None,
            details={"owner_approval_path": _display_path(owner_approval_path)},
            error=approval_error,
        ),
        _check(
            "owner_delivery_packet_ready",
            delivery_packet_status_accounted_for,
            details={
                "status": _status(delivery_packet),
                "failed_check_names": sorted(delivery_failed_check_names),
                "bootstrap_accounted_for": delivery_packet_bootstrap_accounted_for,
            },
            error="owner delivery packet is not ready",
        ),
        _check(
            "owner_stage_approval_request_ready",
            approval_request_status_accounted_for,
            details={
                "status": _status(approval_request),
                "failed_check_names": sorted(request_failed_check_names),
                "bootstrap_accounted_for": request_bootstrap_accounted_for,
            },
            error="owner stage approval request is not ready",
        ),
        _check(
            "approval_decision_present",
            stage_approved,
            details={"decision": approval.get("decision"), "approve_stage": approval.get("approve_stage")},
            error="owner approval payload does not explicitly approve owner staging",
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
            error="owner approval payload must include concrete owner, approval_id, approved_at, and rationale",
        ),
        _check(
            "approval_counts_match_request_and_delivery_packet",
            counts_match,
            details={
                "approval_stage_include_count": approval.get("stage_include_count"),
                "approval_owner_stage_command_count": approval.get("owner_stage_command_count"),
                "request_stage_include_count": request_summary.get("stage_include_count"),
                "template_stage_include_count": template.get("stage_include_count"),
                "delivery_stage_include_count": expected_stage_count,
                "delivery_owner_stage_command_count": expected_command_count,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner approval payload counts do not match request/template/delivery packet",
        ),
        _check(
            "approval_digests_match_request_and_delivery_packet",
            digests_match,
            details={
                "approval_stage_path_digest": approval.get("stage_path_digest"),
                "approval_stage_command_digest": approval.get("stage_command_digest"),
                "approval_expected_stage_path_set_digest": approval.get("expected_stage_path_set_digest"),
                "request_stage_path_digest": request_summary.get("stage_path_digest"),
                "request_stage_command_digest": request_summary.get("stage_command_digest"),
                "request_expected_stage_path_set_digest": request_summary.get("expected_stage_path_set_digest"),
                "template_stage_path_digest": template.get("stage_path_digest"),
                "template_stage_command_digest": template.get("stage_command_digest"),
                "template_expected_stage_path_set_digest": template.get("expected_stage_path_set_digest"),
                "delivery_stage_path_digest": expected_stage_path_digest,
                "delivery_stage_command_digest": expected_stage_command_digest,
                "delivery_expected_stage_path_set_digest": expected_path_set_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner approval payload digests do not match request/template/delivery packet",
        ),
        _check(
            "commit_preview_matches_request_and_delivery_packet",
            commit_preview_matches,
            details={
                "approval_commit_command_preview": approval.get("commit_command_preview"),
                "request_commit_command_preview": request_summary.get("commit_command_preview"),
                "template_commit_command_preview": template.get("commit_command_preview"),
                "delivery_commit_command_preview": expected_commit_preview,
            },
            error="owner approval payload commit preview does not match request/template/delivery packet",
        ),
        _check(
            "owner_acknowledgements_present",
            acknowledgements_present,
            details={
                "acknowledge_pre_stage_verification": approval.get("acknowledge_pre_stage_verification"),
                "acknowledge_post_stage_verification": approval.get("acknowledge_post_stage_verification"),
                "acknowledge_no_broad_git_add": approval.get("acknowledge_no_broad_git_add"),
            },
            error="owner approval payload must acknowledge pre-stage, post-stage, and no broad git add gates",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_delivery_packet_owner_gated": delivery_packet.get("owner_gated"),
                "owner_stage_approval_request_owner_gated": approval_request.get("owner_gated"),
            },
            error="approval payload audit inputs are missing owner-gated markers",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="approval payload audit inputs claim full Codex parity",
        ),
        _check(
            "no_approval_payload_audit_mutation",
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
    approval_payload_valid = approval_payload_present and all(check.status == "passed" for check in checks)
    status = "owner_approval_payload_ready" if approval_payload_valid else "owner_approval_payload_blocked"
    blocking_reasons = _failed_check_names(checks)

    return OwnerApprovalPayloadAudit(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_approval_payload_audit",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        approval_payload_present=approval_payload_present,
        approval_payload_valid=approval_payload_valid,
        ready_for_approval_gate=approval_payload_valid,
        owner=str(owner) if owner is not None else None,
        approval_id=str(approval_id) if approval_id is not None else None,
        approved_at=str(approved_at) if approved_at is not None else None,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={
            "owner_delivery_packet": _status(delivery_packet),
            "owner_stage_approval_request": _status(approval_request),
            "owner_approval": _status(approval),
        },
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": not approval_payload_valid,
            "stage_include_count": expected_stage_count,
            "owner_stage_command_count": expected_command_count,
            "secondary_pending_count": delivery_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": delivery_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": delivery_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": delivery_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": delivery_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "approval_stage_include_count": approval.get("stage_include_count"),
            "approval_owner_stage_command_count": approval.get("owner_stage_command_count"),
            "commit_command_preview": expected_commit_preview,
            "approval_commit_command_preview": approval.get("commit_command_preview"),
            "stage_path_digest": expected_stage_path_digest,
            "approval_stage_path_digest": approval.get("stage_path_digest"),
            "stage_command_digest": expected_stage_command_digest,
            "approval_stage_command_digest": approval.get("stage_command_digest"),
            "expected_stage_path_set_digest": expected_path_set_digest,
            "approval_expected_stage_path_set_digest": approval.get("expected_stage_path_set_digest"),
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "owner_delivery_packet_status_accounted_for": delivery_packet_status_accounted_for,
            "owner_delivery_packet_bootstrap_accounted_for": delivery_packet_bootstrap_accounted_for,
            "owner_delivery_packet_failed_check_names": sorted(delivery_failed_check_names),
            "owner_stage_approval_request_status_accounted_for": approval_request_status_accounted_for,
            "owner_stage_approval_request_bootstrap_accounted_for": request_bootstrap_accounted_for,
            "owner_stage_approval_request_failed_check_names": sorted(request_failed_check_names),
        },
        checks=checks,
        next_actions=[
            "If blocked, create or correct the owner approval payload using the approval request template.",
            "Run commercial_delivery_owner_stage_approval_gate.py only after this audit reports owner_approval_payload_ready.",
            "Do not stage files until the approval gate and stage execution plan are ready.",
        ],
        known_limits=[
            "This audit is read-only except writing local evidence files.",
            "It does not create approval evidence, stage files, commit, push, run tests, call network services, or execute agents.",
            "It does not replace the owner stage approval gate.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_audit(audit: OwnerApprovalPayloadAudit) -> str:
    lines = [
        "# Commercial Delivery Owner Approval Payload Audit",
        "",
        f"- Status: `{audit.status}`",
        f"- Generated at: `{audit.generated_at}`",
        f"- Approval payload present: `{str(audit.approval_payload_present).lower()}`",
        f"- Approval payload valid: `{str(audit.approval_payload_valid).lower()}`",
        f"- Ready for approval gate: `{str(audit.ready_for_approval_gate).lower()}`",
        f"- Owner: `{audit.owner}`",
        f"- Approval ID: `{audit.approval_id}`",
        f"- Owner action required: `{str(audit.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(audit.summary.get('blocking_reasons') or [])}`",
        f"- Stage include count: `{audit.summary.get('stage_include_count')}`",
        f"- Secondary handoff next queue: `{', '.join(audit.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{audit.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{audit.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Expected stage path set digest: `{audit.summary.get('expected_stage_path_set_digest')}`",
        "",
        "## Checks",
        "",
    ]
    for check in audit.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in audit.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(audit: OwnerApprovalPayloadAudit, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_audit(audit: OwnerApprovalPayloadAudit, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_audit(audit), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-stage-approval-request", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_REQUEST)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_owner_approval_payload_audit(
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_stage_approval_request_path=args.owner_stage_approval_request,
        owner_approval_path=args.owner_approval,
    )
    write_report(audit, args.output)
    write_markdown_audit(audit, args.markdown_output)
    print(f"Commercial delivery owner approval payload audit status: {audit.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Approval payload present: {audit.approval_payload_present}")
    print(f"Ready for approval gate: {audit.ready_for_approval_gate}")
    for check in audit.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if audit.status == "owner_approval_payload_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
