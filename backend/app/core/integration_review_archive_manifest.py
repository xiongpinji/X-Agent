from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewArchiveEntry:
    candidate_id: str
    archive_key: str
    status: str
    artifact_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    risk_level: str = "low"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "archive_key": self.archive_key,
            "status": self.status,
            "artifact_refs": list(self.artifact_refs),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "risk_level": self.risk_level,
            "reasons": list(self.reasons),
        }


def summarize_review_archive_entry(
    entry: Mapping[str, Any] | Any,
    *,
    minutes_index: Mapping[str, Mapping[str, Any]] | None = None,
    calendar_evidence: Mapping[str, Sequence[str]] | None = None,
    validation_evidence: Mapping[str, Sequence[str]] | None = None,
    handoff_index: Mapping[str, Sequence[str]] | None = None,
) -> ReviewArchiveEntry:
    payload = _as_mapping(entry)
    candidate_id = str(payload.get("candidate_id") or "")
    minutes = dict((minutes_index or {}).get(candidate_id, {}))
    artifact_refs = tuple(str(ref) for ref in _as_sequence(payload.get("artifact_refs")))
    evidence_refs = tuple(
        _unique(
            [str(ref) for ref in _as_sequence(payload.get("evidence_refs"))]
            + [str(ref) for ref in _as_sequence(minutes.get("evidence_refs"))]
            + [str(ref) for ref in (calendar_evidence or {}).get(candidate_id, ())]
            + [str(ref) for ref in (validation_evidence or {}).get(candidate_id, ())]
        )
    )
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or (handoff_index or {}).get(candidate_id, ())))
    status = str(minutes.get("status") or payload.get("status") or "needs_review")
    risk_level = str(minutes.get("risk_level") or payload.get("risk_level") or "low")
    reasons: list[str] = []
    if not minutes:
        reasons.append("review minutes missing")
    if not artifact_refs:
        reasons.append("archive artifact refs missing")
    if not evidence_refs:
        reasons.append("archive evidence refs missing")
    if not handoff_refs:
        reasons.append("archive handoff refs missing")
    if status == "blocked":
        reasons.append("archive source blocked")
    elif reasons:
        status = "needs_review"
    return ReviewArchiveEntry(
        candidate_id=candidate_id,
        archive_key=str(payload.get("archive_key") or f"review/{candidate_id.replace('_', '-')}"),
        status=status,
        artifact_refs=artifact_refs,
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        owner=str(minutes.get("owner") or payload.get("owner") or ""),
        reviewer=str(minutes.get("reviewer") or payload.get("reviewer") or ""),
        risk_level=risk_level,
        reasons=tuple(reasons),
    )


def build_integration_review_archive_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _archive_items(data)
    if not raw:
        return {
            "kind": "integration_review_archive_manifest",
            "manifest_id": str(data.get("manifest_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"entry_count": 0},
            "entries": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "missing_refs": {},
            "next_actions": ["provide_review_archive_manifest_inputs"],
        }
    minutes_index = _minutes_index(data)
    calendar_evidence = _calendar_evidence(data)
    validation_evidence = _validation_evidence(data)
    handoff_index = _handoff_index(data.get("handoff_refs"))
    entries = [
        summarize_review_archive_entry(
            item,
            minutes_index=minutes_index,
            calendar_evidence=calendar_evidence,
            validation_evidence=validation_evidence,
            handoff_index=handoff_index,
        )
        for item in raw
    ]
    ready = [item.candidate_id for item in entries if item.status == "ready"]
    blocked = [item.candidate_id for item in entries if item.status == "blocked"]
    review = [item.candidate_id for item in entries if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_archive_blockers", "rebuild_integration_review_archive_manifest"]
    elif review:
        status = "needs_review"
        missing_refs = _missing_refs(entries)
        next_actions = ["complete_review_archive_manifest"]
        if any("artifact_refs" in refs for refs in missing_refs.values()):
            next_actions.append("attach_archive_artifact_refs")
        if any("evidence_refs" in refs for refs in missing_refs.values()):
            next_actions.append("attach_archive_evidence_refs")
        if any("handoff_refs" in refs for refs in missing_refs.values()):
            next_actions.append("attach_archive_handoff_refs")
        next_actions.append("rebuild_integration_review_archive_manifest")
    else:
        status = "ready"
        missing_refs = {}
        next_actions = ["share_review_archive_manifest_with_mainline"]
    return {
        "kind": "integration_review_archive_manifest",
        "manifest_id": str(data.get("manifest_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"entry_count": len(entries)},
        "entries": [item.as_dict() for item in entries],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "missing_refs": _missing_refs(entries) if status == "needs_review" else {},
        "next_actions": next_actions,
    }


def _archive_items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("entries"):
        entries = data.get("entries")
        if isinstance(entries, Mapping):
            return [dict({"candidate_id": key}, **_as_mapping(value)) for key, value in entries.items()]
        return _as_sequence(entries)
    return _as_sequence(_as_mapping(data.get("review_minutes")).get("decisions"))


def _minutes_index(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _as_sequence(_as_mapping(data.get("review_minutes")).get("decisions")):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = payload
    return result


def _calendar_evidence(data: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in _as_sequence(_as_mapping(data.get("review_calendar")).get("slots")):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = [str(ref) for ref in _as_sequence(payload.get("evidence_refs"))]
    return result


def _validation_evidence(data: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in _as_sequence(data.get("validation_evidence")):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = [str(ref) for ref in (_as_sequence(payload.get("refs")) or _as_sequence(payload.get("evidence_refs")))]
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


def _missing_refs(entries: Sequence[ReviewArchiveEntry]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in entries:
        missing: list[str] = []
        if "archive artifact refs missing" in entry.reasons:
            missing.append("artifact_refs")
        if "archive evidence refs missing" in entry.reasons:
            missing.append("evidence_refs")
        if "archive handoff refs missing" in entry.reasons:
            missing.append("handoff_refs")
        if missing:
            result[entry.candidate_id] = missing
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
