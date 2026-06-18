import logging
from functools import lru_cache
from hashlib import sha256
from secrets import compare_digest
from secrets import token_urlsafe

from fastapi import Request

from backend.app.api.errors import api_error
from backend.app.core.agent import AgentLoop
from backend.app.core.approvals import ApprovalStore
from backend.app.core.audit import AuditStore
from backend.app.core.browser import BrowserAutomationStore, browser_automation_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.control_modes import ControlModeStore
from backend.app.core.orchestrator import Orchestrator
from backend.app.core.embeddings import build_embedding_model
from backend.app.core.llm import build_llm_router
from backend.app.core.memory import MemorySystem
from backend.app.core.memory_postgres import PostgresMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.services.observability.langfuse_client import langfuse_client
from backend.app.services.memory.indexer import memory_indexer
from backend.app.core.runs import RunStore
from backend.app.core.security import (
    ROLE_SCOPES,
    APIKeyStore,
    Principal,
    RBACPolicy,
    anonymous_principal,
)
from backend.app.core.tools import ToolExecutionStore, build_default_tool_registry
from backend.app.core.tracing import TraceStore, build_tracer
from backend.app.core.tracing_postgres import PostgresTraceStore
from backend.app.core.workflow_events import build_workflow_event_publisher
from backend.app.core.workflows import (
    WorkflowExecutor,
    WorkflowRepository,
    WorkflowRuntimeManager,
    WorkflowScheduler,
    WorkflowScheduleStore,
)
from backend.app.core.desktop import DesktopAutomationStore, desktop_automation_store
from backend.app.settings import get_settings


@lru_cache
def get_memory() -> MemorySystem | PostgresMemorySystem:
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
    embedding_backend: str = "local",
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
    postgres_enable_vector_search: bool = False,
    postgres_vector_dimensions: int = 1536,
) -> MemorySystem | PostgresMemorySystem:
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


def build_trace_store(
    *,
    trace_backend: str,
    database_url: str,
    trace_store_path,
) -> TraceStore | PostgresTraceStore:
    if trace_backend == "postgres":
        return PostgresTraceStore(database_url=database_url)
    if trace_backend == "memory":
        return TraceStore()
    return build_tracer(trace_store_path)


@lru_cache
def get_trace_store() -> TraceStore | PostgresTraceStore:
    settings = get_settings()
    return build_trace_store(
        trace_backend=settings.trace_backend,
        database_url=settings.database_url,
        trace_store_path=settings.trace_store_path,
    )


@lru_cache
def get_run_store() -> RunStore:
    settings = get_settings()
    return RunStore(storage_path=settings.run_store_path)


@lru_cache
def get_control_mode_store() -> ControlModeStore:
    settings = get_settings()
    return ControlModeStore(storage_path=settings.control_mode_store_path)


@lru_cache
def get_browser_store() -> BrowserAutomationStore:
    return browser_automation_store


@lru_cache
def get_desktop_store() -> DesktopAutomationStore:
    return desktop_automation_store


@lru_cache
def get_tool_execution_store() -> ToolExecutionStore:
    settings = get_settings()
    return ToolExecutionStore(storage_path=settings.tool_execution_store_path)


@lru_cache
def get_audit_store() -> AuditStore:
    settings = get_settings()
    hmac_secret = settings.audit_hmac_secret
    if not hmac_secret:
        # Production: hard requirement (settings validator also enforces this at
        # load time). An unsigned audit log in production is a tamper risk.
        if settings.app_mode == "production":
            raise RuntimeError(
                "audit_hmac_secret must be configured in production "
                "(set XAGENT_AUDIT_HMAC_SECRET; see .env.example)"
            )
        # Development/test: settings permits an absent secret, so generate an
        # ephemeral per-process key instead of hard-failing. Audit signing still
        # works for local runs; the key is non-persistent (rotates each restart),
        # which is acceptable for dev but never for production.
        hmac_secret = token_urlsafe(32)
        logging.getLogger("xagent.dependencies").warning(
            "audit_hmac_secret not set; using an ephemeral dev key. "
            "Set XAGENT_AUDIT_HMAC_SECRET for stable audit signatures "
            "(required in production)."
        )
    return AuditStore(
        storage_path=settings.audit_store_path,
        hmac_secret=hmac_secret,
    )


@lru_cache
def get_api_key_store() -> APIKeyStore:
    settings = get_settings()
    return APIKeyStore(storage_path=settings.api_key_store_path)


@lru_cache
def get_approval_store() -> ApprovalStore:
    settings = get_settings()
    return ApprovalStore(storage_path=settings.approval_store_path)


@lru_cache
def get_rbac_policy() -> RBACPolicy:
    return RBACPolicy()


def get_current_principal(request: Request) -> Principal:
    settings = get_settings()
    raw_key = request.headers.get("x-api-key")
    if raw_key:
        if _matches_bootstrap_key(
            raw_key,
            settings.bootstrap_api_key,
            settings.bootstrap_api_key_sha256,
        ):
            principal = Principal(
                tenant_id="default",
                user_id="bootstrap-admin",
                role="admin",
                scopes=list(ROLE_SCOPES["admin"]),
                api_key_id="bootstrap",
                authenticated=True,
            )
            request.scope["principal"] = principal
            return principal
        principal = get_api_key_store().authenticate(raw_key)
        if principal is None:
            raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid API key.")
        request.scope["principal"] = principal
        return principal

    # Fallback to Bearer token (auth session)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            principal = _principal_from_bearer_token(token, token_type="access")
            if principal is not None:
                request.scope["principal"] = principal
                return principal
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid or expired token.")

    # 生产环境绝不回落匿名主体（S5）：即便 require_api_key 默认 False，
    # 生产模式也必须要求显式凭证，避免漏配 enforce_scope 的路由被未鉴权访问。
    if settings.require_api_key or getattr(settings, "app_mode", "development") == "production":
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "API key required.")
    principal = anonymous_principal()
    request.scope["principal"] = principal
    return principal


def get_refresh_principal(request: Request) -> Principal:
    """Resolve a principal from a refresh bearer token only."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            principal = _principal_from_bearer_token(token, token_type="refresh")
            if principal is not None:
                request.scope["principal"] = principal
                return principal
    raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "Invalid or expired refresh token.")


def _principal_from_bearer_token(token: str, *, token_type: str) -> Principal | None:
    from backend.app.api.auth import _get_token_user, _is_token_valid

    if not _is_token_valid(token, token_type=token_type):
        return None
    user_id = _get_token_user(token)
    if not user_id:
        return None

    from backend.app.core.admin import user_store

    user = user_store.get(user_id)
    if not user:
        return None
    return Principal(
        tenant_id=user.tenant_id,
        user_id=user.id,
        role=user.role,
        scopes=list(ROLE_SCOPES.get(user.role, [])),
        authenticated=True,
    )


def _matches_bootstrap_key(
    raw_key: str,
    bootstrap_key: str | None,
    bootstrap_key_sha256: str | None,
) -> bool:
    if bootstrap_key and compare_digest(raw_key, bootstrap_key):
        return True
    if bootstrap_key_sha256:
        key_hash = sha256(raw_key.encode("utf-8")).hexdigest()
        return compare_digest(key_hash, bootstrap_key_sha256)
    return False


def enforce_scope(principal: Principal, scope: str) -> None:
    """Enforce that principal has required scope.

    SECURITY: Rejects unauthenticated users and validates scope.
    """
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
    settings = get_settings()
    return WorkflowRepository(
        definition_path=settings.workflow_store_path,
        run_path=settings.workflow_run_store_path,
    )


@lru_cache
def get_workflow_executor() -> WorkflowExecutor:
    settings = get_settings()
    return WorkflowExecutor(
        agent=get_agent(),
        repository=get_workflow_repository(),
        tracer=get_trace_store(),
        approval_store=get_approval_store(),
        audit_store=get_audit_store(),
        event_publisher=build_workflow_event_publisher(
            workflow_event_broker_backend=settings.workflow_event_broker_backend,
            workflow_event_rabbitmq_url=settings.workflow_event_rabbitmq_url or "",
            workflow_event_exchange=settings.workflow_event_exchange,
        ),
    )


@lru_cache
def get_workflow_runtime() -> WorkflowRuntimeManager:
    return WorkflowRuntimeManager(
        executor=get_workflow_executor(),
        repository=get_workflow_repository(),
    )


@lru_cache
def get_workflow_schedule_store() -> WorkflowScheduleStore:
    settings = get_settings()
    return WorkflowScheduleStore(storage_path=settings.workflow_schedule_store_path)


@lru_cache
def get_workflow_scheduler() -> WorkflowScheduler:
    return WorkflowScheduler(
        repository=get_workflow_repository(),
        runtime=get_workflow_runtime(),
        schedule_store=get_workflow_schedule_store(),
    )


@lru_cache
def get_agent() -> AgentLoop:
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
    return Orchestrator()
