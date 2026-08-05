"""Real parallel agent execution with asyncio.gather (对标 Codex subagents / Hermes fan-out).

P1-09 convergence: This is the CANONICAL parallel agent executor, used by
``api/parallel_agents.py``. The older ``core/parallel_execution_engine.py``
is DEPRECATED and retained only for benchmark backward compat.

For structured orchestration (decompose + dependencies), see
``core/collaboration/orchestrator.py`` (MultiAgentOrchestrator).
For shared-context collaboration rooms, see ``core/collaboration/``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class IsolationMode(StrEnum):
    """Agent isolation mode for parallel execution.

    P1-09 批次 B 裁决（2026-08-04，诚实语义）：本执行器在**同进程**内
    fan-out，不执行任何 OS 级隔离。接受的模式仅为同进程语义：

    - ``SHARED``：共享内存与工具（默认）；
    - ``ISOLATED``：独立上下文语义——由 agent_factory 兑现，执行器透传；
    - ``THREAD``：``SHARED`` 的别名（历史默认值，保留兼容）。

    ``SANDBOXED`` / ``PROCESS`` 在本执行器是装饰参数（曾被注释为互为别名
    而实际均为同进程），现在**显式拒绝**（NotImplementedError）：真实
    PROCESS 隔离请走 ``core/agent_spawner.py``（已实现子进程执行），
    CONTAINER 隔离走 core/sandbox 沙箱路径。
    """
    SHARED = "shared"  # Shared memory and tools
    ISOLATED = "isolated"  # Independent context per agent (factory-honored)
    SANDBOXED = "sandboxed"  # 不支持：显式拒绝，见 spawn_agents
    THREAD = "thread"  # Alias for shared (same-process)
    PROCESS = "process"  # 不支持：真实进程隔离请用 agent_spawner


#: 本执行器实际接受的同进程模式（其余显式拒绝，杜绝装饰参数）。
SUPPORTED_ISOLATION_MODES = frozenset({IsolationMode.SHARED, IsolationMode.ISOLATED, IsolationMode.THREAD})


class AgentTaskStatus(StrEnum):
    """Status of a parallel agent task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class AgentFactoryNotConfiguredError(RuntimeError):
    """Raised when agent factory is not configured but required."""
    pass


@dataclass
class AgentTask:
    """A task to be executed by a parallel agent."""
    id: str = field(default_factory=lambda: str(uuid4()))
    # New API fields
    goal: str = ""
    description: str = ""
    timeout_seconds: float = 300.0
    # D1 wiring fields (consumed by api/parallel_agents.py TaskRequest)
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    # Legacy API fields (kept for backward compat)
    instruction: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout: float = 300.0

    def __post_init__(self):
        # Normalize: goal takes precedence over instruction
        if self.goal and not self.instruction:
            self.instruction = self.goal
        if self.instruction and not self.goal:
            self.goal = self.instruction
        # Normalize timeout
        if self.timeout_seconds != 300.0:
            self.timeout = self.timeout_seconds
        elif self.timeout != 300.0:
            self.timeout_seconds = self.timeout


@dataclass
class AgentTaskResult:
    """Result from a parallel agent task."""
    task_id: str = ""
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    output: str = ""
    error: str | None = None
    duration: float = 0.0
    tool_calls_count: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    # D1 wiring fields (consumed by api/parallel_agents.py TaskResultResponse)
    agent_id: str = ""
    retry_attempts: int = 0

    @property
    def duration_seconds(self) -> float:
        """Alias for ``duration`` matching the API response contract."""
        return self.duration

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": str(self.status),
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "duration_seconds": self.duration,
            "retry_attempts": self.retry_attempts,
            "tool_calls_count": self.tool_calls_count,
            "result": self.result,
        }


@dataclass
class SpawnResult:
    """Result from spawn_agents batch execution."""
    batch_id: str = ""
    total_tasks: int = 0
    results: list[AgentTaskResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def _count(self, *statuses: AgentTaskStatus) -> int:
        return sum(1 for r in self.results if r.status in statuses)

    @property
    def completed_tasks(self) -> int:
        return self._count(AgentTaskStatus.COMPLETED)

    @property
    def failed_tasks(self) -> int:
        return self._count(AgentTaskStatus.FAILED)

    @property
    def cancelled_tasks(self) -> int:
        return self._count(AgentTaskStatus.CANCELLED)

    @property
    def timeout_tasks(self) -> int:
        return self._count(AgentTaskStatus.TIMEOUT)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "batch_id": self.batch_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "cancelled_tasks": self.cancelled_tasks,
            "timeout_tasks": self.timeout_tasks,
            "results": [r.to_dict() for r in self.results],
            "total_duration_seconds": self.total_duration_seconds,
            "metadata": self.metadata,
        }


class ParallelAgentExecutor:
    """Real parallel agent execution with asyncio.gather.

    Supports:
    - Configurable max concurrency via semaphore
    - Per-task timeout
    - Shared memory across agents
    - Independent AgentLoop instances per task
    - spawn_agents API for batch execution with agent_factory
    """

    def __init__(
        self,
        llm_router=None,
        memory=None,
        tools=None,
        max_concurrency: int = 4,
        max_workers: int | None = None,  # alias for backward compat
    ):
        self.llm_router = llm_router
        self.memory = memory
        self.tools = tools
        self.max_concurrency = max_workers or max_concurrency
        self._active_tasks: dict[str, AgentTaskResult] = {}
        self._batches: dict[str, SpawnResult] = {}

    async def spawn_agents(
        self,
        tasks: list[AgentTask],
        isolation: IsolationMode = IsolationMode.SHARED,
        max_parallel: int | None = None,
        agent_factory: Callable[[str, IsolationMode], Any] | None = None,
    ) -> SpawnResult:
        """Spawn multiple agents to execute tasks in parallel.

        Args:
            tasks: List of tasks to execute
            isolation: Isolation mode for agents
            max_parallel: Maximum parallel agents (defaults to max_concurrency)
            agent_factory: Factory function (agent_id, isolation) -> agent with async execute(task)

        Returns:
            SpawnResult with batch_id, results, and metadata

        Raises:
            ValueError: If tasks is empty or isolation mode is invalid
            AgentFactoryNotConfiguredError: If agent_factory is not provided
        """
        # Validate inputs
        if not tasks:
            raise ValueError("tasks list cannot be empty")

        # Validate isolation mode
        valid_modes = {m.value for m in IsolationMode}
        isolation_value = isolation.value if isinstance(isolation, IsolationMode) else str(isolation)
        if isolation_value not in valid_modes:
            raise ValueError(f"Invalid isolation mode: {isolation}. Valid modes: {valid_modes}")
        mode = IsolationMode(isolation_value)
        if mode not in SUPPORTED_ISOLATION_MODES:
            raise NotImplementedError(
                f"Isolation mode '{mode.value}' is not implemented by the parallel "
                "executor (same-process fan-out only). Use 'shared'/'isolated' here, "
                "backend.app.core.agent_spawner for real PROCESS isolation, or "
                "core/sandbox for CONTAINER isolation."
            )

        if agent_factory is None:
            raise AgentFactoryNotConfiguredError(
                "agent_factory is required for spawn_agents. "
                "Provide a callable(agent_id, isolation) -> agent."
            )

        batch_id = str(uuid4())
        concurrency = max_parallel or self.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        start_time = time.time()

        async def run_one(task: AgentTask) -> AgentTaskResult:
            async with semaphore:
                agent_id = f"agent-{task.id[:8]}"
                agent = agent_factory(agent_id, isolation)
                result = AgentTaskResult(
                    task_id=task.id,
                    agent_id=agent_id,
                    status=AgentTaskStatus.RUNNING,
                )
                task_start = time.time()
                try:
                    attempts = 1 + max(0, task.max_retries)
                    for attempt in range(attempts):
                        try:
                            output = await asyncio.wait_for(
                                agent.execute(task),
                                timeout=task.timeout_seconds,
                            )
                            result.status = AgentTaskStatus.COMPLETED
                            result.result = output if isinstance(output, dict) else {"output": output}
                            result.output = str(output)
                            break
                        except TimeoutError:
                            # Timeout is not retried: the agent already had its full budget.
                            result.status = AgentTaskStatus.TIMEOUT
                            result.error = f"Task timed out after {task.timeout_seconds}s"
                            break
                        except Exception as e:
                            result.retry_attempts = attempt
                            if attempt >= attempts - 1:
                                result.status = AgentTaskStatus.FAILED
                                result.error = str(e)
                            else:
                                logger.warning(
                                    f"Task {task.id} attempt {attempt + 1} failed, retrying: {e}"
                                )
                finally:
                    result.duration = time.time() - task_start
                return result

        results = await asyncio.gather(
            *[run_one(task) for task in tasks],
            return_exceptions=True,
        )

        final_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(AgentTaskResult(
                    task_id=tasks[i].id,
                    status=AgentTaskStatus.FAILED,
                    error=str(r),
                ))
            else:
                final_results.append(r)

        spawn_result = SpawnResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            results=final_results,
            total_duration_seconds=time.time() - start_time,
            metadata={
                "isolation_mode": isolation.value,
                "max_parallel": concurrency,
            },
        )
        self._batches[batch_id] = spawn_result
        return spawn_result

    async def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """Get status of a batch execution.

        Raises:
            ValueError: If the batch ID is unknown (API maps this to HTTP 404).
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Batch not found: {batch_id}")
        completed = sum(
            1 for r in batch.results
            if r.status in (AgentTaskStatus.COMPLETED, AgentTaskStatus.FAILED, AgentTaskStatus.TIMEOUT)
        )
        return {
            "batch_id": batch_id,
            "total_tasks": batch.total_tasks,
            "completed_tasks": completed,
            # Alias matching the API BatchStatusResponse contract.
            "completed_results": completed,
            "is_active": completed < batch.total_tasks,
            "status": "completed" if completed >= batch.total_tasks else "running",
        }

    async def get_batch_results(self, batch_id: str) -> list[AgentTaskResult]:
        """Get results of a batch execution.

        Raises:
            ValueError: If the batch ID is unknown (API maps this to HTTP 404).
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            raise ValueError(f"Batch not found: {batch_id}")
        return batch.results

    async def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch execution (best-effort).

        Returns:
            True if batch was found and cancellation was attempted, False otherwise.
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            return False
        # Mark pending tasks as cancelled
        for result in batch.results:
            if result.status == AgentTaskStatus.PENDING:
                result.status = AgentTaskStatus.CANCELLED
        return True

    async def execute_parallel(
        self,
        tasks: list[AgentTask],
        max_concurrency: int | None = None,
    ) -> list[AgentTaskResult]:
        """Execute multiple agent tasks in parallel (legacy API)."""
        concurrency = max_concurrency or self.max_concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(task: AgentTask) -> AgentTaskResult:
            async with semaphore:
                return await self._execute_single(task)

        results = await asyncio.gather(
            *[run_one(task) for task in tasks],
            return_exceptions=True,
        )

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(AgentTaskResult(
                    task_id=tasks[i].id,
                    status=AgentTaskStatus.FAILED,
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    async def _execute_single(self, task: AgentTask) -> AgentTaskResult:
        """Execute a single agent task with timeout."""
        result = AgentTaskResult(task_id=task.id, status=AgentTaskStatus.RUNNING)
        self._active_tasks[task.id] = result
        start_time = time.time()

        try:
            from backend.app.core.agent.loop import AgentLoop

            loop = AgentLoop(
                llm_router=self.llm_router,
                memory=self.memory,
                tools=self.tools,
            )

            run_result = await asyncio.wait_for(
                loop.run(context=task.context, task=task.instruction),
                timeout=task.timeout,
            )

            result.status = AgentTaskStatus.COMPLETED
            result.output = run_result.output if hasattr(run_result, "output") else str(run_result)
            result.tool_calls_count = len(getattr(run_result, "tool_calls", []))

        except TimeoutError:
            result.status = AgentTaskStatus.TIMEOUT
            result.error = f"Task timed out after {task.timeout}s"
            logger.warning(f"Task {task.id} timed out")

        except Exception as e:
            result.status = AgentTaskStatus.FAILED
            result.error = str(e)
            logger.error(f"Task {task.id} failed: {e}")

        finally:
            result.duration = time.time() - start_time
            self._active_tasks.pop(task.id, None)

        return result

    def get_active_tasks(self) -> dict[str, AgentTaskResult]:
        """Get currently active tasks."""
        return dict(self._active_tasks)

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "max_concurrency": self.max_concurrency,
            "active_tasks": len(self._active_tasks),
            "total_batches": len(self._batches),
        }


# ---------------------------------------------------------------------------
# P1-08: ParallelAgentOrchestrator — high-level fan-out / fan-in / pipeline
# ---------------------------------------------------------------------------


@dataclass
class ParallelConfig:
    """Configuration for parallel agent orchestration."""

    max_parallel: int = 5
    timeout_seconds: int = 300
    aggregation_strategy: str = "merge"  # "first_success" | "majority_vote" | "merge"
    token_budget: int = 100_000
    retry_on_failure: bool = False
    max_retries: int = 2


@dataclass
class AgentResult:
    """Result from a single sub-agent execution."""

    agent_id: str = ""
    status: str = "pending"  # pending | completed | failed | timeout
    output: str = ""
    error: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class ParallelAgentOrchestrator:
    """High-level orchestrator for parallel agent patterns.

    Supports three execution patterns:
    - Fan-out: distribute subtasks to independent agents in parallel
    - Fan-in: aggregate results from parallel agents
    - Pipeline: execute stages sequentially, feeding output to next stage

    Each sub-agent gets an independent context and LLM session.
    Resource controls: max parallel count, token budget, timeout.
    """

    def __init__(
        self,
        llm_router: Any | None = None,
        memory: Any | None = None,
        tools: Any | None = None,
    ) -> None:
        self.llm_router = llm_router
        self.memory = memory
        self.tools = tools
        self._execution_log: list[dict[str, Any]] = []

    async def execute_fan_out(
        self,
        task: str,
        subtasks: list[str],
        config: ParallelConfig | None = None,
    ) -> list[AgentResult]:
        """Fan-out: execute multiple subtasks in parallel with independent agents.

        Args:
            task: The parent task description (for context).
            subtasks: List of subtask instructions to execute in parallel.
            config: Parallel execution configuration.

        Returns:
            List of AgentResult, one per subtask.
        """
        cfg = config or ParallelConfig()
        semaphore = asyncio.Semaphore(cfg.max_parallel)

        async def _run_subtask(index: int, subtask: str) -> AgentResult:
            agent_id = f"fan-out-{index}-{uuid4().hex[:6]}"
            async with semaphore:
                start = time.time()
                result = AgentResult(agent_id=agent_id, status="running")
                try:
                    output = await asyncio.wait_for(
                        self._execute_agent(subtask, task_context=task),
                        timeout=cfg.timeout_seconds,
                    )
                    result.status = "completed"
                    result.output = output
                except TimeoutError:
                    result.status = "timeout"
                    result.error = f"Subtask timed out after {cfg.timeout_seconds}s"
                    logger.warning(f"Fan-out agent {agent_id} timed out")
                except Exception as exc:
                    result.status = "failed"
                    result.error = str(exc)
                    logger.error(f"Fan-out agent {agent_id} failed: {exc}")
                finally:
                    result.duration_ms = (time.time() - start) * 1000
                return result

        results = await asyncio.gather(
            *[_run_subtask(i, st) for i, st in enumerate(subtasks)],
            return_exceptions=True,
        )

        final_results: list[AgentResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(AgentResult(
                    agent_id=f"fan-out-{i}-error",
                    status="failed",
                    error=str(r),
                ))
            else:
                final_results.append(r)

        self._execution_log.append({
            "pattern": "fan_out",
            "task": task,
            "subtask_count": len(subtasks),
            "results": [r.to_dict() for r in final_results],
            "timestamp": time.time(),
        })
        return final_results

    async def execute_fan_in(
        self,
        results: list[AgentResult],
        aggregation: str = "merge",
    ) -> AgentResult:
        """Fan-in: aggregate results from parallel agents.

        Args:
            results: List of AgentResult from fan-out execution.
            aggregation: Aggregation strategy - "first_success", "majority_vote", "merge".

        Returns:
            A single aggregated AgentResult.
        """
        start = time.time()
        agent_id = f"fan-in-{uuid4().hex[:6]}"

        successful = [r for r in results if r.status == "completed"]

        if not successful:
            return AgentResult(
                agent_id=agent_id,
                status="failed",
                error="No successful results to aggregate",
                duration_ms=(time.time() - start) * 1000,
            )

        try:
            if aggregation == "first_success":
                output = successful[0].output
            elif aggregation == "majority_vote":
                output = self._majority_vote(successful)
            else:  # "merge"
                output = await self._merge_results(successful)

            return AgentResult(
                agent_id=agent_id,
                status="completed",
                output=output,
                duration_ms=(time.time() - start) * 1000,
                metadata={"aggregation": aggregation, "input_count": len(results)},
            )
        except Exception as exc:
            logger.error(f"Fan-in aggregation failed: {exc}")
            return AgentResult(
                agent_id=agent_id,
                status="failed",
                error=str(exc),
                duration_ms=(time.time() - start) * 1000,
            )

    async def execute_pipeline(
        self,
        stages: list[str],
        config: ParallelConfig | None = None,
    ) -> AgentResult:
        """Pipeline: execute stages sequentially, feeding output to next stage.

        Args:
            stages: List of stage instructions to execute in order.
            config: Parallel execution configuration (timeout applies per stage).

        Returns:
            Final AgentResult from the last pipeline stage.
        """
        cfg = config or ParallelConfig()
        pipeline_id = f"pipeline-{uuid4().hex[:6]}"
        start = time.time()
        accumulated_output = ""

        for i, stage in enumerate(stages):
            stage_start = time.time()
            stage_input = f"{stage}\n\nPrevious stage output:\n{accumulated_output}" if accumulated_output else stage

            try:
                output = await asyncio.wait_for(
                    self._execute_agent(stage_input, task_context=f"Pipeline stage {i+1}/{len(stages)}"),
                    timeout=cfg.timeout_seconds,
                )
                accumulated_output = output
                logger.info(f"Pipeline {pipeline_id} stage {i+1} completed in {(time.time()-stage_start)*1000:.0f}ms")
            except TimeoutError:
                return AgentResult(
                    agent_id=pipeline_id,
                    status="timeout",
                    error=f"Pipeline stage {i+1} timed out after {cfg.timeout_seconds}s",
                    output=accumulated_output,
                    duration_ms=(time.time() - start) * 1000,
                )
            except Exception as exc:
                return AgentResult(
                    agent_id=pipeline_id,
                    status="failed",
                    error=f"Pipeline stage {i+1} failed: {exc}",
                    output=accumulated_output,
                    duration_ms=(time.time() - start) * 1000,
                )

        self._execution_log.append({
            "pattern": "pipeline",
            "stages": len(stages),
            "timestamp": time.time(),
        })

        return AgentResult(
            agent_id=pipeline_id,
            status="completed",
            output=accumulated_output,
            duration_ms=(time.time() - start) * 1000,
            metadata={"stages_completed": len(stages)},
        )

    # ─── Internal helpers ─────────────────────────────────────────────────────

    async def _execute_agent(self, instruction: str, task_context: str = "") -> str:
        """Execute a single agent with independent context and LLM session.

        Uses the project's AgentLoop when available, falls back to direct LLM call.
        """
        # Try AgentLoop-based execution first
        try:
            from backend.app.core.agent.loop import AgentLoop

            loop = AgentLoop(
                llm_router=self.llm_router,
                memory=self.memory,
                tools=self.tools,
            )
            context = {"task_context": task_context} if task_context else {}
            run_result = await loop.run(context=context, task=instruction)
            return run_result.output if hasattr(run_result, "output") else str(run_result)
        except ImportError:
            pass
        except Exception as exc:
            logger.debug(f"AgentLoop execution failed, falling back to LLM: {exc}")

        # Fallback: direct LLM call
        if self.llm_router:
            messages = []
            if task_context:
                messages.append({"role": "system", "content": f"Context: {task_context}"})
            messages.append({"role": "user", "content": instruction})
            response = await self.llm_router.chat(messages, tools=[])
            return response.content if hasattr(response, "content") else str(response)

        raise RuntimeError("No LLM router or AgentLoop available for agent execution")

    def _majority_vote(self, results: list[AgentResult]) -> str:
        """Select the most common output via majority vote."""
        from collections import Counter

        outputs = [r.output.strip() for r in results if r.output.strip()]
        if not outputs:
            return ""
        counter = Counter(outputs)
        return counter.most_common(1)[0][0]

    async def _merge_results(self, results: list[AgentResult]) -> str:
        """Merge multiple outputs using LLM synthesis or concatenation."""
        outputs = [r.output for r in results if r.output]
        if not outputs:
            return ""
        if len(outputs) == 1:
            return outputs[0]

        # Try LLM-based synthesis
        if self.llm_router:
            try:
                combined = "\n---\n".join(f"Agent {i+1} output:\n{o}" for i, o in enumerate(outputs))
                prompt = (
                    "Synthesize the following parallel agent outputs into a single "
                    "coherent, comprehensive result. Remove duplicates and resolve "
                    f"any conflicts:\n\n{combined[:8000]}"
                )
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_router.chat(messages, tools=[])
                return response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning(f"LLM merge failed, falling back to concat: {exc}")

        # Fallback: simple concatenation
        return "\n\n---\n\n".join(outputs)

    def get_execution_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent execution log entries."""
        return self._execution_log[-limit:]


# Global singletons
parallel_executor = ParallelAgentExecutor()
parallel_orchestrator = ParallelAgentOrchestrator()
