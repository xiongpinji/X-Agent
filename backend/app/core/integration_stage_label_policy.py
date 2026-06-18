from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


CANONICAL = {
    "secondary_integration_candidate",
    "mainline_review_candidate",
}
ALIASES = {
    "ready for review": "secondary_review_ready",
    "ready_for_review": "secondary_review_ready",
    "review": "secondary_needs_review",
}


@dataclass(frozen=True)
class StageLabelDecision:
    candidate_id: str
    input_label: str
    normalized_label: str
    status: str
    owner: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "input_label": self.input_label,
            "normalized_label": self.normalized_label,
            "status": self.status,
            "owner": self.owner,
            "reasons": list(self.reasons),
            "next_actions": list(self.next_actions),
        }


def normalize_stage_label(candidate: Mapping[str, Any] | Any) -> StageLabelDecision:
    payload = _as_mapping(candidate)
    raw = str(payload.get("stage_label") or payload.get("stage") or "").strip()
    input_label = raw.replace(" ", "_")
    lower = raw.lower()
    normalized = ALIASES.get(lower) or ALIASES.get(input_label) or input_label
    reasons: list[str] = []
    actions: list[str] = []
    if normalized in CANONICAL:
        status = "ready"
    elif normalized == "blocked":
        status = "blocked"
        reasons.append("stage label blocks review")
        actions.append("resolve_blocking_stage_label")
    elif raw == "production" or not normalized:
        status = "blocked"
        reasons.append("stage label unknown")
        actions.append("replace_unknown_stage_label")
    else:
        status = "needs_review"
        actions.append("confirm_stage_label_alias")
    return StageLabelDecision(
        candidate_id=str(payload.get("candidate_id") or "unknown"),
        input_label=input_label,
        normalized_label=normalized,
        status=status,
        owner=str(payload.get("owner") or ""),
        reasons=tuple(reasons),
        next_actions=tuple(actions),
    )


def build_integration_stage_label_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _items(payload)
    if not candidates:
        return {
            "kind": "integration_stage_label_policy",
            "ok": False,
            "status": "empty",
            "decisions": [],
            "stage_buckets": {},
            "issues": [],
            "next_actions": ["provide_stage_label_candidates"],
        }
    decisions = [normalize_stage_label(item) for item in candidates]
    blocked = [item for item in decisions if item.status == "blocked"]
    review = [item for item in decisions if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_blocked_stage_labels",
            "replace_unknown_stage_label",
            "confirm_stage_label_alias",
            "resolve_blocking_stage_label",
            "rebuild_integration_stage_label_policy",
        ]
    elif review:
        status = "needs_review"
        next_actions = ["review_stage_label_aliases", "confirm_stage_label_alias", "rebuild_integration_stage_label_policy"]
    else:
        status = "ready"
        next_actions = ["share_stage_label_policy_with_mainline"]
    return {
        "kind": "integration_stage_label_policy",
        "ok": status == "ready",
        "status": status,
        "summary": {"candidate_count": len(decisions), "ready_count": len([item for item in decisions if item.status == "ready"]), "blocked_count": len(blocked), "review_count": len(review)},
        "decisions": [item.as_dict() for item in decisions],
        "stage_buckets": _stage_buckets(decisions),
        "issues": [{"code": "stage_label_blocked", "severity": "high"}] if blocked else [],
        "next_actions": next_actions,
    }


def _items(payload: Mapping[str, Any]) -> list[Any]:
    if payload.get("candidates"):
        return _as_sequence(payload.get("candidates"))
    return _as_sequence(_as_mapping(payload.get("review_packet_manifest")).get("entries"))


def _stage_buckets(decisions: Sequence[StageLabelDecision]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.status == "ready":
            buckets.setdefault(decision.normalized_label, []).append(decision.candidate_id)
    return buckets


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
