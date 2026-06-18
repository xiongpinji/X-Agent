from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionRollbackPreviewItem:
    candidate_id: str
    rollback_key: str
    status: str
    recommended_outcome: str
    rollback_operation: str
    source_touched_paths: tuple[str, ...] = field(default_factory=tuple)
    rollback_paths: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rollback_key": self.rollback_key,
            "status": self.status,
            "recommended_outcome": self.recommended_outcome,
            "rollback_operation": self.rollback_operation,
            "source_touched_paths": list(self.source_touched_paths),
            "rollback_paths": list(self.rollback_paths),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_rollback_preview_item(
    item: Mapping[str, Any] | Any,
    *,
    execution_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionRollbackPreviewItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    fallback = dict((execution_index or {}).get(candidate_id, {}))
    touched = tuple(str(path) for path in (_as_sequence(payload.get("source_touched_paths")) or _as_sequence(payload.get("touched_paths")) or _as_sequence(fallback.get("touched_paths"))))
    rollback_paths = tuple(str(path) for path in (_as_sequence(payload.get("rollback_paths")) or _rollback_paths(touched)))
    return ReviewManifestAdoptionRollbackPreviewItem(
        candidate_id=candidate_id,
        rollback_key=str(payload.get("rollback_key") or payload.get("report_key") or candidate_id),
        status=str(payload.get("status") or "needs_review"),
        recommended_outcome=str(payload.get("recommended_outcome") or ""),
        rollback_operation="preview_remove_staged_candidate" if any(path.startswith("stage_include:") for path in touched) else "preview_verify_no_staged_candidate",
        source_touched_paths=touched,
        rollback_paths=rollback_paths,
        validation_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(fallback.get("validation_refs")))),
        handoff_refs=tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(fallback.get("handoff_refs")))),
        warnings=tuple(str(warning) for warning in _as_sequence(payload.get("warnings"))),
        blockers=tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers"))),
    )


def build_integration_review_manifest_adoption_rollback_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_rollback_preview",
            "ok": False,
            "status": "empty",
            "items": [],
            "rollback_sections": {"rollback_paths": [], "warnings": [], "blockers": []},
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_rollback_preview_inputs"],
        }
    execution_index = {
        str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item)
        for item in _as_sequence(_as_mapping(data.get("manifest_adoption_execution_preview")).get("items"))
    }
    items = [summarize_review_manifest_adoption_rollback_preview_item(item, execution_index=execution_index) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked" or item.blockers]
    review = [item.candidate_id for item in items if item.status == "needs_review" and item.candidate_id not in blocked]
    ready = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_rollback_preview_blockers", "rebuild_integration_review_manifest_adoption_rollback_preview"]
    elif review:
        status = "needs_review"
        next_actions = ["complete_manifest_adoption_dry_run_report", "rebuild_integration_review_manifest_adoption_rollback_preview"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_rollback_preview_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_rollback_preview",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "rollback_sections": {
            "rollback_paths": _unique([path for item in items for path in item.rollback_paths]),
            "warnings": _unique([warning for item in items for warning in item.warnings]),
            "blockers": _unique([blocker for item in items for blocker in item.blockers]),
        },
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("rollback_previews"):
        return _as_sequence(data.get("rollback_previews"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_dry_run_report")).get("items"))


def _rollback_paths(paths: Sequence[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        text = str(path)
        if text.startswith("stage_include:"):
            result.append("stage_remove:" + text.removeprefix("stage_include:"))
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
