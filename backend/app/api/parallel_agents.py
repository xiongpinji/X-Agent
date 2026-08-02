"""
Parallel Agents API - REST endpoints for parallel agent execution.

Endpoints:
- POST /api/v1/agents/parallel/spawn - Start parallel agents
- GET /api/v1/agents/parallel/{batch_id}/status - Get batch status
- GET /api/v1/agents/parallel/{batch_id}/results - Get batch results
- POST /api/v1/agents/parallel/{batch_id}/cancel - Cancel batch

P1-09 Collaboration Module Convergence
---------------------------------------
This is ONE of three distinct multi-agent API surfaces (NOT duplicates):

- collaboration  /api/v1/collaboration
    Shared-context rooms, messaging, delegation.
- multi_agent  /api/v1/multi-agent
    Structured orchestration (decompose -> execute with dependencies).
- parallel_agents (THIS)  /api/v1/agents/parallel
    Independent fan-out execution + communication bus.

Cross-references:
    - backend.app.api.collaboration (collaboration rooms API)
    - backend.app.api.multi_agent (orchestration API, P2-01)
    - backend.app.core.parallel_agent_executor (core executor)

NOTE: backend.app.core.parallel_execution_engine is DEPRECATED;
    use backend.app.core.parallel_agent_executor instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.agent_communication_bus import (
    AgentCommunicationBus,
    MessagePriority,
)
from backend.app.core.contracts import RunContext
from backend.app.core.parallel_agent_executor import (
    AgentFactoryNotConfiguredError,
    AgentResult,
    AgentTask,
    IsolationMode,
    ParallelAgentExecutor,
    ParallelAgentOrchestrator,
    ParallelConfig,
)
from backend.app.core.result_aggregator import (
    AggregationConfig,
    ConflictResolution,
    MergeStrategy,
    ResultAggregator,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/parallel", tags=["parallel_agents"])
extended_router = APIRouter(prefix="/api/v1/agents/parallel", tags=["parallel-extended"])  # C2: unmounted; handler bodies unchanged
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global instances
_executor: ParallelAgentExecutor | None = None
_orchestrator: ParallelAgentOrchestrator | None = None
_bus: AgentCommunicationBus | None = None
_aggregator: ResultAggregator | None = None


def get_executor() -> ParallelAgentExecutor:
    """Get or create the parallel agent executor."""
    global _executor
    if _executor is None:
        _executor = ParallelAgentExecutor(max_workers=3)
    return _executor


def get_orchestrator() -> ParallelAgentOrchestrator:
    """Get or create the parallel agent orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        from backend.app.dependencies import get_llm_router

        try:
            llm_router = get_llm_router()
        except Exception:
            llm_router = None
        _orchestrator = ParallelAgentOrchestrator(llm_router=llm_router)
    return _orchestrator


def get_bus() -> AgentCommunicationBus:
    """Get or create the communication bus."""
    global _bus
    if _bus is None:
        _bus = AgentCommunicationBus(enable_persistence=True)
    return _bus


def get_aggregator() -> ResultAggregator:
    """Get or create the result aggregator."""
    global _aggregator
    if _aggregator is None:
        _aggregator = ResultAggregator()
    return _aggregator


# Request/Response Models

class TaskRequest(BaseModel):
    """Request to execute a task."""
    goal: str
    description: str = ""
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    timeout_seconds: int = 300
    max_retries: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)


class SpawnAgentsRequest(BaseModel):
    """Request to spawn parallel agents."""
    tasks: list[TaskRequest]
    isolation: str = "thread"
    max_parallel: int | None = None
    aggregate_results: bool = True
    merge_strategy: str = "merge"
    conflict_resolution: str = "keep_last"


class BatchStatusResponse(BaseModel):
    """Response with batch status."""
    batch_id: str
    status: str
    total_tasks: int
    completed_results: int
    is_active: bool


class TaskResultResponse(BaseModel):
    """Response with task result."""
    task_id: str
    agent_id: str
    status: str
    output: Any = None
    error: str | None = None
    duration_seconds: float = 0.0
    retry_attempts: int = 0


class BatchResultsResponse(BaseModel):
    """Response with batch results."""
    batch_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    timeout_tasks: int
    results: list[TaskResultResponse]
    total_duration_seconds: float
    merged_output: Any = None
    merged_context: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class MessageRequest(BaseModel):
    """Request to send a message."""
    to_agent: str
    content: Any
    priority: str = "normal"
    ttl_seconds: int | None = None


class BroadcastRequest(BaseModel):
    """Request to broadcast a message."""
    content: Any
    priority: str = "normal"
    exclude_agents: list[str] = Field(default_factory=list)


class PublishRequest(BaseModel):
    """Request to publish to a topic."""
    topic: str
    content: Any
    priority: str = "normal"


# Real agent factory (AgentLoop-based)

class _AgentLoopParallelAgent:
    """Adapt the shared AgentLoop engine to the executor's agent protocol
    (``async execute(task)``), following the same wiring pattern as
    ``backend.app.core.agent_spawner``.
    """

    def __init__(
        self,
        agent_loop: Any,
        agent_id: str,
        isolation: IsolationMode,
        principal: Principal,
    ):
        self._loop = agent_loop
        self.agent_id = agent_id
        self.isolation = isolation
        self._principal = principal

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        extra_context: dict[str, Any] = {
            "task_id": task.task_id,
            "description": task.description,
            "constraints": list(task.constraints),
            "success_criteria": list(task.success_criteria),
            "isolation": self.isolation.value,
            "parallel_agent_id": self.agent_id,
        }
        extra_context.update(task.metadata or {})
        context = RunContext(
            tenant_id=self._principal.tenant_id,
            user_id=self._principal.user_id,
            agent_id=self.agent_id,
            permission_scope=list(getattr(self._principal, "scopes", None) or []),
        )
        response = await self._loop.run(context, task.goal, extra_context)
        status_value = getattr(getattr(response, "status", None), "value", None) or str(
            getattr(response, "status", "completed")
        )
        output = {
            "status": status_value,
            "answer": getattr(response, "answer", ""),
            "iterations": getattr(response, "iterations", 0),
            "trace_id": getattr(response, "trace_id", context.trace_id),
            "error": getattr(response, "error", None),
        }
        if status_value.lower() == "failed":
            # Surface the failure so the executor marks the task FAILED
            # instead of reporting a fake success.
            raise RuntimeError(output["error"] or "agent run failed")
        return output


def build_agent_loop_factory(
    principal: Principal,
) -> Callable[[str, IsolationMode], _AgentLoopParallelAgent]:
    """Build a real agent_factory backed by the shared AgentLoop engine.

    Raises AgentFactoryNotConfiguredError when the engine cannot be
    constructed (e.g. LLM/tooling not configured) so the endpoint can
    answer HTTP 501 instead of returning simulated results.
    """
    try:
        # 惰性导入避免循环依赖（与 core/agent_spawner.py 同一模式）。
        from backend.app.dependencies import get_agent

        agent_loop = get_agent()
    except Exception as exc:
        raise AgentFactoryNotConfiguredError(
            f"Parallel agent factory is not configured: {exc}"
        ) from exc

    def factory(agent_id: str, isolation: IsolationMode) -> _AgentLoopParallelAgent:
        return _AgentLoopParallelAgent(agent_loop, agent_id, isolation, principal)

    return factory


# Endpoints

@router.post("/spawn")
async def spawn_agents(
    request: SpawnAgentsRequest,
    principal: PrincipalDependency,
    executor: ParallelAgentExecutor = Depends(get_executor),
    aggregator: ResultAggregator = Depends(get_aggregator),
) -> dict[str, Any]:
    """
    Spawn and execute multiple agents in parallel.

    Args:
        request: Spawn request with tasks
        principal: Current principal
        executor: Parallel executor
        aggregator: Result aggregator

    Returns:
        Batch execution result
    """
    enforce_scope(principal, "agent:run")

    try:
        # Convert requests to tasks
        tasks = [
            AgentTask(
                goal=t.goal,
                description=t.description,
                constraints=t.constraints,
                success_criteria=t.success_criteria,
                timeout_seconds=t.timeout_seconds,
                max_retries=t.max_retries,
                metadata=t.metadata,
                dependencies=t.dependencies,
            )
            for t in request.tasks
        ]

        # Determine isolation mode
        try:
            isolation = IsolationMode(request.isolation)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid isolation mode: {request.isolation}",
            )

        # Build the real AgentLoop-backed factory for this request. Raises
        # AgentFactoryNotConfiguredError (-> HTTP 501) when the engine is
        # not configured, instead of falling back to simulated results.
        agent_factory = build_agent_loop_factory(principal)

        # Execute agents
        batch_result = await executor.spawn_agents(
            tasks=tasks,
            isolation=isolation,
            max_parallel=request.max_parallel,
            agent_factory=agent_factory,
        )

        # Aggregate results if requested
        if request.aggregate_results:
            merge_strategy = MergeStrategy(request.merge_strategy)
            conflict_resolution = ConflictResolution(request.conflict_resolution)

            config = AggregationConfig(
                merge_strategy=merge_strategy,
                conflict_resolution=conflict_resolution,
            )

            aggregated = await aggregator.collect_results(
                [r.to_dict() for r in batch_result.results],
                config=config,
            )

            return {
                "batch_id": batch_result.batch_id,
                "status": "completed",
                "total_tasks": batch_result.total_tasks,
                "completed_tasks": batch_result.completed_tasks,
                "failed_tasks": batch_result.failed_tasks,
                "cancelled_tasks": batch_result.cancelled_tasks,
                "timeout_tasks": batch_result.timeout_tasks,
                "total_duration_seconds": batch_result.total_duration_seconds,
                "results": [r.to_dict() for r in batch_result.results],
                "aggregated": aggregated.to_dict(),
            }
        else:
            return batch_result.to_dict()

    except AgentFactoryNotConfiguredError as e:
        logger.error(f"Parallel agent factory unavailable: {e}")
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        logger.error(f"Error spawning agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    principal: PrincipalDependency,
    executor: ParallelAgentExecutor = Depends(get_executor),
) -> BatchStatusResponse:
    """
    Get the status of a batch execution.

    Args:
        batch_id: Batch ID
        principal: Current principal
        executor: Parallel executor

    Returns:
        Batch status
    """
    enforce_scope(principal, "agent:read")

    try:
        status = await executor.get_batch_status(batch_id)
        return BatchStatusResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting batch status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}/results")
async def get_batch_results(
    batch_id: str,
    principal: PrincipalDependency,
    executor: ParallelAgentExecutor = Depends(get_executor),
    aggregator: ResultAggregator = Depends(get_aggregator),
    aggregate: bool = Query(False),
    merge_strategy: str = Query("merge"),
    conflict_resolution: str = Query("keep_last"),
) -> BatchResultsResponse:
    """
    Get results from a batch execution.

    Args:
        batch_id: Batch ID
        principal: Current principal
        executor: Parallel executor
        aggregator: Result aggregator
        aggregate: Whether to aggregate results
        merge_strategy: Merge strategy
        conflict_resolution: Conflict resolution strategy

    Returns:
        Batch results
    """
    enforce_scope(principal, "agent:read")

    try:
        results = await executor.get_batch_results(batch_id)

        response = BatchResultsResponse(
            batch_id=batch_id,
            total_tasks=len(results),
            completed_tasks=sum(1 for r in results if r.status.value == "completed"),
            failed_tasks=sum(1 for r in results if r.status.value == "failed"),
            cancelled_tasks=sum(1 for r in results if r.status.value == "cancelled"),
            timeout_tasks=sum(1 for r in results if r.status.value == "timeout"),
            results=[
                TaskResultResponse(
                    task_id=r.task_id,
                    agent_id=r.agent_id,
                    status=r.status.value,
                    output=r.output,
                    error=r.error,
                    duration_seconds=r.duration_seconds,
                    retry_attempts=r.retry_attempts,
                )
                for r in results
            ],
            total_duration_seconds=sum(r.duration_seconds for r in results),
        )

        # Aggregate if requested
        if aggregate:
            config = AggregationConfig(
                merge_strategy=MergeStrategy(merge_strategy),
                conflict_resolution=ConflictResolution(conflict_resolution),
            )
            aggregated = await aggregator.collect_results(
                [r.to_dict() for r in results],
                config=config,
            )
            response.merged_output = aggregated.merged_output
            response.merged_context = aggregated.merged_context
            response.errors = aggregated.errors

        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting batch results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    principal: PrincipalDependency,
    executor: ParallelAgentExecutor = Depends(get_executor),
) -> dict[str, Any]:
    """
    Cancel a batch execution.

    Args:
        batch_id: Batch ID
        principal: Current principal
        executor: Parallel executor

    Returns:
        Cancellation result
    """
    enforce_scope(principal, "agent:run")

    try:
        cancelled = await executor.cancel_batch(batch_id)
        return {
            "batch_id": batch_id,
            "cancelled": cancelled,
            "message": "Batch cancelled successfully" if cancelled else "Batch not found or already completed",
        }
    except Exception as e:
        logger.error(f"Error cancelling batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Communication Bus Endpoints

@extended_router.post("/messages/send")
async def send_message(
    request: MessageRequest,
    principal: PrincipalDependency,
    bus: AgentCommunicationBus = Depends(get_bus),
) -> dict[str, Any]:
    """
    Send a direct message between agents.

    Args:
        request: Message request
        principal: Current principal
        bus: Communication bus

    Returns:
        Message ID
    """
    enforce_scope(principal, "agent:run")

    try:
        message_id = await bus.send_message(
            from_agent=principal.agent_id,
            to_agent=request.to_agent,
            content=request.content,
            priority=MessagePriority(request.priority),
            ttl_seconds=request.ttl_seconds,
        )
        return {"message_id": message_id, "status": "sent"}
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@extended_router.post("/messages/broadcast")
async def broadcast_message(
    request: BroadcastRequest,
    principal: PrincipalDependency,
    bus: AgentCommunicationBus = Depends(get_bus),
) -> dict[str, Any]:
    """
    Broadcast a message to all agents.

    Args:
        request: Broadcast request
        principal: Current principal
        bus: Communication bus

    Returns:
        Message ID
    """
    enforce_scope(principal, "agent:run")

    try:
        message_id = await bus.broadcast(
            from_agent=principal.agent_id,
            content=request.content,
            priority=MessagePriority(request.priority),
            exclude_agents=request.exclude_agents,
        )
        return {"message_id": message_id, "status": "broadcast"}
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@extended_router.post("/messages/publish")
async def publish_message(
    request: PublishRequest,
    principal: PrincipalDependency,
    bus: AgentCommunicationBus = Depends(get_bus),
) -> dict[str, Any]:
    """
    Publish a message to a topic.

    Args:
        request: Publish request
        principal: Current principal
        bus: Communication bus

    Returns:
        Message ID
    """
    enforce_scope(principal, "agent:run")

    try:
        message_id = await bus.publish(
            topic=request.topic,
            content=request.content,
            from_agent=principal.agent_id,
            priority=MessagePriority(request.priority),
        )
        return {"message_id": message_id, "status": "published"}
    except Exception as e:
        logger.error(f"Error publishing message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@extended_router.get("/messages/stats")
async def get_message_stats(
    principal: PrincipalDependency,
    bus: AgentCommunicationBus = Depends(get_bus),
) -> dict[str, Any]:
    """
    Get communication bus statistics.

    Args:
        principal: Current principal
        bus: Communication bus

    Returns:
        Statistics
    """
    enforce_scope(principal, "agent:read")

    try:
        stats = await bus.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Orchestrator Endpoints (P1-08) ─────────────────────────────────────────────


class FanOutRequest(BaseModel):
    """Request for fan-out parallel execution."""
    task: str = Field(..., min_length=1, description="Parent task description")
    subtasks: list[str] = Field(..., min_length=1, description="Subtask instructions")
    max_parallel: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    aggregation_strategy: str = Field(default="merge", pattern="^(first_success|majority_vote|merge)$")
    token_budget: int = Field(default=100_000, ge=1000, le=1_000_000)


class FanInRequest(BaseModel):
    """Request for fan-in aggregation."""
    results: list[dict[str, Any]] = Field(..., min_length=1, description="Agent results to aggregate")
    aggregation: str = Field(default="merge", pattern="^(first_success|majority_vote|merge)$")


class PipelineRequest(BaseModel):
    """Request for pipeline execution."""
    stages: list[str] = Field(..., min_length=1, description="Ordered stage instructions")
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    token_budget: int = Field(default=100_000, ge=1000, le=1_000_000)


@router.post("/orchestrator/fan-out")
async def orchestrator_fan_out(
    request: FanOutRequest,
    principal: PrincipalDependency,
    orchestrator: ParallelAgentOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Execute subtasks in parallel (fan-out pattern).

    Each subtask gets an independent agent with its own context and LLM session.
    Results are returned for all subtasks.
    """
    enforce_scope(principal, "agent:run")

    try:
        config = ParallelConfig(
            max_parallel=request.max_parallel,
            timeout_seconds=request.timeout_seconds,
            aggregation_strategy=request.aggregation_strategy,
            token_budget=request.token_budget,
        )
        results = await orchestrator.execute_fan_out(
            task=request.task,
            subtasks=request.subtasks,
            config=config,
        )
        return {
            "pattern": "fan_out",
            "task": request.task,
            "total_subtasks": len(request.subtasks),
            "completed": sum(1 for r in results if r.status == "completed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "timeout": sum(1 for r in results if r.status == "timeout"),
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        logger.error(f"Fan-out execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrator/fan-in")
async def orchestrator_fan_in(
    request: FanInRequest,
    principal: PrincipalDependency,
    orchestrator: ParallelAgentOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Aggregate results from parallel agents (fan-in pattern).

    Supports aggregation strategies: first_success, majority_vote, merge.
    """
    enforce_scope(principal, "agent:run")

    try:
        agent_results = [
            AgentResult(
                agent_id=r.get("agent_id", f"agent-{i}"),
                status=r.get("status", "completed"),
                output=r.get("output", ""),
                error=r.get("error"),
                duration_ms=r.get("duration_ms", 0.0),
            )
            for i, r in enumerate(request.results)
        ]
        result = await orchestrator.execute_fan_in(
            results=agent_results,
            aggregation=request.aggregation,
        )
        return {
            "pattern": "fan_in",
            "aggregation": request.aggregation,
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Fan-in aggregation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@extended_router.post("/orchestrator/pipeline")
async def orchestrator_pipeline(
    request: PipelineRequest,
    principal: PrincipalDependency,
    orchestrator: ParallelAgentOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Execute stages sequentially (pipeline pattern).

    Each stage receives the output of the previous stage as context.
    """
    enforce_scope(principal, "agent:run")

    try:
        config = ParallelConfig(
            timeout_seconds=request.timeout_seconds,
            token_budget=request.token_budget,
        )
        result = await orchestrator.execute_pipeline(
            stages=request.stages,
            config=config,
        )
        return {
            "pattern": "pipeline",
            "total_stages": len(request.stages),
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Pipeline execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Ultra 4-Agent 并行端点 ────────────────────────────────────────────────────


class UltraRequest(BaseModel):
    """Request for Ultra 4-Agent parallel execution."""
    task: str
    max_agents: int = Field(default=4, ge=2, le=8)
    budget_tokens_per_agent: int = Field(default=50000, ge=1000, le=200000)
    timeout_seconds: int = Field(default=600, ge=60, le=3600)
    merge_strategy: str = "synthesize"  # synthesize | concat | vote


@router.post("/ultra")
async def ultra_execute(
    request: UltraRequest,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """
    Ultra 模式: 协调者拆分任务 → N 个 Agent 并行执行 → 聚合结果。

    对标 Codex Ultra 4-Agent 并行模式。
    """
    enforce_scope(principal, "agent:run")

    from backend.app.settings import settings
    if not settings.ultra_mode_enabled:
        raise HTTPException(status_code=403, detail="Ultra mode is not enabled")

    try:
        from backend.app.core.ultra_mode import UltraConfig, UltraOrchestrator
        from backend.app.dependencies import get_agent, get_llm_router

        agent_loop = get_agent()
        llm_router = get_llm_router()

        config = UltraConfig(
            max_agents=min(request.max_agents, settings.ultra_max_agents),
            budget_tokens_per_agent=request.budget_tokens_per_agent,
            timeout_seconds=request.timeout_seconds,
            merge_strategy=request.merge_strategy,
        )

        # agent_factory: (task_description) -> coroutine returning output str
        async def agent_factory(task_description: str) -> str:
            context = RunContext(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                agent_id=f"ultra-{principal.agent_id}",
                permission_scope=list(getattr(principal, "scopes", None) or []),
            )
            response = await agent_loop.run(context, task_description, {})
            return getattr(response, "answer", "") or ""

        orchestrator = UltraOrchestrator(
            agent_factory=agent_factory,
            llm_router=llm_router,
        )
        result = await orchestrator.execute(request.task, {}, config)
        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ultra execution error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ─── L1: Queue Management & Concurrency Monitoring ────────────────────────────


@router.get("/queue/stats")
async def get_queue_stats(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Concurrency pool & queue statistics: active tasks, capacity, throughput."""
    enforce_scope(principal, "agent:run")
    import time

    executor = get_executor()
    stats = executor.get_stats()
    active = executor.get_active_tasks()

    # Compute real-time concurrency utilization
    max_conc = stats.get("max_concurrency", 3)
    active_count = len(active)
    utilization = round(active_count / max_conc * 100, 1) if max_conc > 0 else 0

    # Batch throughput
    total_batches = stats.get("total_batches", 0)
    completed_tasks_in_batches = 0
    failed_tasks_in_batches = 0
    for batch in executor._batches.values():
        for r in batch.results:
            if r.status == "completed":
                completed_tasks_in_batches += 1
            elif r.status in ("failed", "timeout"):
                failed_tasks_in_batches += 1

    return {
        "pool": {
            "max_concurrency": max_conc,
            "active_tasks": active_count,
            "utilization_percent": utilization,
            "capacity_remaining": max(0, max_conc - active_count),
        },
        "queue": {
            "backpressure": utilization >= 90.0,
            "total_batches": total_batches,
        },
        "throughput": {
            "completed_tasks": completed_tasks_in_batches,
            "failed_tasks": failed_tasks_in_batches,
            "success_rate": round(
                completed_tasks_in_batches / max(1, completed_tasks_in_batches + failed_tasks_in_batches) * 100, 1
            ),
        },
        "active_task_ids": list(active.keys())[:20],
        "timestamp": time.time(),
    }


@router.get("/queue/health")
async def get_queue_health(principal: PrincipalDependency = None) -> dict[str, Any]:
    """System resource health for concurrency decisions (CPU, memory, event loop lag)."""
    enforce_scope(principal, "agent:run")
    import asyncio
    import time

    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_available_mb = round(mem.available / 1024 / 1024, 1)
    except Exception:
        cpu_percent = -1
        memory_percent = -1
        memory_available_mb = -1

    # Event loop lag measurement
    loop = asyncio.get_event_loop()
    t0 = time.perf_counter()
    await asyncio.sleep(0)
    loop_lag_ms = round((time.perf_counter() - t0) * 1000, 3)

    executor = get_executor()
    active_count = len(executor.get_active_tasks())
    max_conc = executor.max_concurrency

    # Recommendation
    if cpu_percent > 80 or memory_percent > 85:
        recommendation = "scale_down"
    elif cpu_percent < 30 and memory_percent < 40 and active_count < max_conc:
        recommendation = "scale_up"
    else:
        recommendation = "stable"

    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "memory_available_mb": memory_available_mb,
        "event_loop_lag_ms": loop_lag_ms,
        "concurrency": {"active": active_count, "max": max_conc},
        "recommendation": recommendation,
        "timestamp": time.time(),
    }
