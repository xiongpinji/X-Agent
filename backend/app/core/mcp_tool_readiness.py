from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SAFE_AUTH_MODES = {"none", "anonymous", "api_key", "bearer", "oauth", "oauth2", "service_account"}
SAFE_APPROVAL_PROFILES = {"allow", "auto", "read_only", "ask", "manual", "deny", "blocked"}
DANGEROUS_CAPABILITY_HINTS = {
    "shell": {"shell", "terminal", "command", "exec", "powershell", "bash", "subprocess"},
    "filesystem_write": {"write", "edit", "patch", "delete", "remove", "move", "rename", "filesystem"},
    "network": {"http", "network", "fetch", "request", "webhook", "socket"},
    "database": {"database", "sql", "postgres", "mysql", "redis", "mongodb"},
    "deployment": {"deploy", "release", "publish", "production", "kubernetes", "docker"},
    "secrets": {"secret", "token", "credential", "password", "keychain", "vault"},
}
HIGH_RISK_CAPABILITIES = {"shell", "filesystem_write", "database", "deployment", "secrets"}


@dataclass(frozen=True)
class McpToolReadinessItem:
    name: str
    server: str
    auth_mode: str
    approval_profile: str
    risk_level: str
    capability_flags: tuple[str, ...] = field(default_factory=tuple)
    scope_count: int = 0
    schema_present: bool = False
    decision: str = "ready"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "server": self.server,
            "auth_mode": self.auth_mode,
            "approval_profile": self.approval_profile,
            "risk_level": self.risk_level,
            "capability_flags": list(self.capability_flags),
            "scope_count": self.scope_count,
            "schema_present": self.schema_present,
            "decision": self.decision,
            "reasons": list(self.reasons),
        }


def build_mcp_tool_readiness(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    rows = [assess_mcp_tool_readiness(tool) for tool in _tool_payloads(data)]
    issues = _issues(rows)
    status = _status(rows)

    return {
        "kind": "mcp_tool_readiness",
        "version": 1,
        "ok": status == "ready",
        "status": status,
        "server": str(data.get("server") or data.get("server_name") or ""),
        "summary": {
            "tool_count": len(rows),
            "ready_count": sum(1 for row in rows if row.decision == "ready"),
            "needs_review_count": sum(1 for row in rows if row.decision == "needs_review"),
            "blocked_count": sum(1 for row in rows if row.decision == "blocked"),
            "high_risk_count": sum(1 for row in rows if row.risk_level in {"high", "critical"}),
            "auth_missing_count": sum(1 for row in rows if row.auth_mode in {"", "unknown"}),
            "schema_missing_count": sum(1 for row in rows if not row.schema_present),
        },
        "tools": [row.as_dict() for row in rows],
        "issues": issues,
        "next_actions": _next_actions(rows, issues),
    }


def assess_mcp_tool_readiness(tool: Mapping[str, Any] | Any) -> McpToolReadinessItem:
    payload = _as_mapping(tool)
    name = str(payload.get("name") or payload.get("tool_name") or payload.get("id") or "")
    server = str(payload.get("server") or payload.get("server_name") or payload.get("mcp_server") or "")
    auth_mode = _normalize_token(payload.get("auth_mode") or payload.get("auth") or payload.get("authentication"))
    approval_profile = _normalize_token(payload.get("approval_profile") or payload.get("approval") or payload.get("policy"))
    declared_risk = _normalize_token(payload.get("risk_level") or payload.get("risk") or "")
    capability_flags = _capability_flags(payload)
    scope_count = _scope_count(payload)
    schema_present = _schema_present(payload)
    risk_level = _risk_level(declared_risk, capability_flags)
    decision, reasons = _decision(
        auth_mode=auth_mode,
        approval_profile=approval_profile,
        risk_level=risk_level,
        capability_flags=capability_flags,
        scope_count=scope_count,
        schema_present=schema_present,
    )
    return McpToolReadinessItem(
        name=name,
        server=server,
        auth_mode=auth_mode,
        approval_profile=approval_profile,
        risk_level=risk_level,
        capability_flags=tuple(capability_flags),
        scope_count=scope_count,
        schema_present=schema_present,
        decision=decision,
        reasons=tuple(reasons),
    )


def _decision(
    *,
    auth_mode: str,
    approval_profile: str,
    risk_level: str,
    capability_flags: Sequence[str],
    scope_count: int,
    schema_present: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if auth_mode not in SAFE_AUTH_MODES:
        reasons.append("auth mode missing or unknown")
    if approval_profile not in SAFE_APPROVAL_PROFILES:
        reasons.append("approval profile missing or unknown")
    if approval_profile in {"deny", "blocked"}:
        reasons.append("approval profile blocks tool")
    if risk_level in {"high", "critical"} and approval_profile not in {"ask", "manual", "deny", "blocked"}:
        reasons.append("high-risk tool lacks manual approval")
    if scope_count == 0 and risk_level in {"medium", "high", "critical"}:
        reasons.append("scopes missing for risky tool")
    if not schema_present:
        reasons.append("input schema missing")
    if "secrets" in capability_flags and auth_mode in {"none", "anonymous"}:
        reasons.append("secret-capable tool has anonymous auth")

    if "approval profile blocks tool" in reasons or "secret-capable tool has anonymous auth" in reasons:
        return "blocked", reasons
    if risk_level == "critical" and "high-risk tool lacks manual approval" in reasons:
        return "blocked", reasons
    if reasons:
        return "needs_review", reasons
    return "ready", ["tool ready"]


def _capability_flags(payload: Mapping[str, Any]) -> list[str]:
    explicit = {
        _normalize_token(item)
        for item in _strings(payload.get("capability_flags") or payload.get("risk_flags"))
    }
    text = " ".join(
        [
            str(payload.get("name") or ""),
            str(payload.get("description") or payload.get("summary") or ""),
            " ".join(_strings(payload.get("capabilities"))),
            " ".join(_strings(payload.get("tags"))),
            " ".join(_strings(payload.get("scopes"))),
        ]
    ).lower()
    detected = {
        flag
        for flag, hints in DANGEROUS_CAPABILITY_HINTS.items()
        if flag in explicit or any(hint in text for hint in hints)
    }
    return sorted(detected)


def _risk_level(declared: str, capability_flags: Sequence[str]) -> str:
    if declared in {"low", "medium", "high", "critical"}:
        return declared
    high_count = len(set(capability_flags).intersection(HIGH_RISK_CAPABILITIES))
    if high_count >= 2:
        return "critical"
    if high_count == 1:
        return "high"
    if capability_flags:
        return "medium"
    return "low"


def _issues(rows: Sequence[McpToolReadinessItem]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        if row.decision == "ready":
            continue
        issues.append(
            {
                "code": _issue_code(row),
                "severity": "high" if row.decision == "blocked" else "medium",
                "tool": row.name,
                "server": row.server,
                "reasons": list(row.reasons),
                "risk_level": row.risk_level,
                "capability_flags": list(row.capability_flags),
            }
        )
    return issues


def _issue_code(row: McpToolReadinessItem) -> str:
    if "secret-capable tool has anonymous auth" in row.reasons:
        return "mcp_tool_secret_capability_anonymous_auth"
    if "approval profile blocks tool" in row.reasons:
        return "mcp_tool_approval_profile_blocks"
    if "high-risk tool lacks manual approval" in row.reasons:
        return "mcp_tool_high_risk_without_manual_approval"
    if "scopes missing for risky tool" in row.reasons:
        return "mcp_tool_scopes_missing"
    if "input schema missing" in row.reasons:
        return "mcp_tool_input_schema_missing"
    if "auth mode missing or unknown" in row.reasons:
        return "mcp_tool_auth_unknown"
    if "approval profile missing or unknown" in row.reasons:
        return "mcp_tool_approval_profile_unknown"
    return "mcp_tool_needs_review"


def _status(rows: Sequence[McpToolReadinessItem]) -> str:
    if not rows:
        return "empty"
    if any(row.decision == "blocked" for row in rows):
        return "blocked"
    if any(row.decision == "needs_review" for row in rows):
        return "needs_review"
    return "ready"


def _next_actions(
    rows: Sequence[McpToolReadinessItem],
    issues: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not rows:
        return ["provide_mcp_tool_metadata"]
    codes = {str(issue.get("code") or "") for issue in issues}
    if any(row.decision == "blocked" for row in rows):
        return ["block_or_disable_unsafe_tools", "review_mcp_auth_and_approval"]
    if "mcp_tool_high_risk_without_manual_approval" in codes:
        return ["require_manual_approval_for_high_risk_tools", "refresh_mcp_tool_readiness"]
    if any(code.endswith("_missing") for code in codes):
        return ["collect_missing_tool_schema_or_scopes", "refresh_mcp_tool_readiness"]
    if issues:
        return ["review_mcp_tool_metadata", "decide_tool_enablement"]
    return ["prepare_mcp_tool_integration_review"]


def _tool_payloads(data: Mapping[str, Any]) -> list[Any]:
    raw = data.get("tools") or data.get("mcp_tools") or data.get("manifest") or []
    if isinstance(raw, Mapping):
        nested = raw.get("tools")
        if nested is not None:
            return _as_sequence(nested)
        return list(raw.values())
    return _as_sequence(raw)


def _scope_count(payload: Mapping[str, Any]) -> int:
    scopes = payload.get("scopes") or payload.get("required_scopes") or payload.get("permissions")
    return len(_strings(scopes))


def _schema_present(payload: Mapping[str, Any]) -> bool:
    schema = payload.get("input_schema") or payload.get("parameters") or payload.get("parameters_schema") or payload.get("schema")
    if not schema:
        return False
    if isinstance(schema, Mapping):
        return bool(schema.get("properties") or schema.get("type") or schema)
    return True


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


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
