from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestAdoptionOwnerHandoffItem:
    candidate_id: str
    handoff_key: str
    status: str
    handoff_state: str
    go_no_go: str
    recommended_outcome: str
    owner: str = ""
    reviewer: str = ""
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
            "go_no_go": self.go_no_go,
            "recommended_outcome": self.recommended_outcome,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "missing_assignments": list(self.missing_assignments),
            "owner_actions": list(self.owner_actions),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_owner_handoff_item(
    item: Mapping[str, Any] | Any,
    *,
    go_no_go_index: Mapping[str, Mapping[str, Any]] | None = None,
    owner_context: Mapping[str, Any] | None = None,
    reviewer_context: Mapping[str, Any] | None = None,
) -> ManifestAdoptionOwnerHandoffItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    fallback = dict((go_no_go_index or {}).get(candidate_id, {}))
    owner = str(payload.get("owner") or _as_mapping(owner_context).get(candidate_id) or "")
    reviewer = str(payload.get("reviewer") or _as_mapping(reviewer_context).get(candidate_id) or "")
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(fallback.get("validation_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(fallback.get("handoff_refs"))))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    missing = tuple(label for label, value in (("owner", owner), ("reviewer", reviewer)) if not value)
    status = str(payload.get("status") or "needs_review")
    go_no_go = str(payload.get("go_no_go") or fallback.get("go_no_go") or "")
    if status == "blocked" or go_no_go == "no_go" or blockers:
        status = "blocked"
        state = "blocked"
        owner_actions = ("review_manifest_adoption_blockers",)
    elif missing:
        status = "needs_review"
        state = "needs_assignment"
        owner_actions = ()
    elif validation_refs and handoff_refs:
        status = "ready"
        state = "ready_for_owner_review"
        owner_actions = ("review_manifest_adoption_packet",)
    else:
        status = "needs_review"
        state = "needs_evidence"
        owner_actions = ()
    return ManifestAdoptionOwnerHandoffItem(
        candidate_id=candidate_id,
        handoff_key=str(payload.get("handoff_key") or payload.get("packet_key") or candidate_id),
        status=status,
        handoff_state=state,
        go_no_go=go_no_go,
        recommended_outcome=str(payload.get("recommended_outcome") or fallback.get("recommended_outcome") or ""),
        owner=owner,
        reviewer=reviewer,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        missing_assignments=missing,
        owner_actions=owner_actions,
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_owner_handoff(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_owner_handoff",
            "ok": False,
            "status": "empty",
            "items": [],
            "owner_groups": {},
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_owner_handoff_inputs"],
        }
    go_no_go_index = _index(_as_mapping(data.get("manifest_adoption_go_no_go")).get("items"))
    items = [
        summarize_review_manifest_adoption_owner_handoff_item(
            item,
            go_no_go_index=go_no_go_index,
            owner_context=_as_mapping(data.get("owner_context")),
            reviewer_context=_as_mapping(data.get("reviewer_context")),
        )
        for item in raw
    ]
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_owner_handoff_blockers", "rebuild_integration_review_manifest_adoption_owner_handoff"]
    elif review:
        status = "needs_review"
        next_actions = ["assign_manifest_adoption_owner", "rebuild_integration_review_manifest_adoption_owner_handoff"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_owner_handoff_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_owner_handoff",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "owner_groups": _owner_groups(items),
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("owner_handoffs"):
        return _as_sequence(data.get("owner_handoffs"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_final_packet")).get("items"))


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


def _owner_groups(items: Sequence[ManifestAdoptionOwnerHandoffItem]) -> dict[str, list[str]]:
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
