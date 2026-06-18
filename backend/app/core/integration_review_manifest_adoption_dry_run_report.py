from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionDryRunReportItem:
    candidate_id: str
    report_key: str
    status: str
    recommended_outcome: str
    operation: str
    touched_paths: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "report_key": self.report_key,
            "status": self.status,
            "recommended_outcome": self.recommended_outcome,
            "operation": self.operation,
            "touched_paths": list(self.touched_paths),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_dry_run_report_item(
    item: Mapping[str, Any] | Any,
    *,
    decision_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionDryRunReportItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    fallback = dict((decision_index or {}).get(candidate_id, {}))
    return ReviewManifestAdoptionDryRunReportItem(
        candidate_id=candidate_id,
        report_key=str(payload.get("report_key") or payload.get("preview_key") or candidate_id),
        status=str(payload.get("status") or "needs_review"),
        recommended_outcome=str(payload.get("recommended_outcome") or ""),
        operation=str(payload.get("operation") or ""),
        touched_paths=tuple(str(path) for path in (_as_sequence(payload.get("touched_paths")) or _as_sequence(fallback.get("candidate_paths")))),
        validation_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(fallback.get("validation_refs")))),
        handoff_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(fallback.get("handoff_refs")))),
        warnings=tuple(str(warning) for warning in _as_sequence(payload.get("warnings"))),
        blockers=tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers"))),
    )


def build_integration_review_manifest_adoption_dry_run_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_dry_run_report",
            "ok": False,
            "status": "empty",
            "items": [],
            "report_sections": {"touched_paths": [], "warnings": [], "blockers": []},
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_dry_run_report_inputs"],
        }
    decision_index = {
        str(_as_mapping(row).get("candidate_id") or ""): _as_mapping(row)
        for row in _as_sequence(_as_mapping(data.get("manifest_adoption_decision_sheet")).get("rows"))
    }
    items = [summarize_review_manifest_adoption_dry_run_report_item(item, decision_index=decision_index) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked" or item.blockers]
    review = [item.candidate_id for item in items if item.status == "needs_review" and item.candidate_id not in blocked]
    ready = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_dry_run_report_blockers", "rebuild_integration_review_manifest_adoption_dry_run_report"]
    elif review:
        status = "needs_review"
        next_actions = ["review_manifest_adoption_dry_run_warnings", "rebuild_integration_review_manifest_adoption_dry_run_report"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_dry_run_report_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_dry_run_report",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "report_sections": {
            "touched_paths": _unique([path for item in items for path in item.touched_paths]),
            "warnings": _unique([warning for item in items for warning in item.warnings]),
            "blockers": _unique([blocker for item in items for blocker in item.blockers]),
        },
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("report_items"):
        return _as_sequence(data.get("report_items"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_execution_preview")).get("items"))


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
