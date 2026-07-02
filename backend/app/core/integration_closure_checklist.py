from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


REQUIRED_CHECKS: tuple[tuple[str, str], ...] = (
    ("owner_digest", "integration_owner_digest"),
    ("followup_queue", "integration_followup_queue"),
    ("governance_summary", "integration_governance_summary"),
    ("review_packet", "integration_review_packet"),
    ("traceability_index", "integration_traceability_index"),
    ("sequence_plan", "integration_sequence_plan"),
    ("decision_audit", "integration_decision_audit"),
)


@dataclass(frozen=True)
class ClosureCheck:
    check_id: str
    component_kind: str
    decision: str
    ok: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    missing_evidence_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "component_kind": self.component_kind,
            "decision": self.decision,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "next_actions": list(self.next_actions),
            "issues": list(self.issues),
            "missing_evidence_count": self.missing_evidence_count,
        }


def summarize_closure_check(check_id: str, component: Mapping[str, Any] | Any) -> ClosureCheck:
    payload = _as_mapping(component)
    component_kind = str(payload.get("kind") or "")
    status = str(payload.get("status") or "needs_review")
    ok = bool(payload.get("ok", status == "ready"))
    summary = _as_mapping(payload.get("summary"))
    missing_evidence_count = int(summary.get("missing_evidence_count") or payload.get("missing_evidence_count") or 0)
    issues = tuple(_as_mapping(issue) for issue in _as_sequence(payload.get("issues")))
    next_actions = tuple(str(action) for action in _as_sequence(payload.get("next_actions")))
    if status == "blocked" or ok is False or issues:
        decision = "blocked"
        reasons = ("component blocked for closure",)
    elif missing_evidence_count:
        decision = "needs_review"
        reasons = ("component missing closure evidence",)
    elif status == "ready" and ok:
        decision = "ready"
        reasons = ("component ready for closure",)
    else:
        decision = "needs_review"
        reasons = ("component needs closure review",)
    return ClosureCheck(
        check_id=check_id,
        component_kind=component_kind,
        decision=decision,
        ok=decision == "ready",
        reasons=reasons,
        next_actions=next_actions,
        issues=issues,
        missing_evidence_count=missing_evidence_count,
    )


def build_integration_closure_checklist(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    components = _component_map(data)
    checks: list[ClosureCheck] = []
    missing_checks: list[str] = []
    for check_id, expected_kind in REQUIRED_CHECKS:
        component = components.get(check_id)
        if component is None:
            missing_checks.append(check_id)
            checks.append(
                ClosureCheck(
                    check_id=check_id,
                    component_kind=expected_kind,
                    decision="missing",
                    ok=False,
                    reasons=("component missing for closure checklist",),
                )
            )
            continue
        checks.append(summarize_closure_check(check_id, component))

    blocked_checks = [check.check_id for check in checks if check.decision == "blocked"]
    review_checks = [check.check_id for check in checks if check.decision == "needs_review"]
    ready_checks = [check.check_id for check in checks if check.decision == "ready"]
    missing_evidence_count = sum(check.missing_evidence_count for check in checks)
    issues = _issues(checks, missing_checks, blocked_checks, review_checks)
    if blocked_checks:
        status = "blocked"
        next_actions = _unique(
            [
                "resolve_closure_blockers",
                *[action for check in checks if check.check_id in blocked_checks for action in check.next_actions],
                "rebuild_integration_closure_checklist",
            ]
        )
    elif missing_checks:
        status = "needs_review"
        next_actions = [
            "provide_missing_closure_components",
            *[f"provide_{check_id}" for check_id in missing_checks],
            "rebuild_integration_closure_checklist",
        ]
    elif review_checks or missing_evidence_count:
        status = "needs_review"
        next_actions = ["attach_closure_evidence", "rebuild_integration_closure_checklist"]
    else:
        status = "ready"
        next_actions = ["submit_closure_checklist_for_mainline_review"]
    return {
        "kind": "integration_closure_checklist",
        "ok": status == "ready",
        "status": status,
        "closure_ready": status == "ready",
        "checklist_id": str(data.get("checklist_id") or ""),
        "summary": {
            "check_count": len(REQUIRED_CHECKS),
            "ready_count": len(ready_checks),
            "review_count": len(review_checks),
            "blocked_count": len(blocked_checks),
            "missing_count": len(missing_checks),
            "missing_evidence_count": missing_evidence_count,
        },
        "checks": [check.as_dict() for check in checks],
        "ready_checks": ready_checks,
        "blocked_checks": blocked_checks,
        "review_checks": review_checks,
        "missing_checks": missing_checks,
        "issues": issues,
        "next_actions": next_actions,
    }


def _component_map(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for check_id, expected_kind in REQUIRED_CHECKS:
        if check_id in data:
            components[check_id] = _as_mapping(data.get(check_id))
    for raw in _as_sequence(data.get("components")):
        component = _as_mapping(raw)
        kind = str(component.get("kind") or "")
        check_id = next((name for name, expected in REQUIRED_CHECKS if expected == kind), "")
        if check_id:
            components.setdefault(check_id, component)
    return components


def _issues(
    checks: Sequence[ClosureCheck],
    missing_checks: Sequence[str],
    blocked_checks: Sequence[str],
    review_checks: Sequence[str],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if missing_checks:
        issues.append({"code": "closure_check_component_missing", "checks": list(missing_checks), "severity": "medium"})
    for check in checks:
        if check.check_id in blocked_checks:
            issues.append({"code": "closure_check_blocked", "check": check.check_id, "severity": "high"})
        elif check.check_id in review_checks and check.missing_evidence_count:
            issues.append({"code": "closure_check_missing_evidence", "check": check.check_id, "severity": "medium"})
    return issues


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, bytes):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
