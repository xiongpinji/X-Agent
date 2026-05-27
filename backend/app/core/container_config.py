"""
Container configuration for X-Agent services.

Centralizes service registration and dependency graph configuration.
Resolves circular dependencies through lazy initialization and factory patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.core.container import Container, Scope

if TYPE_CHECKING:
    from backend.app.core.agent import AgentLoop
    from backend.app.core.approvals import ApprovalStore
    from backend.app.core.audit import AuditStore
    from backend.app.core.browser import BrowserAutomationStore
    from backend.app.core.desktop import DesktopAutomationStore
    from backend.app.core.llm import LLMRouter
    from backend.app.core.memory import MemorySystem
    from backend.app.core.memory_postgres import PostgresMemorySystem
    from backend.app.core.orchestrator import Orchestrator
    from backend.app.core.policy import ToolPolicyEngine
    from backend.app.core.runs import RunStore
    from backend.app.core.security import APIKeyStore, RBACPolicy
    from backend.app.core.tools import ToolRegistry
    from backend.app.core.tracing import TraceStore
    from backend.app.core.tracing_postgres import PostgresTraceStore
    from backend.app.core.workflows import (
        WorkflowExecutor,
        WorkflowRepository,
        WorkflowRuntimeManager,
        WorkflowScheduler,
        WorkflowScheduleStore,
    )


def configure_container(container: Container) -> Container:
    """
    Configure the DI container with all X-Agent services.

    This function registers all services and their dependencies,
    resolving circular dependencies through lazy initialization.

    Args:
        container: The container to configure

    Returns:
        The configured container
    """

    # ============================================================================
    # Settings and Configuration (Singletons)
    # ============================================================================

    def _get_settings(c: Container):
        from backend.app.settings import get_settings

        return get_settings()

    container.singleton(type(None).__class__, _get_settings)  # Settings type

    # ============================================================================
    # Storage Stores (Singletons)
    # ============================================================================

    def _get_memory(c: Container):
        from backend.app.dependencies import get_memory

        return get_memory()

    def _get_trace_store(c: Container):
        from backend.app.dependencies import get_trace_store

        return get_trace_store()

    def _get_run_store(c: Container):
        from backend.app.dependencies import get_run_store

        return get_run_store()

    def _get_browser_store(c: Container):
        from backend.app.dependencies import get_browser_store

        return get_browser_store()

    def _get_desktop_store(c: Container):
        from backend.app.dependencies import get_desktop_store

        return get_desktop_store()

    def _get_tool_execution_store(c: Container):
        from backend.app.dependencies import get_tool_execution_store

        return get_tool_execution_store()

    def _get_audit_store(c: Container):
        from backend.app.dependencies import get_audit_store

        return get_audit_store()

    def _get_api_key_store(c: Container):
        from backend.app.dependencies import get_api_key_store

        return get_api_key_store()

    def _get_approval_store(c: Container):
        from backend.app.dependencies import get_approval_store

        return get_approval_store()

    # Register storage stores
    from backend.app.core.memory import MemorySystem
    from backend.app.core.memory_postgres import PostgresMemorySystem
    from backend.app.core.tracing import TraceStore
    from backend.app.core.tracing_postgres import PostgresTraceStore
    from backend.app.core.runs import RunStore
    from backend.app.core.browser import BrowserAutomationStore
    from backend.app.core.desktop import DesktopAutomationStore
    from backend.app.core.tools import ToolExecutionStore
    from backend.app.core.audit import AuditStore
    from backend.app.core.security import APIKeyStore
    from backend.app.core.approvals import ApprovalStore

    container.singleton(MemorySystem | PostgresMemorySystem, _get_memory)
    container.singleton(TraceStore | PostgresTraceStore, _get_trace_store)
    container.singleton(RunStore, _get_run_store)
    container.singleton(BrowserAutomationStore, _get_browser_store)
    container.singleton(DesktopAutomationStore, _get_desktop_store)
    container.singleton(ToolExecutionStore, _get_tool_execution_store)
    container.singleton(AuditStore, _get_audit_store)
    container.singleton(APIKeyStore, _get_api_key_store)
    container.singleton(ApprovalStore, _get_approval_store)

    # ============================================================================
    # Security and Policy (Singletons)
    # ============================================================================

    def _get_rbac_policy(c: Container):
        from backend.app.dependencies import get_rbac_policy

        return get_rbac_policy()

    from backend.app.core.security import RBACPolicy

    container.singleton(RBACPolicy, _get_rbac_policy)

    # ============================================================================
    # LLM and Tools (Singletons)
    # ============================================================================

    def _build_llm_router(c: Container):
        from backend.app.core.llm import build_llm_router
        from backend.app.settings import get_settings

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

    def _build_tool_registry(c: Container):
        from backend.app.core.policy import ToolPolicyEngine
        from backend.app.core.tools import build_default_tool_registry
        from backend.app.settings import get_settings

        settings = get_settings()
        policy = ToolPolicyEngine(enable_high_risk_tools=settings.enable_high_risk_tools)
        return build_default_tool_registry(
            policy,
            approval_store=c.resolve(ApprovalStore),
            execution_store=c.resolve(ToolExecutionStore),
        )

    from backend.app.core.llm import LLMRouter
    from backend.app.core.tools import ToolRegistry

    container.singleton(LLMRouter, _build_llm_router)
    container.singleton(ToolRegistry, _build_tool_registry)

    # ============================================================================
    # Workflow Services (Singletons)
    # ============================================================================

    def _get_workflow_repository(c: Container):
        from backend.app.dependencies import get_workflow_repository

        return get_workflow_repository()

    def _get_workflow_executor(c: Container):
        from backend.app.dependencies import get_workflow_executor

        return get_workflow_executor()

    def _get_workflow_runtime(c: Container):
        from backend.app.dependencies import get_workflow_runtime

        return get_workflow_runtime()

    def _get_workflow_schedule_store(c: Container):
        from backend.app.dependencies import get_workflow_schedule_store

        return get_workflow_schedule_store()

    def _get_workflow_scheduler(c: Container):
        from backend.app.dependencies import get_workflow_scheduler

        return get_workflow_scheduler()

    from backend.app.core.workflows import (
        WorkflowRepository,
        WorkflowExecutor,
        WorkflowRuntimeManager,
        WorkflowScheduleStore,
        WorkflowScheduler,
    )

    container.singleton(WorkflowRepository, _get_workflow_repository)
    container.singleton(WorkflowExecutor, _get_workflow_executor)
    container.singleton(WorkflowRuntimeManager, _get_workflow_runtime)
    container.singleton(WorkflowScheduleStore, _get_workflow_schedule_store)
    container.singleton(WorkflowScheduler, _get_workflow_scheduler)

    # ============================================================================
    # Agent Loop (Singleton - Core Service)
    # ============================================================================

    def _get_agent(c: Container):
        from backend.app.dependencies import get_agent

        return get_agent()

    from backend.app.core.agent import AgentLoop

    container.singleton(AgentLoop, _get_agent)

    # ============================================================================
    # Orchestrator (Singleton)
    # ============================================================================

    def _get_orchestrator(c: Container):
        from backend.app.dependencies import get_orchestrator

        return get_orchestrator()

    from backend.app.core.orchestrator import Orchestrator

    container.singleton(Orchestrator, _get_orchestrator)

    return container


def create_configured_container() -> Container:
    """
    Create and configure a new container instance.

    Returns:
        A fully configured Container
    """
    container = Container()
    return configure_container(container)
