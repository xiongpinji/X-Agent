"""
Refactored dependencies module using DI container.

This module maintains backward compatibility with the existing FastAPI
dependency injection system while using the new DI container internally.

Migration path:
1. Existing @lru_cache functions are preserved for backward compatibility
2. New code should use container.resolve() directly
3. Gradual migration: replace @lru_cache with container registration
"""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from secrets import compare_digest
from typing import TYPE_CHECKING

from fastapi import Request

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import (
    ROLE_SCOPES,
    Principal,
    anonymous_principal,
)
from backend.app.settings import get_settings

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop
    from backend.app.core.approvals import ApprovalStore
    from backend.app.core.audit import AuditStore
    from backend.app.core.browser import BrowserAutomationStore
    from backend.app.core.desktop import DesktopAutomationStore
    from backend.app.core.memory import MemorySystem
    from backend.app.core.memory_postgres import PostgresMemorySystem
    from backend.app.core.orchestrator import Orchestrator
    from backend.app.core.runs import RunStore
    from backend.app.core.security import APIKeyStore, RBACPolicy
    from backend.app.core.tracing import TraceStore
    from backend.app.core.tracing_postgres import PostgresTraceStore
    from backend.app.core.workflows import (
        WorkflowExecutor,
        WorkflowRepository,
        WorkflowRuntimeManager,
        WorkflowScheduler,
        WorkflowScheduleStore,
    )

# ============================================================================
# Container Initialization
# ============================================================================

_container = None


def _get_container():
    """Get or create the global DI container."""
    global _container
    if _container is None:
        from backend.app.core.container_config import create_configured_container

        _container = create_configured_container()
    return _container


# ============================================================================
# Backward Compatibility Layer
# ============================================================================
# These functions maintain the existing API while delegating to the container.
# They are marked with @lru_cache for compatibility with existing code.


@lru_cache
def get_memory() -> MemorySystem | PostgresMemorySystem:
    """Get the memory system instance (singleton)."""

    # Fallback to original implementation for compatibility
    from backend.app.dependencies import build_memory_system

    settings = get_settings()
    return build_memory_system(
        memory_backend=settings.memory_backend,
        database_url=settings.database_url,
        memory_store_path=settings.memory_store_path,
        embedding_backend=settings.embedding_backend,
        openai_api_key=settings.openai_api_key,
        openai_embedding_model=settings.openai_embedding_model,
        openai_embedding_dimensions=settings.openai_embedding_dimensions,
        postgres_enable_vector_search=settings.postgres_enable_vector_search,
        postgres_vector_dimensions=settings.postgres_vector_dimensions,
    )


def build_memory_system(
    *,
    memory_backend: str,
    database_url: str,
    memory_store_path,
    embedding_backend: str = "auto",
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
    postgres_enable_vector_search: bool = False,
    postgres_vector_dimensions: int = 1536,
) -> MemorySystem | PostgresMemorySystem:
    """Build a memory system based on configuration."""
    from backend.app.core.embeddings import build_embedding_model
    from backend.app.core.memory import MemorySystem
    from backend.app.core.memory_postgres import PostgresMemorySystem

    if memory_backend == "postgres":
        embedding_model = None
        if postgres_enable_vector_search:
            embedding_model = build_embedding_model(
                embedding_backend=embedding_backend,
                openai_api_key=openai_api_key,
                openai_embedding_model=openai_embedding_model,
                openai_embedding_dimensions=openai_embedding_dimensions,
            )
        return PostgresMemorySystem(
            database_url=database_url,
            embedding_model=embedding_model,
            enable_vector_search=postgres_enable_vector_search,
            vector_dimensions=postgres_vector_dimensions,
        )
    embedding_model = build_embedding_model(
        embedding_backend=embedding_backend,
        openai_api_key=openai_api_key,
        openai_embedding_model=openai_embedding_model,
        openai_embedding_dimensions=openai_embedding_dimensions,
    )
    if memory_backend == "memory":
        return MemorySystem(embedding_model=embedding_model)
    return MemorySystem(storage_path=memory_store_path, embedding_model=embedding_model)


@lru_cache
def get_trace_store() -> TraceStore | PostgresTraceStore:
    """Get the trace store instance (singleton)."""
    from backend.app.core.tracing import TraceStore, build_tracer
    from backend.app.core.tracing_postgres import PostgresTraceStore

    settings = get_settings()
    trace_backend = settings.trace_backend
    database_url = settings.database_url
    trace_store_path = settings.trace_store_path

    if trace_backend == "postgres":
        return PostgresTraceStore(database_url=database_url)
    if trace_backend == "memory":
        return TraceStore()
    return build_tracer(trace_store_path)


@lru_cache
def get_run_store() -> RunStore:
    """Get the run store instance (singleton)."""
    from backend.app.core.runs import RunStore

    settings = get_settings()
    return RunStore(storage_path=settings.run_store_path)


@lru_cache
def get_browser_store() -> BrowserAutomationStore:
    """Get the browser automation store instance (singleton)."""
    from backend.app.core.browser import browser_automation_store

    return browser_automation_store


@lru_cache
def get_desktop_store() -> DesktopAutomationStore:
    """Get the desktop automation store instance (singleton)."""
    from backend.app.core.desktop import desktop_automation_store

    return desktop_automation_store


@lru_cache
def get_tool_execution_store():
    """Get the tool execution store instance (singleton)."""
    from backend.app.core.tools import ToolExecutionStore

    settings = get_settings()
    return ToolExecutionStore(storage_path=settings.tool_execution_store_path)


@lru_cache
def get_audit_store() -> AuditStore:
    """Get the audit store instance (singleton)."""
    from backend.app.core.audit import AuditStore

    settings = get_settings()
    hmac_secret = settings.audit_hmac_secret
    if not hmac_secret:
        raise RuntimeError("audit_hmac_secret must be configured")
    return AuditStore(
        storage_path=settings.audit_store_path,
        hmac_secret=hmac_secret,
    )


@lru_cache
def get_api_key_store() -> APIKeyStore:
    """Get the API key store instance (singleton)."""
    from backend.app.core.security import APIKeyStore

    settings = get_settings()
    return APIKeyStore(storage_path=settings.api_key_store_path)


@lru_cache
def get_approval_store() -> ApprovalStore:
    """Get the approval store instance (singleton)."""
    from backend.app.core.approvals import ApprovalStore

    settings = get_settings()
    return ApprovalStore(storage_path=settings.approval_store_path)


@lru_cache
def get_rbac_policy() -> RBACPolicy:
    """Get the RBAC policy instance (singleton)."""
    from backend.app.core.security import RBACPolicy

    return RBACPolicy()


def get_current_principal(request: Request) -> Principal:
    """
    Extract and validate the current principal from the request.

    Supports:
    - Bootstrap API key (via x-api-key header)
    - API key authentication (via x-api-key header)
    - Bearer token authentication (via Authorization header)
    - Anonymous principal (if not required)
    """
    settings = get_settings()
    raw_key = request.headers.get("x-api-key")
    if raw_key:
        if _matches_bootstrap_key(
            raw_key,
            settings.bootstrap_api_key,
            settings.bootstrap_api_key_sha256,
        ):
            return Principal(
                tenant_id="default",
                user_id="bootstrap-admin",
                role="admin",
                scopes=list(ROLE_SCOPES["admin"]),
                api_key_id="bootstrap",
                authenticated=True,
            )
        principal = get_api_key_store().authenticate(raw_key)
        if principal is None:
            raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid API key.")
        return principal

    # Fallback to Bearer token (auth session)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            from backend.app.api.auth import _is_token_valid, _token_users

            if _is_token_valid(token):
                user_id = _token_users.get(token)
                if user_id:
                    from backend.app.core.admin import user_store

                    user = user_store.get(user_id)
                    if user:
                        return Principal(
                            tenant_id=user.tenant_id,
                            user_id=user.id,
                            role=user.role,
                            scopes=list(ROLE_SCOPES.get(user.role, [])),
                            authenticated=True,
                        )
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid or expired token.")

    # 生产环境绝不回落匿名主体（与 dependencies.py 的 S5 守卫保持一致）：
    # 即便 require_api_key 默认 False，生产模式也必须要求显式凭证，避免漏配
    # enforce_scope 的路由被未鉴权访问。
    if settings.require_api_key or getattr(settings, "app_mode", "development") == "production":
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "API key required.")
    return anonymous_principal()


def _matches_bootstrap_key(
    raw_key: str,
    bootstrap_key: str | None,
    bootstrap_key_sha256: str | None,
) -> bool:
    """Check if the raw key matches the bootstrap key."""
    if bootstrap_key and compare_digest(raw_key, bootstrap_key):
        return True
    if bootstrap_key_sha256:
        key_hash = sha256(raw_key.encode("utf-8")).hexdigest()
        return compare_digest(key_hash, bootstrap_key_sha256)
    return False


def enforce_scope(principal: Principal, scope: str) -> None:
    """Enforce that the principal has the required scope."""
    if not principal.authenticated:
        raise api_error(
            401,
            ErrorCode.AUTHENTICATION_FAILED,
            "Authentication required.",
        )
    if not get_rbac_policy().has_scope(principal, scope):
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            f"Missing required scope: {scope}",
        )


@lru_cache
def get_workflow_repository() -> WorkflowRepository:
    """Get the workflow repository instance (singleton)."""
    from backend.app.core.workflows import WorkflowRepository

    settings = get_settings()
    return WorkflowRepository(
        definition_path=settings.workflow_store_path,
        run_path=settings.workflow_run_store_path,
    )


@lru_cache
def get_workflow_executor() -> WorkflowExecutor:
    """Get the workflow executor instance (singleton)."""
    from backend.app.core.workflows import WorkflowExecutor

    return WorkflowExecutor(
        agent=get_agent(),
        repository=get_workflow_repository(),
        tracer=get_trace_store(),
        approval_store=get_approval_store(),
        audit_store=get_audit_store(),
    )


@lru_cache
def get_workflow_runtime() -> WorkflowRuntimeManager:
    """Get the workflow runtime manager instance (singleton)."""
    from backend.app.core.workflows import WorkflowRuntimeManager

    return WorkflowRuntimeManager(
        executor=get_workflow_executor(),
        repository=get_workflow_repository(),
    )


@lru_cache
def get_workflow_schedule_store() -> WorkflowScheduleStore:
    """Get the workflow schedule store instance (singleton)."""
    from backend.app.core.workflows import WorkflowScheduleStore

    settings = get_settings()
    return WorkflowScheduleStore(storage_path=settings.workflow_schedule_store_path)


@lru_cache
def get_workflow_scheduler() -> WorkflowScheduler:
    """Get the workflow scheduler instance (singleton)."""
    from backend.app.core.workflows import WorkflowScheduler

    return WorkflowScheduler(
        repository=get_workflow_repository(),
        runtime=get_workflow_runtime(),
        schedule_store=get_workflow_schedule_store(),
    )


@lru_cache
def get_agent() -> AgentLoop:
    """Get the agent loop instance (singleton)."""
    from backend.app.core.agent import AgentLoop
    from backend.app.core.llm import build_llm_router
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.tools import build_default_tool_registry

    settings = get_settings()
    policy = ToolPolicyEngine(enable_high_risk_tools=settings.enable_high_risk_tools)
    tools = build_default_tool_registry(
        policy,
        approval_store=get_approval_store(),
        execution_store=get_tool_execution_store(),
    )
    return AgentLoop(
        llm_router=build_llm_router(
            llm_backend=settings.llm_backend,
            fallback_order=settings.llm_fallback_order,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            deepseek_api_key=settings.deepseek_api_key,
            deepseek_model=settings.deepseek_model,
            deepseek_base_url=settings.deepseek_base_url,
        ),
        memory=get_memory(),
        tools=tools,
        max_iterations=settings.max_iterations,
        tracer=get_trace_store(),
        run_store=get_run_store(),
    )


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Get the orchestrator instance (singleton)."""
    from backend.app.core.orchestrator import Orchestrator

    return Orchestrator()


# ============================================================================
# Container Access Functions (New API)
# ============================================================================


def get_container():
    """Get the global DI container."""
    return _get_container()


def resolve(service_type):
    """Resolve a service from the container."""
    return _get_container().resolve(service_type)


async def resolve_async(service_type):
    """Resolve a service asynchronously from the container."""
    return await _get_container().resolve_async(service_type)
