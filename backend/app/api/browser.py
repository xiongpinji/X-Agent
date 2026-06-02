from __future__ import annotations

import ipaddress
import re
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.api.recovery_helpers import build_recovery_context, build_recovery_payload
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.services.browser.automation import browser_automation

router = APIRouter(prefix="/api/v1/browser", tags=["browser"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


def _is_url_allowed(url: str) -> bool:
    """Block SSRF vectors: private IPs, localhost, file protocol, metadata endpoints."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = parsed.hostname or ""
    if hostname.lower() in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False
    if re.match(r"^169\.254\.", hostname):
        return False
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_multicast:
            return False
    except ValueError:
        pass
    return True


def _sanitize_screenshot_path(path: str) -> str:
    """Restrict screenshot paths to /tmp or relative paths without .."""
    import os
    from pathlib import Path
    normalized = os.path.normpath(path)
    if ".." in normalized.split(os.sep):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid path: traversal detected.")
    # Block absolute paths on any platform
    if Path(path).is_absolute() or path.startswith("/") or path.startswith("\\"):
        allowed_prefixes = ("/tmp", "/var/tmp")
        if not any(str(normalized).lower().startswith(p) for p in allowed_prefixes):
            raise api_error(400, ErrorCode.VALIDATION_ERROR, "Invalid path: absolute paths must be under /tmp.")
    return normalized


class BrowserSessionCreateRequest(BaseModel):
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"


class BrowserActionRequest(BaseModel):
    value: str | None = None
    selector: str | None = None
    url: str | None = None
    path: str | None = None
    text: str | None = None


class BrowserActionResponse(BaseModel):
    action: str
    ok: bool
    detail: str = ""
    data: dict[str, object] = Field(default_factory=dict)


class BrowserSessionResponse(BaseModel):
    session_id: str
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"
    current_url: str | None = None
    active: bool = True
    actions: list[BrowserActionResponse] = Field(default_factory=list)


def _can_access_session(session, principal: Principal) -> bool:
    if principal.role == "admin":
        return True
    return session.tenant_id == principal.tenant_id and session.user_id == principal.user_id


@router.get("/sessions")
async def list_browser_sessions(principal: PrincipalDependency) -> list[BrowserSessionResponse]:
    enforce_scope(principal, "tools:read")
    sessions = browser_automation.list_sessions()
    if principal.role != "admin":
        sessions = [s for s in sessions if _can_access_session(s, principal)]
    return [_session_response(session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=BrowserSessionResponse)
async def browser_get_session(
    session_id: str,
    principal: PrincipalDependency,
) -> BrowserSessionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    return _session_response(session)


@router.get("/sessions/{session_id}/correlation")
async def browser_session_correlation(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, object]:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    trace_id = session.trace_id or session.run_id or session.session_id
    recovery = build_recovery_context(
        status="active" if session.active else "closed",
        resource_type="browser_session",
        resource_id=session.session_id,
        next_actions=["inspect browser session" if session.active else "start a new browser session", "continue browser automation" if session.active else "reopen the browser session"],
        latest_decision="active" if session.active else "closed",
        retryable=session.active,
        confidence=0.9 if session.active else 0.55,
        tool_name="browser_inspect" if session.active else "browser_reopen",
        follow_up=["review browser actions", "continue automation"],
        status_detail=f"browser session {'active' if session.active else 'closed'}",
        remediation="inspect session state and continue automation",
    )
    return {
        "trace_id": trace_id,
        "resource_type": "browser_session",
        "resource_id": session.session_id,
        "status": "active" if session.active else "closed",
        "recovery": build_recovery_payload(
        status="active" if session.active else "closed",
        resource_type="browser_session",
        resource_id=session.session_id,
        next_actions=["inspect browser session" if session.active else "start a new browser session", "continue browser automation" if session.active else "reopen the browser session"],
        latest_decision="active" if session.active else "closed",
        retryable=session.active,
        confidence=0.9 if session.active else 0.55,
        tool_name="browser_inspect" if session.active else "browser_reopen",
        follow_up=["review browser actions", "continue automation"],
        status_detail=f"browser session {'active' if session.active else 'closed'}",
        remediation="inspect session state and continue automation",
    ),
        "trace_summary": {
            "trace_id": trace_id,
            "event_count": len(session.actions),
            "started_at": None,
            "ended_at": None,
            "last_event": session.actions[-1].action if session.actions else "browser.session.created",
            "task": session.current_url or "browser session",
            "snapshot": {
                "resource_type": "browser_session",
                "resource_id": session.session_id,
                "trace_id": trace_id,
                "run_id": session.run_id,
                "tenant_id": session.tenant_id,
                "user_id": session.user_id,
                "current_url": session.current_url,
                "active": session.active,
                "recovery": recovery,
            },
        },
        "snapshot": {
            "resource_type": "browser_session",
            "resource_id": session.session_id,
            "trace_id": trace_id,
            "run_id": session.run_id,
            "tenant_id": session.tenant_id,
            "user_id": session.user_id,
            "current_url": session.current_url,
            "active": session.active,
            "recovery": recovery,
        },
    }


@router.post("/sessions", response_model=BrowserSessionResponse)
async def create_browser_session(
    request: BrowserSessionCreateRequest,
    principal: PrincipalDependency,
) -> BrowserSessionResponse:
    """Create a browser session with strict tenant isolation.

    Security: Enforce that the requested tenant_id matches the principal's tenant_id
    unless the principal is an admin. This prevents tenant isolation bypass attacks.
    """
    enforce_scope(principal, "tools:read")

    # CRITICAL SECURITY FIX: Validate tenant_id matches current principal
    # Non-admin users can only create sessions for their own tenant
    if principal.role != "admin" and request.tenant_id != principal.tenant_id:
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            f"Cannot create session for tenant '{request.tenant_id}'. You can only create sessions for your own tenant '{principal.tenant_id}'."
        )

    # Use principal's user_id if not explicitly provided or if user is not admin
    user_id = request.user_id
    if principal.role != "admin":
        user_id = principal.user_id

    session = browser_automation.create_session(
        trace_id=request.trace_id,
        run_id=request.run_id,
        tenant_id=request.tenant_id,
        user_id=user_id,
    )
    return _session_response(session)


@router.post("/sessions/{session_id}/goto", response_model=BrowserActionResponse)
async def browser_goto(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    if not request.url:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "url is required.")
    if not _is_url_allowed(request.url):
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "URL is not allowed.")
    return _action_response(browser_automation.goto(session_id, request.url))


@router.post("/sessions/{session_id}/click", response_model=BrowserActionResponse)
async def browser_click(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    if not request.selector:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "selector is required.")
    return _action_response(browser_automation.click(session_id, request.selector))


@router.post("/sessions/{session_id}/fill", response_model=BrowserActionResponse)
async def browser_fill(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    if not request.selector or request.value is None:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "selector and value are required.")
    return _action_response(browser_automation.fill(session_id, request.selector, request.value))


@router.post("/sessions/{session_id}/extract-text", response_model=BrowserActionResponse)
async def browser_extract_text(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    selector = request.selector or request.text
    if not selector:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "selector is required.")
    return _action_response(browser_automation.extract_text(session_id, selector))


@router.post("/sessions/{session_id}/wait-for", response_model=BrowserActionResponse)
async def browser_wait_for(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    selector = request.selector or request.text
    if not selector:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "selector is required.")
    return _action_response(browser_automation.wait_for(session_id, selector))


@router.post("/sessions/{session_id}/screenshot", response_model=BrowserActionResponse)
async def browser_screenshot(
    session_id: str,
    request: BrowserActionRequest,
    principal: PrincipalDependency,
) -> BrowserActionResponse:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is None:
        raise api_error(404, ErrorCode.WORKFLOW_INVALID, "Browser session not found.")
    if not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    if not request.path:
        raise api_error(400, ErrorCode.WORKFLOW_INVALID, "path is required.")
    safe_path = _sanitize_screenshot_path(request.path)
    return _action_response(browser_automation.screenshot(session_id, safe_path))


@router.post("/sessions/{session_id}/close")
async def browser_close(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, bool]:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is not None and not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    return {"closed": browser_automation.close(session_id)}


@router.delete("/sessions/{session_id}")
async def browser_delete_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, bool]:
    enforce_scope(principal, "tools:read")
    session = browser_automation.get_session(session_id)
    if session is not None and not _can_access_session(session, principal):
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "Access denied.")
    return {"deleted": browser_automation.close(session_id)}


def _action_response(result) -> BrowserActionResponse:
    return BrowserActionResponse(
        action=result.action,
        ok=result.ok,
        detail=result.detail,
        data=result.data,
    )


def _session_response(session) -> BrowserSessionResponse:
    return BrowserSessionResponse(
        session_id=session.session_id,
        trace_id=session.trace_id,
        run_id=session.run_id,
        tenant_id=session.tenant_id,
        user_id=session.user_id,
        current_url=session.current_url,
        active=session.active,
        actions=[_action_response(action) for action in session.actions],
    )
