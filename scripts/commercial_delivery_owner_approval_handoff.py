#!/usr/bin/env python3
"""Build the final owner approval handoff package.

This report is the last read-only handoff before a human owner creates the
real stage approval payload. It verifies that the approval request, template,
approval brief, delivery packet, rollback plan, closure snapshot, and task
board all describe the same current staging surface. It never writes the real
approval payload, stages files, commits, pushes, calls network services, runs
tests, or executes agents.
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
DEFAULT_OWNER_STAGE_APPROVAL_REQUEST = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_OWNER_STAGE_APPROVAL_TEMPLATE = REPORT_DIR / "commercial-delivery-owner-stage-approval.template.json"
DEFAULT_OWNER_STAGE_APPROVAL_BRIEF = REPORT_DIR / "commercial-delivery-owner-stage-approval-brief.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_STAGING_ROLLBACK_PLAN = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.json"
DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST = (
    REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
)
DEFAULT_CLOSURE_SNAPSHOT = REPORT_DIR / "commercial-delivery-closure-snapshot.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-handoff.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-approval-handoff.md"
OWNER_APPROVAL_TEMPLATE_PLACEHOLDERS = {
    "owner": "<owner-name-or-id>",
    "approval_id": "<approval-id>",
    "approved_at": "<ISO-8601 UTC timestamp>",
}


@dataclass(frozen=True)
class OwnerApprovalHandoffCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerApprovalHandoff:
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
    approval_payload_path: str
    approval_payload_audit_path: str
    template_path: str
    owner_action_required: bool
    stage_allowed: bool
    delivery_complete: bool
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    owner_action_payload_template: dict[str, Any]
    checks: list[OwnerApprovalHandoffCheck]
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


def _read_optional_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, None
    return _read_json(path)


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
) -> OwnerApprovalHandoffCheck:
    return OwnerApprovalHandoffCheck(
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


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _expected_pre_approval_blockers(snapshot: dict[str, Any]) -> bool:
    expected = {
        "owner_stage_approval_gate_not_ready",
        "owner_stage_execution_plan_not_ready",
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
    }
    blockers = snapshot.get("blockers")
    blocker_set = {str(item) for item in blockers} if isinstance(blockers, list) else set()
    return expected.issubset(blocker_set)


def _payload_count_values(payloads: list[dict[str, Any]]) -> list[int | None]:
    values: list[int | None] = []
    for payload in payloads:
        if "stage_include_count" in payload:
            values.append(_int_or_none(payload.get("stage_include_count")))
        values.append(_int_or_none(_summary(payload).get("stage_include_count")))
    return [value for value in values if value is not None]


def _template_identity_placeholders_present(template: dict[str, Any]) -> bool:
    return all(template.get(key) == value for key, value in OWNER_APPROVAL_TEMPLATE_PLACEHOLDERS.items()) and bool(
        str(template.get("rationale") or "").strip()
    )


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
    return _digest_values(_section_commands(packet, "owner_stage_commands")) or _summary(packet).get(
        "stage_command_digest"
    )


def build_owner_approval_handoff(
    *,
    owner_delivery_packet_path: Path = DEFAULT_OWNER_DELIVERY_PACKET,
    owner_stage_approval_request_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_REQUEST,
    owner_stage_approval_template_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_TEMPLATE,
    owner_stage_approval_brief_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_BRIEF,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_staging_rollback_plan_path: Path = DEFAULT_OWNER_STAGING_ROLLBACK_PLAN,
    owner_post_approval_operator_checklist_path: Path = DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    closure_snapshot_path: Path = DEFAULT_CLOSURE_SNAPSHOT,
    task_board_path: Path = DEFAULT_TASK_BOARD,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> OwnerApprovalHandoff:
    report_paths = {
        "owner_delivery_packet": owner_delivery_packet_path,
        "owner_stage_approval_request": owner_stage_approval_request_path,
        "owner_stage_approval_template": owner_stage_approval_template_path,
        "owner_stage_approval_brief": owner_stage_approval_brief_path,
        "owner_approval_payload_audit": owner_approval_payload_audit_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
        "owner_staging_rollback_plan": owner_staging_rollback_plan_path,
        "owner_post_approval_operator_checklist": owner_post_approval_operator_checklist_path,
        "closure_snapshot": closure_snapshot_path,
        "task_board": task_board_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        if name == "owner_post_approval_operator_checklist":
            payload, error = _read_optional_json(path)
        else:
            payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    delivery_packet = reports["owner_delivery_packet"]
    approval_request = reports["owner_stage_approval_request"]
    approval_template = reports["owner_stage_approval_template"]
    approval_brief = reports["owner_stage_approval_brief"]
    approval_payload_audit = reports["owner_approval_payload_audit"]
    approval_gate = reports["owner_stage_approval_gate"]
    stage_execution_plan = reports["owner_stage_execution_plan"]
    rollback_plan = reports["owner_staging_rollback_plan"]
    operator_checklist = reports["owner_post_approval_operator_checklist"]
    closure_snapshot = reports["closure_snapshot"]
    task_board = reports["task_board"]
    delivery_summary = _summary(delivery_packet)
    request_summary = _summary(approval_request)
    brief_summary = _summary(approval_brief)
    snapshot_summary = _summary(closure_snapshot)
    task_summary = _summary(task_board)
    approval_audit_summary = _summary(approval_payload_audit)
    operator_checklist_present = bool(operator_checklist)
    operator_checklist_status = _status(operator_checklist)
    operator_checklist_status_accounted_for = not operator_checklist_present or operator_checklist_status in {
        "owner_post_approval_operator_checklist_waiting_for_owner",
        "owner_post_approval_operator_checklist_ready",
    }
    template_payload = approval_brief.get("owner_action_payload_template")
    if not isinstance(template_payload, dict):
        template_payload = approval_request.get("suggested_owner_approval_payload")
    if not isinstance(template_payload, dict):
        template_payload = {}

    delivery_count = _int_or_none(delivery_summary.get("stage_include_count"))
    command_count = _int_or_none(delivery_summary.get("owner_stage_command_count"))
    rollback_count = _int_or_none(delivery_summary.get("rollback_reset_command_count"))
    template_count = _int_or_none(approval_template.get("stage_include_count"))
    template_command_count = _int_or_none(approval_template.get("owner_stage_command_count"))
    request_count = _int_or_none(request_summary.get("stage_include_count"))
    request_command_count = _int_or_none(request_summary.get("owner_stage_command_count"))
    brief_count = _int_or_none(brief_summary.get("stage_include_count"))
    brief_command_count = _int_or_none(brief_summary.get("owner_stage_command_count"))
    snapshot_count = _int_or_none(snapshot_summary.get("stage_include_count"))
    snapshot_command_count = _int_or_none(snapshot_summary.get("owner_stage_command_count"))
    stage_coverage_counts = [
        delivery_count,
        template_count,
        request_count,
        brief_count,
        snapshot_count,
    ]
    owner_command_counts = [
        command_count,
        rollback_count,
        template_command_count,
        request_command_count,
        brief_command_count,
        snapshot_command_count,
    ]
    stage_coverage_counts_match = (
        delivery_count is not None and all(value == delivery_count for value in stage_coverage_counts if value is not None)
    )
    owner_command_counts_match = command_count is not None and all(
        value == command_count for value in owner_command_counts if value is not None
    )
    owner_command_count_within_stage_coverage = (
        delivery_count is not None and command_count is not None and command_count <= delivery_count
    )
    counts_match = (
        stage_coverage_counts_match and owner_command_counts_match and owner_command_count_within_stage_coverage
    )
    commit_preview = delivery_summary.get("commit_command_preview")
    template_commit_preview = approval_template.get("commit_command_preview")
    request_commit_preview = request_summary.get("commit_command_preview")
    delivery_stage_path_digest = delivery_summary.get("stage_path_digest")
    template_stage_path_digest = approval_template.get("stage_path_digest")
    request_stage_path_digest = request_summary.get("stage_path_digest")
    brief_stage_path_digest = brief_summary.get("stage_path_digest")
    snapshot_expected_stage_path_set_digest = snapshot_summary.get("expected_stage_path_set_digest")
    delivery_expected_stage_path_set_digest = delivery_summary.get("expected_stage_path_set_digest")
    template_expected_stage_path_set_digest = approval_template.get("expected_stage_path_set_digest")
    request_expected_stage_path_set_digest = request_summary.get("expected_stage_path_set_digest")
    brief_expected_stage_path_set_digest = brief_summary.get("expected_stage_path_set_digest")
    delivery_stage_command_digest = _stage_command_digest(delivery_packet)
    delivery_summary_stage_command_digest = delivery_summary.get("stage_command_digest")
    template_stage_command_digest = approval_template.get("stage_command_digest")
    request_stage_command_digest = request_summary.get("stage_command_digest")
    brief_stage_command_digest = brief_summary.get("stage_command_digest")
    template_matches = (
        approval_template.get("decision") == "approve_owner_stage"
        and approval_template.get("approve_stage") is True
        and template_count == delivery_count
        and approval_template.get("owner_stage_command_count") == command_count
        and isinstance(template_stage_path_digest, str)
        and template_stage_path_digest == delivery_stage_path_digest
        and isinstance(template_stage_command_digest, str)
        and template_stage_command_digest == delivery_stage_command_digest
        and delivery_stage_command_digest == delivery_summary_stage_command_digest
        and isinstance(template_expected_stage_path_set_digest, str)
        and template_expected_stage_path_set_digest == delivery_expected_stage_path_set_digest
        and template_commit_preview == commit_preview
        and approval_template.get("acknowledge_pre_stage_verification") is True
        and approval_template.get("acknowledge_post_stage_verification") is True
        and approval_template.get("acknowledge_no_broad_git_add") is True
        and approval_template.get("full_codex_parity_claimed") is False
    )
    template_identity_placeholders_present = _template_identity_placeholders_present(approval_template)
    stage_allowed = approval_gate.get("stage_allowed") is True
    real_owner_approval_written = owner_approval_path.exists()
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    closure_expected = (
        _status(closure_snapshot) == "commercial_delivery_closure_blocked"
        and closure_snapshot.get("delivery_complete") is False
        and _expected_pre_approval_blockers(closure_snapshot)
    )
    delivery_complete = closure_snapshot.get("delivery_complete") is True
    post_approval_operator_checklist_accounted_for = (
        operator_checklist_status in {
            "owner_post_approval_operator_checklist_ready",
            "owner_post_approval_operator_checklist_waiting_for_owner",
        }
        or (
            operator_checklist_status == "owner_post_approval_operator_checklist_blocked"
            and operator_checklist.get("real_owner_approval_present") is True
            and operator_checklist.get("waiting_for_owner") is not True
            and operator_checklist.get("operator_ready") is not True
        )
    )
    post_approval_noop_accounted_for = (
        real_owner_approval_written
        and delivery_summary.get("post_commit_noop_accounted_for") is True
        and _status(approval_payload_audit) == "owner_approval_payload_ready"
        and approval_payload_audit.get("approval_payload_present") is True
        and approval_payload_audit.get("approval_payload_valid") is True
        and approval_payload_audit.get("ready_for_approval_gate") is True
        and _status(approval_gate) == "owner_stage_approval_ready"
        and stage_allowed
        and _status(stage_execution_plan) == "owner_stage_execution_ready"
        and stage_execution_plan.get("stage_allowed") is True
        and delivery_complete
        and post_approval_operator_checklist_accounted_for
    )
    approval_payload_audit_pre_approval_blocked = (
        _status(approval_payload_audit) == "owner_approval_payload_blocked"
        and approval_payload_audit.get("approval_payload_present") is False
        and approval_payload_audit.get("ready_for_approval_gate") is not True
    )
    approval_payload_audit_digest_context_matches = (
        isinstance(delivery_stage_path_digest, str)
        and approval_audit_summary.get("stage_path_digest") == delivery_stage_path_digest
        and isinstance(delivery_stage_command_digest, str)
        and approval_audit_summary.get("stage_command_digest") == delivery_stage_command_digest
        and isinstance(delivery_expected_stage_path_set_digest, str)
        and approval_audit_summary.get("expected_stage_path_set_digest") == delivery_expected_stage_path_set_digest
    )
    owner_gated = (
        delivery_packet.get("owner_gated") is True
        and approval_request.get("owner_gated") is True
        and approval_brief.get("owner_gated") is True
        and approval_payload_audit.get("owner_gated") is True
        and approval_gate.get("owner_gated") is True
        and stage_execution_plan.get("owner_gated") is True
        and rollback_plan.get("owner_gated") is True
        and (not operator_checklist_present or operator_checklist.get("owner_gated") is True)
    )

    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="approval handoff inputs are missing or unreadable"),
        _check(
            "owner_delivery_packet_ready",
            _status(delivery_packet) == "owner_delivery_packet_ready",
            details={"status": _status(delivery_packet), "stage_ready": delivery_packet.get("stage_ready")},
            error="owner delivery packet is not ready",
        ),
        _check(
            "approval_request_ready",
            _status(approval_request) == "owner_stage_approval_request_ready",
            details={"status": _status(approval_request)},
            error="owner approval request is not ready",
        ),
        _check(
            "approval_brief_ready",
            _status(approval_brief) == "owner_stage_approval_brief_ready",
            details={"status": _status(approval_brief)},
            error="owner approval brief is not ready",
        ),
        _check(
            "current_counts_match",
            counts_match,
            details={
                "delivery_stage_include_count": delivery_count,
                "owner_stage_command_count": command_count,
                "rollback_reset_command_count": rollback_count,
                "template_stage_include_count": template_count,
                "template_owner_stage_command_count": template_command_count,
                "request_stage_include_count": request_count,
                "request_owner_stage_command_count": request_command_count,
                "brief_stage_include_count": brief_count,
                "brief_owner_stage_command_count": brief_command_count,
                "snapshot_stage_include_count": snapshot_count,
                "snapshot_owner_stage_command_count": snapshot_command_count,
                "stage_coverage_counts_match": stage_coverage_counts_match,
                "owner_command_counts_match": owner_command_counts_match,
                "owner_command_count_within_stage_coverage": owner_command_count_within_stage_coverage,
            },
            error="owner approval handoff counts do not match the current delivery packet",
        ),
        _check(
            "approval_template_matches_delivery_packet",
            template_matches,
            details={
                "template_decision": approval_template.get("decision"),
                "template_approve_stage": approval_template.get("approve_stage"),
                "template_stage_include_count": template_count,
                "template_owner_stage_command_count": approval_template.get("owner_stage_command_count"),
                "delivery_stage_include_count": delivery_count,
                "delivery_owner_stage_command_count": command_count,
                "template_commit_preview": template_commit_preview,
                "delivery_commit_preview": commit_preview,
                "template_stage_path_digest": template_stage_path_digest,
                "delivery_stage_path_digest": delivery_stage_path_digest,
                "template_stage_command_digest": template_stage_command_digest,
                "delivery_stage_command_digest": delivery_stage_command_digest,
                "delivery_summary_stage_command_digest": delivery_summary_stage_command_digest,
                "template_expected_stage_path_set_digest": template_expected_stage_path_set_digest,
                "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
            },
            error="owner approval template is stale or missing required acknowledgements",
        ),
        _check(
            "approval_template_identity_placeholders_present",
            template_identity_placeholders_present,
            details={
                "template_owner": approval_template.get("owner"),
                "template_approval_id": approval_template.get("approval_id"),
                "template_approved_at": approval_template.get("approved_at"),
                "rationale_present": bool(str(approval_template.get("rationale") or "").strip()),
            },
            error="owner approval template identity fields must remain placeholders until the real owner approval payload is created",
        ),
        _check(
            "approval_request_and_brief_digests_match_delivery_packet",
            isinstance(delivery_stage_path_digest, str)
            and request_stage_path_digest == delivery_stage_path_digest
            and brief_stage_path_digest == delivery_stage_path_digest
            and isinstance(delivery_stage_command_digest, str)
            and delivery_stage_command_digest == delivery_summary_stage_command_digest
            and request_stage_command_digest == delivery_stage_command_digest
            and brief_stage_command_digest == delivery_stage_command_digest
            and isinstance(delivery_expected_stage_path_set_digest, str)
            and request_expected_stage_path_set_digest == delivery_expected_stage_path_set_digest
            and brief_expected_stage_path_set_digest == delivery_expected_stage_path_set_digest
            and template_expected_stage_path_set_digest == delivery_expected_stage_path_set_digest,
            details={
                "delivery_stage_path_digest": delivery_stage_path_digest,
                "request_stage_path_digest": request_stage_path_digest,
                "brief_stage_path_digest": brief_stage_path_digest,
                "delivery_stage_command_digest": delivery_stage_command_digest,
                "delivery_summary_stage_command_digest": delivery_summary_stage_command_digest,
                "request_stage_command_digest": request_stage_command_digest,
                "brief_stage_command_digest": brief_stage_command_digest,
                "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
                "request_expected_stage_path_set_digest": request_expected_stage_path_set_digest,
                "brief_expected_stage_path_set_digest": brief_expected_stage_path_set_digest,
                "template_expected_stage_path_set_digest": template_expected_stage_path_set_digest,
            },
            error="owner approval request or brief digests do not match the delivery packet",
        ),
        _check(
            "approval_payload_audit_pre_approval_blocked",
            approval_payload_audit_pre_approval_blocked or post_approval_noop_accounted_for,
            details={
                "owner_approval_payload_audit_status": _status(approval_payload_audit),
                "approval_payload_present": approval_payload_audit.get("approval_payload_present"),
                "approval_payload_valid": approval_payload_audit.get("approval_payload_valid"),
                "ready_for_approval_gate": approval_payload_audit.get("ready_for_approval_gate"),
            },
            error="owner approval payload audit must show a pre-approval blocked state before handoff",
        ),
        _check(
            "approval_payload_audit_digest_context_matches_delivery_packet",
            approval_payload_audit_digest_context_matches,
            details={
                "audit_stage_path_digest": approval_audit_summary.get("stage_path_digest"),
                "delivery_stage_path_digest": delivery_stage_path_digest,
                "audit_stage_command_digest": approval_audit_summary.get("stage_command_digest"),
                "delivery_stage_command_digest": delivery_stage_command_digest,
                "audit_expected_stage_path_set_digest": approval_audit_summary.get("expected_stage_path_set_digest"),
                "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
            },
            error="owner approval payload audit context does not match the delivery packet",
        ),
        _check(
            "closure_expected_stage_path_set_digest_matches_delivery_packet",
            isinstance(delivery_expected_stage_path_set_digest, str)
            and snapshot_expected_stage_path_set_digest == delivery_expected_stage_path_set_digest,
            details={
                "delivery_expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
                "snapshot_expected_stage_path_set_digest": snapshot_expected_stage_path_set_digest,
                "snapshot_cached_staged_path_set_digest": snapshot_summary.get("cached_staged_path_set_digest"),
            },
            error="closure snapshot expected stage path set digest does not match the owner delivery packet",
        ),
        _check(
            "approval_payload_path_is_real_target",
            approval_request.get("approval_payload_path") == _display_path(owner_approval_path),
            details={
                "approval_request_payload_path": approval_request.get("approval_payload_path"),
                "owner_approval_path": _display_path(owner_approval_path),
            },
            error="owner approval request points at a different approval payload path",
        ),
        _check(
            "template_path_is_not_real_approval",
            owner_stage_approval_template_path.resolve() != owner_approval_path.resolve(),
            details={
                "template_path": _display_path(owner_stage_approval_template_path),
                "owner_approval_path": _display_path(owner_approval_path),
            },
            error="approval template must not be written to the real owner approval path",
        ),
        _check(
            "real_owner_approval_not_written_by_handoff",
            not real_owner_approval_written or post_approval_noop_accounted_for,
            details={"owner_approval_path": _display_path(owner_approval_path)},
            error="real owner approval payload already exists; run approval gate instead of handoff",
        ),
        _check(
            "pre_approval_blockers_accounted_for",
            closure_expected or delivery_complete,
            details={
                "closure_snapshot_status": _status(closure_snapshot),
                "delivery_complete": closure_snapshot.get("delivery_complete"),
                "blockers": closure_snapshot.get("blockers"),
            },
            error="closure snapshot does not show the expected pre-approval blockers",
        ),
        _check(
            "stage_not_allowed_before_owner_approval",
            (
                stage_allowed is False
                and _status(approval_gate) == "owner_stage_approval_blocked"
                and _status(stage_execution_plan) == "owner_stage_execution_blocked"
            )
            or post_approval_noop_accounted_for,
            details={
                "owner_stage_approval_gate_status": _status(approval_gate),
                "owner_stage_execution_plan_status": _status(stage_execution_plan),
                "stage_allowed": approval_gate.get("stage_allowed"),
            },
            error="stage appears allowed before explicit owner approval",
        ),
        _check(
            "rollback_plan_ready",
            _status(rollback_plan) == "owner_staging_rollback_plan_ready",
            details={
                "rollback_plan_status": _status(rollback_plan),
                "rollback_reset_command_count": rollback_plan.get("reset_command_count"),
            },
            error="owner staging rollback plan is not ready",
        ),
        _check(
            "task_board_ready",
            _status(task_board) == "commercial_delivery_ready_for_owner_staging_review",
            details={
                "task_board_status": _status(task_board),
                "secondary_pending_count": task_summary.get("secondary_pending_count"),
            },
            error="commercial delivery task board is not ready for owner approval handoff",
        ),
        _check(
            "operator_checklist_accounted_for",
            operator_checklist_status_accounted_for or post_approval_operator_checklist_accounted_for,
            details={
                "operator_checklist_present": operator_checklist_present,
                "operator_checklist_status": operator_checklist_status,
                "waiting_for_owner": operator_checklist.get("waiting_for_owner"),
                "operator_ready": operator_checklist.get("operator_ready"),
                "real_owner_approval_present": operator_checklist.get("real_owner_approval_present"),
            },
            error="owner post-approval operator checklist is present but not waiting for owner or ready",
        ),
        _check(
            "owner_gate_present",
            owner_gated,
            details={
                "owner_delivery_packet_owner_gated": delivery_packet.get("owner_gated"),
                "approval_request_owner_gated": approval_request.get("owner_gated"),
                "approval_brief_owner_gated": approval_brief.get("owner_gated"),
                "approval_payload_audit_owner_gated": approval_payload_audit.get("owner_gated"),
                "approval_gate_owner_gated": approval_gate.get("owner_gated"),
                "stage_execution_plan_owner_gated": stage_execution_plan.get("owner_gated"),
                "rollback_plan_owner_gated": rollback_plan.get("owner_gated"),
                "operator_checklist_present": operator_checklist_present,
                "operator_checklist_owner_gated": operator_checklist.get("owner_gated"),
            },
            error="one or more owner approval handoff inputs are missing owner-gated markers",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more owner approval handoff inputs claim full Codex parity",
        ),
        _check(
            "no_approval_handoff_mutation",
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
    status = "owner_approval_handoff_ready" if ready else "owner_approval_handoff_blocked"

    return OwnerApprovalHandoff(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_approval_handoff",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        real_owner_approval_written=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        approval_payload_path=_display_path(owner_approval_path),
        approval_payload_audit_path=_display_path(owner_approval_payload_audit_path),
        template_path=_display_path(owner_stage_approval_template_path),
        owner_action_required=True,
        stage_allowed=stage_allowed,
        delivery_complete=delivery_complete,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "stage_include_count": delivery_count,
            "owner_stage_command_count": command_count,
            "rollback_reset_command_count": rollback_count,
            "approval_template_stage_include_count": template_count,
            "approval_template_owner_stage_command_count": template_command_count,
            "approval_request_stage_include_count": request_count,
            "approval_request_owner_stage_command_count": request_command_count,
            "approval_brief_stage_include_count": brief_count,
            "approval_brief_owner_stage_command_count": brief_command_count,
            "closure_snapshot_stage_include_count": snapshot_count,
            "closure_snapshot_owner_stage_command_count": snapshot_command_count,
            "owner_stage_approval_gate_status": _status(approval_gate),
            "owner_approval_payload_audit_status": _status(approval_payload_audit),
            "owner_approval_payload_present": approval_payload_audit.get("approval_payload_present"),
            "owner_approval_payload_valid": approval_payload_audit.get("approval_payload_valid"),
            "owner_approval_payload_ready_for_gate": approval_payload_audit.get("ready_for_approval_gate"),
            "owner_stage_execution_plan_status": _status(stage_execution_plan),
            "owner_post_approval_operator_checklist_present": operator_checklist_present,
            "owner_post_approval_operator_checklist_status": operator_checklist_status,
            "owner_post_approval_operator_checklist_waiting_for_owner": operator_checklist.get("waiting_for_owner"),
            "owner_post_approval_operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
            "owner_post_approval_operator_checklist_real_owner_approval_present": operator_checklist.get(
                "real_owner_approval_present"
            ),
            "closure_snapshot_status": _status(closure_snapshot),
            "secondary_pending_count": task_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": task_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": task_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": task_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": task_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "control_modes_preservation_status": delivery_summary.get("control_modes_preservation_status"),
            "control_modes_plan_only_default": delivery_summary.get("control_modes_plan_only_default"),
            "control_modes_loop_phases": delivery_summary.get("control_modes_loop_phases"),
            "control_modes_surface_file_count": delivery_summary.get("control_modes_surface_file_count"),
            "brief_control_modes_preservation_status": brief_summary.get("control_modes_preservation_status"),
            "brief_control_modes_plan_only_default": brief_summary.get("control_modes_plan_only_default"),
            "commit_command_preview": commit_preview,
            "template_commit_command_preview": template_commit_preview,
            "request_commit_command_preview": request_commit_preview,
            "template_owner_placeholder": approval_template.get("owner"),
            "template_approval_id_placeholder": approval_template.get("approval_id"),
            "template_approved_at_placeholder": approval_template.get("approved_at"),
            "template_identity_placeholders_present": template_identity_placeholders_present,
            "stage_path_digest": delivery_stage_path_digest,
            "template_stage_path_digest": template_stage_path_digest,
            "request_stage_path_digest": request_stage_path_digest,
            "brief_stage_path_digest": brief_stage_path_digest,
            "expected_stage_path_set_digest": delivery_expected_stage_path_set_digest,
            "template_expected_stage_path_set_digest": template_expected_stage_path_set_digest,
            "request_expected_stage_path_set_digest": request_expected_stage_path_set_digest,
            "brief_expected_stage_path_set_digest": brief_expected_stage_path_set_digest,
            "closure_expected_stage_path_set_digest": snapshot_expected_stage_path_set_digest,
            "closure_cached_staged_path_set_digest": snapshot_summary.get("cached_staged_path_set_digest"),
            "stage_command_digest": delivery_stage_command_digest,
            "template_stage_command_digest": template_stage_command_digest,
            "request_stage_command_digest": request_stage_command_digest,
            "brief_stage_command_digest": brief_stage_command_digest,
            "approval_payload_audit_stage_path_digest": approval_audit_summary.get("stage_path_digest"),
            "approval_payload_audit_stage_command_digest": approval_audit_summary.get("stage_command_digest"),
            "approval_payload_audit_expected_stage_path_set_digest": approval_audit_summary.get(
                "expected_stage_path_set_digest"
            ),
            "post_approval_noop_accounted_for": post_approval_noop_accounted_for,
        },
        owner_action_payload_template=dict(template_payload),
        checks=checks,
        next_actions=[
            "Owner reviews this handoff, the approval brief, and the delivery packet.",
            "If approved, create the real owner approval payload at approval_payload_path using the template values and concrete owner fields.",
            "After the real approval payload exists, run commercial_delivery_owner_approval_payload_audit.py before the approval gate.",
            "Do not stage until owner_stage_approval_gate.py and owner_stage_execution_plan.py both report ready.",
            "After owner-approved staging, rerun post-staging verifier, commit gate, commit packet, delivery packet, closure snapshot, and task board.",
        ],
        known_limits=[
            "This handoff is read-only except writing local evidence files.",
            "It does not write the real owner approval payload.",
            "It does not stage, reset, commit, push, call network services, run tests, or execute agents.",
            "It does not claim full Codex parity or commercial delivery completion.",
        ],
    )


def render_markdown_handoff(handoff: OwnerApprovalHandoff) -> str:
    lines = [
        "# Commercial Delivery Owner Approval Handoff",
        "",
        f"- Status: `{handoff.status}`",
        f"- Generated at: `{handoff.generated_at}`",
        f"- Owner action required: `{str(handoff.owner_action_required).lower()}`",
        f"- Stage allowed: `{str(handoff.stage_allowed).lower()}`",
        f"- Delivery complete: `{str(handoff.delivery_complete).lower()}`",
        f"- Approval payload path: `{handoff.approval_payload_path}`",
        f"- Approval payload audit path: `{handoff.approval_payload_audit_path}`",
        f"- Template path: `{handoff.template_path}`",
        f"- Stage include count: `{handoff.summary.get('stage_include_count')}`",
        f"- Owner stage command count: `{handoff.summary.get('owner_stage_command_count')}`",
        f"- Closure snapshot status: `{handoff.summary.get('closure_snapshot_status')}`",
        f"- Owner approval payload audit status: `{handoff.summary.get('owner_approval_payload_audit_status')}`",
        f"- Owner approval payload present: `{handoff.summary.get('owner_approval_payload_present')}`",
        f"- Owner post-approval operator checklist status: `{handoff.summary.get('owner_post_approval_operator_checklist_status')}`",
        f"- Owner post-approval operator checklist waiting: `{handoff.summary.get('owner_post_approval_operator_checklist_waiting_for_owner')}`",
        f"- Owner post-approval operator checklist ready: `{handoff.summary.get('owner_post_approval_operator_checklist_operator_ready')}`",
        f"- Secondary handoff next queue: `{', '.join(handoff.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{handoff.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{handoff.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Control modes preservation: `{handoff.summary.get('control_modes_preservation_status')}`",
        f"- Control modes plan-only default: `{handoff.summary.get('control_modes_plan_only_default')}`",
        f"- Expected stage path set digest: `{handoff.summary.get('expected_stage_path_set_digest')}`",
        f"- Closure cached staged path set digest: `{handoff.summary.get('closure_cached_staged_path_set_digest')}`",
        "",
        "## Checks",
        "",
    ]
    for check in handoff.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Owner Action Payload Template", "", "```json"])
    lines.append(json.dumps(handoff.owner_action_payload_template, ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in handoff.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(handoff: OwnerApprovalHandoff, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(handoff.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_handoff(handoff: OwnerApprovalHandoff, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_handoff(handoff), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-delivery-packet", type=Path, default=DEFAULT_OWNER_DELIVERY_PACKET)
    parser.add_argument("--owner-stage-approval-request", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_REQUEST)
    parser.add_argument("--owner-stage-approval-template", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_TEMPLATE)
    parser.add_argument("--owner-stage-approval-brief", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_BRIEF)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
    parser.add_argument("--owner-staging-rollback-plan", type=Path, default=DEFAULT_OWNER_STAGING_ROLLBACK_PLAN)
    parser.add_argument(
        "--owner-post-approval-operator-checklist",
        type=Path,
        default=DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    )
    parser.add_argument("--closure-snapshot", type=Path, default=DEFAULT_CLOSURE_SNAPSHOT)
    parser.add_argument("--task-board", type=Path, default=DEFAULT_TASK_BOARD)
    parser.add_argument("--owner-approval", type=Path, default=DEFAULT_OWNER_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    handoff = build_owner_approval_handoff(
        owner_delivery_packet_path=args.owner_delivery_packet,
        owner_stage_approval_request_path=args.owner_stage_approval_request,
        owner_stage_approval_template_path=args.owner_stage_approval_template,
        owner_stage_approval_brief_path=args.owner_stage_approval_brief,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_staging_rollback_plan_path=args.owner_staging_rollback_plan,
        owner_post_approval_operator_checklist_path=args.owner_post_approval_operator_checklist,
        closure_snapshot_path=args.closure_snapshot,
        task_board_path=args.task_board,
        owner_approval_path=args.owner_approval,
    )
    write_report(handoff, args.output)
    write_markdown_handoff(handoff, args.markdown_output)
    print(f"Commercial delivery owner approval handoff status: {handoff.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Owner action required: {handoff.owner_action_required}")
    print(f"Stage allowed: {handoff.stage_allowed}")
    for check in handoff.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if handoff.status == "owner_approval_handoff_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
