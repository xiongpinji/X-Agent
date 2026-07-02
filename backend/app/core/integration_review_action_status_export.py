from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


ALLOWED_FORMATS = ("markdown", "json", "csv", "summary")


@dataclass(frozen=True)
class ReviewActionStatusExportRow:
    candidate_id: str
    status_key: str
    status: str
    lane: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    priority: str = "medium"
    export_formats: tuple[str, ...] = ("summary",)
    blockers: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status_key": self.status_key,
            "status": self.status,
            "lane": self.lane,
            "evidence_refs": list(self.evidence_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "priority": self.priority,
            "export_formats": list(self.export_formats),
            "blockers": list(self.blockers),
            "reasons": list(self.reasons),
        }


def summarize_review_action_status_export_row(
    row: Mapping[str, Any] | Any,
    *,
    formats: Sequence[str] | None = None,
    validation_index: Mapping[str, Mapping[str, Any]] | None = None,
) -> ReviewActionStatusExportRow:
    payload = _as_mapping(row)
    candidate_id = str(payload.get("candidate_id") or "")
    status_key = str(payload.get("status_key") or candidate_id)
    validation = dict((validation_index or {}).get(candidate_id, {}))
    status = str(validation.get("status") or payload.get("status") or "needs_review")
    evidence_refs = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(validation.get("refs"))))
    owner = str(payload.get("owner") or "")
    reviewer = str(payload.get("reviewer") or payload.get("primary_reviewer") or "")
    blockers = tuple(str(item) for item in (_as_sequence(validation.get("blockers")) or _as_sequence(payload.get("blockers"))))
    priority = str(payload.get("priority") or "medium")
    if status == "blocked":
        priority = "high"
    export_formats = tuple(_formats(_as_sequence(payload.get("export_formats")) or list(formats or ("summary",))))
    reasons: list[str] = []
    if not evidence_refs:
        reasons.append("export evidence missing")
    if not owner:
        reasons.append("owner missing")
    if not reviewer:
        reasons.append("reviewer missing")
    lane = str(payload.get("lane") or status)
    return ReviewActionStatusExportRow(
        candidate_id=candidate_id,
        status_key=status_key,
        status=status,
        lane=lane,
        evidence_refs=evidence_refs,
        owner=owner,
        reviewer=reviewer,
        priority=priority,
        export_formats=export_formats,
        blockers=blockers,
        reasons=tuple(reasons),
    )


def build_integration_review_action_status_export(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_rows = _rows(data)
    if not raw_rows:
        return {
            "kind": "integration_review_action_status_export",
            "export_id": str(data.get("export_id") or ""),
            "ok": False,
            "status": "empty",
            "formats": _formats(_as_sequence(data.get("formats"))),
            "summary": {"row_count": 0},
            "rows": [],
            "sections": {},
            "missing_inputs": {},
            "render_hints": {"write_files": False},
            "next_actions": ["provide_review_action_status_export_inputs"],
        }
    formats = _formats(_as_sequence(data.get("formats")))
    validation_index = _validation_index(data.get("validation_evidence"))
    rows = [
        summarize_review_action_status_export_row(row, formats=formats, validation_index=validation_index)
        for row in raw_rows
    ]
    blocked = [row.candidate_id for row in rows if row.status == "blocked"]
    review = [row.candidate_id for row in rows if row.status == "needs_review" or row.reasons]
    missing = {row.status_key: list(row.reasons) for row in rows if row.reasons}
    if blocked:
        status = "blocked"
        next_actions = [
            "resolve_review_action_status_export_blockers",
            "attach_export_evidence",
            "rebuild_integration_review_action_status_export",
        ]
    elif review:
        status = "needs_review"
        next_actions = ["complete_review_action_status_export", "attach_export_evidence", "rebuild_integration_review_action_status_export"]
    else:
        status = "ready"
        next_actions = ["share_review_action_status_export_with_mainline"]
    row_dicts = [row.as_dict() for row in rows]
    return {
        "kind": "integration_review_action_status_export",
        "export_id": str(data.get("export_id") or ""),
        "ok": status == "ready",
        "status": status,
        "formats": formats,
        "summary": {"row_count": len(rows), "blocked_count": len(blocked), "needs_review_count": len(review)},
        "rows": row_dicts,
        "sections": _sections(row_dicts),
        "missing_inputs": missing,
        "blocked_candidates": blocked,
        "review_candidates": review,
        "render_hints": {"write_files": False},
        "next_actions": next_actions,
    }


def _rows(data: Mapping[str, Any]) -> list[Any]:
    if data.get("rows"):
        return _as_sequence(data.get("rows"))
    board = _as_mapping(data.get("action_status_board"))
    return _as_sequence(board.get("items"))


def _validation_index(raw: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _as_sequence(raw):
        payload = _as_mapping(item)
        result[str(payload.get("candidate_id") or "")] = payload
    return result


def _sections(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(str(row.get("lane") or row.get("status") or "needs_review"), []).append(dict(row))
    return result


def _formats(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values or ("summary",):
        text = str(value)
        if text in ALLOWED_FORMATS and text not in result:
            result.append(text)
    return result or ["summary"]


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
