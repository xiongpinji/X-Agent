from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceabilityRecord:
    candidate_id: str
    owner: str
    status: str
    files: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    validation_commands: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    decisions: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_statuses: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "status": self.status,
            "files": list(self.files),
            "tests": list(self.tests),
            "validation_commands": list(self.validation_commands),
            "handoff_refs": list(self.handoff_refs),
            "decisions": list(self.decisions),
            "evidence_refs": list(self.evidence_refs),
            "validation_statuses": list(self.validation_statuses),
            "reasons": list(self.reasons),
        }


def analyze_traceability_record(record: Mapping[str, Any] | Any) -> TraceabilityRecord:
    payload = _as_mapping(record)
    decisions = tuple(str(item) for item in _as_sequence(payload.get("decisions")))
    validation_statuses = tuple(str(item) for item in _as_sequence(payload.get("validation_statuses")))
    reasons: list[str] = []
    if not _as_sequence(payload.get("tests")):
        reasons.append("traceability tests missing")
    if not _as_sequence(payload.get("validation_commands")):
        reasons.append("traceability validation commands missing")
    if not _as_sequence(payload.get("handoff_refs")):
        reasons.append("traceability handoff refs missing")
    if any(status == "failed" for status in validation_statuses):
        reasons.append("validation failed")
    if any(decision in {"rejected", "blocked"} for decision in decisions):
        reasons.append("integration decision rejected or blocked")
    if "validation failed" in reasons or "integration decision rejected or blocked" in reasons:
        status = "blocked"
    elif reasons:
        status = "needs_review"
    else:
        status = "ready"
    return TraceabilityRecord(
        candidate_id=str(payload.get("candidate_id") or "unknown"),
        owner=str(payload.get("owner") or ""),
        status=status,
        files=tuple(str(item) for item in _as_sequence(payload.get("files"))),
        tests=tuple(str(item) for item in _as_sequence(payload.get("tests"))),
        validation_commands=tuple(str(item) for item in _as_sequence(payload.get("validation_commands"))),
        handoff_refs=tuple(str(item) for item in _as_sequence(payload.get("handoff_refs"))),
        decisions=decisions,
        evidence_refs=tuple(str(item) for item in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(payload.get("evidence")))),
        validation_statuses=validation_statuses,
        reasons=tuple(reasons),
    )


def build_integration_traceability_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _records(payload)
    if not raw:
        return {
            "kind": "integration_traceability_index",
            "ok": False,
            "status": "empty",
            "records": [],
            "issues": [],
            "coverage": {"test_coverage": 0.0},
            "next_actions": ["provide_traceability_records"],
        }
    records = [analyze_traceability_record(item) for item in raw]
    if any(item.status == "blocked" for item in records):
        status = "blocked"
        next_actions = ["resolve_blocked_traceability_records", "attach_passing_validation_evidence", "rebuild_integration_traceability_index"]
    elif any(item.status == "needs_review" for item in records):
        status = "needs_review"
        next_actions = ["add_candidate_file_and_test_refs", "attach_passing_validation_evidence", "attach_handoff_references", "rebuild_integration_traceability_index"]
    else:
        status = "ready"
        next_actions = ["prepare_auditable_integration_review"]
    return {
        "kind": "integration_traceability_index",
        "ok": status == "ready",
        "status": status,
        "summary": {"record_count": len(records), "ready_count": len([item for item in records if item.status == "ready"]), "review_count": len([item for item in records if item.status == "needs_review"]), "blocked_count": len([item for item in records if item.status == "blocked"])},
        "coverage": {"test_coverage": _coverage(records, "tests"), "validation_coverage": _coverage(records, "validation_commands"), "handoff_coverage": _coverage(records, "handoff_refs")},
        "records": [item.as_dict() for item in records],
        "issues": _issues(records),
        "next_actions": next_actions,
    }


def _records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if payload.get("records"):
        return [_as_mapping(item) for item in _as_sequence(payload.get("records"))]
    if payload.get("candidates"):
        return [_as_mapping(item) for item in _as_sequence(payload.get("candidates"))]
    candidate_ids = _unique(
        [
            *[str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(_as_mapping(payload.get("sequence_plan")).get("candidates"))],
            *[str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(_as_mapping(payload.get("scorecard")).get("candidates"))],
            *[str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(_as_mapping(payload.get("decision_audit")).get("decisions"))],
            *[str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(payload.get("validations"))],
            *[str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(payload.get("handoff_refs"))],
        ]
    )
    return [_merge_record(candidate_id, payload) for candidate_id in candidate_ids]


def _merge_record(candidate_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    sequence = _find(candidate_id, _as_mapping(payload.get("sequence_plan")).get("candidates"))
    score = _find(candidate_id, _as_mapping(payload.get("scorecard")).get("candidates"))
    decision = _find(candidate_id, _as_mapping(payload.get("decision_audit")).get("decisions"))
    validation = _find(candidate_id, payload.get("validations"))
    handoff = _find(candidate_id, payload.get("handoff_refs"))
    return {
        "candidate_id": candidate_id,
        "owner": sequence.get("owner") or decision.get("owner") or "",
        "files": _as_sequence(score.get("files")),
        "tests": _as_sequence(score.get("tests")),
        "validation_commands": _as_sequence(validation.get("command")),
        "handoff_refs": _as_sequence(handoff.get("ref")),
        "decisions": _as_sequence(decision.get("decision")),
        "evidence_refs": _as_sequence(score.get("evidence")) + _as_sequence(decision.get("evidence_refs")),
        "validation_statuses": _as_sequence(validation.get("status")),
    }


def _find(candidate_id: str, raw: Any) -> dict[str, Any]:
    return next((_as_mapping(item) for item in _as_sequence(raw) if str(_as_mapping(item).get("candidate_id") or "") == candidate_id), {})


def _coverage(records: Sequence[TraceabilityRecord], field_name: str) -> float:
    if not records:
        return 0.0
    return len([record for record in records if getattr(record, field_name)]) / len(records)


def _issues(records: Sequence[TraceabilityRecord]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for record in records:
        for reason in record.reasons:
            code = reason.replace(" ", "_")
            if code == "validation_failed":
                code = "traceability_validation_blocked"
            elif code.startswith("traceability_"):
                pass
            else:
                code = "traceability_" + code
            issues.append({"code": code, "candidate_id": record.candidate_id})
    return issues


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
