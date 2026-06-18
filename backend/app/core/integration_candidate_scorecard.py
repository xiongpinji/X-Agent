from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


BLOCKING_RISKS = {"runtime_mutation", "secret_write", "external_mutation"}


@dataclass(frozen=True)
class IntegrationCandidateScore:
    candidate_id: str
    name: str
    owner: str
    payoff_score: float
    evidence_score: float
    effort_score: float
    risk_score: float
    owner_score: float
    priority_score: float
    recommendation: str
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "owner": self.owner,
            "payoff_score": self.payoff_score,
            "evidence_score": self.evidence_score,
            "effort_score": self.effort_score,
            "risk_score": self.risk_score,
            "owner_score": self.owner_score,
            "priority_score": self.priority_score,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
        }


def score_integration_candidate(candidate: Mapping[str, Any] | Any) -> IntegrationCandidateScore:
    payload = _as_mapping(candidate)
    candidate_id = str(payload.get("candidate_id") or payload.get("id") or "")
    owner = str(payload.get("owner") or "")
    payoff_score = _score(payload.get("payoff_score"), len(_as_sequence(payload.get("payoff_tags"))) / 3)
    evidence_score = _score(payload.get("evidence_score"), len(_as_sequence(payload.get("evidence"))) / 4)
    effort_score = _effort_score(payload)
    risks = {str(item) for item in _as_sequence(payload.get("risk_flags"))}
    risk_score = min(1.0, len(risks) * 0.25)
    owner_score = 1.0 if owner else 0.2
    priority_score = round((payoff_score * 0.35) + (evidence_score * 0.30) + (effort_score * 0.25) + (owner_score * 0.10) - (risk_score * 0.35), 3)
    reasons: list[str] = []
    if not owner:
        reasons.append("owner missing")
    if risks & BLOCKING_RISKS:
        recommendation = "block"
        reasons.append("blocking risk present")
    elif priority_score >= 0.68:
        recommendation = "integrate_now"
    elif priority_score >= 0.45:
        recommendation = "review_next"
    else:
        recommendation = "defer"
    if payload.get("issues") and recommendation != "block":
        recommendation = "defer"
        reasons.append("candidate issues present")
    return IntegrationCandidateScore(
        candidate_id=candidate_id,
        name=str(payload.get("name") or candidate_id),
        owner=owner,
        payoff_score=payoff_score,
        evidence_score=evidence_score,
        effort_score=effort_score,
        risk_score=risk_score,
        owner_score=owner_score,
        priority_score=priority_score,
        recommendation=recommendation,
        reasons=tuple(reasons or ["candidate scored"]),
    )


def build_integration_candidate_scorecard(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw = _candidates(data)
    if not raw:
        return {
            "kind": "integration_candidate_scorecard",
            "portfolio": str(data.get("portfolio") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"candidate_count": 0, "integrate_now_count": 0},
            "candidates": [],
            "issues": [],
            "next_actions": ["provide_integration_candidates"],
        }
    candidates = sorted((score_integration_candidate(item) for item in raw), key=lambda item: item.priority_score, reverse=True)
    blocked = [item for item in candidates if item.recommendation == "block"]
    status = "blocked" if blocked else "ready"
    issues = [{"code": "integration_candidate_blocked", "severity": "high", "candidate_id": item.candidate_id} for item in blocked]
    return {
        "kind": "integration_candidate_scorecard",
        "portfolio": str(data.get("portfolio") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": len(candidates),
            "integrate_now_count": sum(1 for item in candidates if item.recommendation == "integrate_now"),
            "review_next_count": sum(1 for item in candidates if item.recommendation == "review_next"),
            "blocked_count": len(blocked),
        },
        "candidates": [item.as_dict() for item in candidates],
        "issues": issues,
        "next_actions": ["remove_or_remediate_blocked_candidates", "rebuild_integration_scorecard"]
        if blocked
        else ["review_top_integration_candidate", "prepare_mainline_integration_plan"],
    }


def _candidates(data: Mapping[str, Any]) -> list[Any]:
    if data.get("candidates"):
        return _as_sequence(data.get("candidates"))
    scorecard = _as_mapping(data.get("scorecard"))
    return _as_sequence(scorecard.get("candidates"))


def _effort_score(payload: Mapping[str, Any]) -> float:
    if "effort_score" in payload:
        return _score(payload.get("effort_score"), 0)
    effort = str(payload.get("integration_effort") or payload.get("effort") or "medium")
    return {"low": 1.0, "medium": 0.65, "high": 0.25}.get(effort, 0.5)


def _score(value: Any, fallback: float) -> float:
    if value is None:
        return round(min(1.0, max(0.0, fallback)), 3)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return round(min(1.0, max(0.0, fallback)), 3)
    if number > 1:
        number = number / 100
    return round(min(1.0, max(0.0, number)), 3)


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
