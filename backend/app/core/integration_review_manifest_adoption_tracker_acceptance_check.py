from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionTrackerAcceptanceCheckItem:
    candidate_id: str
    check_key: str
    status: str
    acceptance_state: str
    accepted: bool
    assignee: str = ""
    reviewer: str = ""
    priority: str = "medium"
    tracker_refs: tuple[str, ...] = field(default_factory=tuple)
    notification_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    missing_refs: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "check_key": self.check_key,
            "status": self.status,
            "acceptance_state": self.acceptance_state,
            "accepted": self.accepted,
            "assignee": self.assignee,
            "reviewer": self.reviewer,
            "priority": self.priority,
            "tracker_refs": list(self.tracker_refs),
            "notification_refs": list(self.notification_refs),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "missing_refs": list(self.missing_refs),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_tracker_acceptance_check_item(
    item: Mapping[str, Any] | Any,
    *,
    tracker_preview_index: Mapping[str, Mapping[str, Any]] | None = None,
    notification_index: Mapping[str, Mapping[str, Any]] | None = None,
    owner_handoff_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionTrackerAcceptanceCheckItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    preview = dict((tracker_preview_index or {}).get(candidate_id, {}))
    notification = dict((notification_index or {}).get(candidate_id, {}))
    owner_handoff = dict((owner_handoff_index or {}).get(candidate_id, {}))
    status = str(payload.get("status") or "needs_review")
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    assignee = str(payload.get("assignee") or preview.get("assignee") or "")
    reviewer = str(payload.get("reviewer") or preview.get("reviewer") or "")
    tracker_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("tracker_refs")) or _as_sequence(preview.get("tracker_key"))))
    notification_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("notification_refs")) or _as_sequence(notification.get("notification_key"))))
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(preview.get("validation_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(owner_handoff.get("handoff_refs"))))
    missing = []
    for name, values in (
        ("assignee", [assignee] if assignee else []),
        ("reviewer", [reviewer] if reviewer else []),
        ("tracker_refs", tracker_refs),
        ("notification_refs", notification_refs),
        ("validation_refs", validation_refs),
        ("handoff_refs", handoff_refs),
    ):
        if not values:
            missing.append(name)
    if status == "blocked" or blockers:
        status = "blocked"
        state = "blocked"
        accepted = False
        priority = "high"
    elif missing:
        status = "needs_review"
        state = "needs_evidence"
        accepted = False
        priority = str(payload.get("priority") or "medium")
    else:
        status = "ready"
        state = "accepted_for_mainline_tracker_review"
        accepted = True
        priority = str(payload.get("priority") or "medium")
    return ReviewManifestAdoptionTrackerAcceptanceCheckItem(
        candidate_id=candidate_id,
        check_key=str(payload.get("check_key") or payload.get("digest_key") or candidate_id),
        status=status,
        acceptance_state=state,
        accepted=accepted,
        assignee=assignee,
        reviewer=reviewer,
        priority=priority,
        tracker_refs=tracker_refs,
        notification_refs=notification_refs,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        missing_refs=tuple(missing),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_tracker_acceptance_check(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_tracker_acceptance_check",
            "ok": False,
            "status": "empty",
            "items": [],
            "accepted_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_tracker_acceptance_check_inputs"],
        }
    items = [
        summarize_review_manifest_adoption_tracker_acceptance_check_item(
            item,
            tracker_preview_index=_index(_as_mapping(data.get("manifest_adoption_tracker_preview")).get("items")),
            notification_index=_index(_as_mapping(data.get("manifest_adoption_notification_preview")).get("items")),
            owner_handoff_index=_index(_as_mapping(data.get("manifest_adoption_owner_handoff")).get("items")),
        )
        for item in raw
    ]
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    accepted = _candidate_ids(item for item in items if item.accepted)
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_tracker_acceptance_blockers", "rebuild_integration_review_manifest_adoption_tracker_acceptance_check"]
    elif review:
        status = "needs_review"
        next_actions = _acceptance_actions(items) + ["rebuild_integration_review_manifest_adoption_tracker_acceptance_check"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_tracker_acceptance_check_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_tracker_acceptance_check",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "accepted_candidates": accepted,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("checks"):
        return _as_sequence(data.get("checks"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_tracker_digest")).get("items"))


def _acceptance_actions(items: Sequence[ReviewManifestAdoptionTrackerAcceptanceCheckItem]) -> list[str]:
    actions: list[str] = []
    missing = {ref for item in items for ref in item.missing_refs}
    if "assignee" in missing:
        actions.append("assign_manifest_adoption_tracker_acceptance_assignee")
    if "validation_refs" in missing:
        actions.append("attach_manifest_adoption_tracker_acceptance_validation_refs")
    if "handoff_refs" in missing:
        actions.append("attach_manifest_adoption_tracker_acceptance_handoff_refs")
    if "tracker_refs" in missing:
        actions.append("attach_manifest_adoption_tracker_acceptance_tracker_refs")
    if "notification_refs" in missing:
        actions.append("attach_manifest_adoption_tracker_acceptance_notification_refs")
    return actions


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


def _candidate_ids(items: Sequence[ReviewManifestAdoptionTrackerAcceptanceCheckItem]) -> list[str]:
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
