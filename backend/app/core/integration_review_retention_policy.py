from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewRetentionDecision:
    candidate_id: str
    status: str
    recommendation: str
    retention_days: int
    risk_level: str
    owner: str = ""
    archive_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status,
            "recommendation": self.recommendation,
            "retention_days": self.retention_days,
            "risk_level": self.risk_level,
            "owner": self.owner,
            "archive_refs": list(self.archive_refs),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "reasons": list(self.reasons),
        }


def review_retention_candidate(candidate: Mapping[str, Any] | Any, *, archive_entry: Mapping[str, Any] | None = None) -> ReviewRetentionDecision:
    payload = _as_mapping(candidate)
    archive = dict(archive_entry or {})
    candidate_id = str(payload.get("candidate_id") or archive.get("candidate_id") or "unknown")
    archive_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("archive_refs")) or _as_sequence(payload.get("archive_key")) or _as_sequence(archive.get("archive_key"))))
    evidence_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(archive.get("evidence_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(archive.get("handoff_refs"))))
    status_value = str(payload.get("status") or archive.get("status") or "ready")
    risk_level = str(payload.get("risk_level") or archive.get("risk_level") or ("high" if status_value == "blocked" else "low"))
    reasons: list[str] = []
    if not archive:
        reasons.append("archive manifest entry missing")
    if not archive_refs:
        reasons.append("archive refs missing")
    if not evidence_refs:
        reasons.append("retention evidence missing")
    if not handoff_refs:
        reasons.append("retention handoff refs missing")
    if status_value == "blocked":
        status = "blocked"
        recommendation = "hold_blocked"
        retention_days = int(payload.get("retention_days") or 1095)
    elif reasons:
        status = "needs_review"
        recommendation = "needs_evidence" if archive else "defer"
        retention_days = int(payload.get("retention_days") or 365)
    else:
        status = "ready"
        recommendation = "retain"
        retention_days = int(payload.get("retention_days") or 365)
    return ReviewRetentionDecision(
        candidate_id=candidate_id,
        status=status,
        recommendation=recommendation,
        retention_days=retention_days,
        risk_level=risk_level,
        owner=str(payload.get("owner") or archive.get("owner") or ""),
        archive_refs=archive_refs,
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        reasons=tuple(reasons),
    )


def build_integration_review_retention_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    entries = [_as_mapping(item) for item in _as_sequence(_as_mapping(payload.get("review_archive_manifest")).get("entries"))]
    explicit = [_as_mapping(item) for item in _as_sequence(payload.get("candidates"))]
    if not entries and not explicit:
        return {
            "kind": "integration_review_retention_policy",
            "ok": False,
            "status": "empty",
            "decisions": [],
            "retain_candidates": [],
            "needs_evidence_candidates": [],
            "hold_blocked_candidates": [],
            "next_actions": ["provide_review_retention_policy_inputs"],
        }
    explicit_by_id = {str(item.get("candidate_id") or ""): item for item in explicit}
    archive_by_id = {str(item.get("candidate_id") or ""): item for item in entries}
    candidate_ids = _unique([*archive_by_id.keys(), *explicit_by_id.keys()])
    decisions = [
        review_retention_candidate({**archive_by_id.get(candidate_id, {}), **explicit_by_id.get(candidate_id, {})}, archive_entry=archive_by_id.get(candidate_id))
        for candidate_id in candidate_ids
    ]
    blocked = [item.candidate_id for item in decisions if item.status == "blocked"]
    needs = [item.candidate_id for item in decisions if item.status == "needs_review"]
    retain = [item.candidate_id for item in decisions if item.recommendation == "retain"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_retention_blockers", "rebuild_integration_review_retention_policy"]
    elif needs:
        status = "needs_review"
        next_actions = [
            "complete_review_retention_policy",
            "attach_retention_archive_refs",
            "attach_retention_evidence",
            "attach_retention_handoff_refs",
            "rebuild_integration_review_retention_policy",
        ]
    else:
        status = "ready"
        next_actions = ["share_review_retention_policy_with_mainline"]
    return {
        "kind": "integration_review_retention_policy",
        "ok": status == "ready",
        "status": status,
        "summary": {"decision_count": len(decisions), "retain_count": len(retain), "needs_evidence_count": len(needs), "blocked_count": len(blocked)},
        "decisions": [item.as_dict() for item in decisions],
        "retain_candidates": retain,
        "needs_evidence_candidates": needs,
        "hold_blocked_candidates": blocked,
        "next_actions": next_actions,
    }


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
