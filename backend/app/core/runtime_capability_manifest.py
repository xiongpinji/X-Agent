from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


READY_STAGES = {"ready", "integrated", "available", "stable", "supported"}
REVIEW_STAGES = {"candidate", "preview", "experimental", "partial", "planned"}
BLOCKED_STAGES = {"blocked", "disabled", "unsupported", "missing"}


@dataclass(frozen=True)
class RuntimeCapabilityItem:
    capability_id: str
    name: str
    owner: str
    integration_stage: str
    evidence_count: int
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    risk_flags: tuple[str, ...] = field(default_factory=tuple)
    decision: str = "ready"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "owner": self.owner,
            "integration_stage": self.integration_stage,
            "evidence_count": self.evidence_count,
            "missing_evidence": list(self.missing_evidence),
            "dependencies": list(self.dependencies),
            "risk_flags": list(self.risk_flags),
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_runtime_capability_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    capabilities = [assess_runtime_capability(item) for item in _capability_payloads(data)]
    issues = _issues(capabilities)
    status = _status(capabilities)

    return {
        "kind": "runtime_capability_manifest",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "runtime": str(data.get("runtime") or data.get("target") or data.get("system") or ""),
        "summary": {
            "capability_count": len(capabilities),
            "ready_count": sum(1 for item in capabilities if item.decision == "ready"),
            "needs_review_count": sum(1 for item in capabilities if item.decision == "needs_review"),
            "blocked_count": sum(1 for item in capabilities if item.decision == "blocked"),
            "owner_missing_count": sum(1 for item in capabilities if not item.owner),
            "missing_evidence_count": sum(len(item.missing_evidence) for item in capabilities),
            "risk_flag_count": sum(len(item.risk_flags) for item in capabilities),
        },
        "capabilities": [item.as_dict() for item in capabilities],
        "issues": issues,
        "next_actions": _next_actions(capabilities, issues),
    }


def assess_runtime_capability(capability: Mapping[str, Any] | Any) -> RuntimeCapabilityItem:
    payload = _as_mapping(capability)
    capability_id = str(payload.get("capability_id") or payload.get("id") or payload.get("name") or "")
    name = str(payload.get("name") or payload.get("title") or capability_id)
    owner = str(payload.get("owner") or payload.get("integration_owner") or payload.get("team") or "")
    integration_stage = _normalize_token(payload.get("integration_stage") or payload.get("stage") or payload.get("status"))
    evidence_count = _evidence_count(payload)
    missing_evidence = tuple(_strings(payload.get("missing_evidence") or payload.get("required_evidence_missing")))
    dependencies = tuple(_strings(payload.get("dependencies") or payload.get("requires")))
    risk_flags = tuple(_strings(payload.get("risk_flags") or payload.get("risks")))
    decision, reasons = _decision(
        owner=owner,
        integration_stage=integration_stage,
        evidence_count=evidence_count,
        missing_evidence=missing_evidence,
        risk_flags=risk_flags,
    )
    return RuntimeCapabilityItem(
        capability_id=capability_id,
        name=name,
        owner=owner,
        integration_stage=integration_stage or "unknown",
        evidence_count=evidence_count,
        missing_evidence=missing_evidence,
        dependencies=dependencies,
        risk_flags=risk_flags,
        decision=decision,
        reasons=tuple(reasons),
    )


def _decision(
    *,
    owner: str,
    integration_stage: str,
    evidence_count: int,
    missing_evidence: Sequence[str],
    risk_flags: Sequence[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if integration_stage in BLOCKED_STAGES:
        reasons.append("capability stage blocked")
    elif integration_stage not in READY_STAGES:
        reasons.append("capability not fully integrated")
    if not owner:
        reasons.append("integration owner missing")
    if evidence_count == 0:
        reasons.append("runtime evidence missing")
    if missing_evidence:
        reasons.append("required evidence missing")
    if risk_flags:
        reasons.append("risk flags present")

    if "capability stage blocked" in reasons:
        return "blocked", reasons
    if risk_flags and any(str(flag).lower() in {"blocked", "security", "unsafe", "broken"} for flag in risk_flags):
        return "blocked", reasons
    if reasons:
        return "needs_review", reasons
    return "ready", ["capability ready"]


def _issues(items: Sequence[RuntimeCapabilityItem]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in items:
        if item.decision == "ready":
            continue
        issues.append(
            {
                "code": _issue_code(item),
                "severity": "high" if item.decision == "blocked" else "medium",
                "capability_id": item.capability_id,
                "name": item.name,
                "owner": item.owner,
                "integration_stage": item.integration_stage,
                "reasons": list(item.reasons),
            }
        )
    return issues


def _issue_code(item: RuntimeCapabilityItem) -> str:
    if "capability stage blocked" in item.reasons:
        return "runtime_capability_stage_blocked"
    if "risk flags present" in item.reasons and item.decision == "blocked":
        return "runtime_capability_blocking_risk"
    if "required evidence missing" in item.reasons:
        return "runtime_capability_required_evidence_missing"
    if "runtime evidence missing" in item.reasons:
        return "runtime_capability_evidence_missing"
    if "integration owner missing" in item.reasons:
        return "runtime_capability_owner_missing"
    if "capability not fully integrated" in item.reasons:
        return "runtime_capability_not_integrated"
    return "runtime_capability_needs_review"


def _status(items: Sequence[RuntimeCapabilityItem]) -> str:
    if not items:
        return "empty"
    if any(item.decision == "blocked" for item in items):
        return "blocked"
    if any(item.decision == "needs_review" for item in items):
        return "needs_review"
    return "ready"


def _next_actions(
    items: Sequence[RuntimeCapabilityItem],
    issues: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not items:
        return ["provide_runtime_capabilities"]
    codes = {str(issue.get("code") or "") for issue in issues}
    if any(item.decision == "blocked" for item in items):
        return ["resolve_blocked_runtime_capabilities", "refresh_runtime_capability_manifest"]
    if any(code.endswith("_missing") for code in codes):
        return ["collect_missing_runtime_evidence", "assign_integration_owners"]
    if issues:
        return ["review_runtime_capability_gaps", "prioritize_mainline_integration"]
    return ["prepare_runtime_capability_review"]


def _capability_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("capabilities") or data.get("items") or data.get("manifest") or []
    if isinstance(raw, Mapping):
        nested = raw.get("capabilities")
        if nested is not None:
            return _as_sequence(nested)
        return list(raw.values())
    return _as_sequence(raw)


def _evidence_count(payload: Mapping[str, Any]) -> int:
    evidence = payload.get("evidence") or payload.get("reports") or payload.get("artifacts") or payload.get("tests")
    count = _count(evidence)
    if payload.get("evidence_count") is not None:
        try:
            return max(count, int(payload.get("evidence_count")))
        except (TypeError, ValueError):
            return count
    return count


def _count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        if "status" in value or "path" in value or "name" in value:
            return 1
        return len(value)
    if isinstance(value, (str, bytes)):
        return 1 if value else 0
    if isinstance(value, Sequence):
        return len([item for item in value if item])
    return 1


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [str(value)] if value else []
    if isinstance(value, Mapping):
        return [str(key) for key in value.keys()]
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _as_sequence(value: Any) -> list[Any]:
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Sequence):
        return list(value)
    return []
