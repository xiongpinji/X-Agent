from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewGateCheck:
    check_id: str
    status: str
    severity: str = "medium"
    count: int = 0
    refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "severity": self.severity,
            "count": self.count,
            "refs": list(self.refs),
            "reasons": list(self.reasons),
            "next_actions": list(self.next_actions),
        }


def evaluate_review_gate_check(check: Mapping[str, Any] | Any) -> ReviewGateCheck:
    payload = _as_mapping(check)
    return ReviewGateCheck(
        check_id=str(payload.get("check_id") or payload.get("name") or ""),
        status=str(payload.get("status") or "needs_review"),
        severity=str(payload.get("severity") or "medium"),
        count=_int(payload.get("count")),
        refs=tuple(str(ref) for ref in _as_sequence(payload.get("refs"))),
        reasons=tuple(str(reason) for reason in _as_sequence(payload.get("reasons"))),
        next_actions=tuple(str(action) for action in _as_sequence(payload.get("next_actions"))),
    )


def build_integration_review_readiness_gate(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    checks = [evaluate_review_gate_check(item) for item in _checks(data)]
    if not checks:
        return {
            "kind": "integration_review_readiness_gate",
            "gate_id": str(data.get("gate_id") or ""),
            "ok": False,
            "status": "empty",
            "verdict": "needs_inputs",
            "summary": {"check_count": 0, "ready_check_count": 0},
            "checks": [],
            "ready_checks": [],
            "blocked_checks": [],
            "review_checks": [],
            "next_actions": ["provide_review_readiness_gate_inputs"],
        }
    blocked = [check.check_id for check in checks if check.status in {"blocked", "failed"} or check.severity == "high" and check.status != "ready"]
    review = [check.check_id for check in checks if check.status == "needs_review"]
    ready = [check.check_id for check in checks if check.status in {"ready", "passed"}]
    if blocked:
        status = "blocked"
        verdict = "blocked"
        next_actions = _unique(["resolve_review_readiness_blockers"] + _blocked_actions(blocked) + [a for c in checks if c.check_id in blocked for a in c.next_actions] + ["rebuild_integration_review_readiness_gate"])
    elif review:
        status = "needs_review"
        verdict = "needs_review"
        next_actions = _unique(["review_readiness_gate_warnings"] + _review_actions(review) + [a for c in checks if c.check_id in review for a in c.next_actions] + ["rebuild_integration_review_readiness_gate"])
    else:
        status = "ready"
        verdict = "ready_for_review"
        next_actions = ["share_review_readiness_gate_with_mainline"]
    return {
        "kind": "integration_review_readiness_gate",
        "gate_id": str(data.get("gate_id") or ""),
        "ok": status == "ready",
        "status": status,
        "verdict": verdict,
        "summary": {"check_count": len(checks), "ready_check_count": len(ready), "blocked_check_count": len(blocked), "review_check_count": len(review)},
        "checks": [check.as_dict() for check in checks],
        "ready_checks": ready,
        "blocked_checks": blocked,
        "review_checks": review,
        "next_actions": next_actions,
    }


def _checks(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "checks" in data:
        return [_as_mapping(item) for item in _as_sequence(data.get("checks"))]
    checks: list[dict[str, Any]] = []
    secondary = _as_mapping(data.get("secondary_index"))
    conflict = _as_mapping(data.get("conflict_risk_register"))
    trace = _as_mapping(data.get("traceability_index"))
    validation_statuses = _validation_statuses(data)
    owners = _owners(data)
    handoff_refs = _handoff_refs(secondary) + _handoff_refs(trace)
    if secondary:
        checks.append(_component_check("secondary_index", secondary))
    if conflict:
        checks.append(_component_check("conflict_risk", conflict))
    if trace:
        checks.append(_component_check("traceability", trace))
    if validation_statuses:
        checks.append({"check_id": "validation", "status": "blocked" if any(s in {"failed", "blocked"} for s in validation_statuses) else "ready", "severity": "high" if any(s in {"failed", "blocked"} for s in validation_statuses) else "low"})
    if secondary or trace:
        checks.append({"check_id": "handoff", "status": "ready" if handoff_refs else "needs_review", "next_actions": ["attach_secondary_handoff_references"] if not handoff_refs else []})
    if secondary or conflict or trace:
        checks.append({"check_id": "owners", "status": "ready" if owners else "needs_review", "next_actions": ["assign_or_confirm_candidate_owners"] if not owners else []})
    return checks


def _component_check(check_id: str, component: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_mapping(component.get("summary"))
    blocked_count = _int(summary.get("blocked_count") or summary.get("high_risk_count"))
    status = str(component.get("status") or "needs_review")
    ok = _bool(component.get("ok")) if "ok" in component else status in {"ready", "passed"}
    if status == "blocked" or blocked_count:
        return {"check_id": check_id, "status": "blocked", "severity": "high", "count": blocked_count}
    return {"check_id": check_id, "status": "ready" if ok and status in {"ready", "passed"} else "needs_review", "severity": "low"}


def _validation_statuses(data: Mapping[str, Any]) -> list[str]:
    validation = _as_mapping(data.get("validation"))
    return [str(value) for value in (_as_sequence(validation.get("statuses")) or _as_sequence(data.get("validation_statuses")))]


def _owners(data: Mapping[str, Any]) -> list[str]:
    if data.get("owners"):
        return [str(owner) for owner in _as_sequence(data.get("owners"))]
    digest = _as_mapping(data.get("owner_digest"))
    return [str(_as_mapping(owner).get("owner") or "") for owner in _as_sequence(digest.get("owners")) if _as_mapping(owner).get("owner")]


def _handoff_refs(component: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("entries", "records"):
        for item in _as_sequence(component.get(key)):
            refs.extend(str(ref) for ref in _as_sequence(_as_mapping(item).get("handoff_refs")))
    return refs


def _blocked_actions(blocked: Sequence[str]) -> list[str]:
    actions: list[str] = []
    if "conflict_risk" in blocked:
        actions.append("resolve_conflict_risk_blockers")
    if "validation" in blocked:
        actions.append("refresh_passing_validation_evidence")
    return actions


def _review_actions(review: Sequence[str]) -> list[str]:
    actions: list[str] = []
    if "handoff" in review:
        actions.append("attach_secondary_handoff_references")
    if "owners" in review:
        actions.append("assign_or_confirm_candidate_owners")
    return actions


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").lower() in {"true", "1", "yes", "ready", "passed"}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
