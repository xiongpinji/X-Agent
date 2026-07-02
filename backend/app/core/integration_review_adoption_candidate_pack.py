from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewAdoptionCandidatePack:
    candidate_id: str
    pack_key: str
    adoption_state: str
    status: str
    files: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    handoff_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "pack_key": self.pack_key,
            "adoption_state": self.adoption_state,
            "status": self.status,
            "files": list(self.files),
            "tests": list(self.tests),
            "evidence_refs": list(self.evidence_refs),
            "handoff_refs": list(self.handoff_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_adoption_candidate_pack(
    item: Mapping[str, Any] | Any,
    *,
    file_ref_index: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
) -> ReviewAdoptionCandidatePack:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "")
    file_refs = dict((file_ref_index or {}).get(candidate_id, {}))
    files = tuple(str(ref) for ref in (_as_sequence(payload.get("files")) or _as_sequence(file_refs.get("files"))))
    tests = tuple(str(ref) for ref in (_as_sequence(payload.get("tests")) or _as_sequence(file_refs.get("tests"))))
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    handoff_refs = tuple(str(ref) for ref in _as_sequence(payload.get("handoff_refs")))
    status = str(payload.get("status") or "needs_review")
    adoption_state = str(payload.get("adoption_state") or ("adoption_ready" if payload.get("verdict") in {"accept", "accepted"} and status == "ready" else status))
    reasons: list[str] = []
    if not files:
        reasons.append("candidate files missing")
    if not tests:
        reasons.append("candidate tests missing")
    if not handoff_refs:
        reasons.append("handoff refs missing")
    if status == "blocked" or payload.get("verdict") == "blocked":
        status = "blocked"
        adoption_state = "blocked"
        reasons.append("candidate source blocked")
    elif reasons:
        status = "needs_review"
        if adoption_state == "adoption_ready":
            adoption_state = "needs_review"
    return ReviewAdoptionCandidatePack(
        candidate_id=candidate_id,
        pack_key=str(payload.get("pack_key") or payload.get("rollup_key") or candidate_id),
        adoption_state=adoption_state,
        status=status,
        files=files,
        tests=tests,
        evidence_refs=evidence_refs,
        handoff_refs=handoff_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        blockers=tuple(str(item) for item in _as_sequence(payload.get("blockers"))),
        reasons=tuple(reasons),
    )


def build_integration_review_adoption_candidate_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _pack_items(data)
    if not raw:
        return {
            "kind": "integration_review_adoption_candidate_pack",
            "pack_id": str(data.get("pack_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"pack_count": 0, "adoption_ready_count": 0},
            "packs": [],
            "adoption_ready_candidates": [],
            "blocked_candidates": [],
            "review_candidates": [],
            "next_actions": ["provide_review_adoption_candidate_pack_inputs"],
        }
    file_ref_index = _file_ref_index(data.get("file_refs"))
    packs = [summarize_review_adoption_candidate_pack(item, file_ref_index=file_ref_index) for item in raw]
    ready = [item.candidate_id for item in packs if item.status == "ready" and item.adoption_state == "adoption_ready"]
    blocked = [item.candidate_id for item in packs if item.status == "blocked"]
    review = [item.candidate_id for item in packs if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_adoption_candidate_blockers",
            "attach_adoption_candidate_evidence",
            "rebuild_integration_review_adoption_candidate_pack",
        ]
    elif review:
        status = "needs_review"
        reasons = [reason for item in packs for reason in item.reasons]
        actions = ["complete_review_adoption_candidate_pack"]
        if "candidate files missing" in reasons:
            actions.append("attach_adoption_candidate_files")
        if "candidate tests missing" in reasons:
            actions.append("attach_adoption_candidate_tests")
        if "handoff refs missing" in reasons:
            actions.append("attach_adoption_candidate_handoff_refs")
        next_actions = actions + ["rebuild_integration_review_adoption_candidate_pack"]
    else:
        status = "ready"
        next_actions = ["share_review_adoption_candidate_pack_with_mainline"]
    return {
        "kind": "integration_review_adoption_candidate_pack",
        "pack_id": str(data.get("pack_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {"pack_count": len(packs), "adoption_ready_count": len(ready)},
        "packs": [item.as_dict() for item in packs],
        "adoption_ready_candidates": ready,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "next_actions": _unique(next_actions),
    }


def _pack_items(data: Mapping[str, Any]) -> list[Any]:
    if data.get("packs"):
        return _as_sequence(data.get("packs"))
    rollup = _as_mapping(data.get("acceptance_rollup"))
    return _as_sequence(rollup.get("items"))


def _file_ref_index(raw: Any) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    if isinstance(raw, Mapping):
        for candidate_id, value in raw.items():
            payload = _as_mapping(value)
            result[str(candidate_id)] = {
                "files": [str(ref) for ref in _as_sequence(payload.get("files"))],
                "tests": [str(ref) for ref in _as_sequence(payload.get("tests"))],
            }
    else:
        for item in _as_sequence(raw):
            payload = _as_mapping(item)
            result[str(payload.get("candidate_id") or "")] = {
                "files": [str(ref) for ref in _as_sequence(payload.get("files"))],
                "tests": [str(ref) for ref in _as_sequence(payload.get("tests"))],
            }
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
