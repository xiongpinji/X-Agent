"""Computer Use API — desktop control via screenshot + mouse/keyboard.

Exposes the Hermes-Agent style computer-use capability over HTTP. See
:mod:`backend.app.core.computer_use` for the underlying engine.
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.computer_use import (
    BackendUnavailableError,
    ComputerUseError,
    ConfirmationRequiredError,
    RateLimitExceededError,
    computer_use_session_store,
)
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/computer-use", tags=["computer-use"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class SessionCreateRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str = "anonymous"
    dry_run: bool = False
    require_confirmation: bool = True
    action_timeout: float = Field(default=30.0, gt=0, le=600)
    max_actions_per_second: int = Field(default=10, ge=1, le=100)
    allowed_applications: list[str] = Field(default_factory=list)
    blocked_applications: list[str] = Field(default_factory=list)


class ExecuteTaskRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=4000)
    confirmed: bool = False
    verify: bool = True


class ActionRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=60)
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_session_or_404(session_id: str):
    session = computer_use_session_store.get(session_id)
    if session is None:
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Computer-use session not found.",
            details={"resource_id": session_id},
        )
    return session


def _translate_error(exc: Exception, session_id: str | None = None):
    """Map engine errors to structured API errors."""
    if isinstance(exc, ConfirmationRequiredError):
        return api_error(
            409,
            ErrorCode.RESOURCE_CONFLICT,
            "Explicit confirmation required for this action.",
            details={"action": exc.action, "reason": exc.reason, "session_id": session_id},
        )
    if isinstance(exc, RateLimitExceededError):
        return api_error(
            429,
            ErrorCode.RATE_LIMIT_EXCEEDED,
            "Computer-use action rate limit exceeded.",
            details={"session_id": session_id},
        )
    if isinstance(exc, BackendUnavailableError):
        return api_error(
            503,
            ErrorCode.INTERNAL_ERROR,
            "No desktop automation backend available on this host.",
            details={"session_id": session_id},
        )
    if isinstance(exc, ComputerUseError):
        return api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            details={"session_id": session_id},
        )
    return api_error(
        500,
        ErrorCode.INTERNAL_ERROR,
        "Unexpected computer-use failure.",
        details={"session_id": session_id, "error": str(exc)},
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("/session")
async def create_session(request: SessionCreateRequest, principal: PrincipalDependency) -> dict[str, Any]:
    """Start a new computer-use session."""
    enforce_scope(principal, "tools:read")
    try:
        from backend.app.core.computer_use import ComputerUseAgent

        agent = ComputerUseAgent(dry_run=request.dry_run)
        session = computer_use_session_store.create(
            agent=agent,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            require_confirmation=request.require_confirmation,
            action_timeout=request.action_timeout,
            max_actions_per_second=request.max_actions_per_second,
            allowed_applications=request.allowed_applications,
            blocked_applications=request.blocked_applications,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise _translate_error(exc) from exc
    return session.to_dict()


@router.post("/{session_id}/execute")
async def execute_task(
    session_id: str, request: ExecuteTaskRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Plan and execute a high-level task on the desktop."""
    enforce_scope(principal, "tools:read")
    session = _get_session_or_404(session_id)
    try:
        result = await session.execute_task(
            request.task, confirmed=request.confirmed, verify=request.verify
        )
    except ConfirmationRequiredError as exc:
        raise _translate_error(exc, session_id) from exc
    except Exception as exc:
        raise _translate_error(exc, session_id) from exc
    return {"session_id": session_id, **result}


@router.get("/{session_id}/screenshot")
async def get_screenshot(
    session_id: str,
    principal: PrincipalDependency,
    encoding: str = "binary",
) -> Any:
    """Return the current screen capture as PNG (or base64 JSON)."""
    enforce_scope(principal, "tools:read")
    session = _get_session_or_404(session_id)
    try:
        image = session.screenshot()
    except Exception as exc:
        raise _translate_error(exc, session_id) from exc
    if encoding == "base64":
        return {
            "session_id": session_id,
            "format": "png",
            "encoding": "base64",
            "data": base64.b64encode(image).decode("ascii"),
            "size_bytes": len(image),
        }
    return Response(content=image, media_type="image/png")


@router.post("/{session_id}/action")
async def perform_action(
    session_id: str, request: ActionRequest, principal: PrincipalDependency
) -> dict[str, Any]:
    """Execute a single low-level action (click, type_text, hotkey, ...)."""
    enforce_scope(principal, "tools:read")
    session = _get_session_or_404(session_id)
    try:
        record = await session.perform_action(
            request.action, request.params, confirmed=request.confirmed
        )
    except ConfirmationRequiredError as exc:
        raise _translate_error(exc, session_id) from exc
    except Exception as exc:
        raise _translate_error(exc, session_id) from exc
    return {"session_id": session_id, "action": record.to_dict()}


@router.get("/{session_id}/history")
async def get_history(session_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Return the recorded action history for replay/audit."""
    enforce_scope(principal, "tools:read")
    session = _get_session_or_404(session_id)
    return {
        "session_id": session_id,
        "action_count": len(session.history),
        "history": session.get_history(),
    }


@router.delete("/{session_id}")
async def end_session(session_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """End and remove a computer-use session."""
    enforce_scope(principal, "tools:read")
    if not computer_use_session_store.remove(session_id):
        raise api_error(
            404,
            ErrorCode.RESOURCE_NOT_FOUND,
            "Computer-use session not found.",
            details={"resource_id": session_id},
        )
    return {"session_id": session_id, "closed": True}
