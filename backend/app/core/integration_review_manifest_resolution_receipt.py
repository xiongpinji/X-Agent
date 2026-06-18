from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewManifestResolutionReceiptItem:
    candidate_id: str
    receipt_key: str
    status: str
    receipt_state: str
    recommended_decision: str
    candidate_paths: tuple[str, ...] = field(default_factory=tuple)
    validation_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    signoffs: tuple[str, ...] = field(default_factory=tuple)
    missing_signoffs: tuple[str, ...] = field(default_factory=tuple)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "receipt_key": self.receipt_key,
            "status": self.status,
            "receipt_state": self.receipt_state,
            "recommended_decision": self.recommended_decision,
            "candidate_paths": list(self.candidate_paths),
            "validation_refs": list(self.validation_refs),
            "handoff_refs": list(self.handoff_refs),
            "signoffs": list(self.signoffs),
            "missing_signoffs": list(self.missing_signoffs),
            "blockers": list(self.blockers),
        }


def summarize_review_manifest_resolution_receipt_item(
    item: Mapping[str, Any] | Any,
    *,
    validation_index: Mapping[str, Sequence[str]] | None = None,
    signoff_index: Mapping[str, Sequence[str]] | None = None,
) -> ReviewManifestResolutionReceiptItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    status = str(payload.get("status") or "needs_review")
    validation_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("validation_refs")) or (validation_index or {}).get(candidate_id, ())))
    signoffs = tuple(str(ref) for ref in (_as_sequence(payload.get("signoffs")) or (signoff_index or {}).get(candidate_id, ())))
    blockers = tuple(str(ref) for ref in _as_sequence(payload.get("blockers")))
    required = []
    if payload.get("owner"):
        required.append("owner")
    if payload.get("reviewer"):
        required.append("reviewer")
    missing = tuple(ref for ref in required if ref not in signoffs)
    if status == "blocked" or blockers:
        status = "blocked"
        state = "blocked"
    elif missing:
        status = "needs_review"
        state = "needs_signoff"
    else:
        status = "ready"
        state = "review_ready"
    return ReviewManifestResolutionReceiptItem(
        candidate_id=candidate_id,
        receipt_key=str(payload.get("receipt_key") or payload.get("plan_key") or candidate_id),
        status=status,
        receipt_state=state,
        recommended_decision=str(payload.get("recommended_decision") or ""),
        candidate_paths=tuple(str(path) for path in _as_sequence(payload.get("candidate_paths"))),
        validation_refs=validation_refs,
        handoff_refs=tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs"))),
        signoffs=signoffs,
        missing_signoffs=missing,
        blockers=blockers,
    )


def build_integration_review_manifest_resolution_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _items(data)
    if not raw:
        return {
            "kind": "integration_review_manifest_resolution_receipt",
            "ok": False,
            "status": "empty",
            "items": [],
            "ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_manifest_resolution_receipt_inputs"],
        }
    validation_index = _validation_index(data.get("validation_evidence"))
    signoff_index = _signoff_index(data.get("signoffs"))
    items = [summarize_review_manifest_resolution_receipt_item(item, validation_index=validation_index, signoff_index=signoff_index) for item in raw]
    blocked = [item.candidate_id for item in items if item.status == "blocked"]
    review = [item.candidate_id for item in items if item.status == "needs_review"]
    ready = [item.candidate_id for item in items if item.status == "ready"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_resolution_receipt_blockers", "rebuild_integration_review_manifest_resolution_receipt"]
    elif review:
        status = "needs_review"
        next_actions = ["collect_manifest_resolution_signoffs", "rebuild_integration_review_manifest_resolution_receipt"]
    else:
        status = "ready"
        next_actions = ["share_manifest_resolution_receipt_with_mainline"]
    return {
        "kind": "integration_review_manifest_resolution_receipt",
        "ok": status == "ready",
        "status": status,
        "items": [item.as_dict() for item in items],
        "ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("receipts"):
        return _as_sequence(data.get("receipts"))
    plan = _as_mapping(data.get("manifest_conflict_resolution_plan"))
    return _as_sequence(plan.get("items"))


def _validation_index(raw: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if isinstance(raw, Mapping):
        for candidate_id, payload in raw.items():
            result[str(candidate_id)] = [str(ref) for ref in _as_sequence(_as_mapping(payload).get("validation_refs"))]
    return result


def _signoff_index(raw: Any) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if isinstance(raw, Mapping):
        for candidate_id, payload in raw.items():
            result[str(candidate_id)] = [str(key) for key, value in _as_mapping(payload).items() if value == "approved"]
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
