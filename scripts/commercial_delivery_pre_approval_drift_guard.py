#!/usr/bin/env python3
"""Build a read-only pre-approval drift guard for commercial delivery.

The guard proves that the owner approval boundary is still intact while the
mainline waits for a real owner approval payload. It checks that the current
stage digests, secondary handoff summary, approval template placeholders, and
absence of the real owner approval file agree across the already-generated
delivery reports. It never stages files, writes an approval payload, commits,
pushes, calls network services, or executes agents.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OWNER_STAGE_APPROVAL_REQUEST = REPORT_DIR / "commercial-delivery-owner-stage-approval-request.json"
DEFAULT_OWNER_APPROVAL_HANDOFF = REPORT_DIR / "commercial-delivery-owner-approval-handoff.json"
DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT = REPORT_DIR / "commercial-delivery-owner-approval-payload-audit.json"
DEFAULT_OWNER_STAGE_APPROVAL_GATE = REPORT_DIR / "commercial-delivery-owner-stage-approval-gate.json"
DEFAULT_OWNER_STAGE_EXECUTION_PLAN = REPORT_DIR / "commercial-delivery-owner-stage-execution-plan.json"
DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST = (
    REPORT_DIR / "commercial-delivery-owner-post-approval-operator-checklist.json"
)
DEFAULT_CLOSURE_SNAPSHOT = REPORT_DIR / "commercial-delivery-closure-snapshot.json"
DEFAULT_TASK_BOARD = REPORT_DIR / "commercial-delivery-task-board.json"
DEFAULT_OWNER_APPROVAL = REPORT_DIR / "commercial-delivery-owner-stage-approval.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-pre-approval-drift-guard.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-pre-approval-drift-guard.md"

EXPECTED_TEMPLATE_PLACEHOLDERS = {
    "template_owner_placeholder": "<owner-name-or-id>",
    "template_approval_id_placeholder": "<approval-id>",
    "template_approved_at_placeholder": "<ISO-8601 UTC timestamp>",
}


@dataclass(frozen=True)
class PreApprovalDriftGuardCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PreApprovalDriftGuard:
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
    approval_payload_path: str
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[PreApprovalDriftGuardCheck]
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


def _summary_value(payload: dict[str, Any], key: str) -> object:
    return _summary(payload).get(key)


def _truthy_summary(payload: dict[str, Any], key: str) -> bool:
    return _summary(payload).get(key) is True


def _digest_sources(payloads: dict[str, dict[str, Any]], field: str) -> dict[str, str | None]:
    field_aliases = [
        field,
        f"closure_{field}",
        f"pre_approval_drift_guard_{field}",
    ]
    sources: dict[str, str | None] = {}
    for name, payload in payloads.items():
        value = None
        summary = _summary(payload)
        for alias in field_aliases:
            value = payload.get(alias)
            if value is None:
                value = summary.get(alias)
            if value is not None:
                break
        sources[name] = str(value) if isinstance(value, str) and value else None
    return sources


def _nonempty_values_match(values: dict[str, str | None]) -> bool:
    present = [value for value in values.values() if value]
    return bool(present) and len(present) == len(values) and len(set(present)) == 1


def _sources_match_excluding(values: dict[str, str | None], excluded_sources: set[str]) -> bool:
    return _nonempty_values_match(
        {
            name: value
            for name, value in values.items()
            if name not in excluded_sources
        }
    )


def _expected_post_approval_stage_blockers(snapshot: dict[str, Any]) -> bool:
    required = {
        "post_staging_verifier_not_ready",
        "owner_commit_packet_not_ready",
    }
    allowed = required | {"cached_staged_path_set_digest_not_ready"}
    blockers = snapshot.get("blockers")
    blocker_set = {str(item) for item in blockers} if isinstance(blockers, list) else set()
    return required.issubset(blocker_set) and blocker_set.issubset(allowed)


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> PreApprovalDriftGuardCheck:
    return PreApprovalDriftGuardCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _secondary_summary_sources(payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keys = (
        "secondary_pending_count",
        "secondary_handoff_next_count",
        "secondary_handoff_next_queue",
        "secondary_handoff_completed_count",
        "secondary_handoff_latest_completed_candidate",
    )
    return {name: {key: _summary_value(payload, key) for key in keys} for name, payload in payloads.items()}


def _secondary_sources_match(sources: dict[str, dict[str, Any]]) -> bool:
    values = list(sources.values())
    return bool(values) and all(value == values[0] for value in values)


def build_pre_approval_drift_guard(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    owner_stage_approval_request_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_REQUEST,
    owner_approval_handoff_path: Path = DEFAULT_OWNER_APPROVAL_HANDOFF,
    owner_approval_payload_audit_path: Path = DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT,
    owner_stage_approval_gate_path: Path = DEFAULT_OWNER_STAGE_APPROVAL_GATE,
    owner_stage_execution_plan_path: Path = DEFAULT_OWNER_STAGE_EXECUTION_PLAN,
    owner_post_approval_operator_checklist_path: Path = DEFAULT_OWNER_POST_APPROVAL_OPERATOR_CHECKLIST,
    closure_snapshot_path: Path = DEFAULT_CLOSURE_SNAPSHOT,
    task_board_path: Path = DEFAULT_TASK_BOARD,
    owner_approval_path: Path = DEFAULT_OWNER_APPROVAL,
) -> PreApprovalDriftGuard:
    report_paths = {
        "manifest": manifest_path,
        "owner_stage_approval_request": owner_stage_approval_request_path,
        "owner_approval_handoff": owner_approval_handoff_path,
        "owner_approval_payload_audit": owner_approval_payload_audit_path,
        "owner_stage_approval_gate": owner_stage_approval_gate_path,
        "owner_stage_execution_plan": owner_stage_execution_plan_path,
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

    request = reports["owner_stage_approval_request"]
    handoff = reports["owner_approval_handoff"]
    payload_audit = reports["owner_approval_payload_audit"]
    approval_gate = reports["owner_stage_approval_gate"]
    execution_plan = reports["owner_stage_execution_plan"]
    operator_checklist = reports["owner_post_approval_operator_checklist"]
    closure = reports["closure_snapshot"]
    task_board = reports["task_board"]

    digest_payloads = {
        "owner_stage_approval_request": request,
        "owner_approval_handoff": handoff,
        "owner_stage_approval_gate": approval_gate,
        "owner_stage_execution_plan": execution_plan,
        "closure_snapshot": closure,
        "task_board": task_board,
    }
    stage_path_digest_sources = _digest_sources(digest_payloads, "stage_path_digest")
    stage_command_digest_sources = _digest_sources(digest_payloads, "stage_command_digest")
    expected_stage_path_set_digest_sources = _digest_sources(
        {
            "owner_stage_approval_request": request,
            "owner_approval_handoff": handoff,
            "closure_snapshot": closure,
            "task_board": task_board,
        },
        "expected_stage_path_set_digest",
    )
    secondary_sources = _secondary_summary_sources(
        {
            "owner_stage_approval_request": request,
            "owner_approval_handoff": handoff,
            "closure_snapshot": closure,
            "task_board": task_board,
        }
    )
    placeholder_sources = {
        "owner_stage_approval_request": {
            key: _summary_value(request, key) for key in EXPECTED_TEMPLATE_PLACEHOLDERS
        }
        | {"template_identity_placeholders_present": _truthy_summary(request, "template_identity_placeholders_present")},
        "owner_approval_handoff": {
            key: _summary_value(handoff, key) for key in EXPECTED_TEMPLATE_PLACEHOLDERS
        }
        | {"template_identity_placeholders_present": _truthy_summary(handoff, "template_identity_placeholders_present")},
    }
    placeholders_present = all(
        source.get("template_identity_placeholders_present") is True
        and all(source.get(key) == expected for key, expected in EXPECTED_TEMPLATE_PLACEHOLDERS.items())
        for source in placeholder_sources.values()
    )
    owner_approval_present = owner_approval_path.exists()
    approval_payload_blocked_before_owner = (
        _status(payload_audit) == "owner_approval_payload_blocked"
        and payload_audit.get("approval_payload_present") is False
        and payload_audit.get("approval_payload_valid") is False
        and payload_audit.get("ready_for_approval_gate") is not True
    )
    approval_gate_blocked_before_owner = (
        _status(approval_gate) == "owner_stage_approval_blocked"
        and approval_gate.get("stage_allowed") is not True
    )
    execution_blocked_before_owner = (
        _status(execution_plan) == "owner_stage_execution_blocked"
        and execution_plan.get("stage_allowed") is not True
    )
    operator_checklist_present = bool(operator_checklist)
    operator_checklist_waiting_before_owner = (
        not operator_checklist_present
        or (
            _status(operator_checklist) == "owner_post_approval_operator_checklist_waiting_for_owner"
            and operator_checklist.get("waiting_for_owner") is True
            and operator_checklist.get("operator_ready") is not True
            and operator_checklist.get("real_owner_approval_present") is not True
        )
    )
    closure_blocked_before_owner = (
        _status(closure) == "commercial_delivery_closure_blocked"
        and closure.get("delivery_complete") is False
        and closure.get("stage_ready") is True
        and closure.get("approval_ready") is False
    )
    post_approval_stage_execution_ready = (
        owner_approval_present
        and _status(handoff) == "owner_approval_handoff_ready"
        and _status(payload_audit) == "owner_approval_payload_ready"
        and payload_audit.get("approval_payload_present") is True
        and payload_audit.get("approval_payload_valid") is True
        and payload_audit.get("ready_for_approval_gate") is True
        and _status(approval_gate) == "owner_stage_approval_ready"
        and approval_gate.get("stage_allowed") is True
        and _status(execution_plan) == "owner_stage_execution_ready"
        and execution_plan.get("stage_allowed") is True
        and (
            not operator_checklist_present
            or (
                _status(operator_checklist) == "owner_post_approval_operator_checklist_ready"
                and operator_checklist.get("operator_ready") is True
                and operator_checklist.get("real_owner_approval_present") is True
            )
        )
        and _status(closure) == "commercial_delivery_closure_blocked"
        and closure.get("delivery_complete") is False
        and closure.get("stage_ready") is True
        and _expected_post_approval_stage_blockers(closure)
    )
    post_approval_accounted_for = (
        owner_approval_present
        and _status(handoff) == "owner_approval_handoff_ready"
        and _status(payload_audit) == "owner_approval_payload_ready"
        and payload_audit.get("approval_payload_present") is True
        and payload_audit.get("approval_payload_valid") is True
        and payload_audit.get("ready_for_approval_gate") is True
        and _status(approval_gate) == "owner_stage_approval_ready"
        and approval_gate.get("stage_allowed") is True
        and _status(execution_plan) == "owner_stage_execution_ready"
        and execution_plan.get("stage_allowed") is True
        and (
            not operator_checklist_present
            or (
                _status(operator_checklist) == "owner_post_approval_operator_checklist_ready"
                and operator_checklist.get("operator_ready") is True
                and operator_checklist.get("real_owner_approval_present") is True
            )
        )
        and _status(closure) == "commercial_delivery_complete"
        and closure.get("delivery_complete") is True
        and closure.get("stage_ready") is True
        and closure.get("approval_ready") is True
    )
    post_approval_or_stage_execution_accounted_for = (
        post_approval_accounted_for or post_approval_stage_execution_ready
    )
    digest_stability_excluded_sources = {"task_board"} if post_approval_stage_execution_ready else set()

    checks = [
        _check("reports_readable", not errors, details={"errors": errors}, error="one or more guard inputs are missing"),
        _check(
            "real_owner_approval_absent",
            not owner_approval_present or post_approval_or_stage_execution_accounted_for,
            details={"approval_payload_path": _display_path(owner_approval_path), "present": owner_approval_present},
            error="real owner approval payload exists before this guard expected it",
        ),
        _check(
            "approval_request_ready",
            _status(request) == "owner_stage_approval_request_ready",
            details={"status": _status(request)},
            error="owner approval request is not ready",
        ),
        _check(
            "approval_handoff_ready",
            _status(handoff) == "owner_approval_handoff_ready",
            details={"status": _status(handoff)},
            error="owner approval handoff is not ready",
        ),
        _check(
            "template_identity_placeholders_preserved",
            placeholders_present,
            details={"placeholder_sources": placeholder_sources},
            error="owner approval template identity placeholders were replaced before real approval",
        ),
        _check(
            "stage_path_digest_stable",
            _nonempty_values_match(stage_path_digest_sources)
            or _sources_match_excluding(stage_path_digest_sources, digest_stability_excluded_sources),
            details={
                "stage_path_digest_sources": stage_path_digest_sources,
                "excluded_sources": sorted(digest_stability_excluded_sources),
            },
            error="stage path digest drifted across pre-approval reports",
        ),
        _check(
            "stage_command_digest_stable",
            _nonempty_values_match(stage_command_digest_sources)
            or _sources_match_excluding(stage_command_digest_sources, digest_stability_excluded_sources),
            details={
                "stage_command_digest_sources": stage_command_digest_sources,
                "excluded_sources": sorted(digest_stability_excluded_sources),
            },
            error="stage command digest drifted across pre-approval reports",
        ),
        _check(
            "expected_stage_path_set_digest_stable",
            _nonempty_values_match(expected_stage_path_set_digest_sources)
            or _sources_match_excluding(expected_stage_path_set_digest_sources, digest_stability_excluded_sources),
            details={
                "expected_stage_path_set_digest_sources": expected_stage_path_set_digest_sources,
                "excluded_sources": sorted(digest_stability_excluded_sources),
            },
            error="expected stage path set digest drifted across pre-approval reports",
        ),
        _check(
            "secondary_handoff_summary_stable",
            _secondary_sources_match(secondary_sources),
            details={"secondary_sources": secondary_sources},
            error="secondary handoff summary drifted across pre-approval reports",
        ),
        _check(
            "approval_payload_blocked_before_owner",
            approval_payload_blocked_before_owner or post_approval_or_stage_execution_accounted_for,
            details={
                "status": _status(payload_audit),
                "approval_payload_present": payload_audit.get("approval_payload_present"),
                "approval_payload_valid": payload_audit.get("approval_payload_valid"),
                "ready_for_approval_gate": payload_audit.get("ready_for_approval_gate"),
            },
            error="approval payload audit is not in the expected pre-owner blocked state",
        ),
        _check(
            "approval_gate_blocked_before_owner",
            approval_gate_blocked_before_owner or post_approval_or_stage_execution_accounted_for,
            details={"status": _status(approval_gate), "stage_allowed": approval_gate.get("stage_allowed")},
            error="approval gate is not in the expected pre-owner blocked state",
        ),
        _check(
            "stage_execution_blocked_before_owner",
            execution_blocked_before_owner or post_approval_or_stage_execution_accounted_for,
            details={"status": _status(execution_plan), "stage_allowed": execution_plan.get("stage_allowed")},
            error="stage execution plan is not in the expected pre-owner blocked state",
        ),
        _check(
            "operator_checklist_waiting_before_owner",
            operator_checklist_waiting_before_owner or post_approval_or_stage_execution_accounted_for,
            details={
                "operator_checklist_present": operator_checklist_present,
                "operator_checklist_status": _status(operator_checklist),
                "waiting_for_owner": operator_checklist.get("waiting_for_owner"),
                "operator_ready": operator_checklist.get("operator_ready"),
                "real_owner_approval_present": operator_checklist.get("real_owner_approval_present"),
            },
            error="post-approval operator checklist is not in the expected waiting-for-owner state",
        ),
        _check(
            "closure_blocked_before_owner",
            closure_blocked_before_owner or post_approval_or_stage_execution_accounted_for,
            details={
                "status": _status(closure),
                "delivery_complete": closure.get("delivery_complete"),
                "stage_ready": closure.get("stage_ready"),
                "approval_ready": closure.get("approval_ready"),
                "post_approval_stage_execution_ready": post_approval_stage_execution_ready,
            },
            error="closure snapshot is not in the expected pre-owner blocked state",
        ),
    ]
    checks_passed = all(check.status == "passed" for check in checks)
    summary = {
        "stage_path_digest": next((value for value in stage_path_digest_sources.values() if value), None),
        "stage_command_digest": next((value for value in stage_command_digest_sources.values() if value), None),
        "expected_stage_path_set_digest": next(
            (value for value in expected_stage_path_set_digest_sources.values() if value),
            None,
        ),
        "secondary_pending_count": _summary_value(task_board, "secondary_pending_count"),
        "secondary_handoff_next_count": _summary_value(task_board, "secondary_handoff_next_count"),
        "secondary_handoff_next_queue": _summary_value(task_board, "secondary_handoff_next_queue"),
        "secondary_handoff_completed_count": _summary_value(task_board, "secondary_handoff_completed_count"),
        "secondary_handoff_latest_completed_candidate": _summary_value(
            task_board,
            "secondary_handoff_latest_completed_candidate",
        ),
        "template_identity_placeholders_present": placeholders_present,
        "owner_approval_payload_present": payload_audit.get("approval_payload_present"),
        "owner_approval_payload_valid": payload_audit.get("approval_payload_valid"),
        "owner_approval_payload_ready_for_gate": payload_audit.get("ready_for_approval_gate"),
        "owner_stage_approval_gate_status": _status(approval_gate),
        "owner_stage_execution_plan_status": _status(execution_plan),
        "owner_post_approval_operator_checklist_present": operator_checklist_present,
        "owner_post_approval_operator_checklist_status": _status(operator_checklist),
        "owner_post_approval_operator_checklist_waiting_for_owner": operator_checklist.get("waiting_for_owner"),
        "owner_post_approval_operator_checklist_operator_ready": operator_checklist.get("operator_ready"),
        "owner_post_approval_operator_checklist_real_owner_approval_present": operator_checklist.get(
            "real_owner_approval_present"
        ),
        "closure_snapshot_status": _status(closure),
        "closure_delivery_complete": closure.get("delivery_complete"),
        "closure_blockers": closure.get("blockers") if isinstance(closure.get("blockers"), list) else [],
        "post_approval_accounted_for": post_approval_accounted_for,
        "post_approval_stage_execution_ready": post_approval_stage_execution_ready,
    }
    return PreApprovalDriftGuard(
        status="pre_approval_drift_guard_ready" if checks_passed else "pre_approval_drift_guard_blocked",
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_pre_approval_drift_guard",
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        real_owner_approval_present=owner_approval_present,
        approval_payload_path=_display_path(owner_approval_path),
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary=summary,
        checks=checks,
        next_actions=[
            "Keep this guard ready while waiting for the real owner approval payload.",
            "If this guard blocks, refresh the commercial delivery report chain before asking the owner to approve staging.",
            "After owner approval is written, rerun owner approval gate, stage execution plan, and post-staging verifier.",
        ],
        known_limits=[
            "This guard is read-only except writing local evidence files.",
            "It does not create, infer, or validate a real owner approval decision.",
            "It does not stage, commit, push, call network services, run tests, or execute agents.",
        ],
    )


def render_markdown_guard(guard: PreApprovalDriftGuard) -> str:
    lines = [
        "# Commercial Delivery Pre-Approval Drift Guard",
        "",
        f"- Status: `{guard.status}`",
        f"- Generated at: `{guard.generated_at}`",
        f"- Real owner approval present: `{str(guard.real_owner_approval_present).lower()}`",
        f"- Stage path digest: `{guard.summary.get('stage_path_digest') or '<missing>'}`",
        f"- Stage command digest: `{guard.summary.get('stage_command_digest') or '<missing>'}`",
        f"- Expected stage path set digest: `{guard.summary.get('expected_stage_path_set_digest') or '<missing>'}`",
        f"- Latest secondary candidate: `{guard.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Next secondary queue: `{', '.join(guard.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Owner post-approval operator checklist: `{guard.summary.get('owner_post_approval_operator_checklist_status')}`",
        f"- Owner post-approval operator ready: `{guard.summary.get('owner_post_approval_operator_checklist_operator_ready')}`",
        "",
        "## Checks",
        "",
    ]
    for check in guard.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in guard.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(guard: PreApprovalDriftGuard, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(guard.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_guard(guard: PreApprovalDriftGuard, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_guard(guard), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--owner-stage-approval-request", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_REQUEST)
    parser.add_argument("--owner-approval-handoff", type=Path, default=DEFAULT_OWNER_APPROVAL_HANDOFF)
    parser.add_argument("--owner-approval-payload-audit", type=Path, default=DEFAULT_OWNER_APPROVAL_PAYLOAD_AUDIT)
    parser.add_argument("--owner-stage-approval-gate", type=Path, default=DEFAULT_OWNER_STAGE_APPROVAL_GATE)
    parser.add_argument("--owner-stage-execution-plan", type=Path, default=DEFAULT_OWNER_STAGE_EXECUTION_PLAN)
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
    guard = build_pre_approval_drift_guard(
        manifest_path=args.manifest,
        owner_stage_approval_request_path=args.owner_stage_approval_request,
        owner_approval_handoff_path=args.owner_approval_handoff,
        owner_approval_payload_audit_path=args.owner_approval_payload_audit,
        owner_stage_approval_gate_path=args.owner_stage_approval_gate,
        owner_stage_execution_plan_path=args.owner_stage_execution_plan,
        owner_post_approval_operator_checklist_path=args.owner_post_approval_operator_checklist,
        closure_snapshot_path=args.closure_snapshot,
        task_board_path=args.task_board,
        owner_approval_path=args.owner_approval,
    )
    write_report(guard, args.output)
    write_markdown_guard(guard, args.markdown_output)
    print(f"Commercial delivery pre-approval drift guard status: {guard.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    for check in guard.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if guard.status == "pre_approval_drift_guard_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
