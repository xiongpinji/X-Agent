from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewEvidenceRecord:
    candidate_id: str
    ref: str
    source: str
    ref_type: str
    status: str
    owner: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "ref": self.ref,
            "source": self.source,
            "ref_type": self.ref_type,
            "status": self.status,
            "owner": self.owner,
            "reasons": list(self.reasons),
        }


def summarize_review_evidence_record(record: Mapping[str, Any] | Any) -> ReviewEvidenceRecord:
    payload = _as_mapping(record)
    ref = str(payload.get("ref") or "")
    status = str(payload.get("status") or "ready")
    reasons: list[str] = []
    if not ref:
        status = "needs_review" if status != "blocked" else status
        reasons.append("evidence ref missing")
    if status == "blocked":
        reasons.append("evidence source blocked")
    return ReviewEvidenceRecord(
        candidate_id=str(payload.get("candidate_id") or "unknown"),
        ref=ref,
        source=str(payload.get("source") or "manual"),
        ref_type=str(payload.get("ref_type") or "evidence"),
        status=status,
        owner=str(payload.get("owner") or ""),
        reasons=tuple(_unique(reasons)),
    )


def build_integration_review_evidence_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_records = _records(data)
    if not raw_records:
        return {
            "kind": "integration_review_evidence_index",
            "ok": False,
            "status": "empty",
            "records": [],
            "by_candidate": {},
            "by_source": {},
            "by_ref_type": {},
            "blocked_candidates": [],
            "missing_refs": [],
            "next_actions": ["provide_review_evidence_index_inputs"],
        }
    records = [summarize_review_evidence_record(record) for record in raw_records]
    blocked = _unique([record.candidate_id for record in records if record.status == "blocked"])
    missing = _unique([record.candidate_id for record in records if not record.ref])
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_evidence_index_blockers", "rebuild_integration_review_evidence_index"]
    elif missing:
        status = "needs_review"
        next_actions = [
            "attach_missing_review_evidence_refs",
            "review_evidence_index_warnings",
            "rebuild_integration_review_evidence_index",
        ]
    else:
        status = "ready"
        next_actions = ["share_review_evidence_index_with_mainline"]
    return {
        "kind": "integration_review_evidence_index",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": len(_unique([record.candidate_id for record in records])),
            "record_count": len(records),
            "blocked_count": len(blocked),
            "missing_ref_count": len(missing),
        },
        "records": [record.as_dict() for record in records],
        "by_candidate": _by(records, "candidate_id"),
        "by_source": _by(records, "source"),
        "by_ref_type": _by(records, "ref_type"),
        "blocked_candidates": blocked,
        "missing_refs": missing,
        "next_actions": next_actions,
    }


def _records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("records"):
        return [_as_mapping(record) for record in _as_sequence(data.get("records"))]
    records: list[dict[str, Any]] = []
    records.extend(_archive_records(data))
    records.extend(_retention_records(data))
    records.extend(_minutes_records(data))
    records.extend(_validation_records(data))
    records.extend(_handoff_records(data))
    return records


def _archive_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in _as_sequence(_as_mapping(data.get("review_archive_manifest")).get("entries")):
        item = _as_mapping(entry)
        result.extend(_refs(item, "integration_review_archive_manifest", "artifact", item.get("artifact_refs")))
        result.extend(_refs(item, "integration_review_archive_manifest", "evidence", item.get("evidence_refs")))
        result.extend(_refs(item, "integration_review_archive_manifest", "handoff", item.get("handoff_refs")))
    return result


def _retention_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for decision in _as_sequence(_as_mapping(data.get("review_retention_policy")).get("decisions")):
        item = _as_mapping(decision)
        result.extend(_refs(item, "integration_review_retention_policy", "archive", item.get("archive_refs")))
        result.extend(_refs(item, "integration_review_retention_policy", "evidence", item.get("evidence_refs")))
        result.extend(_refs(item, "integration_review_retention_policy", "handoff", item.get("handoff_refs")))
    return result


def _minutes_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for decision in _as_sequence(_as_mapping(data.get("review_minutes")).get("decisions")):
        item = _as_mapping(decision)
        result.extend(_refs(item, "integration_review_minutes", "evidence", item.get("evidence_refs")))
    return result


def _validation_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for evidence in _as_sequence(data.get("validation_evidence")):
        item = _as_mapping(evidence)
        result.extend(_refs(item, "validation_evidence", "validation", item.get("refs")))
    return result


def _handoff_records(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("handoff_refs")
    result: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        for candidate_id, payload in raw.items():
            item = _as_mapping(payload)
            result.append(
                {
                    "candidate_id": str(candidate_id),
                    "ref": str(item.get("path") or item.get("ref") or ""),
                    "source": "handoff_refs",
                    "ref_type": "handoff",
                    "status": str(item.get("status") or "ready"),
                    "owner": str(item.get("owner") or ""),
                }
            )
    else:
        for payload in _as_sequence(raw):
            item = _as_mapping(payload)
            result.append(
                {
                    "candidate_id": str(item.get("candidate_id") or "unknown"),
                    "ref": str(item.get("ref") or item.get("path") or ""),
                    "source": "handoff_refs",
                    "ref_type": "handoff",
                    "status": str(item.get("status") or "ready"),
                    "owner": str(item.get("owner") or ""),
                }
            )
    return result


def _refs(item: Mapping[str, Any], source: str, ref_type: str, refs: Any) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": str(item.get("candidate_id") or "unknown"),
            "ref": str(ref),
            "source": source,
            "ref_type": ref_type,
            "status": str(item.get("status") or "ready"),
            "owner": str(item.get("owner") or ""),
        }
        for ref in _as_sequence(refs)
    ]


def _by(records: Sequence[ReviewEvidenceRecord], field_name: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for record in records:
        key = str(getattr(record, field_name))
        if record.ref:
            result.setdefault(key, [])
            if record.ref not in result[key]:
                result[key].append(record.ref)
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
