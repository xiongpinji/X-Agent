import logging
from functools import lru_cache
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:  # 仅类型标注, 运行时惰性导入(可选依赖 qdrant-client)
    from backend.app.core.advanced_rbac import AdvancedRBACEngine
    from backend.app.core.agent import AgentLoop
    from backend.app.core.agent_context import AgentContextManager
    from backend.app.core.audit_shipper import AuditShipper
    from backend.app.core.memory import MemorySystem
    from backend.app.core.tools import ToolRegistry
    from backend.app.core.memory_postgres import PostgresMemorySystem
    from backend.app.core.memory_qdrant import QdrantMemorySystem
    from backend.app.core.orchestrator import Orchestrator
    from backend.app.core.unified_memory import UnifiedMemorySystem
    from backend.app.core.workflows import (
        WorkflowExecutor,
        WorkflowRepository,
        WorkflowRuntimeManager,
        WorkflowScheduler,
        WorkflowScheduleStore,
    )

from backend.app.api.errors import api_error
from backend.app.core.approvals import ApprovalStore
from backend.app.core.audit import AuditStore
from backend.app.core.browser import BrowserAutomationStore, browser_automation_store
from backend.app.core.contracts import ErrorCode
from backend.app.core.desktop import DesktopAutomationStore, desktop_automation_store
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.runs import RunStore
from backend.app.core.security import (
    ROLE_SCOPES,
    APIKeyStore,
    Principal,
    RBACPolicy,
    anonymous_principal,
)
from backend.app.core.tools import ToolExecutionStore
from backend.app.core.tracing import TraceStore, build_tracer
from backend.app.core.tracing_postgres import PostgresTraceStore
from backend.app.settings import get_settings


@lru_cache
def get_memory() -> "MemorySystem | PostgresMemorySystem | QdrantMemorySystem":
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
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=settings.qdrant_api_key,
        qdrant_strict=settings.app_mode == "production",
        embedding_dim=settings.embedding_dim,
    )


@lru_cache
def get_unified_memory() -> "UnifiedMemorySystem":
    """Get the UnifiedMemorySystem wired with real embeddings (P1-13).

    This provides an enhanced memory layer on top of the existing memory
    pipeline, with automatic embedding generation and vector similarity
    search.  Graceful degradation: if the embedding service is unavailable,
    the system falls back to keyword-based retrieval without crashing.

    Usage in routes::

        from backend.app.dependencies import get_unified_memory
        unified = get_unified_memory()
        await unified.store_memory("...", MemoryType.FACT)
        results = await unified.retrieve_memories("query")
    """
    from backend.app.core.unified_memory import build_unified_memory_system

    settings = get_settings()
    return build_unified_memory_system(
        embedding_backend=settings.embedding_backend,
        openai_api_key=settings.openai_api_key,
        openai_embedding_model=settings.openai_embedding_model,
        openai_embedding_dimensions=settings.openai_embedding_dimensions,
        embedding_dim=settings.embedding_dim,
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
    qdrant_url: str | None = None,
    qdrant_api_key: str | None = None,
    qdrant_strict: bool = False,
    embedding_dim: int = 384,
) -> "MemorySystem | PostgresMemorySystem | QdrantMemorySystem":
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
    if memory_backend == "qdrant":
        # P1-13 真实 Qdrant 后端(集成波接线, 按 core/memory_qdrant.py 说明)。
        # strict=True(生产)缺包/连不上显式 RuntimeError; 否则 WARNING 后显式
        # 降级到 JSONL/内存后端(可经 backend_status/degraded_reason 观测), 不静默。
        from backend.app.core.memory_qdrant import build_qdrant_memory_system

        return build_qdrant_memory_system(
            url=qdrant_url,
            api_key=qdrant_api_key,
            embedding_model=embedding_model,
            strict=qdrant_strict,
            fallback_storage_path=memory_store_path,
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
def get_graph_memory_store():
    """Get the Neo4j graph memory store (optional, for memory relationship graphs).

    Returns a GraphMemoryStore instance. When neo4j_enabled=False or the neo4j
    package is not installed, returns a no-op degraded store (reads return empty,
    writes are silently dropped). Check `.available` to verify real persistence.
    """
    from backend.app.core.graph_memory_store import GraphMemoryStore

    settings = get_settings()
    if not settings.neo4j_enabled:
        return GraphMemoryStore(neo4j_driver=None)
    try:
        return GraphMemoryStore.create_driver(
            uri=settings.neo4j_url,
            auth=(settings.neo4j_user, settings.neo4j_password),
            database=settings.neo4j_database,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Neo4j graph store unavailable (%s); falling back to no-op degraded mode. "
            "Set neo4j_enabled=false to silence this, or fix the Neo4j configuration.",
            exc,
        )
        return GraphMemoryStore(neo4j_driver=None)


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
    return _attach_audit_shipper_hook(
        AuditStore(
            storage_path=settings.audit_store_path,
            hmac_secret=hmac_secret,
        )
    )


# ---------------------------------------------------------------------------
# 审计外送(P1-04)挂钩
# ---------------------------------------------------------------------------
# shipper 生命周期由 main.py startup/shutdown 管理(build_shipper + start/stop,
# 配置缺省时保持 None 不启用)。写入点挂钩放在 get_audit_store: AuditStore.record
# 成功落库后非阻塞 enqueue; 外送失败只记日志, 绝不影响审计写入本身。
_audit_shipper: "AuditShipper | None" = None


def set_audit_shipper(shipper: "AuditShipper | None") -> None:
    """注册/清除进程级审计外送 shipper(main.py lifespan 调用)。"""
    global _audit_shipper
    _audit_shipper = shipper


def get_audit_shipper() -> "AuditShipper | None":
    """返回当前审计外送 shipper(未启用为 None)。"""
    return _audit_shipper


def _attach_audit_shipper_hook(store: AuditStore) -> AuditStore:
    """包装 AuditStore.record, 写入成功后 enqueue 到已注册的 shipper。

    shipper 在调用时读取(而非包装时绑定), 因此 lru_cache 单例构造一次即可,
    之后 set_audit_shipper 的注册/清除即时生效。未注册时为零开销 no-op。
    """
    original_record = store.record

    def record_and_enqueue(*args, **kwargs):
        record = original_record(*args, **kwargs)
        shipper = _audit_shipper
        if shipper is not None:
            try:
                shipper.enqueue_event(record)
            except Exception:
                logging.getLogger("xagent.dependencies").warning(
                    "audit shipper enqueue failed", exc_info=True
                )
        return record

    store.record = record_and_enqueue  # type: ignore[method-assign]
    return store


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


_rbac_engine: "AdvancedRBACEngine | None" = None


async def get_rbac_engine() -> "AdvancedRBACEngine":
    """Get the AdvancedRBACEngine with optional persistent storage (P0-05).

    In production (admin_store_backend=postgres), uses PostgresRBACRepository
    for persistent role/assignment storage. In development, uses in-memory.
    """
    global _rbac_engine
    if _rbac_engine is None:
        from backend.app.core.advanced_rbac import AdvancedRBACEngine, PostgresRBACRepository

        settings = get_settings()
        storage = None

        # Use persistent storage in production or when explicitly configured
        if settings.admin_store_backend in {"postgres", "postgresql", "db", "sql"}:
            try:
                import asyncpg
                # Extract connection info from database_url
                # database_url format: postgresql+asyncpg://user:pass@host:port/db
                db_url = settings.database_url
                if "+asyncpg" in db_url:
                    db_url = db_url.replace("+asyncpg", "")
                pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
                storage = PostgresRBACRepository(pool)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to create RBAC PostgreSQL storage, falling back to memory: {e}"
                )
                storage = None

        _rbac_engine = AdvancedRBACEngine(storage=storage)
        await _rbac_engine.initialize()

    return _rbac_engine


def get_current_principal(request: Request) -> Principal:
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

    # 生产环境绝不回落匿名主体（S5）：即便 require_api_key 默认 False，
    # 生产模式也必须要求显式凭证，避免漏配 enforce_scope 的路由被未鉴权访问。
    if settings.require_api_key or getattr(settings, "app_mode", "development") == "production":
        raise api_error(401, ErrorCode.AUTHENTICATION_FAILED, "API key required.")
    return anonymous_principal()


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
def get_workflow_repository() -> "WorkflowRepository":
    from backend.app.core.workflow_store import build_workflow_repository

    settings = get_settings()
    return build_workflow_repository(
        backend=settings.workflow_store_backend,
        database_url=settings.database_url,
        definition_path=settings.workflow_store_path,
        run_path=settings.workflow_run_store_path,
    )


@lru_cache
def get_workflow_executor() -> "WorkflowExecutor":
    from backend.app.core.workflows import WorkflowExecutor

    settings = get_settings()
    return WorkflowExecutor(
        agent=get_agent(),
        repository=get_workflow_repository(),
        tracer=get_trace_store(),
        approval_store=get_approval_store(),
        audit_store=get_audit_store(),
        max_parallel=settings.workflow_max_parallel,
        parallel_mode=settings.workflow_parallel_mode,
        parallel_error_strategy=settings.workflow_parallel_error_strategy,
    )


@lru_cache
def get_workflow_runtime() -> "WorkflowRuntimeManager":
    from backend.app.core.workflows import WorkflowRuntimeManager

    return WorkflowRuntimeManager(
        executor=get_workflow_executor(),
        repository=get_workflow_repository(),
    )


@lru_cache
def get_workflow_schedule_store() -> "WorkflowScheduleStore":
    from backend.app.core.workflow_store import build_workflow_schedule_store

    settings = get_settings()
    return build_workflow_schedule_store(
        backend=settings.workflow_store_backend,
        database_url=settings.database_url,
        storage_path=settings.workflow_schedule_store_path,
    )


@lru_cache
def get_workflow_scheduler() -> "WorkflowScheduler":
    from backend.app.core.workflows import WorkflowScheduler

    return WorkflowScheduler(
        repository=get_workflow_repository(),
        runtime=get_workflow_runtime(),
        schedule_store=get_workflow_schedule_store(),
    )


@lru_cache
def get_agent_context_manager() -> "AgentContextManager":
    """P1-14: 返回共享的 AgentContextManager 实例（统一上下文容器、会话恢复、状态快照）。"""
    from backend.app.core.agent_context import AgentContextManager

    settings = get_settings()
    storage_path = getattr(settings, "agent_context_store_path", None) or "data/agent_contexts"
    return AgentContextManager(storage_path=storage_path)


@lru_cache
def get_runtime_tool_registry() -> "ToolRegistry":
    """唯一的运行时工具注册表（P1-10 "1+1" 收敛的最后接线）。

    AgentLoop（get_agent）、main.py startup（技能注册）、MCP 发现桥接
    （initialize_mcp_manager 的 runtime_registry 参数）全部共享本实例。
    修复此前 main.py 与 dependencies 各建一套注册表、技能/MCP 工具注册进
    agent 用不到的那一套的双实例问题。
    """
    from backend.app.core.tools import build_default_tool_registry

    settings = get_settings()
    policy = ToolPolicyEngine(enable_high_risk_tools=settings.enable_high_risk_tools)
    return build_default_tool_registry(
        policy,
        approval_store=get_approval_store(),
        execution_store=get_tool_execution_store(),
    )


@lru_cache
def get_agent() -> "AgentLoop":
    from backend.app.core.agent import AgentLoop
    from backend.app.core.llm import build_llm_router

    settings = get_settings()
    tools = get_runtime_tool_registry()
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
        agent_context_manager=get_agent_context_manager(),
        # P1-13: Wire UnifiedMemorySystem with real embeddings as enhanced layer
        unified_memory=get_unified_memory(),
    )


@lru_cache
def get_orchestrator() -> "Orchestrator":
    from backend.app.core.orchestrator import Orchestrator

    return Orchestrator()


@lru_cache
def get_llm_router():
    """Return the shared LLMRouter instance (cached)."""
    from backend.app.core.llm import build_llm_router

    settings = get_settings()
    return build_llm_router(
        llm_backend=settings.llm_backend,
        fallback_order=settings.llm_fallback_order,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
    )
