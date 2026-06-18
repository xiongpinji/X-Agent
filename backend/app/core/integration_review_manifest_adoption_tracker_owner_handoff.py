from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionTrackerOwnerHandoffItem:
    candidate_id: str
    handoff_key: str
    status: str
    handoff_state: str
    accepted: bool
    owner: str = ""
    reviewer: str = ""
    tracker_refs: tuple[str, ...] = field(default_factory=tuple)
    notification_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    missing_assignments: tuple[str, ...] = field(default_factory=tuple)
    owner_actions: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "handoff_key": self.handoff_key,
            "status": self.status,
            "handoff_state": self.handoff_state,
            "accepted": self.accepted,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "tracker_refs": list(self.tracker_refs),
            "notification_refs": list(self.notification_refs),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "missing_assignments": list(self.missing_assignments),
            "owner_actions": list(self.owner_actions),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_tracker_owner_handoff_item(
    item: Mapping[str, Any] | Any,
    *,
    acceptance_index: Mapping[str, Mapping[str, Any]] | None = None,
    owner_context: Mapping[str, Any] | None = None,
    reviewer_context: Mapping[str, Any] | None = None,
) -> ReviewManifestAdoptionTrackerOwnerHandoffItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    acceptance = dict((acceptance_index or {}).get(candidate_id, {}))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    status = str(payload.get("status") or "needs_review")
    owner = str(payload.get("owner") or payload.get("assignee") or _as_mapping(owner_context).get(candidate_id) or "")
    reviewer = str(payload.get("reviewer") or _as_mapping(reviewer_context).get(candidate_id) or "")
    tracker_refs = tuple(
        str(ref) for ref in (_as_sequence(payload.get("tracker_refs")) or _as_sequence(acceptance.get("tracker_refs")))
    )
    notification_refs = tuple(
        str(ref)
        for ref in (_as_sequence(payload.get("notification_refs")) or _as_sequence(acceptance.get("notification_refs")))
    )
    validation_refs = tuple(
        str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(acceptance.get("validation_refs")))
    )
    handoff_refs = tuple(
        str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(acceptance.get("handoff_refs")))
    )
    missing_assignments = tuple(label for label, value in (("owner", owner), ("reviewer", reviewer)) if not value)
    missing_refs = tuple(
        label
        for label, values in (
            ("tracker_refs", tracker_refs),
            ("notification_refs", notification_refs),
            ("validation_refs", validation_refs),
            ("handoff_refs", handoff_refs),
        )
        if not values
    )
    if status == "blocked" or blockers:
        status = "blocked"
        accepted = False
        handoff_state = "blocked"
        owner_actions = ("review_tracker_handoff_blockers",)
    elif missing_assignments:
        status = "needs_review"
        accepted = False
        handoff_state = "needs_assignment"
        owner_actions = ()
    elif missing_refs:
        status = "needs_review"
        accepted = False
        handoff_state = "needs_evidence"
        owner_actions = ()
    else:
        status = "ready"
        accepted = bool(payload.get("accepted", True))
        handoff_state = "ready_for_owner_review"
        owner_actions = ("review_tracker_final_packet",)
    return ReviewManifestAdoptionTrackerOwnerHandoffItem(
        candidate_id=candidate_id,
        handoff_key=str(payload.get("handoff_key") or payload.get("packet_key") or candidate_id),
        status=status,
        handoff_state=handoff_state,
        accepted=accepted,
        owner=owner,
        reviewer=reviewer,
        tracker_refs=tracker_refs,
        notification_refs=notification_refs,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        missing_assignments=missing_assignments,
        owner_actions=owner_actions,
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_tracker_owner_handoff(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_tracker_owner_handoff",
            "ok": False,
            "status": "empty",
            "items": [],
            "owner_groups": {},
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_tracker_owner_handoff_inputs"],
        }
    items = [
        summarize_review_manifest_adoption_tracker_owner_handoff_item(
            item,
            acceptance_index=_index(_as_mapping(data.get("manifest_adoption_tracker_acceptance_check")).get("items")),
            owner_context=_as_mapping(data.get("owner_context")),
            reviewer_context=_as_mapping(data.get("reviewer_context")),
        )
        for item in raw
    ]
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_manifest_adoption_tracker_owner_handoff_blockers",
            "rebuild_integration_review_manifest_adoption_tracker_owner_handoff",
        ]
    elif review:
        status = "needs_review"
        next_actions = _review_actions(items) + ["rebuild_integration_review_manifest_adoption_tracker_owner_handoff"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_tracker_owner_handoff_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_tracker_owner_handoff",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "owner_groups": _owner_groups(items),
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("handoffs"):
        return _as_sequence(data.get("handoffs"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_tracker_final_packet")).get("items"))


def _review_actions(items: Sequence[ReviewManifestAdoptionTrackerOwnerHandoffItem]) -> list[str]:
    actions: list[str] = []
    if any("owner" in item.missing_assignments for item in items):
        actions.append("assign_manifest_adoption_tracker_owner_handoff_owner")
    if any("reviewer" in item.missing_assignments for item in items):
        actions.append("assign_manifest_adoption_tracker_owner_handoff_reviewer")
    if any(not item.validation_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_owner_handoff_validation_refs")
    if any(not item.handoff_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_owner_handoff_handoff_refs")
    if any(not item.tracker_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_owner_handoff_tracker_refs")
    if any(not item.notification_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_owner_handoff_notification_refs")
    return actions


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


def _owner_groups(items: Sequence[ReviewManifestAdoptionTrackerOwnerHandoffItem]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for item in items:
        if item.owner:
            groups.setdefault(item.owner, []).append(item.candidate_id)
    return groups


def _candidate_ids(items: Any) -> list[str]:
    result: list[str] = []
    for item in items:
        if item.candidate_id and item.candidate_id not in result:
            result.append(item.candidate_id)
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
