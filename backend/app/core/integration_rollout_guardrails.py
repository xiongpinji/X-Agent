from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RolloutGuardrail:
    guardrail_id: str
    status: str
    severity: str = "low"
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "guardrail_id": self.guardrail_id,
            "status": self.status,
            "severity": self.severity,
            "evidence_refs": list(self.evidence_refs),
            "reasons": list(self.reasons),
        }


def evaluate_rollout_guardrail(
    guardrail_id: str,
    *,
    status: str,
    evidence_refs: Sequence[str] | None = None,
    reasons: Sequence[str] | None = None,
    severity: str = "low",
) -> RolloutGuardrail:
    return RolloutGuardrail(
        guardrail_id=guardrail_id,
        status=status,
        severity=severity,
        evidence_refs=tuple(str(ref) for ref in (evidence_refs or ())),
        reasons=tuple(str(reason) for reason in (reasons or ())),
    )


def build_integration_rollout_guardrails(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    components = _component_map(data)
    adoption_readme = components.get("integration_adoption_readme") or _as_mapping(data.get("adoption_readme"))
    final_review_brief = components.get("integration_final_review_brief") or _as_mapping(data.get("final_review_brief"))
    closure_checklist = components.get("integration_closure_checklist") or _as_mapping(data.get("closure_checklist"))
    rollback = _as_mapping(data.get("rollback_plan")) or _as_mapping(data.get("rollback"))
    validation = _as_mapping(data.get("validation")) or _as_mapping(adoption_readme.get("validation"))
    risks = [_as_mapping(risk) for risk in _as_sequence(data.get("risks"))]

    guardrails = [
        _component_guardrail("adoption_readme_ready", adoption_readme, "integration_adoption_readme"),
        _component_guardrail("final_review_brief_ready", final_review_brief, "integration_final_review_brief"),
        _component_guardrail("closure_checklist_ready", closure_checklist, "integration_closure_checklist"),
        _rollback_guardrail(rollback),
        _validation_guardrail(validation),
        _risk_guardrail(risks),
        _owner_summary_guardrail(final_review_brief),
    ]
    blocked_guardrails = [item.guardrail_id for item in guardrails if item.status == "blocked"]
    review_guardrails = [item.guardrail_id for item in guardrails if item.status == "needs_review"]
    if blocked_guardrails:
        status = "blocked"
        next_actions = _next_actions(blocked=True, review_guardrails=review_guardrails, blocked_guardrails=blocked_guardrails)
    elif review_guardrails:
        status = "needs_review"
        next_actions = _next_actions(blocked=False, review_guardrails=review_guardrails, blocked_guardrails=())
    else:
        status = "ready"
        next_actions = ["review_rollout_guardrails_with_mainline"]
    validation_commands = _as_sequence(validation.get("commands"))
    validation_results = _as_sequence(validation.get("results"))
    issues = _issues(guardrails)
    return {
        "kind": "integration_rollout_guardrails",
        "ok": status == "ready",
        "status": status,
        "safe_to_rollout": status == "ready",
        "guardrail_id": str(data.get("guardrail_id") or ""),
        "summary": {
            "guardrail_count": len(guardrails),
            "ready_count": len([item for item in guardrails if item.status == "ready"]),
            "review_count": len(review_guardrails),
            "blocked_count": len(blocked_guardrails),
            "validation_command_count": len(validation_commands),
            "validation_result_count": len(validation_results),
        },
        "guardrails": [item.as_dict() for item in guardrails],
        "blocked_guardrails": blocked_guardrails,
        "review_guardrails": review_guardrails,
        "issues": issues,
        "next_actions": next_actions,
    }


def _component_guardrail(guardrail_id: str, component: Mapping[str, Any], expected_kind: str) -> RolloutGuardrail:
    if not component:
        return evaluate_rollout_guardrail(
            guardrail_id,
            status="needs_review",
            reasons=(f"{expected_kind} missing from supplied rollout payload",),
            severity="medium",
        )
    status = str(component.get("status") or "needs_review")
    ok = bool(component.get("ok", status == "ready"))
    if status == "blocked" or ok is False:
        return evaluate_rollout_guardrail(
            guardrail_id,
            status="blocked",
            evidence_refs=_as_sequence(component.get("evidence_refs")),
            reasons=(f"{expected_kind} blocks local rollout guardrail",),
            severity="high",
        )
    if status == "ready" and ok:
        return evaluate_rollout_guardrail(
            guardrail_id,
            status="ready",
            evidence_refs=_as_sequence(component.get("evidence_refs")),
            reasons=(f"{expected_kind} supplied ready",),
        )
    return evaluate_rollout_guardrail(
        guardrail_id,
        status="needs_review",
        evidence_refs=_as_sequence(component.get("evidence_refs")),
        reasons=(f"{expected_kind} needs local review",),
        severity="medium",
    )


def _rollback_guardrail(rollback: Mapping[str, Any]) -> RolloutGuardrail:
    steps = _as_sequence(rollback.get("steps"))
    if not steps:
        return evaluate_rollout_guardrail(
            "rollback_plan_ready",
            status="needs_review",
            reasons=("rollback plan steps missing",),
            severity="medium",
        )
    return evaluate_rollout_guardrail("rollback_plan_ready", status="ready", evidence_refs=steps, reasons=("rollback plan supplied",))


def _validation_guardrail(validation: Mapping[str, Any]) -> RolloutGuardrail:
    commands = _as_sequence(validation.get("commands"))
    results = [str(result) for result in _as_sequence(validation.get("results"))]
    if any("failed" in result.lower() or " error" in result.lower() for result in results):
        return evaluate_rollout_guardrail(
            "validation_evidence_ready",
            status="blocked",
            evidence_refs=commands + results,
            reasons=("validation result blocks local rollout guardrail",),
            severity="high",
        )
    if not commands or not results:
        return evaluate_rollout_guardrail(
            "validation_evidence_ready",
            status="needs_review",
            evidence_refs=commands + results,
            reasons=("validation command/result evidence missing",),
            severity="medium",
        )
    return evaluate_rollout_guardrail(
        "validation_evidence_ready",
        status="ready",
        evidence_refs=commands + results,
        reasons=("validation command/result strings supplied",),
    )


def _risk_guardrail(risks: Sequence[Mapping[str, Any]]) -> RolloutGuardrail:
    if not risks:
        return evaluate_rollout_guardrail(
            "risk_summary_ready",
            status="needs_review",
            reasons=("risk summary missing",),
            severity="medium",
        )
    severities = [str(risk.get("severity") or "").lower() for risk in risks]
    if any(severity in {"high", "critical"} for severity in severities):
        return evaluate_rollout_guardrail(
            "risk_summary_ready",
            status="blocked",
            evidence_refs=[str(risk.get("code") or "") for risk in risks],
            reasons=("high or critical risk supplied",),
            severity="high",
        )
    return evaluate_rollout_guardrail(
        "risk_summary_ready",
        status="ready",
        evidence_refs=[str(risk.get("code") or "") for risk in risks],
        reasons=("risk summary supplied without high severity",),
    )


def _owner_summary_guardrail(final_review_brief: Mapping[str, Any]) -> RolloutGuardrail:
    owners = _as_sequence(_as_mapping(final_review_brief.get("owner_summary")).get("owners"))
    if not owners:
        return evaluate_rollout_guardrail(
            "owner_summary_ready",
            status="needs_review",
            reasons=("owner summary missing",),
            severity="medium",
        )
    return evaluate_rollout_guardrail("owner_summary_ready", status="ready", evidence_refs=owners, reasons=("owner summary supplied",))


def _next_actions(
    *,
    blocked: bool,
    review_guardrails: Sequence[str],
    blocked_guardrails: Sequence[str],
) -> list[str]:
    actions: list[str] = ["resolve_rollout_blockers"] if blocked else []
    guardrails = [*blocked_guardrails, *review_guardrails]
    if "rollback_plan_ready" in guardrails:
        actions.append("attach_rollout_rollback_plan")
    if "validation_evidence_ready" in guardrails:
        actions.append("attach_rollout_validation_evidence")
    if "risk_summary_ready" in guardrails:
        actions.append("attach_rollout_risk_summary")
    if any(item in guardrails for item in ("adoption_readme_ready", "final_review_brief_ready", "closure_checklist_ready", "owner_summary_ready")):
        actions.append("attach_rollout_component_artifacts")
    actions.append("rebuild_integration_rollout_guardrails")
    return _unique(actions)


def _issues(guardrails: Sequence[RolloutGuardrail]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for guardrail in guardrails:
        if guardrail.status == "blocked":
            issues.append({"code": "rollout_guardrail_blocked", "guardrail_id": guardrail.guardrail_id, "severity": guardrail.severity})
        elif guardrail.status == "needs_review":
            issues.append({"code": "rollout_guardrail_needs_review", "guardrail_id": guardrail.guardrail_id, "severity": guardrail.severity})
    return issues


def _component_map(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    components = {}
    for raw in _as_sequence(data.get("components")):
        component = _as_mapping(raw)
        kind = str(component.get("kind") or "")
        if kind:
            components[kind] = component
    return components


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
