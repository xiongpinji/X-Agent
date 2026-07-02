from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewMinuteItem:
    candidate_id: str
    owner: str
    reviewer: str
    status: str
    decision: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "status": self.status,
            "decision": self.decision,
            "evidence_refs": list(self.evidence_refs),
            "risk_level": self.risk_level,
            "reasons": list(self.reasons),
        }


def summarize_review_minute_item(
    item: Mapping[str, Any] | Any,
    *,
    calendar_candidates: set[str] | None = None,
    validation_refs: Mapping[str, Sequence[str]] | None = None,
    blocked_candidates: set[str] | None = None,
) -> ReviewMinuteItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    evidence_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or (validation_refs or {}).get(candidate_id, ())))
    reasons: list[str] = []
    status = str(payload.get("status") or "needs_review")
    risk_level = str(payload.get("risk_level") or "low")
    if not evidence_refs:
        reasons.append("validation evidence missing")
    if calendar_candidates is None or candidate_id not in calendar_candidates:
        reasons.append("review calendar slot missing")
    if candidate_id in (blocked_candidates or set()):
        status = "blocked"
        risk_level = "high"
        reasons.append("review input blocked")
    decision = str(payload.get("decision") or ("blocked_pending_resolution" if status == "blocked" else "ready_for_mainline_review" if not reasons else "needs_review"))
    if reasons and status != "blocked":
        status = "needs_review"
    return ReviewMinuteItem(
        candidate_id=candidate_id,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or payload.get("primary_reviewer") or ""),
        status=status,
        decision=decision,
        evidence_refs=evidence_refs,
        risk_level=risk_level,
        reasons=tuple(reasons),
    )


def build_integration_review_minutes(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_items = _minute_items(data)
    if not raw_items:
        return {
            "kind": "integration_review_minutes",
            "minutes_id": str(data.get("minutes_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"candidate_count": 0},
            "attendees": [],
            "agenda": [],
            "decisions": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "risks": [],
            "next_actions": ["provide_review_minutes_inputs"],
        }
    calendar_slots = _calendar_slots(data)
    calendar_candidates = {str(slot.get("candidate_id")) for slot in calendar_slots}
    validation_refs = _validation_refs(data)
    blocked_candidates = _blocked_candidates(data)
    decisions = [
        summarize_review_minute_item(item, calendar_candidates=calendar_candidates, validation_refs=validation_refs, blocked_candidates=blocked_candidates)
        for item in raw_items
    ]
    blocked = [item.candidate_id for item in decisions if item.status == "blocked"]
    review = [item.candidate_id for item in decisions if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_minutes_blockers", "rebuild_integration_review_minutes"]
    elif review:
        status = "needs_review"
        reasons = [reason for item in decisions for reason in item.reasons]
        actions = ["complete_review_minutes"]
        if "validation evidence missing" in reasons:
            actions.append("attach_minutes_validation_evidence")
        if "review calendar slot missing" in reasons:
            actions.append("attach_review_calendar_slot")
        next_actions = actions + ["rebuild_integration_review_minutes"]
    else:
        status = "ready"
        next_actions = ["share_review_minutes_with_mainline"]
    return {
        "kind": "integration_review_minutes",
        "minutes_id": str(data.get("minutes_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"candidate_count": len(decisions)},
        "attendees": sorted({value for item in decisions for value in (item.reviewer, item.owner) if value}),
        "agenda": [{"topic": "Confirm secondary candidate ready for mainline review"}],
        "decisions": [item.as_dict() for item in decisions],
        "blocked_candidates": blocked,
        "review_candidates": review,
        "risks": _risks(decisions),
        "next_actions": next_actions,
    }


def _minute_items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("decisions"):
        return _as_sequence(data.get("decisions"))
    slots = _calendar_slots(data)
    if slots:
        return slots
    matrix = _as_mapping(data.get("reviewer_assignment_matrix"))
    return _as_sequence(matrix.get("assignments"))


def _calendar_slots(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    calendar = _as_mapping(data.get("review_calendar"))
    return [_as_mapping(slot) for slot in _as_sequence(calendar.get("slots"))]


def _validation_refs(data: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = data.get("validation_evidence") or {}
    refs: dict[str, list[str]] = {}
    if isinstance(raw, Mapping):
        for candidate_id, payload in raw.items():
            entry = _as_mapping(payload)
            refs[str(candidate_id)] = [str(ref) for ref in (_as_sequence(entry.get("evidence_refs")) or _as_sequence(entry.get("refs")) or _as_sequence(entry.get("result")))]
    else:
        for item in _as_sequence(raw):
            entry = _as_mapping(item)
            refs[str(entry.get("candidate_id") or "")] = [str(ref) for ref in _as_sequence(entry.get("evidence_refs"))]
    return refs


def _blocked_candidates(data: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    digest = _as_mapping(data.get("manifest_review_digest"))
    for signal in _as_sequence(digest.get("signals")):
        payload = _as_mapping(signal)
        if payload.get("status") == "blocked":
            refs.update(str(ref) for ref in _as_sequence(payload.get("refs")))
    return refs


def _risks(items: Sequence[ReviewMinuteItem]) -> list[str]:
    risks: list[str] = []
    if any(item.status == "blocked" for item in items):
        risks.append("blocked_review_items_present")
    if any(item.risk_level == "high" for item in items):
        risks.append("high_risk_review_items_present")
    return risks


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
