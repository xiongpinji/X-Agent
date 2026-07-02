from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FollowupItem:
    followup_id: str
    owner: str
    action: str
    source_kind: str
    candidate_id: str
    severity: str
    status: str
    priority: int
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "followup_id": self.followup_id,
            "owner": self.owner,
            "action": self.action,
            "source_kind": self.source_kind,
            "candidate_id": self.candidate_id,
            "severity": self.severity,
            "status": self.status,
            "priority": self.priority,
            "evidence_refs": list(self.evidence_refs),
            "topics": list(self.topics),
            "reasons": list(self.reasons),
            "issues": [dict(issue) for issue in self.issues],
        }


def analyze_followup_item(item: Mapping[str, Any] | Any) -> FollowupItem:
    payload = _as_mapping(item)
    severity = str(payload.get("severity") or "medium")
    owner = str(payload.get("owner") or "")
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    followup_id = str(payload.get("followup_id") or payload.get("id") or _slug(str(payload.get("action") or "followup")))
    status = "blocked" if severity in {"high", "critical"} else "ready"
    priority = {"low": 30, "medium": 60, "high": 100, "critical": 100}.get(severity, 60)
    reasons: list[str] = ["followup blocked"] if status == "blocked" else ["followup ready"]
    issues: list[dict[str, Any]] = []
    if not owner:
        status = "needs_review" if status != "blocked" else status
        issues.append({"code": "followup_owner_missing", "severity": "medium", "followup_id": followup_id})
    if not evidence_refs:
        status = "needs_review" if status != "blocked" else status
        issues.append({"code": "followup_evidence_missing", "severity": "medium", "followup_id": followup_id})
    return FollowupItem(
        followup_id=followup_id,
        owner=owner,
        action=str(payload.get("action") or "review_followup"),
        source_kind=str(payload.get("source_kind") or ""),
        candidate_id=str(payload.get("candidate_id") or ""),
        severity=severity,
        status=status,
        priority=priority,
        evidence_refs=evidence_refs,
        topics=tuple(str(topic) for topic in _as_sequence(payload.get("topics"))),
        reasons=tuple(reasons),
        issues=tuple(issues),
    )


def build_integration_followup_queue(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _followups(data)
    if not raw:
        return {
            "kind": "integration_followup_queue",
            "queue_id": str(data.get("queue_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"followup_count": 0},
            "followups": [],
            "issues": [],
            "blocked_followups": [],
            "by_owner": {},
            "next_actions": ["provide_followup_queue_inputs"],
        }
    followups = [analyze_followup_item(item) for item in raw]
    blocked = [item.followup_id for item in followups if item.status == "blocked"]
    review = [item.followup_id for item in followups if item.status == "needs_review"]
    issues = [issue for item in followups for issue in item.issues]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_blocked_followups", "rebuild_integration_followup_queue"]
    elif review:
        status = "needs_review"
        next_actions = ["assign_followup_owners", "attach_followup_evidence", "rebuild_integration_followup_queue"]
    else:
        status = "ready"
        next_actions = ["review_followup_queue_with_mainline"]
    return {
        "kind": "integration_followup_queue",
        "queue_id": str(data.get("queue_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "followup_count": len(followups),
            "blocked_count": len(blocked),
            "owner_missing_count": sum(1 for issue in issues if issue.get("code") == "followup_owner_missing"),
        },
        "followups": [item.as_dict() for item in followups],
        "issues": issues,
        "blocked_followups": blocked,
        "review_followups": review,
        "by_owner": _by_owner(followups),
        "next_actions": next_actions,
    }


def _followups(data: Mapping[str, Any]) -> list[Any]:
    if data.get("followups"):
        return _as_sequence(data.get("followups"))
    if data.get("items"):
        return _as_sequence(data.get("items"))
    generated: list[dict[str, Any]] = []
    governance = _as_mapping(data.get("governance_summary"))
    for issue in _as_sequence(governance.get("issues")):
        payload = _as_mapping(issue)
        code = str(payload.get("code") or "followup")
        generated.append(
            {
                "followup_id": f"followup:{code}",
                "owner": payload.get("owner"),
                "action": f"resolve_{code}",
                "source_kind": governance.get("kind") or "governance_summary",
                "candidate_id": payload.get("candidate_id"),
                "severity": payload.get("severity") or "medium",
                "evidence_refs": payload.get("evidence_refs"),
            }
        )
    for component in _as_sequence(data.get("components")):
        payload = _as_mapping(component)
        seen: set[str] = set()
        for action in _as_sequence(payload.get("next_actions")):
            text = str(action)
            if text in seen:
                continue
            seen.add(text)
            generated.append(
                {
                    "followup_id": f"{payload.get('kind') or 'component'}:{text}",
                    "owner": payload.get("owner"),
                    "action": text,
                    "source_kind": payload.get("kind"),
                    "candidate_id": payload.get("candidate_id") or str(payload.get("kind") or ""),
                    "severity": payload.get("severity") or "medium",
                    "evidence_refs": payload.get("evidence_refs"),
                    "topics": payload.get("review_topics"),
                }
            )
    return generated


def _by_owner(items: Sequence[FollowupItem]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        if item.owner:
            result.setdefault(item.owner, []).append(item.followup_id)
    return result


def _slug(value: str) -> str:
    return value.replace("_", "-").replace(" ", "-")


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
