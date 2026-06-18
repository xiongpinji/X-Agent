from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewAdoptionManifestEntry:
    candidate_id: str
    manifest_key: str
    status: str
    stage_label: str = "secondary_integration_candidate"
    include_paths: tuple[str, ...] = field(default_factory=tuple)
    test_paths: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "manifest_key": self.manifest_key,
            "status": self.status,
            "stage_label": self.stage_label,
            "include_paths": list(self.include_paths),
            "test_paths": list(self.test_paths),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_adoption_manifest_entry(entry: Mapping[str, Any] | Any) -> ReviewAdoptionManifestEntry:
    payload = _as_mapping(entry)
    candidate_id = str(payload.get("candidate_id") or "")
    include_paths = tuple(str(ref) for ref in (_as_sequence(payload.get("include_paths")) or _as_sequence(payload.get("files"))))
    test_paths = tuple(str(ref) for ref in (_as_sequence(payload.get("test_paths")) or _as_sequence(payload.get("tests"))))
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    status = str(payload.get("status") or "needs_review")
    reasons: list[str] = []
    if not include_paths:
        reasons.append("include paths missing")
    if not test_paths:
        reasons.append("test paths missing")
    if not handoff_refs:
        reasons.append("handoff refs missing")
    if status == "blocked":
        reasons.append("manifest source blocked")
    elif reasons:
        status = "needs_review"
    return ReviewAdoptionManifestEntry(
        candidate_id=candidate_id,
        manifest_key=str(payload.get("manifest_key") or payload.get("pack_key") or candidate_id),
        status=status,
        stage_label=str(payload.get("stage_label") or "secondary_integration_candidate"),
        include_paths=include_paths,
        test_paths=test_paths,
        evidence_refs=tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs"))),
        handoff_refs=handoff_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        blockers=tuple(str(item) for item in _as_sequence(payload.get("blockers"))),
        reasons=tuple(reasons),
    )


def build_integration_review_adoption_manifest_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _entries(data)
    if not raw:
        return {
            "kind": "integration_review_adoption_manifest_preview",
            "preview_id": str(data.get("preview_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"entry_count": 0},
            "entries": [],
            "include_paths": [],
            "test_paths": [],
            "by_stage_label": {},
            "render_hints": {"write_manifest": False},
            "next_actions": ["provide_review_adoption_manifest_preview_inputs"],
        }
    entries = [summarize_review_adoption_manifest_entry(item) for item in raw]
    blocked = [item.candidate_id for item in entries if item.status == "blocked"]
    review = [item.candidate_id for item in entries if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_adoption_manifest_blockers",
            "attach_manifest_evidence",
            "rebuild_integration_review_adoption_manifest_preview",
        ]
    elif review:
        status = "needs_review"
        reasons = [reason for item in entries for reason in item.reasons]
        actions = ["complete_review_adoption_manifest_preview"]
        if "include paths missing" in reasons:
            actions.append("attach_manifest_include_paths")
        if "test paths missing" in reasons:
            actions.append("attach_manifest_test_paths")
        if "handoff refs missing" in reasons:
            actions.append("attach_manifest_handoff_refs")
        next_actions = actions + ["rebuild_integration_review_adoption_manifest_preview"]
    else:
        status = "ready"
        next_actions = ["share_review_adoption_manifest_preview_with_mainline"]
    return {
        "kind": "integration_review_adoption_manifest_preview",
        "preview_id": str(data.get("preview_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"entry_count": len(entries)},
        "entries": [item.as_dict() for item in entries],
        "include_paths": _unique([path for item in entries for path in item.include_paths]),
        "test_paths": _unique([path for item in entries for path in item.test_paths]),
        "by_stage_label": _by_stage(entries),
        "blocked_candidates": blocked,
        "review_candidates": review,
        "render_hints": {"write_manifest": False},
        "next_actions": _unique(next_actions),
    }


def _entries(data: Mapping[str, Any]) -> list[Any]:
    if data.get("entries"):
        return _as_sequence(data.get("entries"))
    pack = _as_mapping(data.get("adoption_candidate_pack"))
    return _as_sequence(pack.get("packs"))


def _by_stage(entries: Sequence[ReviewAdoptionManifestEntry]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for entry in entries:
        result.setdefault(entry.stage_label, []).append(entry.manifest_key)
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
