from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


REDACTED_VALUE = "<redacted>"
REDACTED_TOKEN = "<redacted-token>"

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:openai_api_key|deepseek_api_key|xagent_[a-z0-9_]*(?:api_key|secret|token|password)|"
    r"kubeconfig|password|secret|token)\s*[:=]\s*(?!<redacted>\b)[^\s,;]+"
)
SECRET_TOKEN_RE = re.compile(r"\b(?:sk|pk)-[A-Za-z0-9][A-Za-z0-9_-]{10,}\b")

DEFAULT_SECRET_ENV_NAMES = (
    "OPENAI_API_KEY",
    "XAGENT_OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAGENT_DEEPSEEK_API_KEY",
    "XAGENT_LLM_API_KEY",
    "OLLAMA_API_KEY",
    "XAGENT_OLLAMA_API_KEY",
    "XAGENT_AUDIT_HMAC_SECRET",
    "XAGENT_BOOTSTRAP_API_KEY",
    "XAGENT_BOOTSTRAP_API_KEY_SHA256",
    "XAGENT_LANGFUSE_SECRET_KEY",
    "KUBECONFIG",
)


def redact_output_text(
    value: str | bytes | None,
    *,
    env: Mapping[str, str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> str:
    text = coerce_output_text(value)
    for secret in _secret_values(env=env, explicit_values=secret_values):
        text = text.replace(secret, REDACTED_VALUE)
    text = SECRET_ASSIGNMENT_RE.sub(_redact_assignment, text)
    return SECRET_TOKEN_RE.sub(REDACTED_TOKEN, text)


def redact_payload(
    payload: Any,
    *,
    env: Mapping[str, str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> Any:
    if isinstance(payload, Mapping):
        return {
            str(key): redact_payload(value, env=env, secret_values=secret_values)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [redact_payload(item, env=env, secret_values=secret_values) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_payload(item, env=env, secret_values=secret_values) for item in payload)
    if isinstance(payload, (str, bytes)) or payload is None:
        return redact_output_text(payload, env=env, secret_values=secret_values)
    return payload


def output_tail(
    value: str | bytes | None,
    *,
    limit: int = 6000,
    redact: bool = True,
    env: Mapping[str, str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> str:
    text = redact_output_text(value, env=env, secret_values=secret_values) if redact else coerce_output_text(value)
    safe_limit = max(int(limit), 0)
    return text if len(text) <= safe_limit else text[-safe_limit:]


def looks_like_secret_leak(value: str | bytes | None) -> bool:
    text = coerce_output_text(value)
    return bool(SECRET_ASSIGNMENT_RE.search(text) or SECRET_TOKEN_RE.search(text))


def coerce_output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _redact_assignment(match: re.Match[str]) -> str:
    text = match.group(0)
    separator = "=" if "=" in text else ":"
    key = text.split(separator, 1)[0]
    return f"{key}{separator}{REDACTED_VALUE}"


def _secret_values(
    *,
    env: Mapping[str, str] | None,
    explicit_values: Sequence[str] | None,
) -> tuple[str, ...]:
    values: list[str] = []
    for value in explicit_values or ():
        normalized = str(value or "").strip()
        if normalized and normalized not in values:
            values.append(normalized)
    if env:
        for name in DEFAULT_SECRET_ENV_NAMES:
            normalized = str(env.get(name, "")).strip()
            if normalized and normalized not in values:
                values.append(normalized)
    values.sort(key=len, reverse=True)
    return tuple(values)
