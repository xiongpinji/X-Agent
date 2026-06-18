from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewQueryResultDigestItem:
    candidate_id: str
    query_key: str
    status: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    matched_refs: tuple[str, ...] = field(default_factory=tuple)
    missing_refs: tuple[str, ...] = field(default_factory=tuple)
    owner: str = ""
    reviewer: str = ""
    result_count: int = 0
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "query_key": self.query_key,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "matched_refs": list(self.matched_refs),
            "missing_refs": list(self.missing_refs),
            "owner": self.owner,
            "reviewer": self.reviewer,
            "result_count": self.result_count,
            "reasons": list(self.reasons),
        }


def summarize_review_query_result_digest_item(
    item: Mapping[str, Any] | Any,
    *,
    result_items: Sequence[Mapping[str, Any]] | None = None,
    blocked_refs: Sequence[str] | None = None,
) -> ReviewQueryResultDigestItem:
    payload = _as_mapping(item)
    candidate_id = str(payload.get("candidate_id") or "unknown")
    query_key = str(payload.get("query_key") or f"query:{candidate_id}")
    results = [_as_mapping(result) for result in (result_items or [])]
    evidence_refs = tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    matched_refs = tuple(
        _unique(
            [
                *[str(ref) for ref in _as_sequence(payload.get("matched_refs"))],
                *[str(ref) for result in results for ref in _as_sequence(result.get("matched_refs"))],
            ]
        )
    )
    result_count = len(results) if results else (1 if payload.get("matched_refs") else 0)
    blocked_ref_set = set(blocked_refs or [])
    raw_statuses = [str(payload.get("status") or "")] + [str(result.get("status") or "") for result in results]
    missing_refs = tuple(ref for ref in evidence_refs if ref not in matched_refs)
    reasons: list[str] = []
    if "blocked" in raw_statuses or any(ref in blocked_ref_set for ref in matched_refs):
        reasons.append("query result source blocked")
    if not evidence_refs:
        reasons.append("expected refs missing")
    elif not matched_refs:
        reasons.append("query results missing")
    elif missing_refs:
        reasons.append("query refs incomplete")
    if reasons and reasons[0] == "query result source blocked":
        status = "blocked"
    elif reasons:
        status = "needs_review"
    else:
        status = "ready"
    return ReviewQueryResultDigestItem(
        candidate_id=candidate_id,
        query_key=query_key,
        status=status,
        evidence_refs=evidence_refs,
        matched_refs=matched_refs,
        missing_refs=missing_refs,
        owner=str(payload.get("owner") or ""),
        reviewer=str(payload.get("reviewer") or ""),
        result_count=result_count,
        reasons=tuple(reasons),
    )


def build_integration_review_query_result_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_items = _items(data)
    if not raw_items:
        return {
            "kind": "integration_review_query_result_digest",
            "ok": False,
            "status": "empty",
            "digests": [],
            "blocked_queries": [],
            "review_queries": [],
            "missing_refs": {},
            "next_actions": ["provide_review_query_result_digest_inputs"],
        }
    results = [_as_mapping(item) for item in _as_sequence(data.get("query_results"))]
    blocked_refs = [
        str(record.get("ref") or "")
        for record in _as_sequence(_as_mapping(data.get("review_evidence_index")).get("records"))
        if str(_as_mapping(record).get("status") or "") == "blocked"
        for record in [_as_mapping(record)]
    ]
    digests = [
        summarize_review_query_result_digest_item(
            item,
            result_items=_matching_results(item, results),
            blocked_refs=blocked_refs,
        )
        for item in raw_items
    ]
    blocked = [item.query_key for item in digests if item.status == "blocked"]
    review = [item.query_key for item in digests if item.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_review_query_result_blockers", "rebuild_integration_review_query_result_digest"]
    elif review:
        status = "needs_review"
        next_actions = ["attach_review_query_result_payloads", "rebuild_integration_review_query_result_digest"]
    else:
        status = "ready"
        next_actions = ["share_review_query_result_digest_with_mainline"]
    return {
        "kind": "integration_review_query_result_digest",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "digest_count": len(digests),
            "result_count": sum(item.result_count for item in digests),
            "ready_count": len([item for item in digests if item.status == "ready"]),
            "blocked_count": len(blocked),
            "review_count": len(review),
        },
        "digests": [item.as_dict() for item in digests],
        "blocked_queries": blocked,
        "review_queries": review,
        "missing_refs": {item.query_key: list(item.missing_refs) for item in digests if item.missing_refs},
        "next_actions": next_actions,
    }


def _items(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    queries = [_as_mapping(item) for item in _as_sequence(_as_mapping(data.get("review_query_plan")).get("queries"))]
    if queries:
        return queries
    return [_as_mapping(item) for item in _as_sequence(data.get("query_results"))]


def _matching_results(item: Mapping[str, Any] | Any, results: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    payload = _as_mapping(item)
    query_key = str(payload.get("query_key") or "")
    candidate_id = str(payload.get("candidate_id") or "")
    return [
        result
        for result in results
        if (query_key and str(result.get("query_key") or "") == query_key)
        or (not query_key and candidate_id and str(result.get("candidate_id") or "") == candidate_id)
    ]


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
