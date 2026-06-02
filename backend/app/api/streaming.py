"""
Server-Sent Events (SSE) streaming API for real-time agent execution feedback.

Provides real-time streaming of agent execution events including:
- Message updates
- Tool calls and results
- Task status changes
- Progress updates
- Error notifications
- Completion events
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Annotated, Any, AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import RunContext, ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_agent, get_current_principal, get_run_store, get_trace_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["streaming"])
AgentDependency = Annotated[AgentLoop, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
RunStoreDependency = Annotated[object, Depends(get_run_store)]
TraceStoreDependency = Annotated[object, Depends(get_trace_store)]


class StreamEvent(BaseModel):
    """Base model for streaming events."""
    event_type: str = Field(..., description="Type of event: message, tool_call, task_update, error, completion, heartbeat")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str = Field(..., description="ID of the agent run")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    sequence: int = Field(default=0, description="Event sequence number for ordering")


class MessageEvent(BaseModel):
    """Message event from agent."""
    event_type: str = "message"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    content: str = Field(..., description="Message content")
    role: str = Field(default="assistant", description="Message role: assistant, user, system")
    sequence: int = 0


class ToolCallEvent(BaseModel):
    """Tool call event."""
    event_type: str = "tool_call"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    tool_name: str = Field(..., description="Name of the tool being called")
    tool_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique ID for this tool call")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    sequence: int = 0


class ToolResultEvent(BaseModel):
    """Tool result event."""
    event_type: str = "tool_result"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    tool_id: str = Field(..., description="ID of the tool call this result belongs to")
    tool_name: str = Field(..., description="Name of the tool")
    result: Any = Field(..., description="Tool execution result")
    success: bool = Field(default=True, description="Whether tool execution succeeded")
    sequence: int = 0


class TaskUpdateEvent(BaseModel):
    """Task status update event."""
    event_type: str = "task_update"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    task_id: str = Field(..., description="ID of the task")
    status: str = Field(..., description="Task status: pending, in_progress, completed, failed")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress percentage (0-1)")
    details: dict[str, Any] = Field(default_factory=dict, description="Task-specific details")
    sequence: int = 0


class ProgressEvent(BaseModel):
    """Overall progress event."""
    event_type: str = "progress"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    overall_progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall progress (0-1)")
    current_step: str = Field(default="", description="Current execution step")
    total_steps: int = Field(default=0, description="Total steps in execution")
    completed_steps: int = Field(default=0, description="Completed steps")
    sequence: int = 0


class ErrorEvent(BaseModel):
    """Error event."""
    event_type: str = "error"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: dict[str, Any] = Field(default_factory=dict, description="Additional error details")
    recoverable: bool = Field(default=False, description="Whether error is recoverable")
    sequence: int = 0


class CompletionEvent(BaseModel):
    """Completion event."""
    event_type: str = "completion"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    status: str = Field(..., description="Final status: completed, failed, cancelled")
    result: Any = Field(default=None, description="Final result")
    summary: dict[str, Any] = Field(default_factory=dict, description="Execution summary")
    sequence: int = 0


class HeartbeatEvent(BaseModel):
    """Heartbeat event to keep connection alive."""
    event_type: str = "heartbeat"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    sequence: int = 0


class LogEvent(BaseModel):
    """Log event for execution logs."""
    event_type: str = "log"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    level: str = Field(default="info", description="Log level: debug, info, warning, error")
    message: str = Field(..., description="Log message")
    source: str = Field(default="agent", description="Log source: agent, tool, system")
    sequence: int = 0


class MetricEvent(BaseModel):
    """Metric event for real-time metrics."""
    event_type: str = "metric"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    metric_name: str = Field(..., description="Name of the metric")
    metric_value: float | int | str = Field(..., description="Metric value")
    unit: str = Field(default="", description="Unit of measurement")
    sequence: int = 0


class TaskStatusEvent(BaseModel):
    """Task status event for task list updates."""
    event_type: str = "task_status"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    run_id: str
    task_id: str = Field(..., description="ID of the task")
    status: str = Field(..., description="Task status: pending, running, completed, failed")
    title: str = Field(default="", description="Task title")
    details: dict[str, Any] = Field(default_factory=dict, description="Task details")
    sequence: int = 0


# In-memory event store for streaming (in production, use Redis or similar)
class StreamEventStore:
    """In-memory event store for streaming with connection management."""

    def __init__(self, max_events_per_run: int = 1000, max_queue_size: int = 100):
        self.events: dict[str, list[StreamEvent]] = {}
        self.subscribers: dict[str, list[asyncio.Queue]] = {}
        self.sequence_counters: dict[str, int] = {}
        self.max_events_per_run = max_events_per_run
        self.max_queue_size = max_queue_size
        self.connection_count: dict[str, int] = {}

    def add_event(self, run_id: str, event: StreamEvent) -> None:
        """Add event to store and notify subscribers."""
        if run_id not in self.events:
            self.events[run_id] = []
            self.sequence_counters[run_id] = 0

        # Assign sequence number
        self.sequence_counters[run_id] += 1
        event.sequence = self.sequence_counters[run_id]

        # Add event to store
        self.events[run_id].append(event)

        # Keep only recent events (circular buffer)
        if len(self.events[run_id]) > self.max_events_per_run:
            self.events[run_id] = self.events[run_id][-self.max_events_per_run:]

        # Notify all subscribers
        if run_id in self.subscribers:
            dead_queues = []
            for queue in self.subscribers[run_id]:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Event queue full for run {run_id}, dropping oldest event")
                    try:
                        queue.get_nowait()
                        queue.put_nowait(event)
                    except asyncio.QueueEmpty:
                        pass
                except Exception as e:
                    logger.error(f"Error notifying subscriber for run {run_id}: {e}")
                    dead_queues.append(queue)

            # Clean up dead queues
            for queue in dead_queues:
                try:
                    self.subscribers[run_id].remove(queue)
                except ValueError:
                    pass

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Subscribe to events for a run."""
        if run_id not in self.subscribers:
            self.subscribers[run_id] = []
        if run_id not in self.connection_count:
            self.connection_count[run_id] = 0

        queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.subscribers[run_id].append(queue)
        self.connection_count[run_id] += 1

        logger.debug(f"New subscriber for run {run_id}, total connections: {self.connection_count[run_id]}")
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from events."""
        if run_id in self.subscribers:
            try:
                self.subscribers[run_id].remove(queue)
                if run_id in self.connection_count:
                    self.connection_count[run_id] -= 1
                logger.debug(f"Subscriber removed for run {run_id}, remaining connections: {self.connection_count[run_id]}")
            except ValueError:
                pass

    def get_events(self, run_id: str, since_sequence: int = 0) -> list[StreamEvent]:
        """Get events for a run since a specific sequence."""
        if run_id not in self.events:
            return []
        return [e for e in self.events[run_id] if e.sequence > since_sequence]

    def get_connection_count(self, run_id: str) -> int:
        """Get number of active connections for a run."""
        return self.connection_count.get(run_id, 0)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the event store."""
        total_events = sum(len(events) for events in self.events.values())
        total_connections = sum(self.connection_count.values())
        return {
            "total_runs": len(self.events),
            "total_events": total_events,
            "total_connections": total_connections,
            "avg_events_per_run": total_events // len(self.events) if self.events else 0,
        }


# Global event store
event_store = StreamEventStore()


def _context_from_principal(principal: Principal) -> RunContext:
    """Create RunContext from Principal."""
    return RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission_scope=list(principal.scopes)
    )


async def _stream_events(
    run_id: str,
    queue: asyncio.Queue,
    heartbeat_interval: float = 30.0,
) -> AsyncGenerator[str, None]:
    """Stream events from queue as SSE format."""
    last_heartbeat = asyncio.get_event_loop().time()

    try:
        while True:
            try:
                # Wait for event with timeout for heartbeat
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)

                # Send event as SSE
                event_json = json.dumps(event.model_dump())
                yield f"event: {event.event_type}\n"
                yield f"data: {event_json}\n\n"

                last_heartbeat = asyncio.get_event_loop().time()

            except asyncio.TimeoutError:
                # Send heartbeat
                heartbeat = HeartbeatEvent(run_id=run_id)
                event_json = json.dumps(heartbeat.model_dump())
                yield f"event: heartbeat\n"
                yield f"data: {event_json}\n\n"

    except asyncio.CancelledError:
        logger.debug(f"Stream cancelled for run {run_id}")
        raise
    except Exception as e:
        logger.error(f"Error in event stream for run {run_id}: {e}")
        error_event = ErrorEvent(
            run_id=run_id,
            error_code="STREAM_ERROR",
            error_message=str(e),
            recoverable=False,
        )
        event_json = json.dumps(error_event.model_dump())
        yield f"event: error\n"
        yield f"data: {event_json}\n\n"


@router.get("/stream/{run_id}")
async def subscribe_to_stream(
    run_id: str,
    principal: PrincipalDependency,
    since_sequence: int = Query(default=0, ge=0, description="Get events since this sequence number"),
) -> Any:
    """
    Subscribe to real-time streaming events for an agent run.

    Returns Server-Sent Events stream with:
    - message: Agent messages
    - tool_call: Tool invocations
    - tool_result: Tool results
    - task_update: Task status changes
    - progress: Overall progress updates
    - error: Error events
    - completion: Run completion
    - heartbeat: Keep-alive events

    Args:
        run_id: ID of the agent run to stream
        since_sequence: Optional sequence number to resume from

    Returns:
        Server-Sent Events stream
    """
    enforce_scope(principal, "agent:read")

    # Subscribe to events
    queue = event_store.subscribe(run_id)

    # Send any buffered events since sequence
    buffered_events = event_store.get_events(run_id, since_sequence)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send buffered events first
            for event in buffered_events:
                event_json = json.dumps(event.model_dump())
                yield f"event: {event.event_type}\n"
                yield f"data: {event_json}\n\n"

            # Stream new events
            async for chunk in _stream_events(run_id):
                yield chunk

        finally:
            event_store.unsubscribe(run_id, queue)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.post("/run/stream")
async def create_streaming_run(
    task: str = Body(..., min_length=1, max_length=20_000, description="Task to execute"),
    extra_context: dict[str, Any] = Body(default={}, description="Additional context"),
    *,
    agent: AgentDependency,
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
) -> dict[str, Any]:
    """
    Create a new agent run with streaming support.

    Returns a run_id that can be used with /stream/{run_id} endpoint.

    Args:
        task: The task to execute
        extra_context: Additional context for the task

    Returns:
        Dictionary with run_id and stream_url
    """
    enforce_scope(principal, "agent:run")

    run_id = str(uuid4())
    context = _context_from_principal(principal)

    # Create initial event
    initial_event = MessageEvent(
        run_id=run_id,
        content=f"Starting execution of task: {task}",
        role="system",
        sequence=0,
    )
    event_store.add_event(run_id, initial_event)

    # Start async execution in background
    async def run_agent_async():
        try:
            sequence = 1

            # Send progress event
            progress_event = ProgressEvent(
                run_id=run_id,
                overall_progress=0.1,
                current_step="Planning",
                total_steps=4,
                completed_steps=0,
                sequence=sequence,
            )
            event_store.add_event(run_id, progress_event)
            sequence += 1

            # Execute agent
            result = await agent.run(context, task, extra_context)

            # Send completion event
            completion_event = CompletionEvent(
                run_id=run_id,
                status=result.status,
                result=result.answer,
                summary=result.execution_summary,
                sequence=sequence,
            )
            event_store.add_event(run_id, completion_event)

            # Save to run store
            run_store.save(context, task, result)

        except Exception as e:
            logger.error(f"Error executing streaming run {run_id}: {e}")
            error_event = ErrorEvent(
                run_id=run_id,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                recoverable=False,
                sequence=sequence,
            )
            event_store.add_event(run_id, error_event)

    # Schedule background task
    asyncio.create_task(run_agent_async())

    return {
        "run_id": run_id,
        "stream_url": f"/api/v1/agent/stream/{run_id}",
        "status": "started",
    }


@router.get("/stream/{run_id}/events")
async def get_stream_events(
    run_id: str,
    principal: PrincipalDependency,
    since_sequence: int = Query(default=0, ge=0, description="Get events since this sequence"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum events to return"),
) -> dict[str, Any]:
    """
    Get buffered events for a run (non-streaming).

    Useful for polling or getting event history.

    Args:
        run_id: ID of the agent run
        since_sequence: Get events after this sequence number
        limit: Maximum number of events to return

    Returns:
        List of events
    """
    enforce_scope(principal, "agent:read")

    events = event_store.get_events(run_id, since_sequence)
    return {
        "run_id": run_id,
        "events": [e.model_dump() for e in events[:limit]],
        "total": len(events),
        "limited": len(events) > limit,
    }


@router.post("/stream/{run_id}/event")
async def emit_event(
    run_id: str,
    event: StreamEvent,
    principal: PrincipalDependency,
) -> dict[str, str]:
    """
    Emit a custom event to a stream (for internal use).

    Args:
        run_id: ID of the agent run
        event: Event to emit

    Returns:
        Confirmation
    """
    enforce_scope(principal, "agent:run")

    event.run_id = run_id
    event_store.add_event(run_id, event)

    return {"status": "emitted", "run_id": run_id}


@router.post("/stream/{run_id}/log")
async def emit_log(
    run_id: str,
    level: str = Query(default="info", regex="^(debug|info|warning|error)$"),
    message: str = Query(..., min_length=1, max_length=10000),
    source: str = Query(default="agent"),
    *,
    principal: PrincipalDependency,
) -> dict[str, str]:
    """
    Emit a log event to a stream.

    Args:
        run_id: ID of the agent run
        level: Log level (debug, info, warning, error)
        message: Log message
        source: Log source (agent, tool, system)

    Returns:
        Confirmation
    """
    enforce_scope(principal, "agent:run")

    log_event = LogEvent(
        run_id=run_id,
        level=level,
        message=message,
        source=source,
    )
    event_store.add_event(run_id, log_event)

    return {"status": "logged", "run_id": run_id}


@router.post("/stream/{run_id}/metric")
async def emit_metric(
    run_id: str,
    metric_name: str = Query(..., min_length=1, max_length=100),
    metric_value: str = Query(..., min_length=1, max_length=1000),
    unit: str = Query(default=""),
    *,
    principal: PrincipalDependency,
) -> dict[str, str]:
    """
    Emit a metric event to a stream.

    Args:
        run_id: ID of the agent run
        metric_name: Name of the metric
        metric_value: Value of the metric (can be number or string)
        unit: Unit of measurement

    Returns:
        Confirmation
    """
    enforce_scope(principal, "agent:run")

    # Try to parse as number
    try:
        if "." in metric_value:
            value: float | int | str = float(metric_value)
        else:
            value = int(metric_value)
    except ValueError:
        value = metric_value

    metric_event = MetricEvent(
        run_id=run_id,
        metric_name=metric_name,
        metric_value=value,
        unit=unit,
    )
    event_store.add_event(run_id, metric_event)

    return {"status": "metric_emitted", "run_id": run_id}


@router.post("/stream/{run_id}/task-status")
async def emit_task_status(
    run_id: str,
    task_id: str = Query(..., min_length=1),
    status: str = Query(..., regex="^(pending|running|completed|failed)$"),
    title: str = Query(default=""),
    details: dict[str, Any] = Body(default={}),
    *,
    principal: PrincipalDependency,
) -> dict[str, str]:
    """
    Emit a task status event to a stream.

    Args:
        run_id: ID of the agent run
        task_id: ID of the task
        status: Task status (pending, running, completed, failed)
        title: Task title
        details: Task details

    Returns:
        Confirmation
    """
    enforce_scope(principal, "agent:run")

    task_event = TaskStatusEvent(
        run_id=run_id,
        task_id=task_id,
        status=status,
        title=title,
        details=details,
    )
    event_store.add_event(run_id, task_event)

    return {"status": "task_status_emitted", "run_id": run_id}


@router.get("/stream/{run_id}/stats")
async def get_stream_stats(
    run_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """
    Get statistics for a stream.

    Args:
        run_id: ID of the agent run

    Returns:
        Stream statistics
    """
    enforce_scope(principal, "agent:read")

    events = event_store.get_events(run_id)
    connections = event_store.get_connection_count(run_id)

    # Count events by type
    event_counts: dict[str, int] = {}
    for event in events:
        event_type = event.event_type
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    return {
        "run_id": run_id,
        "total_events": len(events),
        "active_connections": connections,
        "event_counts": event_counts,
        "store_stats": event_store.get_stats(),
    }


@router.get("/stream/health")
async def stream_health() -> dict[str, Any]:
    """
    Get health status of the streaming service.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "store_stats": event_store.get_stats(),
    }
