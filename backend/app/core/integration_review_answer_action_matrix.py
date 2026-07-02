from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewAnswerAction:
    candidate_id: str
    action_key: str
    action: str
    status: str
    priority: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "action_key": self.action_key,
            "action": self.action,
            "status": self.status,
            "priority": self.priority,
            "evidence_refs": list(self.evidence_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_answer_action(
    action: Mapping[str, Any] | Any,
    *,
    blocked_candidates: set[str] | None = None,
) -> ReviewAnswerAction:
    payload = _as_mapping(action)
    candidate_id = str(payload.get("candidate_id") or "")
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    missing_refs = _as_sequence(payload.get("missing_refs"))
    owner = str(payload.get("owner") or "")
    status = str(payload.get("status") or "needs_review")
    blockers: list[str] = [str(item) for item in _as_sequence(payload.get("blockers"))]
    if missing_refs or not evidence_refs:
        blockers.append("missing_review_answer_evidence")
    if not owner:
        blockers.append("owner_missing")
    if candidate_id in (blocked_candidates or set()) or status == "blocked":
        status = "blocked"
        blockers.append("answer_source_blocked")
    elif blockers:
        status = "needs_review"
    priority = str(payload.get("priority") or ("high" if status == "blocked" else "medium" if blockers else "low"))
    reasons = ["action blockers present"] if blockers else ["action ready"]
    return ReviewAnswerAction(
        candidate_id=candidate_id,
        action_key=str(payload.get("action_key") or f"review-answer-action:{candidate_id}"),
        action=str(payload.get("action") or f"Schedule mainline evaluation for {candidate_id}."),
        status=status,
        priority=priority,
        evidence_refs=evidence_refs,
        owner=owner,
        reviewer=str(payload.get("reviewer") or ""),
        blockers=tuple(_unique(blockers)),
        reasons=tuple(reasons),
    )


def build_integration_review_answer_action_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _actions(data)
    if not raw:
        return {
            "kind": "integration_review_answer_action_matrix",
            "matrix_id": str(data.get("matrix_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"action_count": 0},
            "actions": [],
            "blocked_actions": [],
            "review_actions": [],
            "by_owner": {},
            "next_actions": ["provide_review_answer_action_matrix_inputs"],
        }
    blocked_candidates = _blocked_candidates(data)
    actions = [summarize_review_answer_action(item, blocked_candidates=blocked_candidates) for item in raw]
    blocked = [item.action_key for item in actions if item.status == "blocked"]
    review = [item.action_key for item in actions if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_answer_action_blockers",
            "attach_review_answer_action_evidence",
            "rebuild_integration_review_answer_action_matrix",
        ]
    elif review:
        status = "needs_review"
        next_actions = [
            "complete_review_answer_action_matrix",
            "assign_review_answer_action_owner",
            "attach_review_answer_action_evidence",
            "rebuild_integration_review_answer_action_matrix",
        ]
    else:
        status = "ready"
        next_actions = ["share_review_answer_action_matrix_with_mainline"]
    return {
        "kind": "integration_review_answer_action_matrix",
        "matrix_id": str(data.get("matrix_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"action_count": len(actions), "blocked_count": len(blocked), "needs_review_count": len(review)},
        "actions": [item.as_dict() for item in actions],
        "blocked_actions": blocked,
        "review_actions": review,
        "by_owner": _by_owner(actions),
        "next_actions": next_actions,
    }


def _actions(data: Mapping[str, Any]) -> list[Any]:
    if data.get("actions"):
        return _as_sequence(data.get("actions"))
    brief = _as_mapping(data.get("answer_brief"))
    return _as_sequence(brief.get("answers"))


def _blocked_candidates(data: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    digest = _as_mapping(data.get("query_result_digest"))
    for item in _as_sequence(digest.get("digests")):
        payload = _as_mapping(item)
        if payload.get("status") == "blocked":
            result.add(str(payload.get("candidate_id") or ""))
    return result


def _by_owner(actions: Sequence[ReviewAnswerAction]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for action in actions:
        if action.owner:
            result.setdefault(action.owner, []).append(action.action_key)
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
