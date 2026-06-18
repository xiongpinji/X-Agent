from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OwnerDigest:
    owner: str
    status: str
    followup_ids: tuple[str, ...] = field(default_factory=tuple)
    candidate_ids: tuple[str, ...] = field(default_factory=tuple)
    actions: tuple[str, ...] = field(default_factory=tuple)
    high_priority_count: int = 0
    blocked_count: int = 0
    missing_evidence_count: int = 0
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "status": self.status,
            "followup_ids": list(self.followup_ids),
            "candidate_ids": list(self.candidate_ids),
            "actions": list(self.actions),
            "high_priority_count": self.high_priority_count,
            "blocked_count": self.blocked_count,
            "missing_evidence_count": self.missing_evidence_count,
            "reasons": list(self.reasons),
        }


def summarize_owner_digest(owner: str, followups: Sequence[Mapping[str, Any] | Any]) -> OwnerDigest:
    items = [_as_mapping(item) for item in followups]
    blocked_count = len([item for item in items if str(item.get("status") or "ready") == "blocked"])
    missing_evidence_count = len([item for item in items if not _as_sequence(item.get("evidence_refs"))])
    high_priority_count = len([item for item in items if _priority(item) >= 80 or str(item.get("severity") or "") == "high"])
    if blocked_count:
        status = "blocked"
        reasons = ("blocked followups require owner review",)
    elif owner == "unassigned" or missing_evidence_count:
        status = "needs_review"
        reasons = tuple(
            reason
            for reason in [
                "owner missing" if owner == "unassigned" else "",
                "owner followup evidence missing" if missing_evidence_count else "",
            ]
            if reason
        )
    else:
        status = "ready"
        reasons = ("owner digest ready",)
    return OwnerDigest(
        owner=owner,
        status=status,
        followup_ids=tuple(_unique([str(item.get("followup_id") or "") for item in items])),
        candidate_ids=tuple(_unique([str(item.get("candidate_id") or "") for item in items])),
        actions=tuple(_unique([str(item.get("action") or "") for item in items])),
        high_priority_count=high_priority_count,
        blocked_count=blocked_count,
        missing_evidence_count=missing_evidence_count,
        reasons=reasons,
    )


def build_integration_owner_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    followups = _followups(data)
    if not followups:
        return {
            "kind": "integration_owner_digest",
            "ok": False,
            "status": "empty",
            "owners": [],
            "blocked_owners": [],
            "review_owners": [],
            "issues": [],
            "next_actions": ["provide_owner_digest_inputs"],
        }
    groups: dict[str, list[dict[str, Any]]] = {}
    for followup in followups:
        owner = str(followup.get("owner") or "unassigned")
        groups.setdefault(owner, []).append(followup)
    owners = [summarize_owner_digest(owner, items) for owner, items in groups.items()]
    blocked = [item.owner for item in owners if item.status == "blocked"]
    review = [item.owner for item in owners if item.status == "needs_review"]
    issues = _issues(owners)
    if blocked:
        status = "blocked"
        next_actions = ["resolve_owner_blocked_followups", "rebuild_integration_owner_digest"]
    elif review:
        status = "needs_review"
        next_actions = _review_actions(owners) + ["rebuild_integration_owner_digest"]
    else:
        status = "ready"
        next_actions = ["review_owner_digest_with_mainline"]
    return {
        "kind": "integration_owner_digest",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "owner_count": len(owners),
            "followup_count": len(followups),
            "blocked_count": sum(item.blocked_count for item in owners),
            "high_priority_count": sum(item.high_priority_count for item in owners),
            "missing_evidence_count": sum(item.missing_evidence_count for item in owners),
        },
        "owners": [owner.as_dict() for owner in owners],
        "blocked_owners": blocked,
        "review_owners": review,
        "issues": issues,
        "next_actions": next_actions,
    }


def _followups(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("followups") or data.get("items") or _as_mapping(data.get("followup_queue")).get("followups")
    return [_as_mapping(item) for item in _as_sequence(raw)]


def _issues(owners: Sequence[OwnerDigest]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if any(owner.blocked_count for owner in owners):
        issues.append({"code": "owner_digest_blocked_followups", "severity": "high"})
    if any(owner.owner == "unassigned" for owner in owners):
        issues.append({"code": "owner_digest_owner_missing", "severity": "medium"})
    if any(owner.missing_evidence_count for owner in owners):
        issues.append({"code": "owner_digest_missing_evidence", "severity": "medium"})
    return issues


def _review_actions(owners: Sequence[OwnerDigest]) -> list[str]:
    actions: list[str] = []
    if any(owner.owner == "unassigned" for owner in owners):
        actions.append("assign_missing_digest_owners")
    if any(owner.missing_evidence_count for owner in owners):
        actions.append("attach_owner_followup_evidence")
    return actions


def _priority(item: Mapping[str, Any]) -> int:
    try:
        return int(item.get("priority") or 0)
    except (TypeError, ValueError):
        return 0


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
