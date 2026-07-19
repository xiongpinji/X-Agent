"""
Core interfaces for AgentLoop refactoring using Protocol-based design.

Defines the contracts for each component following SOLID principles.
"""

from typing import Protocol, Any, Awaitable, Callable
from dataclasses import dataclass
from backend.app.core.contracts import RunContext, ToolCallRecord, TraceEvent


@dataclass
class ExecutionResult:
    """Result of tool execution."""
    success: bool
    output: Any
    error: str | None = None
    latency_ms: int = 0


@dataclass
class PlanStep:
    """Single step in execution plan."""
    kind: str  # "observe", "tool", "reflect", "final"
    instruction: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


@dataclass
class TaskProfile:
    """Analysis of task characteristics."""
    mode: str  # "edit", "analyze", "search", "summarize", "general"
    intent: str  # "code_change", "analysis", "summary", "discovery", "automation"
    complexity: float
    urgency: float
    constraints: list[dict[str, Any]]
    focus: list[str]


class ToolExecutorProtocol(Protocol):
    """Protocol for tool execution engine."""

    async def execute(
        self,
        context: RunContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a tool and return result."""
        ...

    async def verify_write(
        self,
        context: RunContext,
        tool_name: str,
        output: Any,
        arguments: dict[str, Any],
    ) -> bool:
        """Verify write operation success."""
        ...

    async def repair_failed_step(
        self,
        context: RunContext,
        tool_name: str,
        error: str,
        original_arguments: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Suggest repair for failed tool execution."""
        ...


class TaskPlannerProtocol(Protocol):
    """Protocol for task planning engine."""

    async def plan(
        self,
        context: RunContext,
        task: str,
        goal: str,
        extra_context: dict[str, Any],
    ) -> list[PlanStep]:
        """Generate execution plan from task."""
        ...

    def decompose(
        self,
        task: str,
        extra_context: dict[str, Any],
    ) -> list[str]:
        """Break task into subtasks."""
        ...

    def analyze_task(
        self,
        task: str,
        extra_context: dict[str, Any],
    ) -> TaskProfile:
        """Analyze task characteristics."""
        ...


class MemoryManagerProtocol(Protocol):
    """Protocol for memory management."""

    async def store(
        self,
        context: RunContext,
        content: str,
        layer: int,
        importance: float,
        tags: list[str],
        metadata: dict[str, Any],
    ) -> str:
        """Store memory and return ID."""
        ...

    async def retrieve(
        self,
        context: RunContext,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant memories."""
        ...

    async def search(
        self,
        context: RunContext,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memories with scoring."""
        ...


class StateManagerProtocol(Protocol):
    """Protocol for state management."""

    def create_initial_state(
        self,
        context: RunContext,
        task_frame: Any,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Create initial execution state."""
        ...

    def update_state(
        self,
        state: dict[str, Any],
        **updates: Any,
    ) -> dict[str, Any]:
        """Update state with new values."""
        ...

    def get_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Get current state snapshot."""
        ...

    def apply_recovery(
        self,
        state: dict[str, Any],
        recovery_branch: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply recovery strategy to state."""
        ...


class CoordinatorProtocol(Protocol):
    """Protocol for agent coordination."""

    async def run(
        self,
        context: RunContext,
        task: str,
        extra_context: dict[str, Any] | None = None,
        event_callback: Callable[[TraceEvent], Awaitable[None] | None] | None = None,
    ) -> dict[str, Any]:
        """Execute task end-to-end."""
        ...
