from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PostAdoptionSignal:
    signal_id: str
    source_kind: str
    status: str
    severity: str
    owner: str
    metric: str = ""
    threshold: str = ""
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source_kind": self.source_kind,
            "status": self.status,
            "severity": self.severity,
            "owner": self.owner,
            "metric": self.metric,
            "threshold": self.threshold,
            "evidence_refs": list(self.evidence_refs),
            "reasons": list(self.reasons),
        }


def summarize_post_adoption_signal(signal: Mapping[str, Any] | Any) -> PostAdoptionSignal:
    payload = _as_mapping(signal)
    status = str(payload.get("status") or "ready")
    severity = str(payload.get("severity") or "low")
    reasons = [str(reason) for reason in _as_sequence(payload.get("reasons"))]
    if not reasons:
        if status == "alert" or severity in {"high", "critical"}:
            reasons.append(f"{severity} signal requires attention")
        elif status == "watch":
            reasons.append("signal requires watch")
        else:
            reasons.append("signal ready")
    return PostAdoptionSignal(
        signal_id=str(payload.get("signal_id") or ""),
        source_kind=str(payload.get("source_kind") or ""),
        status=status,
        severity=severity,
        owner=str(payload.get("owner") or ""),
        metric=str(payload.get("metric") or ""),
        threshold=str(payload.get("threshold") or ""),
        evidence_refs=tuple(str(ref) for ref in _as_sequence(payload.get("evidence_refs"))),
        reasons=tuple(reasons),
    )


def build_integration_post_adoption_monitor(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    raw_signals = _signals(data)
    if not raw_signals:
        return {
            "kind": "integration_post_adoption_monitor",
            "monitor_id": str(data.get("monitor_id") or ""),
            "ok": False,
            "status": "empty",
            "summary": {"signal_count": 0, "alert_count": 0, "watch_count": 0},
            "watch_signals": [],
            "alert_candidates": [],
            "owner_watchlist": {},
            "issues": [],
            "next_actions": ["provide_post_adoption_monitor_inputs"],
        }

    signals = [summarize_post_adoption_signal(item) for item in raw_signals]
    alerts = [
        signal.signal_id
        for signal in signals
        if signal.status == "alert" or signal.severity in {"high", "critical"}
    ]
    watch = [
        signal
        for signal in signals
        if signal.status in {"watch", "alert"} or signal.severity in {"medium", "high", "critical"}
    ]
    issues = [
        {
            "code": "post_adoption_signal_alert",
            "severity": signal.severity,
            "signal_id": signal.signal_id,
            "reasons": list(signal.reasons),
        }
        for signal in signals
        if signal.signal_id in alerts
    ]
    if alerts:
        status = "blocked"
        next_actions = ["resolve_post_adoption_alerts", "rebuild_integration_post_adoption_monitor"]
    elif watch:
        status = "needs_review"
        next_actions = ["review_post_adoption_watchlist_with_mainline"]
    else:
        status = "ready"
        next_actions = ["review_post_adoption_watchlist_with_mainline"]

    return {
        "kind": "integration_post_adoption_monitor",
        "monitor_id": str(data.get("monitor_id") or ""),
        "ok": status == "ready",
        "status": status,
        "summary": {
            "signal_count": len(signals),
            "alert_count": len(alerts),
            "watch_count": len(watch),
        },
        "watch_signals": [signal.as_dict() for signal in watch],
        "alert_candidates": alerts,
        "owner_watchlist": _owner_watchlist(signals),
        "issues": issues,
        "next_actions": next_actions,
    }


def _signals(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    if data.get("signals"):
        return [_as_mapping(signal) for signal in _as_sequence(data.get("signals"))]
    signals: list[dict[str, Any]] = []
    rollout = _as_mapping(data.get("rollout_guardrails"))
    if rollout:
        safe = bool(rollout.get("safe_to_rollout")) and bool(rollout.get("ok", True)) and str(rollout.get("status") or "") == "ready"
        signals.append(
            {
                "signal_id": "rollout_guardrails_watch",
                "source_kind": str(rollout.get("kind") or "integration_rollout_guardrails"),
                "status": "ready" if safe else "alert",
                "severity": "low" if safe else "high",
                "owner": str(rollout.get("owner") or "mainline"),
                "reasons": ["rollout guardrails ready"] if safe else ["rollout guardrails require attention"],
            }
        )
    owner_digest = _as_mapping(data.get("owner_digest"))
    for owner in _as_sequence(owner_digest.get("owners")):
        owner_payload = _as_mapping(owner)
        owner_name = str(owner_payload.get("owner") or "owner")
        blocked = str(owner_payload.get("status") or "") == "blocked" or int(owner_payload.get("blocked_count") or 0) > 0
        signals.append(
            {
                "signal_id": f"owner_watch_{_slug(owner_name)}",
                "source_kind": str(owner_digest.get("kind") or "integration_owner_digest"),
                "status": "alert" if blocked else "ready",
                "severity": "high" if blocked else "low",
                "owner": owner_name,
                "evidence_refs": owner_payload.get("evidence_refs"),
                "reasons": ["owner has blocked followups"] if blocked else ["owner ready for watchlist"],
            }
        )
    validation = _as_mapping(data.get("validation"))
    if validation:
        results = [str(result).lower() for result in _as_sequence(validation.get("results"))]
        failed = any("failed" in result or "error" in result for result in results)
        signals.append(
            {
                "signal_id": "validation_result_watch",
                "source_kind": "validation",
                "status": "alert" if failed else "ready",
                "severity": "high" if failed else "low",
                "owner": str(validation.get("owner") or "validation"),
                "evidence_refs": validation.get("commands"),
                "reasons": ["validation result failed"] if failed else ["validation result passed"],
            }
        )
    for risk in _as_sequence(data.get("risks")):
        risk_payload = _as_mapping(risk)
        severity = str(risk_payload.get("severity") or "medium")
        code = _slug(str(risk_payload.get("code") or "risk"))
        signals.append(
            {
                "signal_id": f"risk_watch_{code}",
                "source_kind": "risk",
                "status": "alert" if severity in {"high", "critical"} else "ready",
                "severity": severity,
                "owner": str(risk_payload.get("owner") or "risk"),
                "evidence_refs": risk_payload.get("evidence_refs"),
                "reasons": [f"{severity} risk requires attention"] if severity in {"high", "critical"} else ["risk accepted for watchlist"],
            }
        )
    return signals


def _owner_watchlist(signals: Sequence[PostAdoptionSignal]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for signal in signals:
        if signal.owner and signal.source_kind in {"manual", "integration_owner_digest"}:
            result.setdefault(signal.owner, []).append(signal.signal_id)
    return result


def _slug(value: str) -> str:
    return value.replace("_", "-").replace(" ", "-")


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
