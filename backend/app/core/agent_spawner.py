"""
Agent spawner module for X-Agent.

Manages the lifecycle of sub-agents including spawning, termination,
and status tracking.

Isolation-level semantics (honest capability statement, P1-09):

- ``IsolationLevel.NONE`` (alias ``"thread"``): in-process asyncio execution.
  The sub-agent shares the OS process with the spawner; isolation is limited
  to asyncio task boundaries. This is the default.
- ``IsolationLevel.PROCESS``: the sub-agent runs in a real OS child process
  (``multiprocessing``, spawn context). A crash of the child cannot take down
  the parent. Implemented by :func:`_process_worker_entry`.
- ``IsolationLevel.CONTAINER``: **not implemented here**. Requesting it raises
  :class:`NotImplementedError` at spawn time. Container-isolated execution is
  the sandbox path: ``backend.app.core.sandbox.docker_sandbox`` (Docker) behind
  ``backend.app.core.code_sandbox.CodeSandbox``.

Resource limits (``memory_limit_mb`` / ``cpu_limit_percent``) are currently
declarative metadata: they are recorded on the instance and surfaced via
``get_agent_status`` as ``resource_limits_enforced: False``. They are NOT
enforced by the OS on any platform yet; no silent no-op — a warning is logged
whenever a spawn requests them.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import multiprocessing
import queue as queue_module
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class AgentStatus(StrEnum):
    """Status of an agent."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class IsolationLevel(StrEnum):
    """Isolation level for agent execution.

    ``NONE`` is thread-level (in-process asyncio); ``"thread"`` is accepted
    as an input alias and normalized to ``NONE``. ``PROCESS`` runs a real OS
    child process. ``CONTAINER`` is reserved for the sandbox path and raises
    :class:`NotImplementedError` when requested here.
    """

    NONE = "none"
    PROCESS = "process"
    CONTAINER = "container"


#: Human-readable pointer used in the CONTAINER error message and in docs.
CONTAINER_SANDBOX_PATH = "backend.app.core.sandbox.docker_sandbox"


def _normalize_isolation(isolation: str | None) -> IsolationLevel:
    """Normalize the isolation input into an :class:`IsolationLevel`.

    ``"thread"`` is accepted as an alias of ``"none"`` (in-process asyncio).
    ``CONTAINER`` is rejected explicitly: container isolation is the sandbox
    path, not the spawner path. ``NotImplementedError`` (a ``RuntimeError``
    subclass) is raised so existing API error handling surfaces a clear 400.
    """
    if not isolation:
        return IsolationLevel.NONE
    normalized = str(isolation).strip().lower()
    if normalized == "thread":
        return IsolationLevel.NONE
    try:
        level = IsolationLevel(normalized)
    except ValueError:
        raise ValueError(
            f"Unknown isolation level: {isolation!r}. "
            f"Supported: 'none' (thread-level, in-process), 'process'. "
            f"For container isolation use {CONTAINER_SANDBOX_PATH}."
        ) from None
    if level == IsolationLevel.CONTAINER:
        raise NotImplementedError(
            "IsolationLevel.CONTAINER is not implemented in AgentSpawner. "
            f"Container-isolated execution is provided by the sandbox path: "
            f"{CONTAINER_SANDBOX_PATH} behind backend.app.core.code_sandbox.CodeSandbox. "
            "Route container workloads there, or use isolation='process' / 'none'."
        )
    return level


@dataclass
class AgentConfig:
    """Configuration for a spawned agent."""

    agent_type: str
    task: str
    context: dict[str, Any] = field(default_factory=dict)
    isolation: IsolationLevel | None = None
    max_iterations: int = 10
    timeout_seconds: int = 3600
    memory_limit_mb: int = 512
    cpu_limit_percent: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInstance:
    """Represents a spawned agent instance."""

    agent_id: str
    config: AgentConfig
    status: AgentStatus = AgentStatus.INITIALIZING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: Any | None = None
    iterations: int = 0
    task_id: str | None = None


class AgentSpawner:
    """
    Manages spawning and lifecycle of sub-agents.

    Handles agent creation, execution, monitoring, and termination.
    """

    def __init__(self, max_concurrent_agents: int = 10):
        """
        Initialize the agent spawner.

        Args:
            max_concurrent_agents: Maximum number of concurrent agents
        """
        self.max_concurrent_agents = max_concurrent_agents
        self.agents: dict[str, AgentInstance] = {}
        self.agent_tasks: dict[str, asyncio.Task] = {}
        self.logger = logger
        # 并发上限检查与实例登记必须原子化，避免竞态下超额创建（B2）。
        self._spawn_lock = asyncio.Lock()

    async def spawn_agent(
        self,
        agent_type: str,
        task: str,
        context: dict[str, Any],
        isolation: str | None = None,
        **kwargs,
    ) -> str:
        """
        Spawn a new sub-agent.

        Args:
            agent_type: Type of agent to spawn
            task: Task for the agent to execute
            context: Context data for the agent
            isolation: Isolation level (none, process, container)
            **kwargs: Additional configuration options

        Returns:
            Agent ID

        Raises:
            RuntimeError: If max concurrent agents reached
        """
        # Check concurrent limit + create instance atomically (B2: 原子化避免竞态超额)
        async with self._spawn_lock:
            active_agents = sum(
                1 for a in self.agents.values()
                if a.status in (AgentStatus.INITIALIZING, AgentStatus.READY, AgentStatus.RUNNING)
            )
            if active_agents >= self.max_concurrent_agents:
                raise RuntimeError(
                    f"Max concurrent agents ({self.max_concurrent_agents}) reached"
                )

            # Create agent instance
            agent_id = f"agent_{uuid.uuid4().hex[:12]}"
            isolation_level = _normalize_isolation(isolation)

            # Honest limits: recorded but not OS-enforced (see module docstring).
            if kwargs.get("memory_limit_mb") not in (None, 512) or kwargs.get("cpu_limit_percent") not in (None, 100):
                self.logger.warning(
                    "Spawn %s requested memory_limit_mb=%s cpu_limit_percent=%s: "
                    "resource limits are declarative only and NOT enforced.",
                    agent_id,
                    kwargs.get("memory_limit_mb"),
                    kwargs.get("cpu_limit_percent"),
                )

            config = AgentConfig(
                agent_type=agent_type,
                task=task,
                context=context,
                isolation=isolation_level,
                max_iterations=kwargs.get("max_iterations", 10),
                timeout_seconds=kwargs.get("timeout_seconds", 3600),
                memory_limit_mb=kwargs.get("memory_limit_mb", 512),
                cpu_limit_percent=kwargs.get("cpu_limit_percent", 100),
                metadata=kwargs.get("metadata", {}),
            )

            agent = AgentInstance(agent_id=agent_id, config=config)
            self.agents[agent_id] = agent

        self.logger.info(
            f"Spawned agent {agent_id} (type={agent_type}, isolation={isolation_level})"
        )

        # Create execution task
        task_obj = asyncio.create_task(self._execute_agent(agent_id))
        self.agent_tasks[agent_id] = task_obj

        return agent_id

    async def _execute_agent(self, agent_id: str) -> None:
        """
        Execute an agent using the real AgentLoop engine.

        Builds an AgentLoop via the same factory the production /agents path
        uses (backend.app.dependencies.get_agent), constructs a RunContext, and
        runs the configured task under the agent's timeout.

        Args:
            agent_id: ID of agent to execute
        """
        agent = self.agents[agent_id]

        try:
            agent.status = AgentStatus.READY
            agent.started_at = datetime.now(UTC)
            agent.status = AgentStatus.RUNNING

            if agent.config.isolation == IsolationLevel.PROCESS:
                await self._execute_agent_in_process(agent)
                return

            # Build the real agent engine + run context (惰性导入避免循环依赖)。
            from backend.app.core.contracts import RunContext
            from backend.app.dependencies import get_agent

            agent_loop = get_agent()
            agent_loop.max_iterations = agent.config.max_iterations

            ctx_data = agent.config.context or {}
            context = RunContext(
                tenant_id=str(ctx_data.get("tenant_id", "default")),
                user_id=str(ctx_data.get("user_id", "system")),
                agent_id=agent_id,
                request_id=str(ctx_data.get("request_id", agent_id)),
                trace_id=str(ctx_data.get("trace_id", agent_id)),
                permission_scope=list(ctx_data.get("permission_scope", []) or []),
            )

            # Enforce the configured timeout on real execution.
            timeout = agent.config.timeout_seconds
            response = await asyncio.wait_for(
                agent_loop.run(context, agent.config.task, ctx_data),
                timeout=timeout,
            )

            agent.iterations = getattr(response, "iterations", 0) or 0
            status_value = getattr(getattr(response, "status", None), "value", None) or str(
                getattr(response, "status", "completed")
            )
            failed = status_value.lower() == "failed"
            agent.status = AgentStatus.FAILED if failed else AgentStatus.COMPLETED
            agent.completed_at = datetime.now(UTC)
            agent.result = {
                "status": status_value,
                "answer": getattr(response, "answer", ""),
                "iterations": agent.iterations,
                "trace_id": getattr(response, "trace_id", context.trace_id),
                "memory_hits": getattr(response, "memory_hits", 0),
            }
            if failed:
                agent.error = getattr(response, "error", None) or "agent run failed"
                self.logger.error(f"Agent {agent_id} failed: {agent.error}")
            else:
                self.logger.info(f"Agent {agent_id} completed successfully")

        except TimeoutError:
            agent.status = AgentStatus.FAILED
            agent.error = "Execution timeout"
            agent.completed_at = datetime.now(UTC)
            self.logger.error(f"Agent {agent_id} timed out")

        except Exception as e:
            agent.status = AgentStatus.FAILED
            agent.error = str(e)
            agent.completed_at = datetime.now(UTC)
            self.logger.error(f"Agent {agent_id} failed: {e}")

    async def _execute_agent_in_process(self, agent: AgentInstance) -> None:
        """Execute an agent in a real OS child process (IsolationLevel.PROCESS).

        A fresh ``multiprocessing`` spawn-context child rebuilds the AgentLoop
        from application settings and runs the task; the result is returned
        over a queue. The configured ``timeout_seconds`` is enforced on the
        parent side: an overdue child is terminated and reported as a timeout,
        mirroring the in-process path.

        Args:
            agent: Agent instance whose config drives the child run.

        Raises:
            asyncio.TimeoutError: If the child exceeds the configured timeout.
            RuntimeError: If the child dies without reporting a result, or the
                reported run failed at the engine level is NOT raised here —
                engine-level failures are recorded on the agent like the
                in-process path; infrastructure failures raise.
        """
        timeout = agent.config.timeout_seconds
        payload = {
            "agent_id": agent.agent_id,
            "agent_type": agent.config.agent_type,
            "task": agent.config.task,
            "context": agent.config.context or {},
            "max_iterations": agent.config.max_iterations,
        }
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        process = ctx.Process(
            target=_process_worker_entry,
            args=(payload, result_queue),
            name=f"xagent-{agent.agent_id}",
            daemon=True,
        )
        loop = asyncio.get_running_loop()
        process.start()
        self.logger.info(
            "Agent %s running in child process pid=%s", agent.agent_id, process.pid
        )
        try:
            message = await asyncio.wait_for(
                loop.run_in_executor(None, _blocking_queue_get, result_queue, timeout),
                timeout=timeout + 5,
            )
        except (TimeoutError, queue_module.Empty) as exc:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            raise TimeoutError(
                f"Process-isolated agent {agent.agent_id} exceeded timeout of {timeout}s"
            ) from exc
        finally:
            if process.is_alive():
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
            result_queue.close()

        agent.iterations = int(message.get("iterations") or 0)
        status_value = str(message.get("status") or "completed")
        failed = not message.get("ok", False) or status_value.lower() == "failed"
        agent.status = AgentStatus.FAILED if failed else AgentStatus.COMPLETED
        agent.completed_at = datetime.now(UTC)
        agent.result = {
            "status": status_value,
            "answer": message.get("answer", ""),
            "iterations": agent.iterations,
            "trace_id": message.get("trace_id"),
            "memory_hits": message.get("memory_hits", 0),
            "isolation": IsolationLevel.PROCESS.value,
            "child_pid": message.get("child_pid"),
        }
        if failed:
            agent.error = message.get("error") or "agent run failed in child process"
            self.logger.error("Agent %s failed in child process: %s", agent.agent_id, agent.error)
        else:
            self.logger.info("Agent %s completed in child process", agent.agent_id)

    async def terminate_agent(self, agent_id: str) -> bool:
        """
        Terminate a running agent.

        Args:
            agent_id: ID of agent to terminate

        Returns:
            True if terminated, False if not found
        """
        if agent_id not in self.agents:
            self.logger.warning(f"Agent {agent_id} not found")
            return False

        agent = self.agents[agent_id]

        # Cancel the task
        if agent_id in self.agent_tasks:
            task = self.agent_tasks[agent_id]
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        agent.status = AgentStatus.TERMINATED
        agent.completed_at = datetime.now(UTC)

        self.logger.info(f"Agent {agent_id} terminated")
        return True

    async def get_agent_status(self, agent_id: str) -> dict[str, Any] | None:
        """
        Get the status of an agent.

        Args:
            agent_id: ID of agent

        Returns:
            Agent status dict or None if not found
        """
        if agent_id not in self.agents:
            return None

        agent = self.agents[agent_id]

        return {
            "agent_id": agent_id,
            "status": agent.status.value,
            "agent_type": agent.config.agent_type,
            "task": agent.config.task,
            "isolation": (agent.config.isolation or IsolationLevel.NONE).value,
            "resource_limits_enforced": False,
            "created_at": agent.created_at.isoformat(),
            "started_at": agent.started_at.isoformat() if agent.started_at else None,
            "completed_at": agent.completed_at.isoformat() if agent.completed_at else None,
            "iterations": agent.iterations,
            "error": agent.error,
            "result": agent.result,
        }

    async def list_agents(
        self,
        status: str | None = None,
        agent_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List agents with optional filtering.

        Args:
            status: Filter by status
            agent_type: Filter by agent type

        Returns:
            List of agent status dicts
        """
        agents = []

        for agent_id, agent in self.agents.items():
            if status and agent.status.value != status:
                continue
            if agent_type and agent.config.agent_type != agent_type:
                continue

            agents.append(
                {
                    "agent_id": agent_id,
                    "status": agent.status.value,
                    "agent_type": agent.config.agent_type,
                    "task": agent.config.task,
                    "created_at": agent.created_at.isoformat(),
                }
            )

        return agents

    async def wait_for_agent(
        self,
        agent_id: str,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Wait for an agent to complete.

        Args:
            agent_id: ID of agent to wait for
            timeout_seconds: Timeout in seconds

        Returns:
            Agent status dict or None if timeout
        """
        if agent_id not in self.agent_tasks:
            return None

        try:
            await asyncio.wait_for(
                self.agent_tasks[agent_id],
                timeout=timeout_seconds,
            )
        except TimeoutError:
            self.logger.warning(f"Timeout waiting for agent {agent_id}")
            return None

        return await self.get_agent_status(agent_id)

    def get_agent_count(self, status: str | None = None) -> int:
        """
        Get count of agents.

        Args:
            status: Filter by status

        Returns:
            Count of agents
        """
        if not status:
            return len(self.agents)

        return sum(
            1 for a in self.agents.values()
            if a.status.value == status
        )

    async def cleanup_completed_agents(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up completed agents older than max_age.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of agents cleaned up
        """
        now = datetime.now(UTC)
        cleaned = 0

        agent_ids_to_remove = []
        for agent_id, agent in self.agents.items():
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.TERMINATED):
                if agent.completed_at:
                    age = (now - agent.completed_at).total_seconds()
                    if age > max_age_seconds:
                        agent_ids_to_remove.append(agent_id)

        for agent_id in agent_ids_to_remove:
            del self.agents[agent_id]
            if agent_id in self.agent_tasks:
                del self.agent_tasks[agent_id]
            cleaned += 1

        self.logger.info(f"Cleaned up {cleaned} completed agents")
        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """
        Get spawner statistics.

        Returns:
            Statistics dict
        """
        statuses = {}
        for agent in self.agents.values():
            status = agent.status.value
            statuses[status] = statuses.get(status, 0) + 1

        return {
            "total_agents": len(self.agents),
            "active_agents": sum(
                1 for a in self.agents.values()
                if a.status in (AgentStatus.INITIALIZING, AgentStatus.READY, AgentStatus.RUNNING)
            ),
            "status_breakdown": statuses,
            "max_concurrent": self.max_concurrent_agents,
        }


def _blocking_queue_get(result_queue, timeout: float) -> dict:
    """Blocking ``queue.get`` wrapper executed in an executor thread.

    Using a bounded get (instead of an unbounded one) lets the helper thread
    exit on its own when the parent gives up, instead of leaking forever.
    ``queue.Empty`` propagates and is converted to a timeout by the caller.
    """
    return result_queue.get(timeout=max(1.0, float(timeout)))


def _process_worker_entry(config_payload: dict, result_queue) -> None:
    """Child-process entry point for ``IsolationLevel.PROCESS`` execution.

    This function MUST stay module-level and import-safe: under the spawn
    start method the child interpreter re-imports this module and resolves the
    target by qualified name, so closures/lambdas cannot be used.

    The child builds a real AgentLoop through the standard application factory
    (settings-driven; e.g. ``XAGENT_LLM_BACKEND=mock`` is inherited via the
    environment, which makes deterministic offline runs possible), executes
    the task with ``asyncio.run`` and always reports a result dict — the child
    must never die silently.

    Args:
        config_payload: Picklable dict with agent_id/agent_type/task/context/
            max_iterations.
        result_queue: ``multiprocessing.Queue`` for the single result message.
    """
    import os

    message: dict = {"ok": False, "child_pid": os.getpid()}
    try:
        import asyncio as _asyncio

        from backend.app.core.contracts import RunContext
        from backend.app.dependencies import get_agent

        agent_loop = get_agent()
        agent_loop.max_iterations = int(config_payload.get("max_iterations", 10))

        agent_id = str(config_payload.get("agent_id") or "process-agent")
        ctx_data = config_payload.get("context") or {}
        run_context = RunContext(
            tenant_id=str(ctx_data.get("tenant_id", "default")),
            user_id=str(ctx_data.get("user_id", "system")),
            agent_id=agent_id,
            request_id=str(ctx_data.get("request_id", agent_id)),
            trace_id=str(ctx_data.get("trace_id", agent_id)),
            permission_scope=list(ctx_data.get("permission_scope", []) or []),
        )

        response = _asyncio.run(
            agent_loop.run(run_context, str(config_payload.get("task") or ""), ctx_data)
        )
        status_value = getattr(getattr(response, "status", None), "value", None) or str(
            getattr(response, "status", "completed")
        )
        message.update(
            {
                "ok": status_value.lower() != "failed",
                "status": status_value,
                "answer": getattr(response, "answer", ""),
                "iterations": getattr(response, "iterations", 0) or 0,
                "trace_id": getattr(response, "trace_id", run_context.trace_id),
                "memory_hits": getattr(response, "memory_hits", 0),
            }
        )
        if status_value.lower() == "failed":
            message["error"] = getattr(response, "error", None) or "agent run failed"
    except Exception as exc:
        message["error"] = f"{type(exc).__name__}: {exc}"
    with contextlib.suppress(Exception):
        result_queue.put(message)


# Global instance
agent_spawner = AgentSpawner()
