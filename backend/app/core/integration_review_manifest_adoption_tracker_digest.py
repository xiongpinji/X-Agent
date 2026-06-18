from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionTrackerDigestItem:
    candidate_id: str
    digest_key: str
    status: str
    digest_state: str
    summary: str
    assignee: str = ""
    reviewer: str = ""
    priority: str = "medium"
    labels: tuple[str, ...] = field(default_factory=tuple)
    tracker_refs: tuple[str, ...] = field(default_factory=tuple)
    notification_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    missing_refs: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "digest_key": self.digest_key,
            "status": self.status,
            "digest_state": self.digest_state,
            "summary": self.summary,
            "assignee": self.assignee,
            "reviewer": self.reviewer,
            "priority": self.priority,
            "labels": list(self.labels),
            "tracker_refs": list(self.tracker_refs),
            "notification_refs": list(self.notification_refs),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "missing_refs": list(self.missing_refs),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_tracker_digest_item(
    item: Mapping[str, Any] | Any,
    *,
    notification_index: Mapping[str, Mapping[str, Any]] | None = None,
    owner_handoff_index: Mapping[str, Mapping[str, Any]] | None = None,
    final_packet_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionTrackerDigestItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    notification = dict((notification_index or {}).get(candidate_id, {}))
    owner_handoff = dict((owner_handoff_index or {}).get(candidate_id, {}))
    final_packet = dict((final_packet_index or {}).get(candidate_id, {}))
    status = str(payload.get("status") or "needs_review")
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    assignee = str(payload.get("assignee") or notification.get("recipient") or owner_handoff.get("owner") or "")
    reviewer = str(payload.get("reviewer") or owner_handoff.get("reviewer") or "")
    tracker_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("tracker_refs")) or _as_sequence(payload.get("tracker_key"))))
    notification_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("notification_refs")) or _as_sequence(notification.get("notification_key"))))
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(final_packet.get("validation_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(owner_handoff.get("handoff_refs"))))
    missing = []
    if not assignee:
        missing.append("assignee")
    if not validation_refs:
        missing.append("validation_refs")
    if not handoff_refs:
        missing.append("handoff_refs")
    if status == "blocked" or blockers:
        status = "blocked"
        state = "blocked"
        priority = "high"
    elif missing:
        status = "needs_review"
        state = "needs_assignee" if "assignee" in missing else "needs_evidence"
        priority = str(payload.get("priority") or "medium")
    else:
        status = "ready"
        state = "ready_for_mainline_tracker_review"
        priority = str(payload.get("priority") or "medium")
    labels = _unique([str(label) for label in _as_sequence(payload.get("labels"))] + ["tracker_digest"])
    return ReviewManifestAdoptionTrackerDigestItem(
        candidate_id=candidate_id,
        digest_key=str(payload.get("digest_key") or payload.get("tracker_key") or candidate_id),
        status=status,
        digest_state=state,
        summary=str(payload.get("summary") or (f"{candidate_id} tracker digest is local-preview ready." if candidate_id else "")),
        assignee=assignee,
        reviewer=reviewer,
        priority=priority,
        labels=tuple(labels),
        tracker_refs=tracker_refs,
        notification_refs=notification_refs,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        missing_refs=tuple(missing),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_tracker_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_tracker_digest",
            "ok": False,
            "status": "empty",
            "items": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_tracker_digest_inputs"],
        }
    items = [
        summarize_review_manifest_adoption_tracker_digest_item(
            item,
            notification_index=_index(_as_mapping(data.get("manifest_adoption_notification_preview")).get("items")),
            owner_handoff_index=_index(_as_mapping(data.get("manifest_adoption_owner_handoff")).get("items")),
            final_packet_index=_index(_as_mapping(data.get("manifest_adoption_final_packet")).get("items")),
        )
        for item in raw
    ]
    return _result(items)


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("digests"):
        return _as_sequence(data.get("digests"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_tracker_preview")).get("items"))


def _result(items: Sequence[ReviewManifestAdoptionTrackerDigestItem]) -> dict[str, Any]:
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    ready = _candidate_ids(item for item in items if item.status == "ready")
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_tracker_digest_blockers", "rebuild_integration_review_manifest_adoption_tracker_digest"]
    elif review:
        status = "needs_review"
        next_actions = _digest_actions(items) + ["rebuild_integration_review_manifest_adoption_tracker_digest"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_tracker_digest_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_tracker_digest",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _digest_actions(items: Sequence[ReviewManifestAdoptionTrackerDigestItem]) -> list[str]:
    actions: list[str] = []
    if any("assignee" in item.missing_refs for item in items):
        actions.append("assign_manifest_adoption_tracker_digest_assignee")
    if any("validation_refs" in item.missing_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_digest_validation_refs")
    if any("handoff_refs" in item.missing_refs for item in items):
        actions.append("attach_manifest_adoption_tracker_digest_handoff_refs")
    return actions


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


def _candidate_ids(items: Sequence[ReviewManifestAdoptionTrackerDigestItem]) -> list[str]:
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


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
