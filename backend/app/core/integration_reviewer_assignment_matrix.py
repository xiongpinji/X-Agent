from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewerAssignment:
    candidate_id: str
    owner: str
    primary_reviewer: str
    review_status: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"
    secondary_reviewers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "primary_reviewer": self.primary_reviewer,
            "review_status": self.review_status,
            "evidence_refs": list(self.evidence_refs),
            "risk_level": self.risk_level,
            "secondary_reviewers": list(self.secondary_reviewers),
            "reasons": list(self.reasons),
        }


def summarize_reviewer_assignment(
    candidate: Mapping[str, Any] | Any,
    *,
    reviewer_hints: Mapping[str, str] | None = None,
    owner_index: Mapping[str, str] | None = None,
    blocked_candidates: set[str] | None = None,
) -> ReviewerAssignment:
    payload = _as_mapping(candidate)
    candidate_id = str(payload.get("candidate_id") or "")
    owner = str(payload.get("owner") or (owner_index or {}).get(candidate_id, ""))
    primary = str(payload.get("primary_reviewer") or (reviewer_hints or {}).get(candidate_id, ""))
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    status = str(payload.get("review_status") or payload.get("status") or "needs_review")
    risk_level = str(payload.get("risk_level") or "low")
    reasons: list[str] = []
    if not owner:
        reasons.append("owner missing")
    if not primary:
        reasons.append("primary reviewer missing")
    if not evidence_refs:
        reasons.append("review evidence missing")
    secondary = [owner] if risk_level == "high" and owner else []
    if candidate_id in (blocked_candidates or set()):
        status = "blocked"
        risk_level = "high"
        if owner:
            secondary = [owner]
        reasons.append("review digest blocks candidate")
    elif reasons:
        status = "needs_review"
    return ReviewerAssignment(
        candidate_id=candidate_id,
        owner=owner,
        primary_reviewer=primary,
        review_status=status,
        evidence_refs=evidence_refs,
        risk_level=risk_level,
        secondary_reviewers=tuple(_unique(secondary)),
        reasons=tuple(reasons),
    )


def build_integration_reviewer_assignment_matrix(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _candidates(data)
    if not raw:
        return {
            "kind": "integration_reviewer_assignment_matrix",
            "matrix_id": str(data.get("matrix_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"assignment_count": 0},
            "assignments": [],
            "by_reviewer": {},
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_reviewer_assignment_candidates"],
        }
    reviewer_hints = {str(key): str(value) for key, value in _as_mapping(data.get("reviewer_hints")).items()}
    owner_index = _owner_index(data.get("owner_digest"))
    blocked_candidates = _blocked_candidates(data.get("manifest_review_digest"))
    assignments = [
        summarize_reviewer_assignment(
            item,
            reviewer_hints=reviewer_hints,
            owner_index=owner_index,
            blocked_candidates=blocked_candidates,
        )
        for item in raw
    ]
    blocked = [item.candidate_id for item in assignments if item.review_status == "blocked"]
    review = [item.candidate_id for item in assignments if item.review_status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_blocked_reviewer_assignments", "rebuild_integration_reviewer_assignment_matrix"]
    elif review:
        status = "needs_review"
        reasons = [reason for item in assignments for reason in item.reasons]
        actions = ["complete_reviewer_assignment_matrix"]
        if "owner missing" in reasons:
            actions.append("assign_candidate_owner")
        if "primary reviewer missing" in reasons:
            actions.append("assign_primary_reviewer")
        if "review evidence missing" in reasons:
            actions.append("attach_reviewer_assignment_evidence")
        next_actions = actions + ["rebuild_integration_reviewer_assignment_matrix"]
    else:
        status = "ready"
        next_actions = ["share_reviewer_assignment_matrix_with_mainline"]
    return {
        "kind": "integration_reviewer_assignment_matrix",
        "matrix_id": str(data.get("matrix_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"assignment_count": len(assignments), "blocked_count": len(blocked), "needs_review_count": len(review)},
        "assignments": [item.as_dict() for item in assignments],
        "by_reviewer": _by_reviewer(assignments),
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _candidates(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    manifest = _as_mapping(data.get("review_packet_manifest"))
    return _as_sequence(manifest.get("entries"))


def _owner_index(raw: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    digest = _as_mapping(raw)
    for item in _as_sequence(digest.get("owners")):
        payload = _as_mapping(item)
        owner = str(payload.get("owner") or "")
        for candidate_id in _as_sequence(payload.get("candidate_ids")):
            result[str(candidate_id)] = owner
    return result


def _blocked_candidates(raw: Any) -> set[str]:
    result: set[str] = set()
    digest = _as_mapping(raw)
    for signal in _as_sequence(digest.get("signals")):
        payload = _as_mapping(signal)
        if payload.get("status") == "blocked":
            result.update(str(ref) for ref in _as_sequence(payload.get("refs")))
    return result


def _by_reviewer(assignments: Sequence[ReviewerAssignment]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.primary_reviewer:
            result.setdefault(assignment.primary_reviewer, []).append(assignment.candidate_id)
        for reviewer in assignment.secondary_reviewers:
            result.setdefault(reviewer, []).append(assignment.candidate_id)
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
