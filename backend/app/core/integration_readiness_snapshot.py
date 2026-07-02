from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntegrationComponentSummary:
    kind: str
    status: str
    ok: bool
    decision: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "ok": self.ok,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "issues": [dict(issue) for issue in self.issues],
            "next_actions": list(self.next_actions),
            "summary": dict(self.summary),
        }


def summarize_integration_component(component: Mapping[str, Any] | Any) -> IntegrationComponentSummary:
    payload = _as_mapping(component)
    status = str(payload.get("status") or "needs_review")
    ok = _bool(payload.get("ok")) if "ok" in payload else status in {"ready", "passed"}
    issues = tuple(dict(_as_mapping(issue)) for issue in _as_sequence(payload.get("issues")))
    reasons: list[str] = []
    if status == "blocked" or any(str(issue.get("severity")) == "high" for issue in issues):
        decision = "blocked"
        reasons.append("component blocked")
    elif status in {"ready", "passed"} and ok:
        decision = "ready"
        reasons.append("component ready")
    else:
        decision = "needs_review"
        if status == "ready" and not ok:
            reasons.append("ready component has ok=false")
        else:
            reasons.append("component needs review")
    return IntegrationComponentSummary(
        kind=str(payload.get("kind") or "integration_component"),
        status=status,
        ok=ok,
        decision=decision,
        reasons=tuple(reasons),
        issues=issues,
        next_actions=tuple(str(action) for action in _as_sequence(payload.get("next_actions"))),
        summary=dict(_as_mapping(payload.get("summary"))),
    )


def build_integration_readiness_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = data.get("components")
    if isinstance(raw, Mapping):
        raw_components = list(raw.values())
    else:
        raw_components = _as_sequence(raw)
    if not raw_components:
        return {
            "kind": "integration_readiness_snapshot",
            "snapshot_id": str(data.get("snapshot_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"component_count": 0},
            "components": [],
            "issues": [],
            "highlights": {"ready_components": [], "blocked_components": [], "top_next_actions": []},
            "next_actions": ["provide_snapshot_components"],
        }
    components = [summarize_integration_component(item) for item in raw_components]
    blocked = [item for item in components if item.decision == "blocked"]
    review = [item for item in components if item.decision == "needs_review"]
    if blocked:
        status = "blocked"
        issues = [{"code": "integration_snapshot_component_blocked", "severity": "high", "component": item.kind} for item in blocked]
        next_actions = ["resolve_blocked_snapshot_components", "rebuild_integration_readiness_snapshot"]
    elif review:
        status = "needs_review"
        issues = [{"code": "integration_snapshot_unresolved_issues", "severity": "medium", "component": item.kind} for item in review]
        next_actions = _unique([action for item in review for action in item.next_actions])
    else:
        status = "ready"
        issues = []
        next_actions = ["prepare_mainline_integration_review"]
    return {
        "kind": "integration_readiness_snapshot",
        "snapshot_id": str(data.get("snapshot_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "component_count": len(components),
            "ready_count": sum(1 for item in components if item.decision == "ready"),
            "blocked_count": len(blocked),
            "needs_review_count": len(review),
        },
        "components": [item.as_dict() for item in components],
        "issues": issues,
        "highlights": {
            "ready_components": [item.kind for item in components if item.decision == "ready"],
            "blocked_components": [item.kind for item in blocked],
            "top_next_actions": _unique([action for item in components for action in item.next_actions]),
        },
        "next_actions": next_actions,
    }


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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").lower() in {"true", "1", "yes", "ready", "passed"}


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
