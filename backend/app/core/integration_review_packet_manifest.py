from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewPacketManifestEntry:
    candidate_id: str
    stage_label: str
    review_status: str
    owner: str = ""
    files: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    risk_refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "stage_label": self.stage_label,
            "review_status": self.review_status,
            "owner": self.owner,
            "files": list(self.files),
            "tests": list(self.tests),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "risk_refs": list(self.risk_refs),
            "reasons": list(self.reasons),
        }


def summarize_review_packet_manifest_entry(entry: Mapping[str, Any] | Any) -> ReviewPacketManifestEntry:
    payload = _as_mapping(entry)
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs") or payload.get("validation_results")))
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    risk_refs = tuple(str(ref) for ref in _as_sequence(payload.get("risk_refs")))
    status = str(payload.get("review_status") or payload.get("status") or "ready")
    reasons: list[str] = []
    if status == "blocked":
        reasons.append("risk register blocked candidate")
    if status != "blocked" and not evidence_refs:
        status = "needs_review"
        reasons.append("evidence references missing")
    if status != "blocked" and not handoff_refs:
        status = "needs_review"
        reasons.append("handoff references missing")
    if not reasons:
        reasons.append("manifest entry ready")
    return ReviewPacketManifestEntry(
        candidate_id=str(payload.get("candidate_id") or ""),
        stage_label=str(payload.get("stage_label") or payload.get("integration_status") or "secondary_integration_candidate"),
        review_status=status,
        owner=str(payload.get("owner") or ""),
        files=tuple(str(path) for path in _as_sequence(payload.get("files"))),
        tests=tuple(str(path) for path in _as_sequence(payload.get("tests"))),
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        risk_refs=risk_refs,
        reasons=tuple(reasons),
    )


def build_integration_review_packet_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    entries = _entries(data)
    if not entries:
        return {
            "kind": "integration_review_packet_manifest",
            "manifest_id": str(data.get("manifest_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"entry_count": 0, "ready_count": 0},
            "entries": [],
            "stage_buckets": {},
            "next_actions": ["provide_review_packet_manifest_candidates"],
        }
    risk = _risk_by_candidate(data)
    trace = _trace_by_candidate(data)
    summarized = []
    for entry in entries:
        merged = dict(_as_mapping(entry))
        candidate_id = str(merged.get("candidate_id") or "")
        if candidate_id in trace:
            merged["evidence_refs"] = _unique(_as_sequence(trace[candidate_id].get("evidence_refs")) + _as_sequence(merged.get("evidence_refs") or merged.get("validation_results")))
            merged["handoff_refs"] = _unique(_as_sequence(trace[candidate_id].get("handoff_refs")) + _as_sequence(merged.get("handoff_refs")))
        if candidate_id in risk:
            risk_entry = risk[candidate_id]
            merged["risk_refs"] = _as_sequence(risk_entry.get("reasons"))
            if risk_entry.get("review_status") == "blocked":
                merged["review_status"] = "blocked"
        summarized.append(summarize_review_packet_manifest_entry(merged))
    blocked = [entry for entry in summarized if entry.review_status == "blocked"]
    review = [entry for entry in summarized if entry.review_status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_blocked_manifest_entries", "rebuild_integration_review_packet_manifest"]
    elif review:
        status = "needs_review"
        reasons = [reason for entry in review for reason in entry.reasons]
        actions = []
        if "evidence references missing" in reasons:
            actions.append("complete_review_packet_manifest_evidence")
        if "handoff references missing" in reasons:
            actions.append("attach_manifest_handoff_refs")
        next_actions = actions + ["rebuild_integration_review_packet_manifest"]
    else:
        status = "ready"
        next_actions = ["share_review_packet_manifest_with_mainline"]
    return {
        "kind": "integration_review_packet_manifest",
        "manifest_id": str(data.get("manifest_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "entry_count": len(summarized),
            "ready_count": sum(1 for entry in summarized if entry.review_status == "ready"),
            "needs_review_count": len(review),
            "blocked_count": len(blocked),
        },
        "entries": [entry.as_dict() for entry in summarized],
        "stage_buckets": _stage_buckets(summarized),
        "next_actions": next_actions,
    }


def _entries(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    secondary = _as_mapping(data.get("secondary_index"))
    return _as_sequence(secondary.get("entries"))


def _risk_by_candidate(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    register = _as_mapping(data.get("conflict_risk_register"))
    return {str(_as_mapping(entry).get("candidate_id") or ""): _as_mapping(entry) for entry in _as_sequence(register.get("entries"))}


def _trace_by_candidate(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index = _as_mapping(data.get("traceability_index"))
    return {str(_as_mapping(entry).get("candidate_id") or ""): _as_mapping(entry) for entry in _as_sequence(index.get("records"))}


def _stage_buckets(entries: Sequence[ReviewPacketManifestEntry]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for entry in entries:
        buckets.setdefault(entry.stage_label, []).append(entry.candidate_id)
    return buckets


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


def _unique(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result
