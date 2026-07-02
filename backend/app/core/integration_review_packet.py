from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewComponent:
    kind: str
    status: str
    ok: bool
    decision: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    summary: dict[str, Any] = field(default_factory=dict)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "ok": self.ok,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "summary": dict(self.summary),
            "issues": [dict(issue) for issue in self.issues],
            "next_actions": list(self.next_actions),
        }


def summarize_review_component(component: Mapping[str, Any] | Any) -> ReviewComponent:
    payload = _as_mapping(component)
    status = str(payload.get("status") or "needs_review")
    issues = tuple(dict(issue) for issue in _as_sequence(payload.get("issues")))
    ok = _bool(payload.get("ok")) if "ok" in payload else status in {"ready", "passed"}
    reasons: list[str] = []
    if status == "blocked" or any(str(issue.get("severity")) == "high" for issue in issues):
        decision = "blocked"
        if any(str(issue.get("severity")) == "high" for issue in issues):
            reasons.append("component has high severity issues")
        else:
            reasons.append("component blocked")
    elif status in {"ready", "passed"} and ok:
        decision = "ready"
        reasons.append("component ready")
    else:
        decision = "needs_review"
        reasons.append("component needs review")
    return ReviewComponent(
        kind=str(payload.get("kind") or "integration_component"),
        status=status,
        ok=ok,
        decision=decision,
        reasons=tuple(reasons),
        summary=dict(payload.get("summary") or {}),
        issues=issues,
        next_actions=tuple(str(action) for action in _as_sequence(payload.get("next_actions"))),
    )


def build_integration_review_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _components(data)
    if not raw:
        return {
            "kind": "integration_review_packet",
            "packet_id": str(data.get("packet_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"component_count": 0},
            "components": [],
            "highlights": {"ready_components": [], "blocked_components": [], "needs_review_components": []},
            "review_sections": [],
            "issues": [],
            "recommendations": [],
            "next_actions": ["provide_review_packet_inputs"],
        }
    components = [summarize_review_component(item) for item in raw]
    blocked = [item for item in components if item.decision == "blocked"]
    review = [item for item in components if item.decision == "needs_review"]
    if blocked:
        status = "blocked"
        recommendations: list[str] = []
        next_actions = _unique(["resolve_blocked_review_packet_components", "rerun_review_packet"] + [a for c in blocked for a in c.next_actions])
    elif review:
        status = "needs_review"
        recommendations = []
        next_actions = _unique(["review_packet_issues", "complete_missing_review_evidence"] + [a for c in review for a in c.next_actions])
    else:
        status = "ready"
        recommendations = ["submit_packet_for_mainline_review"]
        next_actions = recommendations
    return {
        "kind": "integration_review_packet",
        "packet_id": str(data.get("packet_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "component_count": len(components),
            "candidate_count": max((_int(c.summary.get("candidate_count")) for c in components), default=0),
            "needs_review_count": len(review),
            "blocked_count": len(blocked),
        },
        "components": [item.as_dict() for item in components],
        "highlights": {
            "ready_components": [c.kind for c in components if c.decision == "ready"],
            "blocked_components": [c.kind for c in blocked],
            "needs_review_components": [c.kind for c in review],
        },
        "review_sections": [{"title": _title(c.kind), "status": c.status} for c in components],
        "issues": _issues(components),
        "recommendations": recommendations,
        "next_actions": next_actions,
    }


def _components(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("components")
    if raw:
        if isinstance(raw, Mapping):
            return list(raw.values())
        return _as_sequence(raw)
    keys = ("scorecard", "dependency_map", "sequence_plan", "traceability_index")
    return [data[key] for key in keys if data.get(key)]


def _issues(components: Sequence[ReviewComponent]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for component in components:
        if component.decision == "blocked":
            issues.append({"code": "review_packet_component_blocked", "severity": "high", "component": component.kind})
        issues.extend(dict(issue) for issue in component.issues)
    return issues


def _title(kind: str) -> str:
    return kind.replace("_", " ").title()


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
