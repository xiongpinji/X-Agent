from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionDecisionRow:
    candidate_id: str
    decision_key: str
    decision_status: str
    recommended_outcome: str
    stage_label: str
    owner: str = ""
    reviewer: str = ""
    candidate_paths: tuple[str, ...] = field(default_factory=tuple)
    manifest_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_gaps: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision_key": self.decision_key,
            "decision_status": self.decision_status,
            "recommended_outcome": self.recommended_outcome,
            "stage_label": self.stage_label,
            "owner": self.owner,
            "reviewer": self.reviewer,
            "candidate_paths": list(self.candidate_paths),
            "manifest_refs": list(self.manifest_refs),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "evidence_gaps": list(self.evidence_gaps),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_decision_row(
    item: Mapping[str, Any] | Any,
    *,
    owner_context: Mapping[str, Any] | None = None,
    reviewer_context: Mapping[str, Any] | None = None,
    manifest_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionDecisionRow:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    manifest = dict((manifest_index or {}).get(candidate_id, {}))
    status = str(payload.get("status") or payload.get("decision_status") or "needs_review")
    outcome = str(payload.get("recommended_outcome") or _outcome_for_status(status, payload.get("recommended_decision")))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    gaps = [str(gap) for gap in _as_sequence(payload.get("evidence_gaps"))]
    if status == "blocked" or blockers:
        status = "blocked"
        outcome = "defer"
    elif status == "needs_review" or str(payload.get("receipt_state") or "") in {"incomplete", "needs_signoff"}:
        status = "needs_review"
        outcome = "review"
        gaps.append("resolution receipt still needs review")
    elif not outcome:
        outcome = "adopt"
    return ReviewManifestAdoptionDecisionRow(
        candidate_id=candidate_id,
        decision_key=str(payload.get("decision_key") or payload.get("receipt_key") or candidate_id),
        decision_status=status,
        recommended_outcome=outcome,
        stage_label=str(payload.get("stage_label") or _stage_label(outcome)),
        owner=str(payload.get("owner") or _context_value(owner_context, candidate_id)),
        reviewer=str(payload.get("reviewer") or _context_value(reviewer_context, candidate_id)),
        candidate_paths=tuple(str(path) for path in (_as_sequence(payload.get("candidate_paths")) or _as_sequence(manifest.get("include_paths")))),
        manifest_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("manifest_refs")) or _as_sequence(manifest.get("manifest_key")))),
        validation_refs=tuple(str(ref) for ref in _as_sequence(payload.get("validation_refs"))),
        handoff_refs=tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs"))),
        evidence_gaps=tuple(_unique(gaps)),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_decision_sheet(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_decision_sheet",
            "ok": False,
            "status": "empty",
            "rows": [],
            "adopt_candidates": [],
            "reject_candidates": [],
            "defer_candidates": [],
            "review_candidates": [],
            "blocked_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_decision_inputs"],
        }
    manifest_index = {
        str(_as_mapping(entry).get("candidate_id") or ""): _as_mapping(entry)
        for entry in _as_sequence(_as_mapping(data.get("adoption_manifest_preview")).get("entries"))
    }
    rows = [
        summarize_review_manifest_adoption_decision_row(
            item,
            owner_context=_as_mapping(data.get("owner_context")),
            reviewer_context=_as_mapping(data.get("reviewer_context")),
            manifest_index=manifest_index,
        )
        for item in raw
    ]
    blocked = [row.candidate_id for row in rows if row.decision_status == "blocked"]
    review = [row.candidate_id for row in rows if row.decision_status == "needs_review"]
    adopt = [row.candidate_id for row in rows if row.recommended_outcome == "adopt"]
    reject = [row.candidate_id for row in rows if row.recommended_outcome == "reject"]
    defer = [row.candidate_id for row in rows if row.recommended_outcome == "defer"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_decision_blockers", "rebuild_integration_review_manifest_adoption_decision_sheet"]
    elif review:
        status = "needs_review"
        next_actions = ["complete_manifest_resolution_receipt", "rebuild_integration_review_manifest_adoption_decision_sheet"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_decision_sheet_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_decision_sheet",
        "ok": status == "ready",
        "status": status,
        "rows": [row.as_dict() for row in rows],
        "adopt_candidates": adopt,
        "reject_candidates": reject,
        "defer_candidates": defer,
        "review_candidates": review,
        "blocked_candidates": blocked,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("decisions"):
        return _as_sequence(data.get("decisions"))
    return _as_sequence(_as_mapping(data.get("manifest_resolution_receipt")).get("items"))


def _outcome_for_status(status: str, decision: Any) -> str:
    if str(decision or "") == "defer_candidate_until_blockers_resolved":
        return "defer"
    if status == "blocked":
        return "defer"
    if status == "ready":
        return "adopt"
    return "review"


def _stage_label(outcome: str) -> str:
    return {
        "adopt": "secondary_integration_candidate",
        "defer": "secondary_deferred",
        "reject": "secondary_rejected",
        "review": "secondary_needs_review",
    }.get(outcome, "secondary_needs_review")


def _context_value(context: Mapping[str, Any] | None, candidate_id: str) -> str:
    value = (context or {}).get(candidate_id, "")
    if isinstance(value, Mapping):
        return str(value.get("owner") or value.get("reviewer") or value.get("recipient") or "")
    return str(value or "")


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
