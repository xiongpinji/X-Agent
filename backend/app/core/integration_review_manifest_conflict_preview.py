from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestConflictItem:
    candidate_id: str
    conflict_key: str
    status: str
    conflict_level: str
    candidate_paths: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    overlaps: tuple[str, ...] = field(default_factory=tuple)
    forbidden_paths: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "conflict_key": self.conflict_key,
            "status": self.status,
            "conflict_level": self.conflict_level,
            "candidate_paths": list(self.candidate_paths),
            "handoff_refs": list(self.handoff_refs),
            "overlaps": list(self.overlaps),
            "forbidden_paths": list(self.forbidden_paths),
            "reasons": list(self.reasons),
        }


def summarize_review_manifest_conflict_item(
    item: Mapping[str, Any] | Any,
    *,
    active_scopes: Sequence[str] | None = None,
    forbidden_paths: Sequence[str] | None = None,
) -> ReviewManifestConflictItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    candidate_paths = tuple(str(path) for path in (_as_sequence(payload.get("candidate_paths")) or _as_sequence(payload.get("include_paths"))))
    active = [str(path) for path in (active_scopes or [])]
    forbidden = [str(path) for path in (forbidden_paths or _as_sequence(payload.get("forbidden_paths")))]
    overlaps = tuple(f"{path}::{scope}" for path in candidate_paths for scope in active if _path_overlaps(path, scope))
    forbidden_hits = tuple(scope for scope in forbidden if any(_path_overlaps(path, scope) for path in candidate_paths))
    reasons: list[str] = []
    status = str(payload.get("status") or "ready")
    if forbidden_hits:
        status = "blocked"
        conflict_level = "blocked"
        reasons.append("forbidden scope overlap")
    elif overlaps:
        status = "needs_review"
        conflict_level = "review"
        reasons.append("active scope overlap")
    else:
        conflict_level = str(payload.get("conflict_level") or "none")
        if conflict_level == "none":
            reasons.append("manifest conflict clear")
    return ReviewManifestConflictItem(
        candidate_id=candidate_id,
        conflict_key=str(payload.get("conflict_key") or payload.get("manifest_key") or candidate_id),
        status=status,
        conflict_level=conflict_level,
        candidate_paths=candidate_paths,
        handoff_refs=tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs"))),
        overlaps=overlaps,
        forbidden_paths=forbidden_hits,
        reasons=tuple(reasons),
    )


def build_integration_review_manifest_conflict_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_conflict_preview",
            "ok": False,
            "status": "empty",
            "items": [],
            "clear_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_conflict_preview_inputs"],
        }
    active_scopes = _paths(data.get("active_scopes"))
    forbidden = [str(path) for path in _as_sequence(data.get("forbidden_paths"))]
    items = [summarize_review_manifest_conflict_item(item, active_scopes=active_scopes, forbidden_paths=forbidden) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review"]
    clear = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_manifest_conflict_blockers",
            "remove_forbidden_manifest_paths",
            "rebuild_integration_review_manifest_conflict_preview",
        ]
    elif review:
        status = "needs_review"
        next_actions = ["review_manifest_scope_overlap", "rebuild_integration_review_manifest_conflict_preview"]
    else:
        status = "ready"
        next_actions = ["share_review_manifest_conflict_preview_with_mainline"]
    return {
        "kind": "integration_review_manifest_conflict_preview",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "clear_candidates": clear,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("conflicts"):
        return _as_sequence(data.get("conflicts"))
    preview = _as_mapping(data.get("adoption_manifest_preview"))
    return _as_sequence(preview.get("entries"))


def _paths(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for item in value.values():
            paths.extend(str(path) for path in _as_sequence(_as_mapping(item).get("paths")))
        return paths
    return [str(path) for path in _as_sequence(value)]


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
