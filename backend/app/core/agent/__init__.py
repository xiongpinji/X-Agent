"""
X-Agent refactored core module with reduced coupling.

This package contains the refactored AgentLoop components following SOLID principles.
"""

from backend.app.core.agent.executor import ToolExecutor
from backend.app.core.agent.planner import TaskPlanner
from backend.app.core.agent.memory_manager import MemoryManager
from backend.app.core.agent.state_manager import StateManager
from backend.app.core.agent.coordinator import AgentCoordinator

__all__ = [
    "ToolExecutor",
    "TaskPlanner",
    "MemoryManager",
    "StateManager",
    "AgentCoordinator",
]
