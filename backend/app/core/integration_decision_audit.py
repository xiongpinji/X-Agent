from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntegrationDecisionAuditItem:
    candidate_id: str
    decision: str
    status: str
    owner: str = ""
    rationale: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    rollback_plan: str = ""
    followups: tuple[str, ...] = field(default_factory=tuple)
    review_condition: str = ""
    reconsideration_condition: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "decision": self.decision,
            "status": self.status,
            "owner": self.owner,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "rollback_plan": self.rollback_plan,
            "followups": list(self.followups),
            "review_condition": self.review_condition,
            "reconsideration_condition": self.reconsideration_condition,
            "reasons": list(self.reasons),
        }


def audit_integration_decision(decision: Mapping[str, Any] | Any) -> IntegrationDecisionAuditItem:
    payload = _as_mapping(decision)
    normalized = _normalize_decision(payload.get("decision"))
    evidence = tuple(str(ref) for ref in (_as_sequence(payload.get("evidence_refs")) or _as_sequence(payload.get("evidence"))))
    followups = tuple(str(item) for item in _as_sequence(payload.get("followups")))
    reasons: list[str] = []
    if not normalized:
        reasons.append("integration decision missing")
    if not payload.get("owner"):
        reasons.append("owner missing")
    if not payload.get("rationale"):
        reasons.append("rationale missing")
    if not evidence:
        reasons.append("decision evidence missing")
    if normalized == "accepted" and not payload.get("rollback_plan"):
        reasons.append("rollback plan missing for accepted decision")
    if normalized == "deferred":
        if not followups:
            reasons.append("followups missing for deferred decision")
        if not payload.get("review_condition"):
            reasons.append("review condition missing for deferred decision")
    if normalized == "rejected" and not payload.get("reconsideration_condition"):
        reasons.append("reconsideration condition missing for rejected decision")
    if not normalized:
        status = "blocked"
    elif reasons:
        status = "needs_review"
    else:
        status = "passed"
    return IntegrationDecisionAuditItem(
        candidate_id=str(payload.get("candidate_id") or "unknown"),
        decision=normalized or "",
        status=status,
        owner=str(payload.get("owner") or ""),
        rationale=str(payload.get("rationale") or ""),
        evidence_refs=evidence,
        rollback_plan=str(payload.get("rollback_plan") or ""),
        followups=followups,
        review_condition=str(payload.get("review_condition") or ""),
        reconsideration_condition=str(payload.get("reconsideration_condition") or ""),
        reasons=tuple(reasons),
    )


def build_integration_decision_audit(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = _items(payload)
    if not raw:
        return {
            "kind": "integration_decision_audit",
            "ok": False,
            "status": "empty",
            "decisions": [],
            "issues": [],
            "next_actions": ["provide_integration_decisions"],
        }
    decisions = [audit_integration_decision(item) for item in raw]
    if any(item.status == "blocked" for item in decisions):
        status = "blocked"
        next_actions = ["record_missing_decisions", "rerun_integration_decision_audit"]
    elif any(item.status == "needs_review" for item in decisions):
        status = "needs_review"
        next_actions = ["complete_integration_decision_review", "rerun_integration_decision_audit"]
    else:
        status = "passed"
        next_actions = ["prepare_traceable_integration_handoff"]
    return {
        "kind": "integration_decision_audit",
        "ok": status == "passed",
        "status": status,
        "summary": {
            "decision_count": len(decisions),
            "passed_count": len([item for item in decisions if item.status == "passed"]),
            "review_count": len([item for item in decisions if item.status == "needs_review"]),
            "blocked_count": len([item for item in decisions if item.status == "blocked"]),
        },
        "decisions": [item.as_dict() for item in decisions],
        "issues": _issues(decisions),
        "next_actions": next_actions,
    }


def _items(payload: Mapping[str, Any]) -> list[Any]:
    if payload.get("decisions"):
        return _as_sequence(payload.get("decisions"))
    return _as_sequence(_as_mapping(payload.get("audit")).get("decisions"))


def _normalize_decision(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"accepted", "approved", "accept", "approve", "integrate_now"}:
        return "accepted"
    if text in {"defer", "deferred", "hold"}:
        return "deferred"
    if text in {"reject", "rejected"}:
        return "rejected"
    return ""


def _issues(decisions: Sequence[IntegrationDecisionAuditItem]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if any("integration decision missing" in item.reasons for item in decisions):
        issues.append({"code": "integration_decision_missing", "severity": "high"})
    if any("followups missing for deferred decision" in item.reasons for item in decisions):
        issues.append({"code": "integration_decision_followups_missing", "severity": "medium"})
    return issues


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
