"""Parallel execution engine for X-Agent.

This module provides:
- ParallelToolExecutor: Execute multiple tools in parallel with dependency awareness
- ParallelAgentExecutor: Execute multiple agents in parallel with coordination
- AgentCommunicationBus: Inter-agent messaging and coordination
"""

from .tool_executor import ParallelToolExecutor, ToolCall, ToolResult, BatchExecutionStats
from .agent_executor import ParallelAgentExecutor, AgentTask, AgentResult, BatchExecutionResult
from .communication_bus import AgentCommunicationBus, Message, MessageType, MessagePriority

__all__ = [
    "ParallelToolExecutor",
    "ToolCall",
    "ToolResult",
    "BatchExecutionStats",
    "ParallelAgentExecutor",
    "AgentTask",
    "AgentResult",
    "BatchExecutionResult",
    "AgentCommunicationBus",
    "Message",
    "MessageType",
    "MessagePriority",
]
