"""
Parallel Agents API - REST endpoints for parallel agent execution.

Endpoints:
- POST /api/v1/agents/parallel/spawn - Start parallel agents
- GET /api/v1/agents/parallel/{batch_id}/status - Get batch status
- GET /api/v1/agents/parallel/{batch_id}/results - Get batch results
- POST /api/v1/agents/parallel/{batch_id}/cancel - Cancel batch
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.parallel_agent_executor import (
    ParallelAgentExecutor,
    AgentTask,
    IsolationMode,
    BatchExecutionResult,
)
from backend.app.core.agent_communication_bus import (
    AgentCommunicationBus,
    Message,
    MessagePriority,
)
from backend.app.core.result_aggregator import (
    ResultAggregator,
    AggregationConfig,
    MergeStrategy,
    ConflictResolution,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/parallel", tags=["parallel_agents"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global instances
_executor: Optional[ParallelAgentExecutor] = None
_bus: Optional[AgentCommunicationBus] = None
_aggregator: Optional[ResultAggregator] = None


def get_executor() -> ParallelAgentExecutor:
    """Get or create the parallel agent executor."""
    global _executor
    if _executor is None:
        _executor = ParallelAgentExecutor(max_workers=3)
    return _executor


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
    max_parallel: Optional[int] = None
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
    error: Optional[str] = None
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
    ttl_seconds: Optional[int] = None


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

        # Execute agents
        batch_result = await executor.spawn_agents(
            tasks=tasks,
            isolation=isolation,
            max_parallel=request.max_parallel,
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

@router.post("/messages/send")
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


@router.post("/messages/broadcast")
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


@router.post("/messages/publish")
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


@router.get("/messages/stats")
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
