from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestAdoptionFinalPacketItem:
    candidate_id: str
    packet_key: str
    status: str
    packet_state: str
    go_no_go: str
    recommended_outcome: str
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "packet_key": self.packet_key,
            "status": self.status,
            "packet_state": self.packet_state,
            "go_no_go": self.go_no_go,
            "recommended_outcome": self.recommended_outcome,
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_final_packet_item(
    item: Mapping[str, Any] | Any,
    *,
    rollback_index: Mapping[str, Mapping[str, Any]] | None = None,
    dry_run_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ManifestAdoptionFinalPacketItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    rollback = dict((rollback_index or {}).get(candidate_id, {}))
    dry_run = dict((dry_run_index or {}).get(candidate_id, {}))
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(rollback.get("validation_refs")) or _as_sequence(dry_run.get("validation_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(dry_run.get("handoff_refs")) or _as_sequence(rollback.get("handoff_refs"))))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    go_no_go = str(payload.get("go_no_go") or "")
    status = str(payload.get("status") or "needs_review")
    if status == "blocked" or go_no_go == "no_go" or blockers:
        status = "blocked"
        packet_state = "blocked"
    elif go_no_go == "hold":
        status = "needs_review"
        packet_state = "needs_mainline_review"
    elif validation_refs and handoff_refs:
        status = "ready"
        packet_state = "ready_for_mainline_review"
    else:
        status = "needs_review"
        packet_state = "needs_evidence"
    return ManifestAdoptionFinalPacketItem(
        candidate_id=candidate_id,
        packet_key=str(payload.get("packet_key") or payload.get("decision_key") or candidate_id),
        status=status,
        packet_state=packet_state,
        go_no_go=go_no_go,
        recommended_outcome=str(payload.get("recommended_outcome") or ""),
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_final_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_final_packet",
            "ok": False,
            "status": "empty",
            "items": [],
            "packet_sections": {"blockers": []},
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_final_packet_inputs"],
        }
    rollback_index = _index(_as_mapping(data.get("manifest_adoption_rollback_preview")).get("items"))
    dry_run_index = _index(_as_mapping(data.get("manifest_adoption_dry_run_report")).get("items"))
    items = [summarize_review_manifest_adoption_final_packet_item(item, rollback_index=rollback_index, dry_run_index=dry_run_index) for item in raw]
    blocked = _candidate_ids(item for item in items if item.status == "blocked")
    review = _candidate_ids(item for item in items if item.status == "needs_review")
    ready = _candidate_ids(item for item in items if item.status == "ready")
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_final_packet_blockers", "rebuild_integration_review_manifest_adoption_final_packet"]
    elif review:
        status = "needs_review"
        next_actions = ["resolve_manifest_adoption_hold_decision", "rebuild_integration_review_manifest_adoption_final_packet"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_final_packet_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_final_packet",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "packet_sections": {"blockers": _unique([blocker for item in items for blocker in item.blockers])},
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("packets"):
        return _as_sequence(data.get("packets"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_go_no_go")).get("items"))


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


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


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
