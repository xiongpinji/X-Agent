from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SecondaryCandidate:
    candidate_id: str
    integration_status: str
    status: str
    owner: str = ""
    files: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    validation_commands: tuple[str, ...] = field(default_factory=tuple)
    validation_results: tuple[str, ...] = field(default_factory=tuple)
    validation_statuses: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "integration_status": self.integration_status,
            "status": self.status,
            "owner": self.owner,
            "files": list(self.files),
            "tests": list(self.tests),
            "validation_commands": list(self.validation_commands),
            "validation_results": list(self.validation_results),
            "validation_statuses": list(self.validation_statuses),
            "handoff_refs": list(self.handoff_refs),
            "tags": list(self.tags),
            "reasons": list(self.reasons),
            "issues": [dict(issue) for issue in self.issues],
        }


def summarize_secondary_candidate(
    candidate: Mapping[str, Any] | Any,
    *,
    validation_index: Mapping[str, Mapping[str, Any]] | None = None,
    handoff_index: Mapping[str, Sequence[str]] | None = None,
) -> SecondaryCandidate:
    payload = _as_mapping(candidate)
    candidate_id = str(payload.get("candidate_id") or payload.get("id") or "")
    validation = dict((validation_index or {}).get(candidate_id, {}))
    validation_results = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_results")) or _as_sequence(validation.get("result"))))
    validation_statuses = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_statuses")) or _as_sequence(validation.get("status"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or (handoff_index or {}).get(candidate_id, ())))
    integration_status = str(payload.get("integration_status") or "secondary_integration_candidate")
    issues: list[dict[str, Any]] = []
    reasons: list[str] = []
    if not _as_sequence(payload.get("validation_commands")):
        issues.append({"code": "secondary_index_validation_commands_missing", "severity": "medium", "candidate_id": candidate_id})
    if not validation_results:
        issues.append({"code": "secondary_index_validation_results_missing", "severity": "medium", "candidate_id": candidate_id})
    if not handoff_refs:
        issues.append({"code": "secondary_index_handoff_refs_missing", "severity": "medium", "candidate_id": candidate_id})
    if integration_status != "secondary_integration_candidate":
        issues.append({"code": "secondary_index_status_not_detached", "severity": "high", "candidate_id": candidate_id})
    if any(status == "failed" for status in validation_statuses) or any("failed" in result for result in validation_results):
        issues.append({"code": "secondary_index_validation_blocked", "severity": "high", "candidate_id": candidate_id})
    if any(issue.get("severity") == "high" for issue in issues):
        status = "blocked"
    elif issues:
        status = "needs_review"
    else:
        status = "ready"
        reasons.append("secondary index entry complete")
    return SecondaryCandidate(
        candidate_id=candidate_id,
        integration_status=integration_status,
        status=status,
        owner=str(payload.get("owner") or ""),
        files=tuple(str(ref) for ref in _as_sequence(payload.get("files"))),
        tests=tuple(str(ref) for ref in _as_sequence(payload.get("tests"))),
        validation_commands=tuple(str(ref) for ref in _as_sequence(payload.get("validation_commands"))),
        validation_results=validation_results,
        validation_statuses=validation_statuses,
        handoff_refs=handoff_refs,
        tags=tuple(str(ref) for ref in _as_sequence(payload.get("tags"))),
        reasons=tuple(reasons),
        issues=tuple(issues),
    )


def build_integration_secondary_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _candidates(data)
    if not raw:
        return {
            "kind": "integration_secondary_index",
            "index_id": str(data.get("index_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"candidate_count": 0},
            "entries": [],
            "issues": [],
            "by_status": {},
            "by_owner": {},
            "next_actions": ["provide_secondary_candidate_entries"],
        }
    validation_index = _validation_index(data.get("validations"))
    handoff_index = _handoff_index(data.get("handoff_refs"))
    entries = [summarize_secondary_candidate(item, validation_index=validation_index, handoff_index=handoff_index) for item in raw]
    blocked = [item for item in entries if item.status == "blocked"]
    review = [item for item in entries if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_blocked_secondary_index_entries",
            "attach_passing_secondary_validation_status",
            "rebuild_integration_secondary_index",
        ]
    elif review:
        status = "needs_review"
        next_actions = [
            "attach_secondary_candidate_validation_evidence",
            "attach_secondary_handoff_references",
            "rebuild_integration_secondary_index",
        ]
    else:
        status = "ready"
        next_actions = ["share_secondary_index_with_mainline_for_review"]
    return {
        "kind": "integration_secondary_index",
        "index_id": str(data.get("index_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": len(entries),
            "ready_count": sum(1 for item in entries if item.status == "ready"),
            "blocked_count": len(blocked),
            "needs_review_count": len(review),
        },
        "entries": [item.as_dict() for item in entries],
        "issues": [issue for item in entries for issue in item.issues],
        "by_status": _by(entries, "status"),
        "by_owner": _by_owner(entries),
        "next_actions": next_actions,
    }


def _candidates(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    traceability = _as_mapping(data.get("traceability_index"))
    return _as_sequence(traceability.get("records"))


def _validation_index(raw: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _as_sequence(raw):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = payload
    return result


def _handoff_index(raw: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in _as_sequence(raw):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = [str(ref) for ref in (_as_sequence(payload.get("refs")) or _as_sequence(payload.get("ref")))]
    return result


def _by(entries: Sequence[SecondaryCandidate], attr: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in entries:
        result.setdefault(str(getattr(entry, attr)), []).append(entry.candidate_id)
    return result


def _by_owner(entries: Sequence[SecondaryCandidate]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in entries:
        if entry.owner:
            result.setdefault(entry.owner, []).append(entry.candidate_id)
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
