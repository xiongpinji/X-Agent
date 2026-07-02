from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReviewBriefSignal:
    kind: str
    status: str
    ok: bool
    verdict: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    summary: dict[str, Any] = field(default_factory=dict)
    issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "ok": self.ok,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "summary": dict(self.summary),
            "issues": [dict(issue) for issue in self.issues],
            "next_actions": list(self.next_actions),
            "evidence_refs": list(self.evidence_refs),
        }


def summarize_review_brief_signal(component: Mapping[str, Any] | Any) -> ReviewBriefSignal:
    payload = _as_mapping(component)
    kind = str(payload.get("kind") or payload.get("name") or "integration_signal")
    status = str(payload.get("status") or "needs_review")
    ok = _bool(payload.get("ok")) if "ok" in payload else status in {"ready", "passed"}
    summary = dict(payload.get("summary") or {})
    issues = tuple(dict(issue) for issue in _as_sequence(payload.get("issues")))
    next_actions = tuple(str(action) for action in _as_sequence(payload.get("next_actions")))
    evidence_refs = tuple(_evidence_refs(payload))

    reasons: list[str] = []
    if status == "blocked" or not ok and _has_high_issue(issues):
        verdict = "blocked"
        reasons.append("signal blocked for final review brief")
    elif status in {"ready", "passed"} and ok:
        verdict = "ready"
        reasons.append("signal ready for final review brief")
    else:
        verdict = "needs_review"
        reasons.append("signal needs review before final review brief")

    return ReviewBriefSignal(
        kind=kind,
        status=status,
        ok=ok,
        verdict=verdict,
        reasons=tuple(reasons),
        summary=summary,
        issues=issues,
        next_actions=next_actions,
        evidence_refs=evidence_refs,
    )


def build_integration_final_review_brief(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    signals = [summarize_review_brief_signal(item) for item in _signal_payloads(data)]
    if not signals:
        return {
            "kind": "integration_final_review_brief",
            "brief_id": str(data.get("brief_id") or ""),
            "ok": False,
            "status": "needs_review",
            "verdict": "needs_inputs",
            "summary": {
                "signal_count": 0,
                "ready_signal_count": 0,
                "blocked_signal_count": 0,
                "needs_review_signal_count": 0,
                "evidence_ref_count": 0,
            },
            "signals": [],
            "owner_summary": {"owner_count": 0, "owners": []},
            "evidence_summary": {"evidence_ref_count": 0, "missing_evidence_count": 0, "evidence_refs": []},
            "issues": [],
            "risks": [],
            "next_actions": ["provide_final_review_brief_inputs"],
        }

    blocked = [signal for signal in signals if signal.verdict == "blocked"]
    review = [signal for signal in signals if signal.verdict == "needs_review"]
    issues = _brief_issues(signals)
    evidence_refs = _collect_evidence_refs(signals)
    missing_evidence_count = sum(_int(signal.summary.get("missing_evidence_count")) for signal in signals)
    owners = _owner_names(data, signals)
    risks = _risks(blocked, issues, missing_evidence_count)

    if blocked:
        status = "blocked"
        verdict = "blocked"
        next_actions = _unique(
            ["resolve_final_review_blockers"]
            + [action for signal in blocked for action in signal.next_actions]
            + ["rebuild_integration_final_review_brief"]
        )
    elif review or issues or missing_evidence_count:
        status = "needs_review"
        verdict = "needs_review"
        next_actions = ["review_final_brief_issues", "rebuild_integration_final_review_brief"]
    else:
        status = "ready"
        verdict = "ready_for_mainline_review"
        next_actions = ["submit_final_review_brief_to_mainline"]

    return {
        "kind": "integration_final_review_brief",
        "brief_id": str(data.get("brief_id") or ""),
        "ok": status == "ready",
        "status": status,
        "verdict": verdict,
        "summary": {
            "signal_count": len(signals),
            "ready_signal_count": sum(1 for signal in signals if signal.verdict == "ready"),
            "blocked_signal_count": len(blocked),
            "needs_review_signal_count": len(review),
            "evidence_ref_count": len(evidence_refs),
        },
        "signals": [signal.as_dict() for signal in signals],
        "owner_summary": {"owner_count": len(owners), "owners": owners},
        "evidence_summary": {
            "evidence_ref_count": len(evidence_refs),
            "missing_evidence_count": missing_evidence_count,
            "evidence_refs": evidence_refs,
        },
        "issues": issues,
        "risks": risks,
        "next_actions": next_actions,
    }


def _signal_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("signals") or data.get("components")
    if raw:
        if isinstance(raw, Mapping):
            return list(raw.values())
        return _as_sequence(raw)
    keys = (
        "closure_checklist",
        "owner_digest",
        "governance_summary",
        "review_packet",
        "traceability_index",
    )
    return [data[key] for key in keys if data.get(key)]


def _brief_issues(signals: Sequence[ReviewBriefSignal]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for signal in signals:
        if signal.verdict == "blocked":
            issues.append(
                {
                    "code": "final_review_signal_blocked",
                    "severity": "high",
                    "signal": signal.kind,
                }
            )
        elif signal.verdict == "needs_review":
            issues.append(
                {
                    "code": "final_review_signal_needs_review",
                    "severity": "medium",
                    "signal": signal.kind,
                }
            )
        issues.extend(dict(issue) for issue in signal.issues)
    return issues


def _owner_names(data: Mapping[str, Any], signals: Sequence[ReviewBriefSignal]) -> list[str]:
    owner_payloads: list[Any] = []
    owner_digest = data.get("owner_digest")
    if owner_digest:
        owner_payloads.extend(_as_sequence(_as_mapping(owner_digest).get("owners")))
    for signal in signals:
        if signal.kind == "integration_owner_digest":
            original = _find_original_signal(data, signal.kind)
            owner_payloads.extend(_as_sequence(_as_mapping(original).get("owners")))
    owners: list[str] = []
    for owner in owner_payloads:
        name = str(_as_mapping(owner).get("owner") or "").strip()
        if name and name != "unassigned" and name not in owners:
            owners.append(name)
    return owners


def _find_original_signal(data: Mapping[str, Any], kind: str) -> Any:
    for item in _signal_payloads(data):
        if str(_as_mapping(item).get("kind") or "") == kind:
            return item
    return {}


def _collect_evidence_refs(signals: Sequence[ReviewBriefSignal]) -> list[str]:
    refs: list[str] = []
    for signal in signals:
        refs.extend(signal.evidence_refs)
    return _unique(refs)


def _evidence_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    refs.extend(str(ref) for ref in _as_sequence(payload.get("evidence_refs")))
    for owner in _as_sequence(payload.get("owners")):
        refs.extend(str(ref) for ref in _as_sequence(_as_mapping(owner).get("evidence_refs")))
    return refs


def _risks(
    blocked: Sequence[ReviewBriefSignal],
    issues: Sequence[Mapping[str, Any]],
    missing_evidence_count: int,
) -> list[str]:
    risks: list[str] = []
    if blocked:
        risks.append("blocked_signals_present")
    if issues:
        risks.append("unresolved_review_issues_present")
    if missing_evidence_count:
        risks.append("missing_evidence_present")
    return risks


def _has_high_issue(issues: Sequence[Mapping[str, Any]]) -> bool:
    return any(str(issue.get("severity") or "").lower() == "high" for issue in issues)


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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "passed", "ready"}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _unique(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
