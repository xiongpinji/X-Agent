from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GovernanceSignal:
    kind: str
    status: str
    ok: bool
    posture: str
    topics: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "ok": self.ok,
            "posture": self.posture,
            "topics": list(self.topics),
            "issues": [dict(issue) for issue in self.issues],
            "next_actions": list(self.next_actions),
            "summary": dict(self.summary),
        }


def summarize_governance_signal(signal: Mapping[str, Any] | Any) -> GovernanceSignal:
    payload = _as_mapping(signal)
    kind = str(payload.get("kind") or payload.get("name") or "integration_signal")
    status = str(payload.get("status") or "needs_review")
    ok = _bool(payload.get("ok")) if "ok" in payload else status in {"ready", "passed"}
    summary = dict(payload.get("summary") or {})
    issues = tuple(dict(issue) for issue in _as_sequence(payload.get("issues")))
    next_actions = tuple(str(action) for action in _as_sequence(payload.get("next_actions")))
    topics = _topics(kind, status, ok, summary, issues)

    if status == "blocked" or _has_high_issue(issues):
        posture = "blocked"
    elif status in {"ready", "passed"} and ok:
        posture = "ready"
    else:
        posture = "needs_review"

    return GovernanceSignal(
        kind=kind,
        status=status,
        ok=ok,
        posture=posture,
        topics=tuple(topics),
        issues=issues,
        next_actions=next_actions,
        summary=summary,
    )


def build_integration_governance_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    signals = [summarize_governance_signal(item) for item in _signal_payloads(data)]
    if not signals:
        return {
            "kind": "integration_governance_summary",
            "summary_id": str(data.get("summary_id") or ""),
            "ok": False,
            "status": "empty",
            "governance_posture": "empty",
            "summary": {"signal_count": 0, "candidate_count": 0},
            "signals": [],
            "governance_topics": [],
            "ready_components": [],
            "blocked_topics": [],
            "review_topics": [],
            "issues": [],
            "recommendations": [],
            "next_actions": ["provide_governance_summary_inputs"],
        }

    blocked = [signal for signal in signals if signal.posture == "blocked"]
    review = [signal for signal in signals if signal.posture == "needs_review"]
    status = "blocked" if blocked else "needs_review" if review else "ready"
    issues = _issues(signals)
    topic_counts = Counter(topic for signal in signals for topic in signal.topics)
    candidate_count = max((_int(signal.summary.get("candidate_count")) for signal in signals), default=0)

    if status == "blocked":
        recommendations = ["resolve_blocked_governance_signals", "rerun_governance_summary"]
        next_actions = _unique(recommendations + [action for signal in blocked for action in signal.next_actions])
    elif status == "needs_review":
        recommendations = ["review_governance_signals", "complete_governance_evidence"]
        next_actions = _unique(recommendations + [action for signal in review for action in signal.next_actions])
    else:
        recommendations = ["approve_governance_summary_for_mainline_review"]
        next_actions = recommendations

    return {
        "kind": "integration_governance_summary",
        "summary_id": str(data.get("summary_id") or ""),
        "ok": status == "ready",
        "status": status,
        "governance_posture": status,
        "summary": {
            "signal_count": len(signals),
            "candidate_count": candidate_count,
            "ready_count": sum(1 for signal in signals if signal.posture == "ready"),
            "blocked_count": len(blocked),
            "needs_review_count": len(review),
        },
        "signals": [signal.as_dict() for signal in signals],
        "governance_topics": [{"topic": topic, "count": count} for topic, count in sorted(topic_counts.items())],
        "ready_components": [signal.kind for signal in signals if signal.posture == "ready"],
        "blocked_topics": _unique([topic for signal in blocked for topic in signal.topics]),
        "review_topics": _unique([topic for signal in review for topic in signal.topics]),
        "issues": issues,
        "recommendations": recommendations,
        "next_actions": next_actions,
    }


def _signal_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("signals") or data.get("components")
    if raw:
        if isinstance(raw, Mapping):
            return list(raw.values())
        return _as_sequence(raw)
    keys = ("review_packet", "traceability_index", "decision_audit")
    return [data[key] for key in keys if data.get(key)]


def _topics(
    kind: str,
    status: str,
    ok: bool,
    summary: Mapping[str, Any],
    issues: Sequence[Mapping[str, Any]],
) -> list[str]:
    topics = [kind]
    if status == "blocked":
        topics.append("blocked_status")
    elif status not in {"ready", "passed"}:
        topics.append("review_status")
    if not ok:
        topics.append("not_ok")
    for issue in issues:
        code = str(issue.get("code") or "")
        if code:
            topics.append(code)
        if str(issue.get("severity") or "").lower() == "high":
            topics.append("high_severity_issue")
    for key, value in summary.items():
        if key.endswith("_count") and _int(value) > 0 and key != "candidate_count":
            topics.append(key)
    return _unique(topics)


def _issues(signals: Sequence[GovernanceSignal]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for signal in signals:
        if signal.posture == "blocked":
            issues.append(
                {
                    "code": "governance_signal_blocked",
                    "severity": "high",
                    "signal": signal.kind,
                    "topics": list(signal.topics),
                }
            )
        elif signal.posture == "needs_review":
            issues.append(
                {
                    "code": "governance_signal_needs_review",
                    "severity": "medium",
                    "signal": signal.kind,
                    "topics": list(signal.topics),
                }
            )
        issues.extend(dict(issue) for issue in signal.issues)
    return issues


def _has_high_issue(issues: Sequence[Mapping[str, Any]]) -> bool:
    return any(str(issue.get("severity") or "").lower() == "high" for issue in issues)


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
    return str(value or "").strip().lower() in {"1", "true", "yes", "passed", "ready"}


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
