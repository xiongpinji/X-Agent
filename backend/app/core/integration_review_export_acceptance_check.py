from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewExportAcceptanceDecision:
    candidate_id: str
    check_key: str
    status: str
    verdict: str
    export_formats: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "check_key": self.check_key,
            "status": self.status,
            "verdict": self.verdict,
            "export_formats": list(self.export_formats),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_export_acceptance_decision(
    decision: Mapping[str, Any] | Any,
    *,
    export_candidates: set[str] | None = None,
    validation_index: Mapping[str, Mapping[str, Any]] | None = None,
    handoff_index: Mapping[str, Sequence[str]] | None = None,
) -> ReviewExportAcceptanceDecision:
    payload = _as_mapping(decision)
    candidate_id = str(payload.get("candidate_id") or "")
    validation = dict((validation_index or {}).get(candidate_id, {}))
    status = str(validation.get("status") or payload.get("status") or "needs_review")
    export_formats = tuple(str(item) for item in _as_sequence(payload.get("export_formats")))
    evidence_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(validation.get("refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or (handoff_index or {}).get(candidate_id, ())))
    blockers = tuple(str(item) for item in (_as_sequence(validation.get("blockers")) or _as_sequence(payload.get("blockers"))))
    reasons: list[str] = []
    if export_candidates is None or candidate_id not in export_candidates:
        reasons.append("export row missing")
    if not export_formats:
        reasons.append("export formats missing")
    if not handoff_refs:
        reasons.append("handoff refs missing")
    if status == "blocked":
        reasons.append("acceptance source blocked")
        verdict = "blocked"
    elif not reasons and status == "ready":
        verdict = "accept"
    else:
        verdict = str(payload.get("verdict") or "needs_review")
        if verdict == "accept" and reasons:
            verdict = "needs_review"
    if reasons and status != "blocked":
        status = "needs_review"
    return ReviewExportAcceptanceDecision(
        candidate_id=candidate_id,
        check_key=str(payload.get("check_key") or payload.get("status_key") or candidate_id),
        status=status,
        verdict=verdict,
        export_formats=export_formats,
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        blockers=blockers,
        reasons=tuple(reasons),
    )


def build_integration_review_export_acceptance_check(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _decisions(data)
    if not raw:
        return {
            "kind": "integration_review_export_acceptance_check",
            "check_id": str(data.get("check_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"decision_count": 0, "accepted_count": 0},
            "decisions": [],
            "accepted_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_export_acceptance_inputs"],
        }
    export_candidates = _export_candidates(data)
    validation_index = _validation_index(data.get("validation_evidence"))
    handoff_index = _handoff_index(data.get("handoff_refs"))
    decisions = [
        summarize_review_export_acceptance_decision(
            item,
            export_candidates=export_candidates,
            validation_index=validation_index,
            handoff_index=handoff_index,
        )
        for item in raw
    ]
    accepted = [item.candidate_id for item in decisions if item.verdict == "accept"]
    blocked = [item.candidate_id for item in decisions if item.verdict == "blocked" or item.status == "blocked"]
    review = [item.candidate_id for item in decisions if item.status == "needs_review" or item.verdict == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_export_acceptance_blockers",
            "attach_export_acceptance_evidence",
            "rebuild_integration_review_export_acceptance_check",
        ]
    elif review:
        status = "needs_review"
        reasons = [reason for item in decisions for reason in item.reasons]
        actions = ["complete_review_export_acceptance_check"]
        if "export formats missing" in reasons:
            actions.append("attach_export_formats")
        if "handoff refs missing" in reasons:
            actions.append("attach_export_acceptance_handoff_refs")
        next_actions = actions + ["rebuild_integration_review_export_acceptance_check"]
    else:
        status = "ready"
        next_actions = ["share_review_export_acceptance_check_with_mainline"]
    return {
        "kind": "integration_review_export_acceptance_check",
        "check_id": str(data.get("check_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"decision_count": len(decisions), "accepted_count": len(accepted)},
        "decisions": [item.as_dict() for item in decisions],
        "accepted_candidates": accepted,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _decisions(data: Mapping[str, Any]) -> list[Any]:
    if data.get("decisions"):
        return _as_sequence(data.get("decisions"))
    export = _as_mapping(data.get("action_status_export"))
    return _as_sequence(export.get("rows"))


def _export_candidates(data: Mapping[str, Any]) -> set[str]:
    export = _as_mapping(data.get("action_status_export"))
    return {str(_as_mapping(row).get("candidate_id") or "") for row in _as_sequence(export.get("rows"))}


def _validation_index(raw: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _as_sequence(raw):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = payload
    return result


def _handoff_index(raw: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if isinstance(raw, Mapping):
        for candidate_id, value in raw.items():
            payload = _as_mapping(value)
            result[str(candidate_id)] = [str(ref) for ref in (_as_sequence(payload.get("refs")) or _as_sequence(payload.get("path")))]
    else:
        for item in _as_sequence(raw):
            payload = _as_mapping(item)
            result[str(payload.get("candidate_id") or "")] = [str(ref) for ref in (_as_sequence(payload.get("refs")) or _as_sequence(payload.get("path")))]
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
