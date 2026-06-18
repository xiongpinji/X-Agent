from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConflictRiskEntry:
    candidate_id: str
    integration_status: str
    owner: str
    files: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    validation_statuses: tuple[str, ...] = field(default_factory=tuple)
    risk_level: str = "low"
    review_status: str = "ready"
    forbidden_matches: tuple[str, ...] = field(default_factory=tuple)
    active_scope_matches: tuple[str, ...] = field(default_factory=tuple)
    shared_owner_matches: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "integration_status": self.integration_status,
            "owner": self.owner,
            "files": list(self.files),
            "tests": list(self.tests),
            "validation_statuses": list(self.validation_statuses),
            "risk_level": self.risk_level,
            "review_status": self.review_status,
            "forbidden_matches": list(self.forbidden_matches),
            "active_scope_matches": list(self.active_scope_matches),
            "shared_owner_matches": list(self.shared_owner_matches),
            "reasons": list(self.reasons),
            "next_actions": list(self.next_actions),
        }


def assess_conflict_risk(
    candidate: Mapping[str, Any] | Any,
    *,
    forbidden_paths: Sequence[str] | None = None,
    active_mainline_scopes: Sequence[str] | None = None,
    active_owners: Sequence[str] | None = None,
) -> ConflictRiskEntry:
    payload = _as_mapping(candidate)
    files = tuple(str(path) for path in _as_sequence(payload.get("files")))
    statuses = tuple(str(status) for status in _as_sequence(payload.get("validation_statuses")))
    owner = str(payload.get("owner") or "")
    forbidden = tuple(
        scope
        for scope in (str(path) for path in (forbidden_paths or ()))
        if any(_path_overlaps(path, scope) for path in files)
    )
    active_matches = tuple(
        scope
        for scope in (str(path) for path in (active_mainline_scopes or ()))
        if any(_path_overlaps(path, scope) for path in files)
    )
    shared_owners = (owner,) if owner and owner in {str(item) for item in (active_owners or ())} else ()

    reasons: list[str] = []
    next_actions: list[str] = []
    failed_validation = any(status.lower() in {"failed", "blocked", "error"} for status in statuses)
    if forbidden or failed_validation:
        risk_level = "high"
        review_status = "blocked"
        if forbidden:
            reasons.append("candidate touches forbidden path")
            next_actions.append("exclude_or_reclassify_candidate_scope")
        if failed_validation:
            reasons.append("validation failed or blocked")
            next_actions.append("refresh_candidate_validation_evidence")
        next_actions.append("rebuild_integration_conflict_risk_register")
    elif active_matches or shared_owners:
        risk_level = "medium"
        review_status = "needs_review"
        if active_matches:
            reasons.append("candidate overlaps active mainline scope")
            next_actions.append("coordinate_with_active_mainline_scope_owner")
        if shared_owners:
            reasons.append("candidate shares active owner")
            next_actions.append("confirm_owner_capacity_before_review")
        next_actions.append("rebuild_integration_conflict_risk_register")
    else:
        risk_level = "low"
        review_status = "ready"
        reasons.append("conflict risk low")

    return ConflictRiskEntry(
        candidate_id=str(payload.get("candidate_id") or ""),
        integration_status=str(payload.get("integration_status") or ""),
        owner=owner,
        files=files,
        tests=tuple(str(path) for path in _as_sequence(payload.get("tests"))),
        validation_statuses=statuses,
        risk_level=risk_level,
        review_status=review_status,
        forbidden_matches=forbidden,
        active_scope_matches=active_matches,
        shared_owner_matches=shared_owners,
        reasons=tuple(_unique(reasons)),
        next_actions=tuple(_unique(next_actions)),
    )


def build_integration_conflict_risk_register(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    candidates = _candidates(data)
    if not candidates:
        return {
            "kind": "integration_conflict_risk_register",
            "register_id": str(data.get("register_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"candidate_count": 0, "low_risk_count": 0, "blocked_count": 0, "review_count": 0},
            "entries": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "owner_conflicts": {},
            "next_actions": ["provide_conflict_risk_candidates"],
        }

    forbidden_paths = [str(path) for path in _as_sequence(data.get("forbidden_paths"))]
    active_scopes = [str(path) for path in _as_sequence(data.get("active_mainline_scopes"))]
    active_owners = [str(owner) for owner in _as_sequence(data.get("active_owners"))]
    entries = [
        assess_conflict_risk(
            candidate,
            forbidden_paths=forbidden_paths,
            active_mainline_scopes=active_scopes,
            active_owners=active_owners,
        )
        for candidate in candidates
    ]
    blocked = [entry.candidate_id for entry in entries if entry.review_status == "blocked"]
    review = [entry.candidate_id for entry in entries if entry.review_status == "needs_review"]
    ready = [entry.candidate_id for entry in entries if entry.review_status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = _unique([action for entry in entries for action in entry.next_actions])
    elif review:
        status = "needs_review"
        next_actions = _unique([action for entry in entries for action in entry.next_actions])
    else:
        status = "ready"
        next_actions = ["share_conflict_risk_register_with_mainline_for_review"]

    return {
        "kind": "integration_conflict_risk_register",
        "register_id": str(data.get("register_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": len(entries),
            "low_risk_count": len(ready),
            "blocked_count": len(blocked),
            "review_count": len(review),
        },
        "entries": [entry.as_dict() for entry in entries],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "owner_conflicts": _owner_conflicts(entries),
        "next_actions": next_actions,
    }


def _candidates(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("candidates"):
        return [_as_mapping(item) for item in _as_sequence(data.get("candidates"))]
    secondary = _as_mapping(data.get("secondary_index"))
    candidates = [_as_mapping(item) for item in _as_sequence(secondary.get("entries"))]
    validation_index = {
        str(_as_mapping(row).get("candidate_id") or ""): str(_as_mapping(row).get("status") or "")
        for row in _as_sequence(data.get("validations"))
    }
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in validation_index and not candidate.get("validation_statuses"):
            candidate["validation_statuses"] = [validation_index[candidate_id]]
    return candidates


def _owner_conflicts(entries: Sequence[ConflictRiskEntry]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in entries:
        for owner in entry.shared_owner_matches:
            result.setdefault(owner, []).append(entry.candidate_id)
    return result


def _path_overlaps(path: str, scope: str) -> bool:
    return path == scope or path.startswith(scope.rstrip("/") + "/") or scope.startswith(path.rstrip("/") + "/")


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
