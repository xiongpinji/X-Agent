"""
X-Agent refactored core module with reduced coupling.

This package contains the refactored AgentLoop components following SOLID principles.
"""

from backend.app.core.agent.coordinator import AgentCoordinator
from backend.app.core.agent.executor import ToolExecutor
from backend.app.core.agent.loop import (
    AgentLoop,
    AgentPlanStep,
    AgentTrajectory,
)
from backend.app.core.agent.memory_manager import MemoryManager
from backend.app.core.agent.planner import TaskPlanner
from backend.app.core.agent.state_manager import StateManager

# Re-export AgentPlanStepRecord for backward compatibility — the old single-file
# agent.py had this symbol in its namespace (imported from contracts), and
# agent_v2/phases/execution.py imports it from here at runtime.
from backend.app.core.contracts import AgentPlanStepRecord

__all__ = [
    "AgentCoordinator",
    "AgentLoop",
    "AgentPlanStep",
    "AgentPlanStepRecord",
    "AgentTrajectory",
    "MemoryManager",
    "StateManager",
    "TaskPlanner",
    "ToolExecutor",
]

