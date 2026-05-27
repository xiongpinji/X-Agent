"""
Backward compatibility adapter for AgentLoop refactoring.

Allows existing code to use the new architecture without changes.
Provides deprecation warnings for migration path.
"""

import warnings
from typing import Any, Awaitable, Callable

from backend.app.core.contracts import (
    RunContext, AgentRunResponse, TraceEvent, ToolCallRecord,
    ExecutionFrame, TaskFrame, RecoveryFrame,
)
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import MemorySystem
from backend.app.core.tools import ToolRegistry
from backend.app.core.browser import BrowserAutomationStore
from backend.app.core.desktop import DesktopAutomationStore
from backend.app.core.tracing import TraceStore, tracer as default_tracer
from backend.app.core.audit import AuditStore
from backend.app.core.runs import RunStore
from backend.app.core.orchestrator import Orchestrator
from backend.app.core.verification import VerificationEngine
from backend.app.core.repair_loop import RepairLoop
from backend.app.core.agent_state_manager import AgentStateManager
from backend.app.core.agent_runtime_adapter import AgentRuntimeAdapter

from backend.app.core.agent.executor import ToolExecutor
from backend.app.core.agent.planner import TaskPlanner
from backend.app.core.agent.memory_manager import MemoryManager
from backend.app.core.agent.state_manager import StateManager
from backend.app.core.agent.coordinator import AgentCoordinator


class AgentLoopCompat:
    """
    Backward-compatible wrapper for AgentLoop.

    Maintains the original interface while using the new refactored components.
    Provides deprecation warnings to guide migration.
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        memory: MemorySystem,
        tools: ToolRegistry,
        max_iterations: int = 4,
        tracer: TraceStore | None = None,
        run_store: RunStore | None = None,
        browser_store: BrowserAutomationStore | None = None,
        desktop_store: DesktopAutomationStore | None = None,
        audit_store: AuditStore | None = None,
        orchestrator: Orchestrator | None = None,
        verification_engine: VerificationEngine | None = None,
        repair_loop: RepairLoop | None = None,
    ) -> None:
        """
        Initialize AgentLoop with backward compatibility.

        Args:
            llm_router: LLM router instance
            memory: Memory system instance
            tools: Tool registry instance
            max_iterations: Maximum iterations
            tracer: Trace store (optional)
            run_store: Run store (optional)
            browser_store: Browser automation store (optional)
            desktop_store: Desktop automation store (optional)
            audit_store: Audit store (optional)
            orchestrator: Orchestrator (optional)
            verification_engine: Verification engine (optional)
            repair_loop: Repair loop (optional)
        """
        warnings.warn(
            "AgentLoop is deprecated. Use AgentCoordinator with individual components instead. "
            "See REFACTORING_GUIDE.md for migration instructions.",
            DeprecationWarning,
            stacklevel=2,
        )

        self.llm = llm_router
        self.memory = memory
        self.tools = tools
        self.max_iterations = max_iterations
        self.tracer = tracer or default_tracer
        self.run_store = run_store
        self.browser_store = browser_store
        self.desktop_store = desktop_store
        self.audit_store = audit_store
        self.orchestrator = orchestrator or Orchestrator()
        self.verification_engine = verification_engine or VerificationEngine()
        self.repair_loop = repair_loop or RepairLoop(self.verification_engine)

        # Legacy components (kept for compatibility)
        self.state_manager = AgentStateManager()
        self.runtime_adapter = AgentRuntimeAdapter(self.state_manager)

        # Initialize new refactored components
        self._init_refactored_components()

    def _init_refactored_components(self) -> None:
        """Initialize the new refactored components."""
        self.executor = ToolExecutor(self.tools, self.repair_loop)
        self.planner = TaskPlanner(self.llm, self.tools)
        self.memory_manager = MemoryManager(self.memory)
        self.state_manager_new = StateManager()
        self.coordinator = AgentCoordinator(
            self.executor,
            self.planner,
            self.memory_manager,
            self.state_manager_new,
            tracer=self.tracer,
            audit_store=self.audit_store,
            run_store=self.run_store,
            max_iterations=self.max_iterations,
        )

    async def run(
        self,
        context: RunContext,
        task: str,
        extra_context: dict | None = None,
        event_callback: Callable[[TraceEvent], Awaitable[None] | None] | None = None,
    ) -> AgentRunResponse:
        """
        Execute task using the new refactored architecture.

        This method maintains the original interface while delegating to
        the new AgentCoordinator internally.

        Args:
            context: Execution context
            task: Task description
            extra_context: Additional context
            event_callback: Event callback

        Returns:
            AgentRunResponse with results
        """
        # Delegate to new coordinator
        return await self.coordinator.run(
            context,
            task,
            extra_context=extra_context,
            event_callback=event_callback,
        )

    # Legacy methods for compatibility (deprecated)

    def _build_initial_recovery_frame(self, tool_name: str | None = None) -> RecoveryFrame:
        """Legacy method - use StateManager instead."""
        warnings.warn(
            "_build_initial_recovery_frame is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        return RecoveryFrame(
            branch="continue",
            retryable=False,
            confidence=0.5,
            tool_name=tool_name,
            follow_up=["continue planning", "execute selected tool"],
            status_detail="initial agent recovery frame",
            remediation="continue with plan execution",
        )

    def _compress_context(self, extra_context: dict[str, object]) -> dict[str, object]:
        """Legacy method - context compression."""
        warnings.warn(
            "_compress_context is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        keys = [
            "root", "path", "target_path", "file", "pattern", "limit",
            "read_limit", "replace_all", "old_text", "new_text", "replacement",
            "content", "goal", "objective", "patches", "resume_trace_id",
            "skip_observe_on_resume"
        ]
        compact: dict[str, object] = {}
        for key in keys:
            if key in extra_context:
                compact[key] = extra_context[key]
        return compact

    def _derive_goal(self, task: str, extra_context: dict[str, object]) -> str:
        """Legacy method - goal derivation."""
        warnings.warn(
            "_derive_goal is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        prompt = str(extra_context.get("goal") or extra_context.get("objective") or "")
        if prompt.strip():
            return prompt.strip()
        text = task.strip().splitlines()[0] if task.strip() else ""
        if len(text) > 240:
            text = text[:240]
        return text or "complete the task"

    def _decompose_task(self, task: str, extra_context: dict[str, object]) -> list[str]:
        """Legacy method - use TaskPlanner.decompose instead."""
        warnings.warn(
            "_decompose_task is deprecated. Use TaskPlanner.decompose instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.planner.decompose(task, extra_context)

    def _stringify(self, value: object) -> str:
        """Legacy method - value stringification."""
        import json
        if isinstance(value, (str, int, float, bool)) or value is None:
            return json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
        return json.dumps(value, ensure_ascii=False, default=str)

    # Properties for backward compatibility

    @property
    def approval_store(self) -> Any:
        """Legacy property - approval store."""
        return None

    @property
    def workflow_repository(self) -> Any:
        """Legacy property - workflow repository."""
        return None


# Factory function for easy migration
def create_agent_loop(
    llm_router: LLMRouter,
    memory: MemorySystem,
    tools: ToolRegistry,
    **kwargs: Any,
) -> AgentLoopCompat:
    """
    Create an AgentLoop instance with backward compatibility.

    This is the recommended way to create an agent for existing code.

    Args:
        llm_router: LLM router instance
        memory: Memory system instance
        tools: Tool registry instance
        **kwargs: Additional arguments

    Returns:
        AgentLoopCompat instance
    """
    return AgentLoopCompat(llm_router, memory, tools, **kwargs)


# Migration helper
def migrate_to_new_architecture(
    agent: AgentLoopCompat,
) -> tuple[ToolExecutor, TaskPlanner, MemoryManager, StateManager, AgentCoordinator]:
    """
    Extract new components from legacy AgentLoop.

    Use this to gradually migrate from AgentLoopCompat to the new architecture.

    Args:
        agent: AgentLoopCompat instance

    Returns:
        Tuple of (executor, planner, memory_manager, state_manager, coordinator)
    """
    return (
        agent.executor,
        agent.planner,
        agent.memory_manager,
        agent.state_manager_new,
        agent.coordinator,
    )
