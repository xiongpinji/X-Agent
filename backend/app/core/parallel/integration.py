"""Parallel execution integration for AgentLoop."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.app.core.parallel.tool_executor import ParallelToolExecutor, ToolCall
from backend.app.core.parallel.agent_executor import ParallelAgentExecutor, AgentTask
from backend.app.core.parallel.communication_bus import AgentCommunicationBus

logger = logging.getLogger(__name__)


class ParallelExecutionConfig:
    """Configuration for parallel execution."""

    def __init__(
        self,
        enable_tool_parallelism: bool = True,
        enable_agent_parallelism: bool = True,
        max_concurrent_tools: int = 10,
        max_concurrent_agents: int = 3,
        tool_timeout_seconds: float = 30.0,
        agent_timeout_seconds: int = 300,
        enable_caching: bool = True,
        cache_ttl_seconds: int = 3600,
        enable_communication_bus: bool = True,
    ) -> None:
        """Initialize parallel execution configuration.

        Args:
            enable_tool_parallelism: Enable parallel tool execution
            enable_agent_parallelism: Enable parallel agent execution
            max_concurrent_tools: Maximum concurrent tool executions
            max_concurrent_agents: Maximum concurrent agents
            tool_timeout_seconds: Default timeout for tool execution
            agent_timeout_seconds: Default timeout for agent execution
            enable_caching: Enable result caching
            cache_ttl_seconds: Cache TTL in seconds
            enable_communication_bus: Enable communication bus
        """
        self.enable_tool_parallelism = enable_tool_parallelism
        self.enable_agent_parallelism = enable_agent_parallelism
        self.max_concurrent_tools = max_concurrent_tools
        self.max_concurrent_agents = max_concurrent_agents
        self.tool_timeout_seconds = tool_timeout_seconds
        self.agent_timeout_seconds = agent_timeout_seconds
        self.enable_caching = enable_caching
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_communication_bus = enable_communication_bus


class ParallelExecutionManager:
    """Manages parallel execution of tools and agents."""

    def __init__(
        self,
        tool_registry: Any,
        config: Optional[ParallelExecutionConfig] = None,
    ) -> None:
        """Initialize the parallel execution manager.

        Args:
            tool_registry: Tool registry for executing tools
            config: Parallel execution configuration
        """
        self._tool_registry = tool_registry
        self._config = config or ParallelExecutionConfig()

        # Initialize components
        if self._config.enable_tool_parallelism:
            from backend.app.core.parallel.tool_executor import ToolResultCache

            cache = ToolResultCache(ttl_seconds=self._config.cache_ttl_seconds) if self._config.enable_caching else None
            self._tool_executor = ParallelToolExecutor(
                tool_registry=tool_registry,
                cache=cache,
                max_concurrent=self._config.max_concurrent_tools,
                default_timeout=self._config.tool_timeout_seconds,
            )
        else:
            self._tool_executor = None

        if self._config.enable_agent_parallelism:
            self._agent_executor = ParallelAgentExecutor(
                max_workers=self._config.max_concurrent_agents,
            )
        else:
            self._agent_executor = None

        if self._config.enable_communication_bus:
            self._communication_bus = AgentCommunicationBus()
        else:
            self._communication_bus = None

    async def execute_tools_parallel(
        self,
        tool_calls: list[dict[str, Any]],
        context: Any = None,
        allow_partial_failure: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute multiple tools in parallel.

        Args:
            tool_calls: List of tool calls
            context: Execution context
            allow_partial_failure: If False, stop on first failure

        Returns:
            List of tool results
        """
        if not self._config.enable_tool_parallelism or not self._tool_executor:
            logger.warning("Tool parallelism is disabled")
            return []

        # Convert tool calls to ToolCall objects
        calls = []
        for call in tool_calls:
            tool_call = ToolCall(
                tool_name=call.get("tool_name", ""),
                arguments=call.get("arguments", {}),
                call_id=call.get("call_id"),
                timeout_seconds=call.get("timeout_seconds", self._config.tool_timeout_seconds),
                retry_count=call.get("retry_count", 0),
            )
            calls.append(tool_call)

        # Check if tools have dependencies
        has_dependencies = any(call.get("dependencies") for call in tool_calls)

        if has_dependencies:
            # Execute with dependency analysis
            results_dict = await self._tool_executor.execute_with_dependencies(
                calls,
                context=context,
                allow_partial_failure=allow_partial_failure,
            )
            results = list(results_dict.values())
        else:
            # Execute without dependency analysis
            results = await self._tool_executor.execute_batch(
                calls,
                context=context,
                allow_partial_failure=allow_partial_failure,
            )

        # Convert results to dictionaries
        return [
            {
                "call_id": result.call_id,
                "tool_name": result.tool_name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "latency_ms": result.latency_ms,
                "cached": result.cached,
                "retry_attempt": result.retry_attempt,
            }
            for result in results
        ]

    async def execute_agents_parallel(
        self,
        tasks: list[dict[str, Any]],
        agent_factory: Any,
        allow_partial_failure: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute multiple agents in parallel.

        Args:
            tasks: List of agent tasks
            agent_factory: Factory function to create agents
            allow_partial_failure: If False, stop on first failure

        Returns:
            List of agent results
        """
        if not self._config.enable_agent_parallelism or not self._agent_executor:
            logger.warning("Agent parallelism is disabled")
            return []

        # Convert tasks to AgentTask objects
        agent_tasks = []
        for task in tasks:
            agent_task = AgentTask(
                task_id=task.get("task_id"),
                goal=task.get("goal", ""),
                description=task.get("description", ""),
                constraints=task.get("constraints", []),
                success_criteria=task.get("success_criteria", []),
                timeout_seconds=task.get("timeout_seconds", self._config.agent_timeout_seconds),
                retry_count=task.get("retry_count", 0),
                max_retries=task.get("max_retries", 3),
                metadata=task.get("metadata", {}),
                dependencies=task.get("dependencies", []),
            )
            agent_tasks.append(agent_task)

        # Check if tasks have dependencies
        has_dependencies = any(task.dependencies for task in agent_tasks)

        if has_dependencies:
            # Execute with coordination
            batch_result = await self._agent_executor.execute_with_coordination(
                agent_tasks,
                agent_factory=agent_factory,
            )
        else:
            # Execute without coordination
            batch_result = await self._agent_executor.execute_tasks(
                agent_tasks,
                agent_factory=agent_factory,
                allow_partial_failure=allow_partial_failure,
            )

        # Convert results to dictionaries
        return [result.to_dict() for result in batch_result.results]

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        message_type: str = "direct",
    ) -> Optional[str]:
        """Send a message between agents.

        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            content: Message content
            message_type: Message type (direct, broadcast, topic)

        Returns:
            Message ID or None if communication bus is disabled
        """
        if not self._config.enable_communication_bus or not self._communication_bus:
            logger.warning("Communication bus is disabled")
            return None

        if message_type == "direct":
            return await self._communication_bus.send_direct(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
            )
        elif message_type == "broadcast":
            return await self._communication_bus.send_broadcast(
                from_agent=from_agent,
                content=content,
            )
        elif message_type == "topic":
            topic = content.get("topic", "")
            return await self._communication_bus.publish_topic(
                from_agent=from_agent,
                topic=topic,
                content=content.get("data"),
            )
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None

    async def receive_message(
        self,
        agent_id: str,
        message_type: str = "direct",
        timeout_seconds: float = 5.0,
    ) -> Optional[dict[str, Any]]:
        """Receive a message for an agent.

        Args:
            agent_id: Agent ID
            message_type: Message type (direct, broadcast, topic)
            timeout_seconds: Timeout for receiving

        Returns:
            Message dictionary or None if timeout
        """
        if not self._config.enable_communication_bus or not self._communication_bus:
            logger.warning("Communication bus is disabled")
            return None

        if message_type == "direct":
            message = await self._communication_bus.receive_direct(
                agent_id=agent_id,
                timeout_seconds=timeout_seconds,
            )
        elif message_type == "broadcast":
            message = await self._communication_bus.receive_broadcast(
                agent_id=agent_id,
                timeout_seconds=timeout_seconds,
            )
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None

        if message:
            return message.to_dict()
        return None

    async def get_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "config": {
                "enable_tool_parallelism": self._config.enable_tool_parallelism,
                "enable_agent_parallelism": self._config.enable_agent_parallelism,
                "max_concurrent_tools": self._config.max_concurrent_tools,
                "max_concurrent_agents": self._config.max_concurrent_agents,
            },
        }

        if self._tool_executor:
            tool_stats = self._tool_executor.get_stats()
            stats["tool_executor"] = {
                "total_calls": tool_stats.total_calls,
                "successful_calls": tool_stats.successful_calls,
                "failed_calls": tool_stats.failed_calls,
                "cached_calls": tool_stats.cached_calls,
                "total_latency_ms": tool_stats.total_latency_ms,
                "execution_layers": tool_stats.execution_layers,
                "parallelism_factor": tool_stats.parallelism_factor,
            }

        if self._agent_executor:
            agent_stats = self._agent_executor.get_pool_stats()
            stats["agent_executor"] = agent_stats

        if self._communication_bus:
            bus_stats = await self._communication_bus.get_stats()
            stats["communication_bus"] = bus_stats

        return stats
