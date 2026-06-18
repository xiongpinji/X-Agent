from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SunsetCandidateReview:
    candidate_id: str
    owner: str
    adoption_state: str
    monitor_state: str
    validation_state: str
    recommendation: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "adoption_state": self.adoption_state,
            "monitor_state": self.monitor_state,
            "validation_state": self.validation_state,
            "recommendation": self.recommendation,
            "evidence_refs": list(self.evidence_refs),
            "reasons": list(self.reasons),
        }


def review_sunset_candidate(
    candidate: Mapping[str, Any] | Any,
    *,
    monitor_state: str | None = None,
    validation_state: str | None = None,
    owner_index: Mapping[str, str] | None = None,
    owner_evidence: Mapping[str, Sequence[str]] | None = None,
) -> SunsetCandidateReview:
    payload = _as_mapping(candidate)
    candidate_id = str(payload.get("candidate_id") or payload.get("signal_id") or "")
    monitor = str(payload.get("monitor_state") or monitor_state or payload.get("status") or "needs_review")
    validation = str(payload.get("validation_state") or validation_state or "needs_review")
    owner = str(payload.get("owner") or (owner_index or {}).get(candidate_id, ""))
    evidence_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or (owner_evidence or {}).get(candidate_id, ())))
    requested = str(payload.get("recommendation") or "keep")
    reasons: list[str] = []
    if monitor != "ready" or validation != "ready" or not evidence_refs:
        recommendation = "defer"
        reasons.append("candidate deferred pending stable local evidence")
    elif requested == "merge":
        recommendation = "merge_deeper"
        reasons.append("candidate stable for deeper merge recommendation")
    elif requested == "sunset":
        recommendation = "sunset"
        reasons.append("candidate stable for sunset recommendation")
    else:
        recommendation = "keep"
        reasons.append("candidate stable after adoption")
    return SunsetCandidateReview(
        candidate_id=candidate_id,
        owner=owner,
        adoption_state=str(payload.get("adoption_state") or "ready"),
        monitor_state=monitor,
        validation_state=validation,
        recommendation=recommendation,
        evidence_refs=evidence_refs,
        reasons=tuple(reasons),
    )


def build_integration_sunset_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _candidates(data)
    if not raw:
        return {
            "kind": "integration_sunset_review",
            "review_id": str(data.get("review_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"candidate_count": 0},
            "candidates": [],
            "keep_candidates": [],
            "merge_deeper_candidates": [],
            "sunset_candidates": [],
            "defer_candidates": [],
            "issues": [],
            "next_actions": ["provide_sunset_review_candidates"],
        }
    monitor = _as_mapping(data.get("post_adoption_monitor"))
    monitor_state = str(monitor.get("status") or "needs_review")
    validation_state = _validation_state(data)
    owner_index, owner_evidence = _owner_indexes(data.get("owner_digest"))
    candidates = [
        review_sunset_candidate(item, monitor_state=monitor_state, validation_state=validation_state, owner_index=owner_index, owner_evidence=owner_evidence)
        for item in raw
    ]
    keep = [item.candidate_id for item in candidates if item.recommendation == "keep"]
    merge = [item.candidate_id for item in candidates if item.recommendation == "merge_deeper"]
    sunset = [item.candidate_id for item in candidates if item.recommendation == "sunset"]
    defer = [item.candidate_id for item in candidates if item.recommendation == "defer"]
    if defer:
        status = "needs_review"
        issues = [{"code": "sunset_review_candidate_deferred", "severity": "medium", "candidate_id": item} for item in defer]
        next_actions = ["resolve_deferred_sunset_candidates", "rebuild_integration_sunset_review"]
    else:
        status = "ready"
        issues = []
        next_actions = ["review_sunset_recommendations_with_mainline"]
    return {
        "kind": "integration_sunset_review",
        "review_id": str(data.get("review_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": len(candidates),
            "keep_count": len(keep),
            "merge_deeper_count": len(merge),
            "sunset_count": len(sunset),
            "defer_count": len(defer),
        },
        "candidates": [item.as_dict() for item in candidates],
        "keep_candidates": keep,
        "merge_deeper_candidates": merge,
        "sunset_candidates": sunset,
        "defer_candidates": defer,
        "issues": issues,
        "next_actions": next_actions,
    }


def _candidates(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    monitor = _as_mapping(data.get("post_adoption_monitor"))
    return _as_sequence(monitor.get("watch_signals"))


def _validation_state(data: Mapping[str, Any]) -> str:
    raw = _as_sequence(data.get("validation_results")) or _as_sequence(_as_mapping(data.get("validation")).get("results"))
    if not raw:
        return "needs_review"
    return "blocked" if any("failed" in str(item) for item in raw) else "ready"


def _owner_indexes(raw: Any) -> tuple[dict[str, str], dict[str, list[str]]]:
    owners: dict[str, str] = {}
    evidence: dict[str, list[str]] = {}
    digest = _as_mapping(raw)
    for item in _as_sequence(digest.get("owners")):
        payload = _as_mapping(item)
        owner = str(payload.get("owner") or "")
        refs = [str(ref) for ref in _as_sequence(payload.get("evidence_refs"))]
        for candidate_id in _as_sequence(payload.get("candidate_ids")):
            text = str(candidate_id)
            owners[text] = owner
            evidence[text] = refs
    return owners, evidence


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
