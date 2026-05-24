from __future__ import annotations

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


class FeishuConfigRequest(BaseModel):
    app_id: str = Field(..., min_length=1)
    app_secret: str = Field(..., min_length=1)
    base_url: str = Field(default="https://open.feishu.cn", min_length=1)


class FeishuSendRequest(BaseModel):
    receive_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=20_000)
    receive_id_type: str = Field(default="chat_id", min_length=1)
    session_id: str | None = None


class FeishuEventRequest(BaseModel):
    payload: dict[str, Any]


@router.post("/configure")
async def configure_feishu(request: FeishuConfigRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "security:manage")
    feishu_bridge.configure(app_id=request.app_id, app_secret=request.app_secret, base_url=request.base_url)
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
async def feishu_event_callback(request: Request, x_feishu_signature: str | None = Header(default=None), x_feishu_timestamp: str | None = Header(default=None), x_feishu_nonce: str | None = Header(default=None)) -> dict[str, object]:
    body = await request.body()
    if not (x_feishu_signature and x_feishu_timestamp and x_feishu_nonce):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Missing Feishu signature headers.")
    if not feishu_bridge.verify_signature(
        timestamp=x_feishu_timestamp,
        nonce=x_feishu_nonce,
        body=body,
        signature=x_feishu_signature,
    ):
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid Feishu signature.")
    payload = await request.json()
    result = await feishu_bridge.handle_event(payload)
    return {"ok": True, "result": result}
