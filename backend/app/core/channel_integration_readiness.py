from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SUPPORTED_CHANNELS = {"slack", "linear", "github", "feishu", "lark", "teams", "discord", "telegram", "dingtalk"}
INBOUND_EVIDENCE_KEYS = {"callback_received", "webhook_received", "event_id", "callback_id", "delivery_id"}
OUTBOUND_EVIDENCE_KEYS = {"message_sent", "delivery_receipt", "response_status", "acknowledged"}


@dataclass(frozen=True)
class ChannelReadinessItem:
    channel: str
    name: str
    direction: str
    auth_configured: bool
    signature_verified: bool
    callback_evidence_count: int
    delivery_evidence_count: int
    correlation_present: bool
    retry_policy_present: bool
    owner_approved: bool
    mutation_requested: bool
    decision: str = "ready"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "name": self.name,
            "direction": self.direction,
            "auth_configured": self.auth_configured,
            "signature_verified": self.signature_verified,
            "callback_evidence_count": self.callback_evidence_count,
            "delivery_evidence_count": self.delivery_evidence_count,
            "correlation_present": self.correlation_present,
            "retry_policy_present": self.retry_policy_present,
            "owner_approved": self.owner_approved,
            "mutation_requested": self.mutation_requested,
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_channel_integration_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    rows = [assess_channel_integration(item) for item in _channel_payloads(data)]
    issues = _issues(rows)
    status = _status(rows)

    return {
        "kind": "channel_integration_readiness",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "workspace": str(data.get("workspace") or data.get("tenant") or ""),
        "summary": {
            "channel_count": len(rows),
            "ready_count": sum(1 for row in rows if row.decision == "ready"),
            "needs_review_count": sum(1 for row in rows if row.decision == "needs_review"),
            "blocked_count": sum(1 for row in rows if row.decision == "blocked"),
            "owner_approval_missing_count": sum(1 for row in rows if row.mutation_requested and not row.owner_approved),
            "callback_evidence_count": sum(row.callback_evidence_count for row in rows),
            "delivery_evidence_count": sum(row.delivery_evidence_count for row in rows),
        },
        "channels": [row.as_dict() for row in rows],
        "issues": issues,
        "next_actions": _next_actions(rows, issues),
    }


def assess_channel_integration(channel: Mapping[str, Any] | Any) -> ChannelReadinessItem:
    payload = _as_mapping(channel)
    channel_name = _normalize_token(payload.get("channel") or payload.get("provider") or payload.get("type"))
    name = str(payload.get("name") or payload.get("integration") or channel_name)
    direction = _direction(payload)
    auth_configured = _auth_configured(payload)
    signature_verified = _bool(payload.get("signature_verified") or payload.get("signature_check") or payload.get("verified"))
    callback_evidence_count = _callback_evidence_count(payload)
    delivery_evidence_count = _delivery_evidence_count(payload)
    correlation_present = _correlation_present(payload)
    retry_policy_present = _retry_policy_present(payload)
    mutation_requested = _bool(payload.get("mutation_requested") or payload.get("send_message") or payload.get("outbound_enabled"))
    owner_approved = _bool(payload.get("owner_approved") or payload.get("approval") or payload.get("owner_gate_passed"))
    decision, reasons = _decision(
        channel=channel_name,
        direction=direction,
        auth_configured=auth_configured,
        signature_verified=signature_verified,
        callback_evidence_count=callback_evidence_count,
        delivery_evidence_count=delivery_evidence_count,
        correlation_present=correlation_present,
        retry_policy_present=retry_policy_present,
        mutation_requested=mutation_requested,
        owner_approved=owner_approved,
    )
    return ChannelReadinessItem(
        channel=channel_name,
        name=name,
        direction=direction,
        auth_configured=auth_configured,
        signature_verified=signature_verified,
        callback_evidence_count=callback_evidence_count,
        delivery_evidence_count=delivery_evidence_count,
        correlation_present=correlation_present,
        retry_policy_present=retry_policy_present,
        owner_approved=owner_approved,
        mutation_requested=mutation_requested,
        decision=decision,
        reasons=tuple(reasons),
    )


def _decision(
    *,
    channel: str,
    direction: str,
    auth_configured: bool,
    signature_verified: bool,
    callback_evidence_count: int,
    delivery_evidence_count: int,
    correlation_present: bool,
    retry_policy_present: bool,
    mutation_requested: bool,
    owner_approved: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if channel not in SUPPORTED_CHANNELS:
        reasons.append("unsupported channel")
    if not auth_configured:
        reasons.append("auth missing")
    if direction in {"inbound", "bidirectional"} and not signature_verified:
        reasons.append("signature verification missing")
    if direction in {"inbound", "bidirectional"} and callback_evidence_count == 0:
        reasons.append("callback evidence missing")
    if direction in {"outbound", "bidirectional"} and delivery_evidence_count == 0:
        reasons.append("delivery evidence missing")
    if not correlation_present:
        reasons.append("correlation id missing")
    if not retry_policy_present:
        reasons.append("retry policy missing")
    if mutation_requested and not owner_approved:
        reasons.append("owner approval missing for outbound mutation")

    if "unsupported channel" in reasons or "owner approval missing for outbound mutation" in reasons:
        return "blocked", reasons
    if reasons:
        return "needs_review", reasons
    return "ready", ["channel ready"]


def _issues(rows: Sequence[ChannelReadinessItem]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        if row.decision == "ready":
            continue
        issues.append(
            {
                "code": _issue_code(row),
                "severity": "high" if row.decision == "blocked" else "medium",
                "channel": row.channel,
                "name": row.name,
                "direction": row.direction,
                "reasons": list(row.reasons),
            }
        )
    return issues


def _issue_code(row: ChannelReadinessItem) -> str:
    if "unsupported channel" in row.reasons:
        return "channel_integration_unsupported_channel"
    if "owner approval missing for outbound mutation" in row.reasons:
        return "channel_integration_owner_approval_missing"
    if "signature verification missing" in row.reasons:
        return "channel_integration_signature_missing"
    if "callback evidence missing" in row.reasons:
        return "channel_integration_callback_evidence_missing"
    if "delivery evidence missing" in row.reasons:
        return "channel_integration_delivery_evidence_missing"
    if "auth missing" in row.reasons:
        return "channel_integration_auth_missing"
    if "correlation id missing" in row.reasons:
        return "channel_integration_correlation_missing"
    if "retry policy missing" in row.reasons:
        return "channel_integration_retry_policy_missing"
    return "channel_integration_needs_review"


def _status(rows: Sequence[ChannelReadinessItem]) -> str:
    if not rows:
        return "empty"
    if any(row.decision == "blocked" for row in rows):
        return "blocked"
    if any(row.decision == "needs_review" for row in rows):
        return "needs_review"
    return "ready"


def _next_actions(
    rows: Sequence[ChannelReadinessItem],
    issues: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not rows:
        return ["provide_channel_payloads"]
    codes = {str(issue.get("code") or "") for issue in issues}
    if "channel_integration_owner_approval_missing" in codes:
        return ["obtain_owner_approval_before_outbound_send", "refresh_channel_readiness"]
    if "channel_integration_unsupported_channel" in codes:
        return ["reject_or_map_unsupported_channels", "refresh_channel_readiness"]
    if any(code.endswith("_missing") for code in codes):
        return ["collect_missing_channel_evidence", "refresh_channel_readiness"]
    if issues:
        return ["review_channel_integration_issues", "decide_channel_enablement"]
    return ["prepare_channel_integration_review"]


def _channel_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("channels") or data.get("integrations") or data.get("payloads") or []
    if isinstance(raw, Mapping):
        return list(raw.values())
    return _as_sequence(raw)


def _direction(payload: Mapping[str, Any]) -> str:
    raw = _normalize_token(payload.get("direction") or payload.get("mode"))
    if raw in {"inbound", "outbound", "bidirectional"}:
        return raw
    inbound = _bool(payload.get("inbound") or payload.get("webhook_enabled"))
    outbound = _bool(payload.get("outbound") or payload.get("send_message") or payload.get("outbound_enabled"))
    if inbound and outbound:
        return "bidirectional"
    if outbound:
        return "outbound"
    return "inbound"


def _auth_configured(payload: Mapping[str, Any]) -> bool:
    auth = payload.get("auth") or payload.get("auth_mode") or payload.get("token_ref") or payload.get("credential_ref")
    if isinstance(auth, Mapping):
        return bool(auth.get("configured") or auth.get("mode") or auth.get("token_ref") or auth.get("credential_ref"))
    return bool(str(auth or "").strip())


def _callback_evidence_count(payload: Mapping[str, Any]) -> int:
    evidence = payload.get("callback_evidence") or payload.get("webhook_evidence") or payload.get("inbound_evidence")
    count = _count(evidence)
    if any(payload.get(key) for key in INBOUND_EVIDENCE_KEYS):
        count += 1
    return count


def _delivery_evidence_count(payload: Mapping[str, Any]) -> int:
    evidence = payload.get("delivery_evidence") or payload.get("outbound_evidence") or payload.get("receipt")
    count = _count(evidence)
    if any(payload.get(key) for key in OUTBOUND_EVIDENCE_KEYS):
        count += 1
    return count


def _correlation_present(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("correlation_id")
        or payload.get("request_id")
        or payload.get("event_id")
        or payload.get("delivery_id")
        or payload.get("callback_id")
    )


def _retry_policy_present(payload: Mapping[str, Any]) -> bool:
    retry = payload.get("retry_policy") or payload.get("dead_letter") or payload.get("dlq") or payload.get("replay_strategy")
    if isinstance(retry, Mapping):
        return bool(retry.get("enabled") or retry.get("max_attempts") or retry.get("strategy"))
    return bool(retry)


def _count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        if "status" in value or "event_id" in value or "delivery_id" in value:
            return 1
        return len(value)
    if isinstance(value, (str, bytes)):
        return 1 if value else 0
    if isinstance(value, Sequence):
        return len([item for item in value if item])
    return 1


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "passed", "approved", "enabled"}


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
