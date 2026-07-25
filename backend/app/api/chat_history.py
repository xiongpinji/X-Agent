"""Chat history persistence API.

Provides endpoints for storing and retrieving chat conversations.
Sessions are persisted to PostgreSQL (or in-memory fallback for dev).

Endpoints:
- GET    /api/v1/chat/history          — List conversation sessions
- GET    /api/v1/chat/history/{id}     — Get messages for a session
- DELETE /api/v1/chat/history/{id}     — Delete a session
- DELETE /api/v1/chat/history          — Clear all history
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/chat", tags=["chat-history"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Models ────────────────────────────────────────────────────────────────────


class ChatMessageRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:12]}")
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: f"session-{uuid.uuid4().hex[:12]}")
    title: str = ""
    agent_id: str = "default"
    user_id: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    message_count: int = 0
    messages: list[ChatMessageRecord] = Field(default_factory=list)


class SessionSummary(BaseModel):
    id: str
    title: str
    agent_id: str
    created_at: float
    updated_at: float
    message_count: int


# ─── In-memory store (dev fallback) ───────────────────────────────────────────

_sessions: dict[str, ChatSession] = {}


def _get_user_sessions(user_id: str) -> list[ChatSession]:
    return [s for s in _sessions.values() if s.user_id == user_id]


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/history")
async def list_chat_history(
    limit: int = Query(50, ge=1, le=200),
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """List chat sessions for the current user."""
    enforce_scope(principal, "agent:read")
    user_id = principal.user_id if principal else "anonymous"
    sessions = _get_user_sessions(user_id)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
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
            for s in sessions[:limit]
        ],
        "total": len(sessions),
    }


@router.get("/history/{session_id}")
async def get_chat_session(
    session_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Get full message history for a session."""
    enforce_scope(principal, "agent:read")
    session = _sessions.get(session_id)
    if not session:
        return {"error": "Session not found", "messages": []}
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
    payload: dict[str, Any] | None = None,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Create a new chat session."""
    enforce_scope(principal, "agent:run")
    user_id = principal.user_id if principal else "anonymous"
    payload = payload or {}
    session = ChatSession(
        title=payload.get("title", ""),
        agent_id=payload.get("agent_id", "default"),
        user_id=user_id,
    )
    _sessions[session.id] = session
    return {"id": session.id, "title": session.title, "created_at": session.created_at}


@router.post("/history/{session_id}/messages")
async def add_message_to_session(
    session_id: str,
    payload: dict[str, Any],
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Add a message to an existing session."""
    enforce_scope(principal, "agent:run")
    session = _sessions.get(session_id)
    if not session:
        # Auto-create session
        user_id = principal.user_id if principal else "anonymous"
        session = ChatSession(id=session_id, user_id=user_id)
        _sessions[session_id] = session

    msg = ChatMessageRecord(
        role=payload.get("role", "user"),
        content=payload.get("content", ""),
        metadata=payload.get("metadata", {}),
    )
    session.messages.append(msg)
    session.message_count = len(session.messages)
    session.updated_at = time.time()
    if not session.title and msg.role == "user":
        session.title = msg.content[:50]
    return {"id": msg.id, "session_id": session_id, "message_count": session.message_count}


@router.delete("/history/{session_id}")
async def delete_chat_session(
    session_id: str,
    principal: PrincipalDependency = None,
) -> dict[str, str]:
    """Delete a specific chat session."""
    enforce_scope(principal, "agent:run")
    if session_id in _sessions:
        del _sessions[session_id]
        return {"status": "deleted", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@router.delete("/history")
async def clear_all_history(
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Clear all chat history for the current user."""
    enforce_scope(principal, "agent:run")
    user_id = principal.user_id if principal else "anonymous"
    to_delete = [sid for sid, s in _sessions.items() if s.user_id == user_id]
    for sid in to_delete:
        del _sessions[sid]
    return {"status": "cleared", "deleted_count": len(to_delete)}
