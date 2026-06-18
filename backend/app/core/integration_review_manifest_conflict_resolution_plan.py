from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestConflictResolutionItem:
    candidate_id: str
    plan_key: str
    status: str
    conflict_level: str
    recommended_decision: str
    priority: str
    candidate_paths: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    required_actions: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "plan_key": self.plan_key,
            "status": self.status,
            "conflict_level": self.conflict_level,
            "recommended_decision": self.recommended_decision,
            "priority": self.priority,
            "candidate_paths": list(self.candidate_paths),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "required_actions": list(self.required_actions),
            "reasons": list(self.reasons),
        }


def summarize_review_manifest_conflict_resolution_item(
    item: Mapping[str, Any] | Any,
    *,
    owner_hints: Mapping[str, str] | None = None,
    reviewer_hints: Mapping[str, Any] | None = None,
) -> ReviewManifestConflictResolutionItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    status = str(payload.get("status") or "needs_review")
    level = str(payload.get("conflict_level") or "review")
    owner = str(payload.get("owner") or (owner_hints or {}).get(candidate_id, ""))
    reviewer_hint = (reviewer_hints or {}).get(candidate_id, "")
    reviewer = str(payload.get("reviewer") or _as_mapping(reviewer_hint).get("reviewer") or reviewer_hint or "")
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    blockers = tuple(str(ref) for ref in (_as_sequence(payload.get("blockers")) or _as_sequence(payload.get("forbidden_paths"))))
    reasons = [str(reason) for reason in _as_sequence(payload.get("reasons"))]
    required_actions = [str(action) for action in _as_sequence(payload.get("required_actions"))]
    if not handoff_refs:
        status = "needs_review" if status != "blocked" else status
        reasons.append("handoff refs missing")
        required_actions.append("attach_manifest_conflict_handoff_refs")
    if status == "blocked" or level == "blocked":
        status = "blocked"
        priority = "high"
        decision = str(payload.get("recommended_decision") or "defer_candidate_until_blockers_resolved")
    elif status == "needs_review" or level == "review":
        priority = "medium"
        decision = str(payload.get("recommended_decision") or "coordinate_candidate_with_mainline_owner")
        required_actions.append("coordinate_manifest_conflict_with_mainline_owner")
    else:
        priority = "low"
        decision = str(payload.get("recommended_decision") or "prepare_candidate_for_mainline_evaluation")
    return ReviewManifestConflictResolutionItem(
        candidate_id=candidate_id,
        plan_key=str(payload.get("plan_key") or payload.get("conflict_key") or candidate_id),
        status=status,
        conflict_level=level,
        recommended_decision=decision,
        priority=priority,
        candidate_paths=tuple(str(path) for path in _as_sequence(payload.get("candidate_paths"))),
        handoff_refs=handoff_refs,
        owner=owner,
        reviewer=reviewer,
        blockers=blockers,
        required_actions=tuple(_unique(required_actions)),
        reasons=tuple(_unique(reasons)),
    )


def build_integration_review_manifest_conflict_resolution_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_conflict_resolution_plan",
            "ok": False,
            "status": "empty",
            "items": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_conflict_resolution_inputs"],
        }
    owner_hints = {str(k): str(v) for k, v in _as_mapping(data.get("owner_hints")).items()}
    reviewer_hints = _as_mapping(data.get("reviewer_hints"))
    items = [summarize_review_manifest_conflict_resolution_item(item, owner_hints=owner_hints, reviewer_hints=reviewer_hints) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review"]
    ready = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_conflict_resolution_plan_blockers"] + _unique([action for item in items for action in item.required_actions])
    elif review:
        status = "needs_review"
        next_actions = _unique([action for item in items for action in item.required_actions] + ["rebuild_integration_review_manifest_conflict_resolution_plan"])
    else:
        status = "ready"
        next_actions = ["share_manifest_conflict_resolution_plan_with_mainline"]
    return {
        "kind": "integration_review_manifest_conflict_resolution_plan",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("resolutions"):
        return _as_sequence(data.get("resolutions"))
    preview = _as_mapping(data.get("manifest_conflict_preview"))
    return _as_sequence(preview.get("items"))


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
