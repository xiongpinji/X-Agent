from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewAcceptanceRollupItem:
    candidate_id: str
    rollup_key: str
    verdict: str
    status: str
    acceptance_refs: tuple[str, ...] = field(default_factory=tuple)
    export_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rollup_key": self.rollup_key,
            "verdict": self.verdict,
            "status": self.status,
            "acceptance_refs": list(self.acceptance_refs),
            "export_refs": list(self.export_refs),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_acceptance_rollup_item(
    item: Mapping[str, Any] | Any,
    *,
    export_refs_by_candidate: Mapping[str, Sequence[str]] | None = None,
) -> ReviewAcceptanceRollupItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    acceptance_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("acceptance_refs")) or _as_sequence(payload.get("check_key"))))
    export_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("export_refs")) or (export_refs_by_candidate or {}).get(candidate_id, ())))
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    status = str(payload.get("status") or "needs_review")
    verdict = str(payload.get("verdict") or "needs_review")
    reasons: list[str] = []
    if not export_refs:
        reasons.append("export refs missing")
    if not evidence_refs:
        reasons.append("rollup evidence missing")
    if status == "blocked" or verdict == "blocked":
        status = "blocked"
        verdict = "blocked"
        reasons.append("rollup source blocked")
    elif reasons:
        status = "needs_review"
        if verdict in {"accept", "accepted"}:
            verdict = "needs_review"
    return ReviewAcceptanceRollupItem(
        candidate_id=candidate_id,
        rollup_key=str(payload.get("rollup_key") or payload.get("check_key") or candidate_id),
        verdict=verdict,
        status=status,
        acceptance_refs=acceptance_refs,
        export_refs=export_refs,
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        blockers=tuple(str(item) for item in _as_sequence(payload.get("blockers"))),
        reasons=tuple(reasons),
    )


def build_integration_review_acceptance_rollup(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _rollup_items(data)
    if not raw:
        return {
            "kind": "integration_review_acceptance_rollup",
            "rollup_id": str(data.get("rollup_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"item_count": 0, "accepted_count": 0},
            "items": [],
            "accepted_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "readiness": {"score": 0.0},
            "next_actions": ["provide_review_acceptance_rollup_inputs"],
        }
    export_refs = _export_refs(data)
    items = [summarize_review_acceptance_rollup_item(item, export_refs_by_candidate=export_refs) for item in raw]
    accepted = [item.candidate_id for item in items if item.verdict in {"accept", "accepted"} and item.status == "ready"]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_acceptance_rollup_blockers",
            "attach_acceptance_rollup_evidence",
            "rebuild_integration_review_acceptance_rollup",
        ]
    elif review:
        status = "needs_review"
        reasons = [reason for item in items for reason in item.reasons]
        actions = ["complete_review_acceptance_rollup"]
        if "export refs missing" in reasons:
            actions.append("attach_acceptance_rollup_export_refs")
        if "rollup evidence missing" in reasons:
            actions.append("attach_acceptance_rollup_evidence")
        next_actions = actions + ["rebuild_integration_review_acceptance_rollup"]
    else:
        status = "ready"
        next_actions = ["share_review_acceptance_rollup_with_mainline"]
    return {
        "kind": "integration_review_acceptance_rollup",
        "rollup_id": str(data.get("rollup_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "item_count": len(items),
            "accepted_count": len(accepted),
            "blocked_count": len(blocked),
            "needs_review_count": len(review),
        },
        "items": [item.as_dict() for item in items],
        "accepted_candidates": accepted,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "readiness": {"score": round(len(accepted) / len(items), 3) if items else 0.0},
        "next_actions": _unique(next_actions),
    }


def _rollup_items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("rollups"):
        return _as_sequence(data.get("rollups"))
    check = _as_mapping(data.get("export_acceptance_check"))
    return _as_sequence(check.get("decisions"))


def _export_refs(data: Mapping[str, Any]) -> dict[str, list[str]]:
    export = _as_mapping(data.get("action_status_export"))
    result: dict[str, list[str]] = {}
    for row in _as_sequence(export.get("rows")):
        payload = _as_mapping(row)
        candidate_id = str(payload.get("candidate_id") or "")
        refs = [str(ref) for ref in (_as_sequence(payload.get("status_key")) or _as_sequence(payload.get("export_refs")))]
        result[candidate_id] = refs
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
