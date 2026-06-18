from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestAdoptionExecutionPreviewItem:
    candidate_id: str
    preview_key: str
    status: str
    recommended_outcome: str
    operation: str
    candidate_paths: tuple[str, ...] = field(default_factory=tuple)
    manifest_refs: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    touched_paths: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "preview_key": self.preview_key,
            "status": self.status,
            "recommended_outcome": self.recommended_outcome,
            "operation": self.operation,
            "candidate_paths": list(self.candidate_paths),
            "manifest_refs": list(self.manifest_refs),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "touched_paths": list(self.touched_paths),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_execution_preview_item(
    item: Mapping[str, Any] | Any,
    *,
    manifest_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewManifestAdoptionExecutionPreviewItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    manifest = dict((manifest_index or {}).get(candidate_id, {}))
    outcome = str(payload.get("recommended_outcome") or "review")
    status = str(payload.get("decision_status") or payload.get("status") or "needs_review")
    candidate_paths = tuple(str(path) for path in (_as_sequence(payload.get("candidate_paths")) or _as_sequence(manifest.get("include_paths"))))
    manifest_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("manifest_refs")) or _as_sequence(manifest.get("manifest_key"))))
    validation_refs = tuple(str(ref) for ref in _as_sequence(payload.get("validation_refs")))
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    warnings = [str(warning) for warning in _as_sequence(payload.get("warnings"))]
    if status == "blocked" or blockers:
        status = "blocked"
    elif outcome == "adopt":
        if not manifest_refs:
            warnings.append("manifest refs missing")
        if not validation_refs:
            warnings.append("validation refs missing")
        if warnings:
            status = "needs_review"
        else:
            status = "ready"
    else:
        status = "ready" if status == "ready" else status
    operation = _operation(outcome)
    return ReviewManifestAdoptionExecutionPreviewItem(
        candidate_id=candidate_id,
        preview_key=str(payload.get("preview_key") or payload.get("decision_key") or candidate_id),
        status=status,
        recommended_outcome=outcome,
        operation=operation,
        candidate_paths=candidate_paths,
        manifest_refs=manifest_refs,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        touched_paths=tuple(_touched_paths(operation, candidate_paths)),
        warnings=tuple(_unique(warnings)),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_execution_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _as_sequence(_as_mapping(data.get("manifest_adoption_decision_sheet")).get("rows"))
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_execution_preview",
            "ok": False,
            "status": "empty",
            "items": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_execution_preview_inputs"],
        }
    manifest_index = {
        str(_as_mapping(entry).get("candidate_id") or ""): _as_mapping(entry)
        for entry in _as_sequence(_as_mapping(data.get("adoption_manifest_preview")).get("entries"))
    }
    items = [summarize_review_manifest_adoption_execution_preview_item(item, manifest_index=manifest_index) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review"]
    ready = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_execution_preview_blockers", "rebuild_integration_review_manifest_adoption_execution_preview"]
    elif review:
        status = "needs_review"
        actions = ["review_manifest_adoption_execution_preview_warnings"]
        if any("manifest refs missing" in item.warnings for item in items):
            actions.append("attach_manifest_adoption_execution_manifest_refs")
        if any("validation refs missing" in item.warnings for item in items):
            actions.append("attach_manifest_adoption_execution_validation_refs")
        next_actions = actions + ["rebuild_integration_review_manifest_adoption_execution_preview"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_execution_preview_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_execution_preview",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _operation(outcome: str) -> str:
    return {
        "adopt": "preview_stage_candidate_for_adoption",
        "defer": "preview_mark_candidate_deferred",
        "reject": "preview_mark_candidate_rejected",
    }.get(outcome, "preview_review_candidate")


def _touched_paths(operation: str, paths: Sequence[str]) -> list[str]:
    if operation != "preview_stage_candidate_for_adoption":
        return [str(path) for path in paths]
    return [str(path) for path in paths] + [f"stage_include:{path}" for path in paths]


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
