from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewQueryPlanItem:
    candidate_id: str
    query_key: str
    status: str
    filters: dict[str, list[str]]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "query_key": self.query_key,
            "status": self.status,
            "filters": {key: list(values) for key, values in self.filters.items()},
            "evidence_refs": list(self.evidence_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "reasons": list(self.reasons),
        }


def summarize_review_query_plan_item(item: Mapping[str, Any] | Any) -> ReviewQueryPlanItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "unknown")
    query_key = str(payload.get("query_key") or f"review-query:{candidate_id}")
    filters = _filters(payload, candidate_id)
    evidence_refs = tuple(
        str(ref)
        for ref in (
            _as_sequence(payload.get("evidence_refs"))
            or _as_sequence(payload.get("refs"))
            or _as_sequence(payload.get("ref"))
        )
    )
    owner = str(payload.get("owner") or "")
    reviewer = str(payload.get("reviewer") or "")
    raw_status = str(payload.get("status") or "ready")
    blockers = tuple(str(blocker) for blocker in _as_sequence(payload.get("blockers")))
    reasons: list[str] = []
    if raw_status == "blocked" or blockers:
        reasons.append("query source blocked")
    if candidate_id == "unknown":
        reasons.append("candidate id missing")
    if not evidence_refs:
        reasons.append("evidence refs missing")
    if not owner:
        reasons.append("owner hint missing")
    if not reviewer:
        reasons.append("reviewer hint missing")
    if raw_status == "blocked" or blockers:
        status = "blocked"
    elif reasons:
        status = "needs_review"
    else:
        status = "ready"
    return ReviewQueryPlanItem(
        candidate_id=candidate_id,
        query_key=query_key,
        status=status,
        filters=filters,
        evidence_refs=evidence_refs,
        owner=owner,
        reviewer=reviewer,
        reasons=tuple(reasons),
    )


def build_integration_review_query_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_items = _items(data)
    if not raw_items:
        return {
            "kind": "integration_review_query_plan",
            "ok": False,
            "status": "empty",
            "queries": [],
            "blocked_queries": [],
            "review_queries": [],
            "next_actions": ["provide_review_query_plan_inputs"],
        }
    queries = [summarize_review_query_plan_item(item) for item in raw_items]
    blocked = [item.query_key for item in queries if item.status == "blocked"]
    review = [item.query_key for item in queries if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_query_plan_blockers", "rebuild_integration_review_query_plan"]
    elif review:
        status = "needs_review"
        next_actions = ["complete_review_query_plan", "rebuild_integration_review_query_plan"]
    else:
        status = "ready"
        next_actions = ["share_review_query_plan_with_mainline"]
    return {
        "kind": "integration_review_query_plan",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "query_count": len(queries),
            "ready_count": len([item for item in queries if item.status == "ready"]),
            "blocked_count": len(blocked),
            "review_count": len(review),
        },
        "queries": [item.as_dict() for item in queries],
        "blocked_queries": blocked,
        "review_queries": review,
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("queries"):
        return [_query_payload(_as_mapping(item), data) for item in _as_sequence(data.get("queries"))]
    records = [_as_mapping(item) for item in _as_sequence(_as_mapping(data.get("review_evidence_index")).get("records"))]
    candidate_filters = [_as_mapping(item) for item in _as_sequence(data.get("candidate_filters"))]
    retention = [_as_mapping(item) for item in _as_sequence(_as_mapping(data.get("review_retention_policy")).get("decisions"))]
    candidate_ids = _unique(
        [
            str(item.get("candidate_id") or "")
            for item in [*records, *candidate_filters, *retention]
            if item.get("candidate_id")
        ]
    )
    return [_candidate_payload(candidate_id, records, candidate_filters, retention, data) for candidate_id in candidate_ids]


def _query_payload(item: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = str(item.get("candidate_id") or "unknown")
    merged = dict(item)
    merged["candidate_id"] = candidate_id
    merged["owner"] = item.get("owner") or _as_mapping(data.get("owner_hints")).get(candidate_id) or ""
    merged["reviewer"] = item.get("reviewer") or _as_mapping(data.get("reviewer_hints")).get(candidate_id) or ""
    merged["sources"] = _unique(
        [
            *_as_sequence(_as_mapping(data.get("filters")).get("source")),
            *_as_sequence(item.get("sources")),
            *_as_sequence(item.get("source")),
        ]
    )
    merged["ref_types"] = _unique(
        [
            *_as_sequence(_as_mapping(data.get("filters")).get("ref_type")),
            *_as_sequence(item.get("ref_types")),
            *_as_sequence(item.get("ref_type")),
        ]
    )
    return merged


def _candidate_payload(
    candidate_id: str,
    records: Sequence[Mapping[str, Any]],
    candidate_filters: Sequence[Mapping[str, Any]],
    retention: Sequence[Mapping[str, Any]],
    data: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_records = [item for item in records if str(item.get("candidate_id") or "") == candidate_id]
    candidate_filter = next((item for item in candidate_filters if str(item.get("candidate_id") or "") == candidate_id), {})
    retention_decision = next((item for item in retention if str(item.get("candidate_id") or "") == candidate_id), {})
    evidence_refs = _unique([str(item.get("ref") or "") for item in candidate_records] + [str(ref) for ref in _as_sequence(retention_decision.get("evidence_refs"))])
    sources = _unique(
        [
            *[str(value) for value in _as_sequence(_as_mapping(data.get("filters")).get("source"))],
            *[str(value) for value in _as_sequence(candidate_filter.get("sources"))],
            *[str(item.get("source") or "") for item in candidate_records],
        ]
    )
    ref_types = _unique(
        [
            *[str(value) for value in _as_sequence(_as_mapping(data.get("filters")).get("ref_type"))],
            *[str(value) for value in _as_sequence(candidate_filter.get("ref_types"))],
            *[str(item.get("ref_type") or "") for item in candidate_records],
        ]
    )
    status = "blocked" if any(str(item.get("status") or "") == "blocked" for item in [*candidate_records, retention_decision]) else "ready"
    return {
        "candidate_id": candidate_id,
        "query_key": candidate_filter.get("query_key") or f"review-query:{candidate_id}",
        "status": status,
        "sources": sources,
        "ref_types": ref_types,
        "evidence_refs": evidence_refs,
        "owner": candidate_filter.get("owner")
        or retention_decision.get("owner")
        or _as_mapping(data.get("owner_hints")).get(candidate_id)
        or next((item.get("owner") for item in candidate_records if item.get("owner")), ""),
        "reviewer": candidate_filter.get("reviewer") or _as_mapping(data.get("reviewer_hints")).get(candidate_id) or "",
    }


def _filters(payload: Mapping[str, Any], candidate_id: str) -> dict[str, list[str]]:
    raw = _as_mapping(payload.get("filters"))
    result: dict[str, list[str]] = {}
    if candidate_id != "unknown":
        result["candidate_id"] = [candidate_id]
    sources = _unique([str(value) for value in _as_sequence(raw.get("source")) + _as_sequence(payload.get("sources")) + _as_sequence(payload.get("source"))])
    ref_types = _unique([str(value) for value in _as_sequence(raw.get("ref_type")) + _as_sequence(payload.get("ref_types")) + _as_sequence(payload.get("ref_type"))])
    if sources:
        result["source"] = sources
    if ref_types:
        result["ref_type"] = ref_types
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
