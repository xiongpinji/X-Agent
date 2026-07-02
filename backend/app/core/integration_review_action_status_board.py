from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewActionStatusItem:
    candidate_id: str
    status_key: str
    status: str
    lane: str
    priority: str
    action_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status_key": self.status_key,
            "status": self.status,
            "lane": self.lane,
            "priority": self.priority,
            "action_refs": list(self.action_refs),
            "evidence_refs": list(self.evidence_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_action_status_item(
    item: Mapping[str, Any] | Any,
    *,
    validation_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewActionStatusItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    validation = dict((validation_index or {}).get(candidate_id, {}))
    status = str(validation.get("status") or payload.get("status") or "needs_review")
    blockers = [str(item) for item in (_as_sequence(validation.get("blockers")) or _as_sequence(payload.get("blockers")))]
    if validation.get("status") == "blocked":
        blockers.append("validation_blocked")
    owner = str(payload.get("owner") or "")
    priority = str(payload.get("priority") or ("high" if status == "blocked" else "medium"))
    if status == "blocked":
        priority = "high"
    lane = str(payload.get("lane") or ("blocked" if status == "blocked" else "priority_review" if priority == "high" and status == "ready" else status))
    reasons = ["status blockers present"] if blockers else ["status ready"]
    return ReviewActionStatusItem(
        candidate_id=candidate_id,
        status_key=str(payload.get("status_key") or payload.get("action_key") or candidate_id),
        status=status,
        lane=lane,
        priority=priority,
        action_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("action_refs")) or _as_sequence(payload.get("action_key")))),
        evidence_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(validation.get("refs")))),
        owner=owner,
        reviewer=str(payload.get("reviewer") or ""),
        blockers=tuple(_unique(blockers)),
        reasons=tuple(reasons),
    )


def build_integration_review_action_status_board(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_action_status_board",
            "board_id": str(data.get("board_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"item_count": 0},
            "items": [],
            "lanes": {},
            "by_owner": {},
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_action_status_board_inputs"],
        }
    validation_index = _validation_index(data.get("validation_state"))
    items = [summarize_review_action_status_item(item, validation_index=validation_index) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review" or item.blockers or not item.owner]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_action_status_blockers",
            "attach_review_action_status_evidence",
            "rebuild_integration_review_action_status_board",
        ]
    elif review:
        status = "needs_review"
        next_actions = [
            "complete_review_action_status_board",
            "assign_review_action_status_owner",
            "attach_review_action_status_evidence",
            "rebuild_integration_review_action_status_board",
        ]
    else:
        status = "ready"
        next_actions = ["share_review_action_status_board_with_mainline"]
    return {
        "kind": "integration_review_action_status_board",
        "board_id": str(data.get("board_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"item_count": len(items), "blocked_count": len(blocked), "needs_review_count": len(review)},
        "items": [item.as_dict() for item in items],
        "lanes": _lanes(items),
        "by_owner": _by_owner(items),
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("statuses"):
        return _as_sequence(data.get("statuses"))
    matrix = _as_mapping(data.get("answer_action_matrix"))
    return _as_sequence(matrix.get("actions"))


def _validation_index(raw: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _as_sequence(raw):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = payload
    return result


def _lanes(items: Sequence[ReviewActionStatusItem]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        result.setdefault(item.lane, []).append(item.status_key)
    return result


def _by_owner(items: Sequence[ReviewActionStatusItem]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        if item.owner:
            result.setdefault(item.owner, []).append(item.status_key)
    return result


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
