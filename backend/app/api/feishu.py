from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.core.feishu_bridge import feishu_bridge
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/integrations/feishu", tags=["feishu"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
logger = logging.getLogger("xagent.feishu")
LIVE_EVIDENCE_ENV = "XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_EVIDENCE"
LIVE_EVIDENCE_PATH_ENV = "XAGENT_COMMERCIAL_PILOT_FEISHU_LIVE_REPORT_PATH"
DEFAULT_LIVE_EVIDENCE_PATH = Path(".xagent_runtime/reports/commercial-pilot-feishu-live.json")


class FeishuConfigRequest(BaseModel):
    app_id: str = Field(..., min_length=1)
    app_secret: str = Field(..., min_length=1)
    base_url: str = Field(default="https://open.feishu.cn", min_length=1)
    encrypt_key: str | None = Field(default=None, min_length=1)


class FeishuSendRequest(BaseModel):
    receive_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=20_000)
    receive_id_type: str = Field(default="chat_id", min_length=1)
    session_id: str | None = None


class FeishuEventRequest(BaseModel):
    payload: dict[str, Any]


@dataclass(frozen=True)
class FeishuLiveEvidence:
    status: str
    generated_at: str
    channel: str
    evidence_type: str
    owner_gated: bool
    event_id: str | None
    event_type: str | None
    tenant_key_present: bool
    message_id_present: bool
    chat_id_present: bool
    content_present: bool
    signature_mode: str
    encrypted_callback: bool
    app_id_configured: bool
    app_secret_configured: bool
    encrypt_key_configured: bool
    mutation_performed: bool
    outbound_message_sent: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    known_limits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _live_evidence_path() -> Path:
    return Path(os.getenv(LIVE_EVIDENCE_PATH_ENV, str(DEFAULT_LIVE_EVIDENCE_PATH)))


def _message(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    return message


def _write_live_evidence(
    *,
    payload: dict[str, Any],
    result: dict[str, Any],
    signature_mode: str,
    encrypted_callback: bool,
) -> None:
    if not _env_flag(LIVE_EVIDENCE_ENV):
        return
    if result.get("accepted") is not True:
        return

    message = _message(payload)
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    sender = event.get("sender") if isinstance(event.get("sender"), dict) else {}
    report = FeishuLiveEvidence(
        status="passed",
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        channel="feishu",
        evidence_type="commercial_pilot_feishu_live",
        owner_gated=True,
        event_id=result.get("event_id"),
        event_type=result.get("event_type"),
        tenant_key_present=bool(payload.get("tenant_key") or payload.get("header", {}).get("tenant_key")),
        message_id_present=bool(message.get("message_id") or payload.get("event", {}).get("message_id")),
        chat_id_present=bool(message.get("chat_id") or payload.get("event", {}).get("chat_id")),
        content_present=bool(message.get("content")),
        signature_mode=signature_mode,
        encrypted_callback=encrypted_callback,
        app_id_configured=bool(feishu_bridge.app_id),
        app_secret_configured=bool(feishu_bridge.app_secret),
        encrypt_key_configured=bool(feishu_bridge.encrypt_key),
        mutation_performed=False,
        outbound_message_sent=False,
        checks=[
            {"name": "event_accepted", "status": "passed"},
            {"name": "sender_present", "status": "passed" if sender else "preview"},
            {"name": "message_id_present", "status": "passed" if message.get("message_id") else "preview"},
            {"name": "no_outbound_mutation", "status": "passed"},
        ],
        known_limits=[
            "This report proves inbound Feishu event delivery only.",
            "Outbound Feishu message send remains separately owner-gated.",
            "Full Codex parity is not claimed by this report.",
        ],
    )
    output_path = _live_evidence_path()
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to write Feishu live evidence report: %s", exc)


def _resolve_signature_context(
    *,
    x_lark_signature: str | None,
    x_lark_timestamp: str | None,
    x_lark_nonce: str | None,
    x_feishu_signature: str | None,
    x_feishu_timestamp: str | None,
    x_feishu_nonce: str | None,
) -> tuple[str, str, str, str]:
    if x_lark_signature and x_lark_timestamp and x_lark_nonce:
        return x_lark_signature, x_lark_timestamp, x_lark_nonce, "lark_sha256"
    if x_feishu_signature and x_feishu_timestamp and x_feishu_nonce:
        return x_feishu_signature, x_feishu_timestamp, x_feishu_nonce, "legacy_hmac_sha256"
    raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Missing Feishu signature headers.")


@router.post("/configure")
async def configure_feishu(request: FeishuConfigRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    feishu_bridge.configure(
        app_id=request.app_id,
        app_secret=request.app_secret,
        base_url=request.base_url,
        encrypt_key=request.encrypt_key,
    )
    return {"configured": True, "base_url": request.base_url}


@router.get("/status")
async def feishu_status(principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    snapshot = await feishu_bridge.store.snapshot()
    return {
        "configured": bool(feishu_bridge.app_id and feishu_bridge.app_secret),
        "base_url": feishu_bridge.base_url,
        "snapshot": snapshot,
    }


@router.post("/send")
async def send_feishu_message(request: FeishuSendRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "agent:run")
    if not feishu_bridge.app_id or not feishu_bridge.app_secret:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Feishu app is not configured.")
    payload = await feishu_bridge.send_text_message(
        receive_id=request.receive_id,
        text=request.text,
        receive_id_type=request.receive_id_type,
    )
    return {
        "accepted": True,
        "session_id": request.session_id,
        "receive_id": request.receive_id,
        "result": payload,
    }


@router.post("/events")
async def feishu_event_callback(
    request: Request,
    x_lark_signature: str | None = Header(default=None, alias="X-Lark-Signature"),
    x_lark_timestamp: str | None = Header(default=None, alias="X-Lark-Request-Timestamp"),
    x_lark_nonce: str | None = Header(default=None, alias="X-Lark-Request-Nonce"),
    x_feishu_signature: str | None = Header(default=None),
    x_feishu_timestamp: str | None = Header(default=None),
    x_feishu_nonce: str | None = Header(default=None),
) -> dict[str, object]:
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid Feishu event JSON.")
    if not isinstance(payload, dict):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Feishu event payload must be an object.")

    if isinstance(payload.get("encrypt"), str):
        try:
            payload = feishu_bridge.decrypt_callback_payload(payload["encrypt"])
        except Exception as exc:  # noqa: BLE001 - invalid encrypted callbacks are auth failures
            raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, f"Invalid Feishu encrypted payload: {exc}")
        if payload.get("type") == "url_verification" and isinstance(payload.get("challenge"), str):
            return {"challenge": payload["challenge"]}
        signature, timestamp, nonce, mode = _resolve_signature_context(
            x_lark_signature=x_lark_signature,
            x_lark_timestamp=x_lark_timestamp,
            x_lark_nonce=x_lark_nonce,
            x_feishu_signature=x_feishu_signature,
            x_feishu_timestamp=x_feishu_timestamp,
            x_feishu_nonce=x_feishu_nonce,
        )
        if not feishu_bridge.verify_signature(
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            signature=signature,
            mode=mode,
        ):
            raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid Feishu signature.")
        result = await feishu_bridge.handle_event(payload)
        _write_live_evidence(
            payload=payload,
            result=result,
            signature_mode=mode,
            encrypted_callback=True,
        )
        return {"ok": True, "result": result}

    if payload.get("type") == "url_verification" and isinstance(payload.get("challenge"), str):
        return {"challenge": payload["challenge"]}

    signature, timestamp, nonce, mode = _resolve_signature_context(
        x_lark_signature=x_lark_signature,
        x_lark_timestamp=x_lark_timestamp,
        x_lark_nonce=x_lark_nonce,
        x_feishu_signature=x_feishu_signature,
        x_feishu_timestamp=x_feishu_timestamp,
        x_feishu_nonce=x_feishu_nonce,
    )
    if not feishu_bridge.verify_signature(
        timestamp=timestamp,
        nonce=nonce,
        body=body,
        signature=signature,
        mode=mode,
    ):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid Feishu signature.")
    result = await feishu_bridge.handle_event(payload)
    _write_live_evidence(
        payload=payload,
        result=result,
        signature_mode=mode,
        encrypted_callback=False,
    )
    return {"ok": True, "result": result}
