"""API endpoints for session management and context control.

Provides REST API for:
- Session management (list, create, restore, delete)
- Context compression control
- Session statistics and metrics

SECURITY (P1-14): tenant_id 一律强制收敛到认证主体（Principal），
绝不直信客户端请求体/查询参数中的 tenant_id。所有会话级操作
（恢复/删除/统计/保存/读上下文/写消息）都做租户归属校验：
不匹配一律返回 404（不泄露会话存在性）。

集成波接线说明：本路由当前未在 main.py 注册。挂载时需：
1. ``app.include_router(router)``（本模块 router）
2. 启动时调用 ``set_context_manager(context_manager)`` 注入共享 ContextManager
   （见 backend/app/core/context/INTEGRATION_GUIDE.md 第 2.2 节）。
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.context import ContextManager, SessionMetadata, SessionStats
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

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


def _require_current_session(context_manager: ContextManager, principal: Principal):
    """获取当前活跃会话并校验租户归属。

    Raises:
        HTTPException 409: 无活跃会话
        HTTPException 404: 会话不属于当前租户（不泄露存在性）
    """
    session = context_manager.current_session
    if session is None:
        raise HTTPException(status_code=409, detail="No active session. Initialize one first.")
    if session.tenant_id and session.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session.session_id}")
    return session


async def _load_session_for_tenant(context_manager: ContextManager, session_id: str, principal: Principal):
    """从存储加载会话并校验租户归属（restore/delete/stats 前置校验）。

    Raises:
        HTTPException 404: 会话不存在或不属于当前租户
    """
    session_state = await context_manager.session_recovery.load_snapshot(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if session_state.tenant_id and session_state.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session_state


# Request/Response models


class InitializeSessionRequest(BaseModel):
    """Request to initialize a session.

    注意：不包含 tenant_id —— 租户强制收敛到认证主体（principal.tenant_id）。
    """

    session_id: str
    agent_id: str = ""
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
async def initialize_session(
    request: InitializeSessionRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Initialize or restore a session.

    tenant_id 强制取 principal.tenant_id（忽略客户端任何租户声称）。
    恢复的会话租户与主体不匹配时返回 404。
    """
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        session_state = await context_manager.initialize_session(
            session_id=request.session_id,
            agent_id=request.agent_id,
            tenant_id=principal.tenant_id,
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

    except ValueError as e:
        # ContextManager 的租户防线：显式报错统一映射为 404（不泄露存在性）
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages", response_model=MessageResponse)
async def add_message(
    request: AddMessageRequest,
    principal: PrincipalDependency,
) -> MessageResponse:
    """Add a message to the current session（需当前会话归属当前租户）。"""
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        _require_current_session(context_manager, principal)
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context", response_model=ContextResponse)
async def get_context(
    principal: PrincipalDependency,
    limit: int = Query(None, description="Maximum number of messages"),
    include_metadata: bool = Query(False, description="Include message metadata"),
) -> ContextResponse:
    """Get current context（需当前会话归属当前租户）。"""
    enforce_scope(principal, "agent:read")
    try:
        context_manager = get_context_manager()
        _require_current_session(context_manager, principal)
        messages = await context_manager.get_context(limit=limit, include_metadata=include_metadata)

        total_tokens = sum(msg.get("token_count", 0) for msg in messages)

        return ContextResponse(
            messages=messages,
            total_messages=len(messages),
            total_tokens=total_tokens,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compress", response_model=CompressionResultResponse | None)
async def compress_context(principal: PrincipalDependency) -> CompressionResultResponse | None:
    """Manually trigger context compression（需当前会话归属当前租户）。

    Returns:
        Compression result if performed, None otherwise
    """
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        _require_current_session(context_manager, principal)
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/save", response_model=dict[str, Any])
async def save_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Save a session（仅当其为当前活跃会话且归属当前租户）。"""
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        session = _require_current_session(context_manager, principal)
        if session.session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found or not active: {session_id}",
            )
        success = await context_manager.save_session()

        return {
            "session_id": session_id,
            "success": success,
            "message": "Session saved successfully" if success else "Failed to save session",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/restore", response_model=dict[str, Any])
async def restore_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Restore a session（仅当会话归属当前租户）。"""
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        # 先校验存在性与租户归属，再恢复（避免污染当前会话）
        await _load_session_for_tenant(context_manager, session_id, principal)
        session_state = await context_manager.restore_session(session_id)

        if not session_state:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        return {
            "session_id": session_state.session_id,
            "agent_id": session_state.agent_id,
            "tenant_id": session_state.tenant_id,
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
    principal: PrincipalDependency,
    agent_id: str = Query(None, description="Filter by agent ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of sessions"),
) -> SessionListResponse:
    """List sessions（强制只列当前租户的会话）。"""
    enforce_scope(principal, "agent:read")
    try:
        context_manager = get_context_manager()
        sessions = await context_manager.list_sessions(
            agent_id=agent_id,
            limit=limit,
            tenant_id=principal.tenant_id,
        )

        return SessionListResponse(
            sessions=sessions,
            total_count=len(sessions),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}", response_model=dict[str, Any])
async def delete_session(
    session_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Delete a session（仅当会话归属当前租户）。"""
    enforce_scope(principal, "agent:run")
    try:
        context_manager = get_context_manager()
        await _load_session_for_tenant(context_manager, session_id, principal)
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
async def get_session_stats(
    session_id: str,
    principal: PrincipalDependency,
) -> SessionStatsResponse:
    """Get statistics for a session（仅当会话归属当前租户）。"""
    enforce_scope(principal, "agent:read")
    try:
        context_manager = get_context_manager()
        await _load_session_for_tenant(context_manager, session_id, principal)
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
async def get_metrics(principal: PrincipalDependency) -> ContextMetricsResponse:
    """Get current context metrics（管理器级计数器，需认证）。"""
    enforce_scope(principal, "agent:read")
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
