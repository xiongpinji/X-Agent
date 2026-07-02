from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewCalendarSlot:
    candidate_id: str
    owner: str
    reviewer: str
    status: str
    window: str
    risk_level: str = "low"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "status": self.status,
            "window": self.window,
            "risk_level": self.risk_level,
            "reasons": list(self.reasons),
        }


def summarize_review_calendar_slot(slot: Mapping[str, Any] | Any, *, default_window: str = "review_window") -> ReviewCalendarSlot:
    payload = _as_mapping(slot)
    reviewer = str(payload.get("reviewer") or payload.get("primary_reviewer") or "")
    owner = str(payload.get("owner") or "")
    risk = str(payload.get("risk_level") or "low")
    reasons: list[str] = []
    if not reviewer:
        reasons.append("reviewer missing")
    if not owner:
        reasons.append("owner missing")
    status = "needs_review" if reasons else str(payload.get("status") or payload.get("review_status") or "ready")
    window = str(payload.get("window") or ("review_window_urgent" if risk == "high" else default_window))
    return ReviewCalendarSlot(
        candidate_id=str(payload.get("candidate_id") or ""),
        owner=owner,
        reviewer=reviewer,
        status=status,
        window=window,
        risk_level=risk,
        reasons=tuple(reasons),
    )


def build_integration_review_calendar(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    assignments = _assignments(data)
    if not assignments:
        return {
            "kind": "integration_review_calendar",
            "calendar_id": str(data.get("calendar_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"slot_count": 0},
            "slots": [],
            "by_reviewer": {},
            "by_window": {},
            "blocked_candidates": [],
            "next_actions": ["provide_review_calendar_inputs"],
        }
    blocked_refs = _blocked_refs(data)
    urgency = _as_mapping(data.get("urgency_hints"))
    slots: list[ReviewCalendarSlot] = []
    for item in assignments:
        slot = summarize_review_calendar_slot(item, default_window=str(data.get("default_window") or "review_window"))
        if slot.candidate_id in blocked_refs:
            reasons = tuple(list(slot.reasons) + ["review digest blocks calendar slot"])
            slot = ReviewCalendarSlot(slot.candidate_id, slot.owner, slot.reviewer, "blocked", "review_window_urgent", "high", reasons)
        elif _int(urgency.get(slot.candidate_id)) >= 80 and slot.risk_level != "high":
            slot = ReviewCalendarSlot(slot.candidate_id, slot.owner, slot.reviewer, slot.status, "review_window_urgent", "high", slot.reasons)
        elif _int(urgency.get(slot.candidate_id)) < 80 and urgency and slot.window == data.get("default_window"):
            slot = ReviewCalendarSlot(slot.candidate_id, slot.owner, slot.reviewer, slot.status, f"{slot.window}_later", slot.risk_level, slot.reasons)
        slots.append(slot)
    slots.sort(key=lambda slot: (-_int(urgency.get(slot.candidate_id)), slot.candidate_id))
    blocked = [slot.candidate_id for slot in slots if slot.status == "blocked"]
    review = [slot for slot in slots if slot.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_blocked_review_calendar_slots", "rebuild_integration_review_calendar"]
    elif review:
        status = "needs_review"
        actions = ["complete_review_calendar_plan"]
        if any("reviewer missing" in slot.reasons for slot in review):
            actions.append("assign_calendar_reviewer")
        if any("owner missing" in slot.reasons for slot in review):
            actions.append("assign_calendar_owner")
        next_actions = actions + ["rebuild_integration_review_calendar"]
    else:
        status = "ready"
        next_actions = ["share_review_calendar_with_mainline"]
    return {
        "kind": "integration_review_calendar",
        "calendar_id": str(data.get("calendar_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"slot_count": len(slots)},
        "slots": [slot.as_dict() for slot in slots],
        "by_reviewer": _bucket(slots, "reviewer"),
        "by_window": _bucket(slots, "window"),
        "blocked_candidates": blocked,
        "next_actions": next_actions,
    }


def _assignments(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    matrix = _as_mapping(data.get("reviewer_assignment_matrix"))
    return _as_sequence(matrix.get("assignments"))


def _blocked_refs(data: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    digest = _as_mapping(data.get("manifest_review_digest"))
    for signal in _as_sequence(digest.get("signals")):
        payload = _as_mapping(signal)
        if payload.get("status") == "blocked":
            refs.update(str(ref) for ref in _as_sequence(payload.get("refs")))
    return refs


def _bucket(slots: Sequence[ReviewCalendarSlot], attr: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for slot in slots:
        key = getattr(slot, attr)
        if key:
            result.setdefault(key, []).append(slot.candidate_id)
    return result


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
