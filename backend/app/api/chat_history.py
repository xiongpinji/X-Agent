"""Chat history persistence API.

Provides endpoints for storing and retrieving chat conversations.
Sessions are persisted to PostgreSQL in production and file SQLite in dev.

Endpoints:
- GET    /api/v1/chat/history          — List conversation sessions
- GET    /api/v1/chat/history/{id}     — Get messages for a session
- DELETE /api/v1/chat/history/{id}     — Delete a session
- DELETE /api/v1/chat/history          — Clear all history
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.chat_history_store import (
    ChatHistoryStore,
    get_chat_history_store,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/chat", tags=["chat-history"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
StoreDependency = Annotated[ChatHistoryStore, Depends(get_chat_history_store)]


# ─── Models ────────────────────────────────────────────────────────────────────


class SessionSummary(BaseModel):
    id: str
    title: str
    agent_id: str
    created_at: float
    updated_at: float
    message_count: int


class CreateChatSessionRequest(BaseModel):
    title: str = Field(default="", max_length=255, strict=True)
    agent_id: str = Field(default="default", min_length=1, max_length=64, strict=True)


class AddChatMessageRequest(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(min_length=1, max_length=100_000, strict=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/history")
async def list_chat_history(
    limit: int = Query(50, ge=1, le=200),
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, Any]:
    """List chat sessions for the current user."""
    enforce_scope(principal, "agent:read")
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    sessions, total = await store.list_sessions(
        tenant_id=tenant_id,
        user_id=user_id,
        limit=limit,
    )
    return {
        "sessions": [
            SessionSummary(
                id=s.id,
                title=s.title or f"Chat {s.id[-6:]}",
                agent_id=s.agent_id,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=s.message_count,
            ).model_dump()
            for s in sessions
        ],
        "total": total,
    }


@router.get("/history/{session_id}")
async def get_chat_session(
    session_id: str,
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, Any]:
    """Get full message history for a session."""
    enforce_scope(principal, "agent:read")
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    session = await store.get_session(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "title": session.title,
        "agent_id": session.agent_id,
        "messages": [m.model_dump() for m in session.messages],
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.post("/history")
async def create_chat_session(
    payload: CreateChatSessionRequest | None = None,
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, Any]:
    """Create a new chat session."""
    enforce_scope(principal, "agent:run")
    payload = payload or CreateChatSessionRequest()
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    session = await store.create_session(
        tenant_id=tenant_id,
        user_id=user_id,
        title=payload.title,
        agent_id=payload.agent_id,
    )
    return {"id": session.id, "title": session.title, "created_at": session.created_at}


@router.post("/history/{session_id}/messages")
async def add_message_to_session(
    session_id: str,
    payload: AddChatMessageRequest,
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, Any]:
    """Add a message to an existing session."""
    enforce_scope(principal, "agent:run")
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    message = await store.append_message(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        role=payload.role,
        content=payload.content,
        metadata=payload.metadata,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Session not found")
    session = await store.get_session(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": message.id, "session_id": session_id, "message_count": session.message_count}


@router.delete("/history/{session_id}")
async def delete_chat_session(
    session_id: str,
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, str]:
    """Delete a specific chat session."""
    enforce_scope(principal, "agent:run")
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    deleted = await store.delete_session(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.delete("/history")
async def clear_all_history(
    principal: PrincipalDependency = None,
    store: StoreDependency = None,
) -> dict[str, Any]:
    """Clear all chat history for the current user."""
    enforce_scope(principal, "agent:run")
    tenant_id = principal.tenant_id if principal else "default"
    user_id = principal.user_id if principal else "anonymous"
    deleted_count = await store.clear_sessions(tenant_id=tenant_id, user_id=user_id)
    return {"status": "cleared", "deleted_count": deleted_count}
