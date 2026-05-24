from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.recovery_helpers import build_recovery_context
from backend.app.core.contracts import ErrorCode
from backend.app.core.desktop import desktop_automation_store
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.services.desktop.ui_tars_client import ui_tars_desktop_client

router = APIRouter(prefix="/api/v1/desktop", tags=["desktop"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class DesktopSessionCreateRequest(BaseModel):
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    provider: str = "ui-tars"
    metadata: dict[str, object] = Field(default_factory=dict)


class DesktopActionRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=80)
    target: str | None = None
    value: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


@router.get("/sessions")
async def list_desktop_sessions(principal: PrincipalDependency) -> list[dict[str, object]]:
    enforce_scope(principal, "tools:read")
    return [_session_to_dict(session) for session in desktop_automation_store.list_sessions()]


@router.post("/sessions")
async def create_desktop_session(request: DesktopSessionCreateRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    session = desktop_automation_store.create_session(
        trace_id=request.trace_id,
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        provider=request.provider,
        metadata=request.metadata,
    )
    provider_session = ui_tars_desktop_client.create_session(
        trace_id=request.trace_id,
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
    )
    session.metadata.update({"ui_tars_session_id": provider_session.session_id, "provider": request.provider})
    return _session_to_dict(session)


@router.get("/sessions/{session_id}")
async def get_desktop_session(session_id: str, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    session = desktop_automation_store.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Desktop session not found.", details={"resource_id": session_id})
    return _session_to_dict(session)


@router.post("/sessions/{session_id}/actions")
async def send_desktop_action(session_id: str, request: DesktopActionRequest, principal: PrincipalDependency) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    session = desktop_automation_store.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Desktop session not found.", details={"resource_id": session_id})
    provider_session_id = str(session.metadata.get("ui_tars_session_id") or session.session_id)
    action = ui_tars_desktop_client.send_action(
        provider_session_id,
        request.action,
        target=request.target,
        value=request.value,
        metadata=request.metadata,
    )
    local_action = desktop_automation_store.send_action(
        session_id,
        request.action,
        target=request.target,
        value=request.value,
        metadata={**request.metadata, "provider_action": action.data},
    )
    return {
        "session_id": session_id,
        "accepted": local_action.ok and action.ok,
        "action": local_action.model_dump(mode="json"),
        "provider_action": action.__dict__,
        "provider_session_id": provider_session_id,
    }


@router.post("/sessions/{session_id}/close")
async def close_desktop_session(session_id: str, principal: PrincipalDependency) -> dict[str, bool]:
    enforce_scope(principal, "tools:read")
    session = desktop_automation_store.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Desktop session not found.", details={"resource_id": session_id})
    provider_session_id = str(session.metadata.get("ui_tars_session_id") or session.session_id)
    ui_tars_desktop_client.close(provider_session_id)
    if not desktop_automation_store.close(session_id):
        raise api_error(404, ErrorCode.RESOURCE_NOT_FOUND, "Desktop session not found.", details={"resource_id": session_id})
    return {"closed": True}


def _session_to_dict(session) -> dict[str, object]:
    data = session.model_dump(mode="json")
    recovery = build_recovery_context(
        status="active" if session.active else "closed",
        resource_type="desktop_session",
        resource_id=session.session_id,
        next_actions=[
            "inspect desktop session" if session.active else "start a new desktop session",
            "continue desktop automation" if session.active else "reopen the desktop session",
        ],
        latest_decision="active" if session.active else "closed",
        retryable=session.active,
        confidence=0.9 if session.active else 0.55,
        tool_name="desktop_inspect" if session.active else "desktop_reopen",
        follow_up=["review desktop actions", "continue automation"],
        status_detail=f"desktop session {'active' if session.active else 'closed'}",
        remediation="inspect desktop session and continue automation",
    )
    data["recovery"] = build_recovery_payload(
        status="active" if session.active else "closed",
        resource_type="desktop_session",
        resource_id=session.session_id,
        next_actions=[
            "inspect desktop session" if session.active else "start a new desktop session",
            "continue desktop automation" if session.active else "reopen the desktop session",
        ],
        latest_decision="active" if session.active else "closed",
        retryable=session.active,
        confidence=0.9 if session.active else 0.55,
        tool_name="desktop_inspect" if session.active else "desktop_reopen",
        follow_up=["review desktop actions", "continue automation"],
        status_detail=f"desktop session {'active' if session.active else 'closed'}",
        remediation="inspect desktop session and continue automation",
    )
    if "ui_tars_session_id" in session.metadata:
        data["provider_session_id"] = session.metadata["ui_tars_session_id"]
        data["provider"] = session.provider
    return data
