from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


READY_STATUSES = {"ready", "passed", "secondary_review_ready"}
BLOCKED_STATUSES = {"blocked", "failed", "error"}
COMPARE_FIELDS = ("stage_label", "review_status", "owner", "files", "tests", "evidence_refs", "handoff_refs", "risk_refs")


@dataclass(frozen=True)
class ManifestDiffEntry:
    candidate_id: str
    change_type: str
    previous_stage: str = ""
    proposed_stage: str = ""
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    risk_change: str = "unchanged"
    readiness_change: str = "unchanged"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "change_type": self.change_type,
            "previous_stage": self.previous_stage,
            "proposed_stage": self.proposed_stage,
            "changed_fields": list(self.changed_fields),
            "risk_change": self.risk_change,
            "readiness_change": self.readiness_change,
        }


def summarize_manifest_diff_entry(entry: Mapping[str, Any] | Any) -> ManifestDiffEntry:
    payload = _as_mapping(entry)
    return ManifestDiffEntry(
        candidate_id=str(payload.get("candidate_id") or ""),
        change_type=str(payload.get("change_type") or "unchanged"),
        previous_stage=str(payload.get("previous_stage") or payload.get("previous_status") or ""),
        proposed_stage=str(payload.get("proposed_stage") or payload.get("proposed_status") or ""),
        changed_fields=tuple(str(field) for field in _as_sequence(payload.get("changed_fields"))),
        risk_change=str(payload.get("risk_change") or "unchanged"),
        readiness_change=str(payload.get("readiness_change") or "unchanged"),
    )


def build_integration_manifest_diff_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    previous_entries = _manifest_entries(data.get("previous_manifest"))
    proposed_entries = _manifest_entries(data.get("proposed_manifest"))
    if not previous_entries and not proposed_entries:
        return {
            "kind": "integration_manifest_diff_summary",
            "diff_id": str(data.get("diff_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {
                "entry_count": 0,
                "added_count": 0,
                "removed_count": 0,
                "changed_count": 0,
                "unchanged_count": 0,
            },
            "entries": [],
            "added_candidates": [],
            "removed_candidates": [],
            "changed_candidates": [],
            "next_actions": ["provide_previous_and_proposed_manifests"],
        }

    previous_by_id = {str(entry.get("candidate_id") or ""): entry for entry in previous_entries}
    proposed_by_id = {str(entry.get("candidate_id") or ""): entry for entry in proposed_entries}
    candidate_ids = sorted((set(previous_by_id) | set(proposed_by_id)) - {""})
    entries = [_diff_entry(candidate_id, previous_by_id.get(candidate_id), proposed_by_id.get(candidate_id)) for candidate_id in candidate_ids]
    added = [entry.candidate_id for entry in entries if entry.change_type == "added"]
    removed = [entry.candidate_id for entry in entries if entry.change_type == "removed"]
    changed = [entry.candidate_id for entry in entries if entry.change_type == "changed"]
    risk_increases = [entry.candidate_id for entry in entries if entry.risk_change == "increased"]
    readiness_regressions = [entry.candidate_id for entry in entries if entry.readiness_change == "regressed"]
    status = "needs_review" if risk_increases or readiness_regressions else "ready"

    next_actions: list[str] = []
    if risk_increases:
        next_actions.append("review_manifest_risk_increases")
    if readiness_regressions:
        next_actions.append("review_manifest_readiness_regressions")
    if removed:
        next_actions.append("review_removed_manifest_candidates")
    if changed:
        next_actions.append("review_changed_manifest_candidates")
    next_actions.append("rebuild_integration_manifest_diff_summary" if next_actions else "share_manifest_diff_summary_with_mainline")

    return {
        "kind": "integration_manifest_diff_summary",
        "diff_id": str(data.get("diff_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "entry_count": len(entries),
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "unchanged_count": sum(1 for entry in entries if entry.change_type == "unchanged"),
            "risk_increase_count": len(risk_increases),
            "readiness_regression_count": len(readiness_regressions),
        },
        "entries": [entry.as_dict() for entry in entries],
        "added_candidates": added,
        "removed_candidates": removed,
        "changed_candidates": changed,
        "next_actions": next_actions,
    }


def _diff_entry(candidate_id: str, previous: Mapping[str, Any] | None, proposed: Mapping[str, Any] | None) -> ManifestDiffEntry:
    if previous is None:
        return ManifestDiffEntry(
            candidate_id=candidate_id,
            change_type="added",
            previous_stage="",
            proposed_stage=str(proposed.get("stage_label") or "") if proposed else "",
            risk_change="increased" if _risk_count(proposed) else "unchanged",
            readiness_change="improved" if _readiness_rank(proposed) == 2 else "unchanged",
        )
    if proposed is None:
        return ManifestDiffEntry(
            candidate_id=candidate_id,
            change_type="removed",
            previous_stage=str(previous.get("stage_label") or ""),
            proposed_stage="",
            risk_change="reduced" if _risk_count(previous) else "unchanged",
            readiness_change="regressed" if _readiness_rank(previous) == 2 else "unchanged",
        )
    changed_fields = tuple(field for field in COMPARE_FIELDS if previous.get(field) != proposed.get(field))
    return ManifestDiffEntry(
        candidate_id=candidate_id,
        change_type="changed" if changed_fields else "unchanged",
        previous_stage=str(previous.get("stage_label") or ""),
        proposed_stage=str(proposed.get("stage_label") or ""),
        changed_fields=changed_fields,
        risk_change=_risk_change(previous, proposed),
        readiness_change=_readiness_change(previous, proposed),
    )


def _manifest_entries(manifest: Any) -> list[dict[str, Any]]:
    payload = _as_mapping(manifest)
    raw = payload.get("entries") or payload.get("candidates") or []
    return [_as_mapping(entry) for entry in _as_sequence(raw)]


def _risk_change(previous: Mapping[str, Any], proposed: Mapping[str, Any]) -> str:
    before = _risk_count(previous)
    after = _risk_count(proposed)
    if after > before:
        return "increased"
    if after < before:
        return "reduced"
    return "unchanged"


def _readiness_change(previous: Mapping[str, Any], proposed: Mapping[str, Any]) -> str:
    before = _readiness_rank(previous)
    after = _readiness_rank(proposed)
    if after > before:
        return "improved"
    if after < before:
        return "regressed"
    return "unchanged"


def _risk_count(entry: Mapping[str, Any] | None) -> int:
    if not entry:
        return 0
    return len(_as_sequence(entry.get("risk_refs") or entry.get("risks")))


def _readiness_rank(entry: Mapping[str, Any] | None) -> int:
    if not entry:
        return 0
    status = str(entry.get("review_status") or entry.get("status") or "").lower()
    if status in READY_STATUSES:
        return 2
    if status in BLOCKED_STATUSES:
        return 0
    return 1


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []
