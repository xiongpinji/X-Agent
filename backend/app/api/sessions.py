"""API endpoints for session management and context control.

Provides REST API for:
- Session management (list, create, restore, delete)
- Context compression control
- Session statistics and metrics
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.context import ContextManager, SessionMetadata, SessionStats

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Global context manager instance (will be injected)
_context_manager: ContextManager | None = None


def set_context_manager(context_manager: ContextManager) -> None:
    """Set the global context manager instance."""
    global _context_manager
    _context_manager = context_manager


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    if not _context_manager:
        raise HTTPException(status_code=500, detail="Context manager not initialized")
    return _context_manager


# Request/Response models


class InitializeSessionRequest(BaseModel):
    """Request to initialize a session."""

    session_id: str
    agent_id: str = ""
    tenant_id: str = ""
    context_window: int = 128_000


class AddMessageRequest(BaseModel):
    """Request to add a message."""

    role: str = Field(..., description="Message role: user, assistant, system, tool")
    content: str = Field(..., description="Message content")
    metadata: dict = Field(default_factory=dict, description="Optional metadata")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score")


class MessageResponse(BaseModel):
    """Response containing a message."""

    id: str
    role: str
    content: str
    timestamp: str
    importance: float
    compressed: bool
    token_count: int


class ContextResponse(BaseModel):
    """Response containing context."""

    messages: list[dict[str, Any]]
    total_messages: int
    total_tokens: int


class SessionListResponse(BaseModel):
    """Response containing session list."""

    sessions: list[dict[str, Any]]
    total_count: int


class SessionStatsResponse(BaseModel):
    """Response containing session statistics."""

    session_id: str
    message_count: int
    total_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compression_count: int
    created_at: str
    updated_at: str
    last_checkpoint: str
    storage_size_mb: float


class CompressionResultResponse(BaseModel):
    """Response containing compression result."""

    success: bool
    messages_before: int
    messages_after: int
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    duration_ms: float


class ContextMetricsResponse(BaseModel):
    """Response containing context metrics."""

    total_messages: int
    total_tokens: int
    compressed_tokens: int
    compression_ratio: float
    compression_count: int
    last_compression_time: str | None
    average_compression_duration_ms: float
    memory_usage_mb: float


# Endpoints


@router.post("/initialize", response_model=dict[str, Any])
async def initialize_session(request: InitializeSessionRequest) -> dict[str, Any]:
    """Initialize or restore a session.

    Args:
        request: Session initialization request

    Returns:
        Session state information
    """
    try:
        context_manager = get_context_manager()
        session_state = await context_manager.initialize_session(
            session_id=request.session_id,
            agent_id=request.agent_id,
            tenant_id=request.tenant_id,
            context_window=request.context_window,
        )

        return {
            "session_id": session_state.session_id,
            "agent_id": session_state.agent_id,
            "tenant_id": session_state.tenant_id,
            "message_count": len(session_state.messages),
            "total_tokens": session_state.total_tokens,
            "created_at": session_state.created_at.isoformat(),
            "updated_at": session_state.updated_at.isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages", response_model=MessageResponse)
async def add_message(request: AddMessageRequest) -> MessageResponse:
    """Add a message to the current session.

    Args:
        request: Message to add

    Returns:
        Added message
    """
    try:
        context_manager = get_context_manager()
        message = await context_manager.add_message(
            role=request.role,
            content=request.content,
            metadata=request.metadata,
            importance=request.importance,
        )

        return MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            timestamp=message.timestamp.isoformat(),
            importance=message.importance,
            compressed=message.compressed,
            token_count=message.token_count,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context", response_model=ContextResponse)
async def get_context(
    limit: int = Query(None, description="Maximum number of messages"),
    include_metadata: bool = Query(False, description="Include message metadata"),
) -> ContextResponse:
    """Get current context.

    Args:
        limit: Maximum number of messages to return
        include_metadata: Include message metadata

    Returns:
        Current context
    """
    try:
        context_manager = get_context_manager()
        messages = await context_manager.get_context(limit=limit, include_metadata=include_metadata)

        total_tokens = sum(msg.get("token_count", 0) for msg in messages)

        return ContextResponse(
            messages=messages,
            total_messages=len(messages),
            total_tokens=total_tokens,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compress", response_model=CompressionResultResponse | None)
async def compress_context() -> CompressionResultResponse | None:
    """Manually trigger context compression.

    Returns:
        Compression result if performed, None otherwise
    """
    try:
        context_manager = get_context_manager()
        result = await context_manager.compress_if_needed()

        if result:
            return CompressionResultResponse(
                success=result.success,
                messages_before=result.metrics.messages_before,
                messages_after=result.metrics.messages_after,
                original_tokens=result.metrics.original_tokens,
                compressed_tokens=result.metrics.compressed_tokens,
                compression_ratio=result.metrics.compression_ratio,
                duration_ms=0,  # Would need to track this
            )

        return None

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/save", response_model=dict[str, Any])
async def save_session(session_id: str) -> dict[str, Any]:
    """Save a session.

    Args:
        session_id: Session ID to save

    Returns:
        Save result
    """
    try:
        context_manager = get_context_manager()
        success = await context_manager.save_session()

        return {
            "session_id": session_id,
            "success": success,
            "message": "Session saved successfully" if success else "Failed to save session",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/restore", response_model=dict[str, Any])
async def restore_session(session_id: str) -> dict[str, Any]:
    """Restore a session.

    Args:
        session_id: Session ID to restore

    Returns:
        Restored session information
    """
    try:
        context_manager = get_context_manager()
        session_state = await context_manager.restore_session(session_id)

        if not session_state:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {
            "session_id": session_state.session_id,
            "agent_id": session_state.agent_id,
            "message_count": len(session_state.messages),
            "total_tokens": session_state.total_tokens,
            "created_at": session_state.created_at.isoformat(),
            "updated_at": session_state.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    agent_id: str = Query(None, description="Filter by agent ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of sessions"),
) -> SessionListResponse:
    """List all sessions.

    Args:
        agent_id: Filter by agent ID
        limit: Maximum number of sessions

    Returns:
        List of sessions
    """
    try:
        context_manager = get_context_manager()
        sessions = await context_manager.list_sessions(agent_id=agent_id, limit=limit)

        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", response_model=dict[str, Any])
async def delete_session(session_id: str) -> dict[str, Any]:
    """Delete a session.

    Args:
        session_id: Session ID to delete

    Returns:
        Delete result
    """
    try:
        context_manager = get_context_manager()
        success = await context_manager.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {
            "session_id": session_id,
            "success": True,
            "message": "Session deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/stats", response_model=SessionStatsResponse)
async def get_session_stats(session_id: str) -> SessionStatsResponse:
    """Get statistics for a session.

    Args:
        session_id: Session ID

    Returns:
        Session statistics
    """
    try:
        context_manager = get_context_manager()
        stats = await context_manager.get_session_stats(session_id)

        if not stats:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return SessionStatsResponse(
            session_id=stats.session_id,
            message_count=stats.message_count,
            total_tokens=stats.total_tokens,
            compressed_tokens=stats.compressed_tokens,
            compression_ratio=stats.compression_ratio,
            compression_count=stats.compression_count,
            created_at=stats.created_at.isoformat(),
            updated_at=stats.updated_at.isoformat(),
            last_checkpoint=stats.last_checkpoint.isoformat(),
            storage_size_mb=stats.storage_size_mb,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=ContextMetricsResponse)
async def get_metrics() -> ContextMetricsResponse:
    """Get current context metrics.

    Returns:
        Context metrics
    """
    try:
        context_manager = get_context_manager()
        metrics = await context_manager.get_metrics()

        return ContextMetricsResponse(
            total_messages=metrics.total_messages,
            total_tokens=metrics.total_tokens,
            compressed_tokens=metrics.compressed_tokens,
            compression_ratio=metrics.compression_ratio,
            compression_count=metrics.compression_count,
            last_compression_time=metrics.last_compression_time.isoformat()
            if metrics.last_compression_time
            else None,
            average_compression_duration_ms=metrics.average_compression_duration_ms,
            memory_usage_mb=metrics.memory_usage_mb,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
