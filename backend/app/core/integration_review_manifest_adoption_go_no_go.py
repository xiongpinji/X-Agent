from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestAdoptionGoNoGoItem:
    candidate_id: str
    decision_key: str
    status: str
    go_no_go: str
    recommended_outcome: str
    confidence: str
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    required_evidence: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision_key": self.decision_key,
            "status": self.status,
            "go_no_go": self.go_no_go,
            "recommended_outcome": self.recommended_outcome,
            "confidence": self.confidence,
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "required_evidence": list(self.required_evidence),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_adoption_go_no_go_item(
    item: Mapping[str, Any] | Any,
    *,
    dry_run_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ManifestAdoptionGoNoGoItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    fallback = dict((dry_run_index or {}).get(candidate_id, {}))
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or _as_sequence(fallback.get("validation_refs"))))
    handoff_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("handoff_refs")) or _as_sequence(fallback.get("handoff_refs"))))
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    status = str(payload.get("status") or "needs_review")
    recommended = str(payload.get("recommended_outcome") or "")
    go_no_go = str(payload.get("go_no_go") or _decision_from(status, recommended))
    required: list[str] = []
    if status == "needs_review":
        required.append("rollback preview must be completed")
    if not validation_refs:
        required.append("validation refs required")
    if not handoff_refs:
        required.append("handoff refs required")
    if status == "blocked" or blockers or go_no_go == "no_go":
        status = "blocked"
        go_no_go = "no_go"
        confidence = "low"
    elif required and payload.get("go_no_go") != "hold":
        status = "needs_review"
        go_no_go = "hold"
        confidence = "medium"
    else:
        status = str(payload.get("status") or "ready")
        confidence = "high" if go_no_go == "go" else "medium"
    return ManifestAdoptionGoNoGoItem(
        candidate_id=candidate_id,
        decision_key=str(payload.get("decision_key") or payload.get("rollback_key") or candidate_id),
        status=status,
        go_no_go=go_no_go,
        recommended_outcome=recommended,
        confidence=confidence,
        validation_refs=validation_refs,
        handoff_refs=handoff_refs,
        required_evidence=tuple(required),
        blockers=blockers,
    )


def build_integration_review_manifest_adoption_go_no_go(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_adoption_go_no_go",
            "ok": False,
            "status": "empty",
            "items": [],
            "go_candidates": [],
            "hold_candidates": [],
            "no_go_candidates": [],
            "next_actions": ["provide_review_manifest_adoption_go_no_go_inputs"],
        }
    dry_run_index = _index(_as_mapping(data.get("manifest_adoption_dry_run_report")).get("items"))
    items = [summarize_review_manifest_adoption_go_no_go_item(item, dry_run_index=dry_run_index) for item in raw]
    no_go = _candidate_ids(item for item in items if item.status == "blocked" or item.go_no_go == "no_go")
    hold = _candidate_ids(item for item in items if item.go_no_go == "hold" and item.candidate_id not in no_go)
    go = _candidate_ids(item for item in items if item.go_no_go == "go" and item.candidate_id not in no_go)
    if no_go:
        status = "blocked"
        next_actions = ["resolve_manifest_adoption_go_no_go_blockers", "rebuild_integration_review_manifest_adoption_go_no_go"]
    elif any(item.status == "needs_review" for item in items):
        status = "needs_review"
        next_actions = ["complete_manifest_adoption_rollback_preview", "rebuild_integration_review_manifest_adoption_go_no_go"]
    else:
        status = "ready"
        next_actions = ["share_manifest_adoption_go_no_go_with_mainline"]
    return {
        "kind": "integration_review_manifest_adoption_go_no_go",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "go_candidates": go,
        "hold_candidates": hold,
        "no_go_candidates": no_go,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("decisions"):
        return _as_sequence(data.get("decisions"))
    return _as_sequence(_as_mapping(data.get("manifest_adoption_rollback_preview")).get("items"))


def _decision_from(status: str, recommended: str) -> str:
    if status == "blocked":
        return "no_go"
    if status == "needs_review":
        return "hold"
    if recommended in {"adopt", "integrate"}:
        return "go"
    return "hold"


def _index(raw: Any) -> dict[str, dict[str, Any]]:
    return {str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item) for item in _as_sequence(raw)}


def _candidate_ids(items: Any) -> list[str]:
    result: list[str] = []
    for item in items:
        if item.candidate_id and item.candidate_id not in result:
            result.append(item.candidate_id)
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
