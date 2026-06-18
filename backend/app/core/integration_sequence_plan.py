from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SequenceCandidate:
    candidate_id: str
    owner: str
    recommendation: str
    priority_score: float
    state: str
    phase: str
    order_index: int
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "owner": self.owner,
            "recommendation": self.recommendation,
            "priority_score": self.priority_score,
            "state": self.state,
            "phase": self.phase,
            "order_index": self.order_index,
            "reasons": list(self.reasons),
        }


def analyze_sequence_candidate(
    candidate: Mapping[str, Any] | Any,
    *,
    decision: Mapping[str, Any] | Any | None = None,
    dependency: Mapping[str, Any] | Any | None = None,
    readiness_state: str = "ready",
    order_index: int = 0,
) -> SequenceCandidate:
    payload = _as_mapping(candidate)
    decision_payload = _as_mapping(decision)
    dependency_payload = _as_mapping(dependency)
    candidate_id = str(payload.get("candidate_id") or "")
    decision_value = str(decision_payload.get("decision") or "")
    dependency_state = str(dependency_payload.get("state") or "ready")
    reasons: list[str] = []
    if dependency_state == "blocked" or readiness_state == "blocked":
        state = "blocked"
        phase = "blocked"
        reasons.append("candidate dependency blocked")
    elif not decision_payload or decision_value not in {"accepted", "accept", "approved"}:
        state = "needs_review"
        phase = "review_required"
        reasons.append("candidate needs review")
    else:
        state = "ready"
        phase = "ordered_integration"
        reasons.append("candidate ready for ordered integration")
    return SequenceCandidate(
        candidate_id=candidate_id,
        owner=str(payload.get("owner") or dependency_payload.get("owner") or decision_payload.get("owner") or ""),
        recommendation=str(payload.get("recommendation") or ""),
        priority_score=_score(payload.get("priority_score")),
        state=state,
        phase=phase,
        order_index=order_index,
        reasons=tuple(reasons),
    )


def build_integration_sequence_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    components = _components(data)
    scorecard = _component(data, components, "scorecard", "integration_candidate_scorecard")
    dependency_map = _component(data, components, "dependency_map", "candidate_dependency_map")
    decision_audit = _component(data, components, "decision_audit", "integration_decision_audit")
    readiness_snapshot = _component(data, components, "readiness_snapshot", "integration_readiness_snapshot")
    raw_candidates = [_as_mapping(item) for item in _as_sequence(scorecard.get("candidates"))]
    if not raw_candidates:
        return {
            "kind": "integration_sequence_plan",
            "plan_id": str(data.get("plan_id") or ""),
            "ok": False,
            "status": "empty",
            "candidates": [],
            "integration_order": [],
            "phases": [],
            "blocked_candidates": [],
            "review_queue": [],
            "issues": [],
            "next_actions": ["provide_sequence_plan_inputs"],
        }

    dependency_index = {
        str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item)
        for item in _as_sequence(dependency_map.get("candidates"))
    }
    decision_index = {
        str(_as_mapping(item).get("candidate_id") or ""): _as_mapping(item)
        for item in _as_sequence(decision_audit.get("decisions"))
    }
    order = [str(item) for item in _as_sequence(dependency_map.get("integration_order"))]
    if not order:
        order = [
            str(item.get("candidate_id") or "")
            for item in sorted(raw_candidates, key=lambda row: _score(row.get("priority_score")), reverse=True)
        ]
    order_index = {candidate_id: index for index, candidate_id in enumerate(order)}
    readiness_state = str(readiness_snapshot.get("status") or "ready")
    candidates = [
        analyze_sequence_candidate(
            candidate,
            decision=decision_index.get(str(candidate.get("candidate_id") or "")),
            dependency=dependency_index.get(str(candidate.get("candidate_id") or ""), {"state": "ready"}),
            readiness_state=readiness_state,
            order_index=order_index.get(str(candidate.get("candidate_id") or ""), len(order_index)),
        )
        for candidate in raw_candidates
    ]
    candidates = sorted(candidates, key=lambda item: item.order_index)
    blocked = [item.candidate_id for item in candidates if item.state == "blocked"]
    review = [item.candidate_id for item in candidates if item.state == "needs_review"]
    issues: list[dict[str, Any]] = []
    if str(dependency_map.get("status") or "") == "blocked" or blocked:
        status = "blocked"
        blocked = blocked or [str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(dependency_map.get("candidates")) if str(_as_mapping(item).get("state") or "") == "blocked"]
        issues.append({"code": "integration_sequence_dependency_map_blocked", "severity": "high"})
        next_actions = ["resolve_sequence_blockers", "rebuild_integration_sequence_plan"]
    elif review:
        status = "needs_review"
        issues.append({"code": "integration_sequence_decision_missing", "severity": "medium"})
        next_actions = ["record_missing_integration_decisions", "rebuild_integration_sequence_plan"]
    else:
        status = "ready"
        next_actions = ["prepare_traceable_integration_sequence"]

    integration_order = [candidate_id for candidate_id in order if candidate_id]
    return {
        "kind": "integration_sequence_plan",
        "plan_id": str(data.get("plan_id") or ""),
        "ok": status == "ready",
        "status": status,
        "candidates": [item.as_dict() for item in candidates],
        "integration_order": integration_order,
        "phases": _phases(candidates, status),
        "blocked_candidates": blocked,
        "review_queue": review,
        "issues": issues,
        "next_actions": next_actions,
    }


def _phases(candidates: Sequence[SequenceCandidate], status: str) -> list[dict[str, Any]]:
    if status != "ready":
        return []
    ready = [item.candidate_id for item in candidates if item.state == "ready"]
    if not ready:
        return []
    return [
        {
            "phase_id": "phase_1_ordered_integration",
            "phase": "ordered_integration",
            "candidate_ids": ready,
            "action": "prepare_ordered_mainline_integration_review",
        }
    ]


def _components(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [_as_mapping(item) for item in _as_sequence(data.get("components"))]


def _component(data: Mapping[str, Any], components: Sequence[Mapping[str, Any]], key: str, kind: str) -> dict[str, Any]:
    direct = _as_mapping(data.get(key))
    if direct:
        return direct
    for component in components:
        if component.get("kind") == kind:
            return dict(component)
    return {}


def _score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return score / 100 if score > 1 else score


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
