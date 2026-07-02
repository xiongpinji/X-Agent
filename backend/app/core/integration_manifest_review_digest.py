from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ManifestReviewSignal:
    signal_id: str
    status: str
    severity: str = "low"
    refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    next_actions: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "status": self.status,
            "severity": self.severity,
            "refs": list(self.refs),
            "reasons": list(self.reasons),
            "next_actions": list(self.next_actions),
        }


def summarize_manifest_review_signal(signal: Mapping[str, Any] | Any) -> ManifestReviewSignal:
    payload = _as_mapping(signal)
    return ManifestReviewSignal(
        signal_id=str(payload.get("signal_id") or payload.get("kind") or ""),
        status=str(payload.get("status") or "needs_review"),
        severity=str(payload.get("severity") or _severity(payload)),
        refs=tuple(str(ref) for ref in _as_sequence(payload.get("refs"))),
        reasons=tuple(str(reason) for reason in _as_sequence(payload.get("reasons"))),
        next_actions=tuple(str(action) for action in _as_sequence(payload.get("next_actions"))),
    )


def build_integration_manifest_review_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_signals = _signals(data)
    if not raw_signals:
        return {
            "kind": "integration_manifest_review_digest",
            "ok": False,
            "status": "empty",
            "signals": [],
            "blocked_signals": [],
            "review_signals": [],
            "next_actions": ["provide_manifest_review_digest_inputs"],
        }
    signals = [summarize_manifest_review_signal(signal) for signal in raw_signals]
    blocked = [signal.signal_id for signal in signals if signal.status == "blocked"]
    review = [signal.signal_id for signal in signals if signal.status == "needs_review"]
    if blocked:
        status = "blocked"
        next_actions = ["resolve_manifest_review_digest_blockers", "rebuild_integration_manifest_review_digest"]
    elif review:
        status = "needs_review"
        next_actions = _review_actions(signals) + ["rebuild_integration_manifest_review_digest"]
    else:
        status = "ready"
        next_actions = ["share_manifest_review_digest_with_mainline"]
    return {
        "kind": "integration_manifest_review_digest",
        "ok": status == "ready",
        "status": status,
        "summary": {
            "candidate_count": _candidate_count(data),
            "signal_count": len(signals),
            "ready_count": len([signal for signal in signals if signal.status == "ready"]),
            "blocked_count": len(blocked),
            "review_count": len(review),
        },
        "signals": [signal.as_dict() for signal in signals],
        "blocked_signals": blocked,
        "review_signals": review,
        "next_actions": next_actions,
    }


def _signals(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if "signals" in data:
        return [_as_mapping(signal) for signal in _as_sequence(data.get("signals"))]
    raw = [
        ("manifest", "review_packet_manifest", "provide_review_packet_manifest_payload"),
        ("stage_policy", "stage_label_policy", "provide_stage_policy_payload"),
        ("diff_summary", "manifest_diff_summary", "provide_manifest_diff_summary_payload"),
        ("readiness_gate", "review_readiness_gate", "provide_review_readiness_gate_payload"),
        ("conflict_risk", "conflict_risk_register", "provide_conflict_risk_register_payload"),
    ]
    signals: list[Mapping[str, Any]] = []
    for signal_id, key, missing_action in raw:
        component = _as_mapping(data.get(key))
        if component:
            signals.append(_component_signal(signal_id, component))
        else:
            signals.append(
                {
                    "signal_id": signal_id,
                    "status": "needs_review",
                    "severity": "medium",
                    "reasons": [f"{signal_id} payload missing"],
                    "next_actions": [missing_action],
                }
            )
    return signals


def _component_signal(signal_id: str, component: Mapping[str, Any]) -> dict[str, Any]:
    status = str(component.get("status") or ("ready" if component.get("ok") else "needs_review"))
    reasons = [str(reason) for reason in _as_sequence(component.get("reasons"))]
    refs = _candidate_refs(component)
    next_actions = [str(action) for action in _as_sequence(component.get("next_actions"))]
    return {
        "signal_id": signal_id,
        "status": status,
        "severity": _severity(component),
        "refs": refs,
        "reasons": reasons,
        "next_actions": next_actions,
    }


def _candidate_count(data: Mapping[str, Any]) -> int:
    for key in ("review_packet_manifest", "stage_label_policy", "conflict_risk_register"):
        summary = _as_mapping(_as_mapping(data.get(key)).get("summary"))
        count = summary.get("candidate_count")
        if isinstance(count, int):
            return count
    return len(_candidate_refs(_as_mapping(data.get("review_packet_manifest"))))


def _candidate_refs(component: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("entries", "decisions", "items", "candidates"):
        refs.extend(str(_as_mapping(item).get("candidate_id") or "") for item in _as_sequence(component.get(key)))
    refs.extend(str(value) for value in _as_sequence(component.get("changed_candidates")))
    refs.extend(str(value) for value in _as_sequence(component.get("removed_candidates")))
    return _unique(refs)


def _severity(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status") or "")
    if status == "blocked":
        return "high"
    if status == "needs_review":
        return "medium"
    return "low"


def _review_actions(signals: Sequence[ManifestReviewSignal]) -> list[str]:
    actions: list[str] = ["review_manifest_digest_warnings"]
    for signal in signals:
        actions.extend(signal.next_actions)
    return _unique(actions)


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
