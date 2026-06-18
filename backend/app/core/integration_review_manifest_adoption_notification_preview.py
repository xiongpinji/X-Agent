from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionNotificationPreviewItem:
    candidate_id: str
    notification_key: str
    status: str
    notification_state: str
    recipient_role: str
    recipient: str
    channel: str
    go_no_go: str
    recommended_outcome: str
    subject: str = ""
    message: str = ""
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "notification_key": self.notification_key,
            "status": self.status,
            "notification_state": self.notification_state,
            "recipient_role": self.recipient_role,
            "recipient": self.recipient,
            "channel": self.channel,
            "go_no_go": self.go_no_go,
            "recommended_outcome": self.recommended_outcome,
            "subject": self.subject,
            "message": self.message,
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_notification_preview_item(
    item: Mapping[str, Any] | Any,
) -> ReviewManifestAdoptionNotificationPreviewItem:
    payload = _as_mapping(item)
    role = str(payload.get("recipient_role") or "owner")
    recipient = str(payload.get("recipient") or payload.get(role) or "")
    status = str(payload.get("status") or "needs_review")
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    if status == "blocked" or blockers:
        status = "blocked"
        state = "blocked"
    elif not recipient:
        status = "needs_review"
        state = "needs_recipient"
    else:
        status = "ready"
        state = "ready_to_notify"
    candidate_id = str(payload.get("candidate_id") or "")
    base_key = str(payload.get("notification_key") or payload.get("handoff_key") or candidate_id)
    return ReviewManifestAdoptionNotificationPreviewItem(
        candidate_id=candidate_id,
        notification_key=f"{base_key}:{role}" if ":" not in base_key else base_key,
        status=status,
        notification_state=state,
        recipient_role=role,
        recipient=recipient,
        channel=str(payload.get("channel") or "handoff-doc"),
        go_no_go=str(payload.get("go_no_go") or ""),
        recommended_outcome=str(payload.get("recommended_outcome") or ""),
        subject=str(payload.get("subject") or (f"Review {candidate_id}" if candidate_id else "")),
        message=str(payload.get("message") or ""),
        validation_refs=tuple(str(ref) for ref in _as_sequence(payload.get("validation_refs"))),
        handoff_refs=tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs"))),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_notification_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_notification_preview",
            "ok": False,
            "status": "empty",
            "summary": {"owner_notification_count": 0, "reviewer_notification_count": 0},
            "items": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_notification_preview_inputs"],
        }

    items = [summarize_review_manifest_adoption_notification_preview_item(item) for item in raw]
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    ready = _candidate_ids(item for item in items if item.status == "ready")
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_notification_preview_blockers", "rebuild_integration_review_manifest_adoption_notification_preview"]
    elif review:
        status = "needs_review"
        next_actions = _recipient_actions(items) + ["rebuild_integration_review_manifest_adoption_notification_preview"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_notification_preview_with_mainline"]

    return {
        "kind": "integration_review_manifest_adoption_notification_preview",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "owner_notification_count": sum(1 for item in items if item.recipient_role == "owner"),
            "reviewer_notification_count": sum(1 for item in items if item.recipient_role == "reviewer"),
        },
        "items": [item.as_dict() for item in items],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("notifications"):
        rows: list[dict[str, Any]] = []
        for notification in _as_sequence(data.get("notifications")):
            payload = _as_mapping(notification)
            roles = _as_sequence(payload.get("recipient_roles")) or [payload.get("recipient_role") or "owner"]
            for role in roles:
                row = dict(payload)
                row["recipient_role"] = str(role)
                rows.append(row)
        return rows

    handoff = _as_mapping(data.get("manifest_adoption_owner_handoff"))
    final_packet_index = {
        str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item)
        for item in _as_sequence(_as_mapping(data.get("manifest_adoption_final_packet")).get("items"))
    }
    owner_context = _as_mapping(data.get("owner_context"))
    reviewer_context = _as_mapping(data.get("reviewer_context"))
    rows = []
    for item in _as_sequence(handoff.get("items")):
        payload = _as_mapping(item)
        candidate_id = str(payload.get("candidate_id") or "")
        fallback = final_packet_index.get(candidate_id, {})
        for role in ("owner", "reviewer"):
            context = _as_mapping((owner_context if role == "owner" else reviewer_context).get(candidate_id))
            row = dict(payload)
            row["recipient_role"] = role
            row["recipient"] = payload.get(role) or context.get("recipient")
            row["channel"] = context.get("channel") or payload.get("channel")
            row["validation_refs"] = payload.get("validation_refs") or fallback.get("validation_refs")
            row["handoff_refs"] = payload.get("handoff_refs") or fallback.get("handoff_refs")
            rows.append(row)
    return rows


def _recipient_actions(items: Sequence[ReviewManifestAdoptionNotificationPreviewItem]) -> list[str]:
    actions: list[str] = []
    if any(item.notification_state == "needs_recipient" and item.recipient_role == "owner" for item in items):
        actions.append("assign_manifest_adoption_owner_notification_recipient")
    if any(item.notification_state == "needs_recipient" and item.recipient_role == "reviewer" for item in items):
        actions.append("assign_manifest_adoption_reviewer_notification_recipient")
    return actions


def _candidate_ids(items: Sequence[ReviewManifestAdoptionNotificationPreviewItem]) -> list[str]:
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
