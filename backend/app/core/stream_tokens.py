from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.core.security import Principal
from backend.app.settings import get_settings


STREAM_TOKEN_TTL_SECONDS = 60


def create_stream_token(
    *,
    stream_id: str,
    principal: Principal,
    scopes: list[str],
    ttl_seconds: int = STREAM_TOKEN_TTL_SECONDS,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    payload = {
        "stream_id": stream_id,
        "tenant_id": principal.tenant_id,
        "user_id": principal.user_id,
        "agent_id": principal.agent_id,
        "trace_id": principal.trace_id,
        "role": principal.role,
        "scopes": scopes,
        "exp": int(expires_at.timestamp()),
    }
    encoded_payload = _encode_payload(payload)
    signature = _sign_payload(encoded_payload)
    return f"{encoded_payload}.{signature}"


def principal_from_stream_token(stream_id: str, token: str | None) -> Principal | None:
    if not token or "." not in token:
        return None
    encoded_payload, signature = token.rsplit(".", 1)
    expected_signature = _sign_payload(encoded_payload)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    payload = _decode_payload(encoded_payload)
    if not payload:
        return None
    if payload.get("stream_id") != stream_id:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(datetime.now(timezone.utc).timestamp()):
        return None

    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    if not isinstance(tenant_id, str) or not isinstance(user_id, str):
        return None

    raw_scopes = payload.get("scopes", [])
    scopes = [scope for scope in raw_scopes if isinstance(scope, str)]
    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=str(payload.get("agent_id") or "default-agent"),
        trace_id=str(payload.get("trace_id") or ""),
        role=str(payload.get("role") or "user"),
        scopes=scopes,
        authenticated=True,
    )


def _secret() -> bytes:
    settings = get_settings()
    return settings.jwt_secret.encode("utf-8")


def _encode_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_payload(encoded: str) -> dict[str, Any] | None:
    try:
        padding = "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sign_payload(encoded_payload: str) -> str:
    digest = hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
