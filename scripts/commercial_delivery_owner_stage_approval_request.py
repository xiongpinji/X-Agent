#!/usr/bin/env python3
"""Build the owner stage approval request and template.

This request helps the owner review the exact staging approval payload that
would satisfy the stage approval gate. It writes a request report, markdown
summary, and a template JSON file. It never writes the real approval payload,
stages files, creates commits, pushes, calls network services, or runs agents.
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

DEFAULT_OWNER_DELIVERY_PACKET = REPORT_DIR / "commercial-delivery-owner-delivery-packet.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.md"
DEFAULT_TEMPLATE_OUTPUT = REPORT_DIR / "commercial-delivery-owner-stage-approval.template.json"
OWNER_APPROVAL_TEMPLATE_PLACEHOLDERS = {
    "owner": "<owner-name-or-id>",
    "approval_id": "<approval-id>",
    "approved_at": "<ISO-8601 UTC timestamp>",
}


@dataclass(frozen=True)
class OwnerStageApprovalRequestCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStageApprovalRequest:
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
    approval_required: bool
    approval_payload_path: str
    template_output_path: str
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    suggested_owner_approval_payload: dict[str, Any]
    checks: list[OwnerStageApprovalRequestCheck]
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
) -> OwnerStageApprovalRequestCheck:
    return OwnerStageApprovalRequestCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


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
    if not values:
        return None
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stage_command_digest(packet: dict[str, Any]) -> str | None:
    return _digest_values(_section_commands(packet, "owner_stage_commands"))


def _template_identity_placeholders_present(template: dict[str, Any]) -> bool:
    return all(template.get(key) == value for key, value in OWNER_APPROVAL_TEMPLATE_PLACEHOLDERS.items()) and bool(
        str(template.get("rationale") or "").strip()
    )


def _build_suggested_payload(
    *,
    stage_include_count: int | None,
    owner_stage_command_count: int | None,
    commit_command_preview: object,
    stage_path_digest: str | None,
    stage_command_digest: str | None,
    expected_stage_path_set_digest: str | None,
) -> dict[str, Any]:
    return {
        "status": "owner_stage_approval_submitted",
        "decision": "approve_owner_stage",
        "approve_stage": True,
        "owner": "<owner-name-or-id>",
        "approval_id": "<approval-id>",
        "approved_at": "<ISO-8601 UTC timestamp>",
        "rationale": "Owner reviewed the delivery packet and approves explicit staging commands.",
        "stage_include_count": stage_include_count,
        "owner_stage_command_count": owner_stage_command_count,
        "stage_path_digest": stage_path_digest,
        "stage_command_digest": stage_command_digest,
        "expected_stage_path_set_digest": expected_stage_path_set_digest,
        "commit_command_preview": str(commit_command_preview or ""),
        "acknowledge_pre_stage_verification": True,
        "acknowledge_post_stage_verification": True,
        "acknowledge_no_broad_git_add": True,
        "full_codex_parity_claimed": False,
    }


def build_owner_stage_approval_request(
    *,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
    template_output_path: Path = DEFAULT_TEMPLATE_OUTPUT,
) -> OwnerStageApprovalRequest:
    delivery_packet, delivery_error = _read_json(owner_delivery_packet_path)
    approval_gate, approval_gate_error = _read_json(owner_stage_approval_gate_path)
    delivery_summary = _summary(delivery_packet)
    stage_include_count = _int_or_none(delivery_summary.get("stage_include_count"))
    raw_eligible_stage_count = _int_or_none(delivery_summary.get("eligible_stage_count"))
    owner_stage_command_count = _int_or_none(delivery_summary.get("owner_stage_command_count"))
    eligible_stage_count = (
        raw_eligible_stage_count
        if raw_eligible_stage_count is not None
        else owner_stage_command_count
    )
    commit_preview = delivery_summary.get("commit_command_preview")
    stage_path_digest = delivery_summary.get("stage_path_digest")
    summary_stage_command_digest = delivery_summary.get("stage_command_digest")
    expected_stage_path_set_digest = delivery_summary.get("expected_stage_path_set_digest")
    stage_command_digest = _stage_command_digest(delivery_packet)
    approval_gate_status = _status(approval_gate)
    approval_gate_stage_allowed = approval_gate.get("stage_allowed")
    full_codex_parity_claimed = (
        delivery_packet.get("full_codex_parity_claimed") is True
        or approval_gate.get("full_codex_parity_claimed") is True
    )
    counts_match = (
        stage_include_count is not None
        and eligible_stage_count is not None
        and owner_stage_command_count is not None
        and stage_include_count > 0
        and owner_stage_command_count > 0
        and owner_stage_command_count == eligible_stage_count
        and owner_stage_command_count <= stage_include_count
    )
    approval_gate_accounted_for = (
        approval_gate_status == "owner_stage_approval_ready"
        and approval_gate_stage_allowed is True
    ) or (
        approval_gate_status == "owner_stage_approval_blocked"
        and approval_gate_stage_allowed is not True
    )
    suggested_payload = _build_suggested_payload(
        stage_include_count=stage_include_count,
        owner_stage_command_count=owner_stage_command_count,
        commit_command_preview=commit_preview,
        stage_path_digest=str(stage_path_digest) if isinstance(stage_path_digest, str) else None,
        stage_command_digest=stage_command_digest,
        expected_stage_path_set_digest=(
            str(expected_stage_path_set_digest) if isinstance(expected_stage_path_set_digest, str) else None
        ),
    )
    template_identity_placeholders_present = _template_identity_placeholders_present(suggested_payload)

    checks = [
        _check(
            "owner_delivery_packet_readable",
            delivery_error is None,
            details={"owner_delivery_packet_path": _display_path(owner_delivery_packet_path)},
            error=delivery_error,
        ),
        _check(
            "owner_stage_approval_gate_readable",
            approval_gate_error is None,
            details={"owner_stage_approval_gate_path": _display_path(owner_stage_approval_gate_path)},
            error=approval_gate_error,
        ),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready",
            details={"status": _status(delivery_packet)},
            error="owner delivery packet is not ready",
        ),
        _check(
            "owner_delivery_packet_requires_approval",
            delivery_packet.get("stage_ready") is True and delivery_packet.get("owner_approval_required") is True,
            details={
                "stage_ready": delivery_packet.get("stage_ready"),
                "owner_approval_required": delivery_packet.get("owner_approval_required"),
            },
            error="owner delivery packet is not in owner approval state",
        ),
        _check(
            "stage_counts_match_delivery_packet",
            counts_match,
            details={
                "stage_include_count": stage_include_count,
                "eligible_stage_count": eligible_stage_count,
                "owner_stage_command_count": owner_stage_command_count,
            },
            error="owner delivery packet stage counts are missing or do not match eligible staging commands",
        ),
        _check(
            "commit_preview_present",
            isinstance(commit_preview, str) and commit_preview.startswith("git commit "),
            details={"commit_command_preview": commit_preview},
            error="owner delivery packet does not include a commit preview",
        ),
        _check(
            "stage_path_digest_present",
            isinstance(stage_path_digest, str) and len(stage_path_digest) == 64,
            details={"stage_path_digest": stage_path_digest},
            error="owner delivery packet does not include a stage path digest",
        ),
        _check(
            "stage_command_digest_present",
            isinstance(stage_command_digest, str)
            and len(stage_command_digest) == 64
            and stage_command_digest == summary_stage_command_digest,
            details={
                "stage_command_digest": stage_command_digest,
                "summary_stage_command_digest": summary_stage_command_digest,
            },
            error="owner delivery packet does not include digestable owner stage commands",
        ),
        _check(
            "expected_stage_path_set_digest_present",
            isinstance(expected_stage_path_set_digest, str) and len(expected_stage_path_set_digest) == 64,
            details={"expected_stage_path_set_digest": expected_stage_path_set_digest},
            error="owner delivery packet does not include an expected stage path set digest",
        ),
        _check(
            "approval_gate_accounted_for",
            approval_gate_accounted_for,
            details={
                "owner_stage_approval_gate_status": approval_gate_status,
                "stage_allowed": approval_gate_stage_allowed,
            },
            error="owner stage approval gate is missing or in an unknown state",
        ),
        _check(
            "template_does_not_target_real_approval_file",
            template_output_path.resolve() != owner_approval_path.resolve(),
            details={
                "template_output_path": _display_path(template_output_path),
                "owner_approval_path": _display_path(owner_approval_path),
            },
            error="template output must not be the real owner approval payload path",
        ),
        _check(
            "template_identity_placeholders_present",
            template_identity_placeholders_present,
            details={
                "template_owner": suggested_payload.get("owner"),
                "template_approval_id": suggested_payload.get("approval_id"),
                "template_approved_at": suggested_payload.get("approved_at"),
                "rationale_present": bool(str(suggested_payload.get("rationale") or "").strip()),
            },
            error="suggested owner approval payload identity fields must remain placeholders",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="owner approval request inputs claim full Codex parity",
        ),
        _check(
            "no_approval_request_mutation",
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
    status = "owner_stage_approval_request_ready" if ready else "owner_stage_approval_request_blocked"

    return OwnerStageApprovalRequest(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_stage_approval_request",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        approval_required=True,
        approval_payload_path=_display_path(owner_approval_path),
        template_output_path=_display_path(template_output_path),
        reports={
            "owner_delivery_packet": _display_path(owner_delivery_packet_path),
            "owner_stage_approval_gate": _display_path(owner_stage_approval_gate_path),
        },
        report_statuses={
            "owner_delivery_packet": _status(delivery_packet),
            "owner_stage_approval_gate": approval_gate_status,
        },
        summary={
            "stage_include_count": stage_include_count,
            "eligible_stage_count": eligible_stage_count,
            "owner_stage_command_count": owner_stage_command_count,
            "owner_stage_approval_gate_status": approval_gate_status,
            "stage_allowed": approval_gate_stage_allowed,
            "approval_payload_path": _display_path(owner_approval_path),
            "template_output_path": _display_path(template_output_path),
            "template_owner_placeholder": suggested_payload.get("owner"),
            "template_approval_id_placeholder": suggested_payload.get("approval_id"),
            "template_approved_at_placeholder": suggested_payload.get("approved_at"),
            "template_identity_placeholders_present": template_identity_placeholders_present,
            "commit_command_preview": commit_preview,
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "secondary_pending_count": delivery_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": delivery_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": delivery_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": delivery_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": delivery_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
        },
        suggested_owner_approval_payload=suggested_payload,
        checks=checks,
        next_actions=[
            "Owner reviews the delivery packet and this approval request.",
            "If approved, create the real owner approval payload at the approval_payload_path with concrete owner fields.",
            "Run commercial_delivery_owner_stage_approval_gate.py after the real approval payload exists.",
            "Execute stage commands only after the approval gate reports owner_stage_approval_ready.",
        ],
        known_limits=[
            "This request is read-only except writing local request/template evidence files.",
            "It does not write the real owner approval payload.",
            "It does not stage, commit, push, call network services, run tests, or execute agents.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_request(request: OwnerStageApprovalRequest) -> str:
    lines = [
        "# Commercial Delivery Owner Stage Approval Request",
        "",
        f"- Status: `{request.status}`",
        f"- Generated at: `{request.generated_at}`",
        f"- Approval payload path: `{request.approval_payload_path}`",
        f"- Template output path: `{request.template_output_path}`",
        f"- Stage include count: `{request.summary.get('stage_include_count')}`",
        f"- Owner stage command count: `{request.summary.get('owner_stage_command_count')}`",
        f"- Approval gate status: `{request.summary.get('owner_stage_approval_gate_status')}`",
        f"- Stage allowed: `{str(request.summary.get('stage_allowed')).lower()}`",
        f"- Secondary handoff next queue: `{', '.join(request.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{request.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{request.summary.get('secondary_handoff_latest_completed_candidate')}`",
        "",
        "## Checks",
        "",
    ]
    for check in request.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Suggested Approval Payload", "", "```json"])
    lines.append(json.dumps(request.suggested_owner_approval_payload, ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in request.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(request: OwnerStageApprovalRequest, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(request.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_request(
    request: OwnerStageApprovalRequest,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_request(request), encoding="utf-8")


def write_template(request: OwnerStageApprovalRequest, output_path: Path = DEFAULT_TEMPLATE_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(request.suggested_owner_approval_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--template-output", type=Path, default=DEFAULT_TEMPLATE_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = build_owner_stage_approval_request(
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_approval_path=args.owner_approval,
        template_output_path=args.template_output,
    )
    write_report(request, args.output)
    write_markdown_request(request, args.markdown_output)
    write_template(request, args.template_output)
    print(f"Commercial delivery owner stage approval request status: {request.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Template written to {args.template_output}")
    print(f"Approval payload path: {request.approval_payload_path}")
    for check in request.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if request.status == "owner_stage_approval_request_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
