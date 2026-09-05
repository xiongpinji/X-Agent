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
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from backend.app.core.agent import AgentLoop
from backend.app.core.approvals import ApprovalStatus
from backend.app.core.contracts import RunContext, RunStatus, TraceEvent
from backend.app.core.security import Principal
from backend.app.dependencies import (
    enforce_scope,
    get_agent,
    get_current_principal,
    get_run_store,
    get_trace_store,
)

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
                with contextlib.suppress(ValueError):
                    self.subscribers[run_id].remove(queue)

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


# ---------------------------------------------------------------------------
# Fine-grained agent event bridging (TraceEvent -> SSE StreamEvent)
#
# AgentLoop._emit_trace pushes every lifecycle event through the
# ``event_callback`` hook passed to ``agent.run(...)``. The streaming run
# endpoint installs a bridge that converts those trace events into SSE
# StreamEvents so subscribers see each agent step in real time.
#
# New SSE event types (consumed by the CLI TUI):
#   iteration        — an agent loop iteration started (step_kind/instruction)
#   tool_call        — a tool invocation reached completion (name/success/latency)
#   tool_result      — post-run tool detail (arguments summary + output summary)
#   plan             — execution plan created (goal/step_count)
#   observation      — observe-step output preview
#   reflection       — reflect-step output preview
#   agent            — generic whitelisted lifecycle event (resumed/fast_path/...)
#   approval_required— a tool call is blocked on a pending approval decision
#
# Legacy event types (message/progress/completion/error/heartbeat/...) are
# preserved unchanged for compatibility.
# ---------------------------------------------------------------------------

TERMINAL_EVENT_TYPES = frozenset({"completion", "error"})

#: Whitelisted AgentLoop trace events -> SSE event types. Events not listed
#: here (including internal ones like agent.completed, whose payload is
#: superseded by the run-level completion event) are dropped to avoid leaking
#: internal state over the stream.
_TRACE_EVENT_TYPE_MAP: dict[str, str] = {
    "agent.iteration.started": "iteration",
    "agent.tool.completed": "tool_call",
    "agent.plan.created": "plan",
    "agent.observation.recorded": "observation",
    "agent.reflection.created": "reflection",
    "agent.task.decomposed": "agent",
    "agent.resumed": "agent",
    "agent.fast_path": "agent",
    "agent.blocked": "agent",
    "agent.orchestrated": "agent",
    "agent.continuation.replan": "agent",
    "agent.replan.after_reflect": "agent",
    "agent.write.retry_scheduled": "agent",
    "agent.repair.retry_scheduled": "agent",
    "agent.auto_verify.injected": "agent",
    "agent.test_failure.repair_injected": "agent",
    "agent.observe.completed": "agent",
    "agent.plan.ready": "agent",
    "agent.write.verified": "agent",
    "agent.write.needs_repair": "agent",
    "agent.context.session_opened": "agent",
    "agent.context.compressed": "agent",
}

_MAX_INSTRUCTION_CHARS = 200
_MAX_TEXT_CHARS = 200
_MAX_ARGS_CHARS = 300
_MAX_RESULT_CHARS = 400


def _trunc(value: Any, limit: int) -> str:
    """Stringify and truncate a value for safe transport over SSE."""
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "ok")


def _coerce_number(value: Any) -> Any:
    """Trace events stringify scalars via json.dumps; parse numbers back."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def trace_to_stream_event(run_id: str, trace_event: TraceEvent) -> StreamEvent | None:
    """Convert an AgentLoop TraceEvent into an SSE StreamEvent.

    Returns None for trace events that should not be surfaced on the stream
    (unknown/internal events). Pure function — unit-testable without a server.
    """
    name = str(getattr(trace_event, "event", "") or "")
    sse_type = _TRACE_EVENT_TYPE_MAP.get(name)
    if sse_type is None:
        return None

    data = getattr(trace_event, "data", None) or {}
    if not isinstance(data, dict):
        data = {}

    payload: dict[str, Any] = {}
    if sse_type == "iteration":
        payload["iteration"] = _coerce_number(data.get("iteration"))
        payload["step_kind"] = str(data.get("step_kind") or "")
        payload["instruction"] = _trunc(data.get("instruction"), _MAX_INSTRUCTION_CHARS)
    elif sse_type == "tool_call":
        payload["phase"] = "completed"
        payload["tool_name"] = str(data.get("tool_name") or "")
        payload["success"] = _coerce_bool(data.get("success"))
        payload["latency_ms"] = _coerce_number(data.get("latency_ms"))
        payload["iteration"] = _coerce_number(data.get("iteration"))
    elif sse_type == "plan":
        payload["goal"] = _trunc(data.get("goal"), _MAX_TEXT_CHARS)
        payload["step_count"] = _coerce_number(data.get("step_count"))
        payload["task"] = _trunc(data.get("task"), 120)
    elif sse_type == "observation":
        payload["iteration"] = _coerce_number(data.get("iteration"))
        payload["observation"] = _trunc(data.get("observation"), _MAX_TEXT_CHARS)
    elif sse_type == "reflection":
        payload["iteration"] = _coerce_number(data.get("iteration"))
        payload["reflection"] = _trunc(data.get("reflection"), _MAX_TEXT_CHARS)
    else:  # generic whitelisted lifecycle event
        payload["trace_event"] = name
        for key, value in data.items():
            payload[str(key)] = _trunc(value, 160) if isinstance(value, str) and len(value) > 160 else value

    payload["trace_id"] = getattr(trace_event, "trace_id", None)
    return StreamEvent(event_type=sse_type, run_id=run_id, data=payload)


def tool_call_to_result_event(run_id: str, record: Any) -> StreamEvent:
    """Convert a final ToolCallRecord into a detailed tool_result SSE event.

    Carries the tool name, an arguments summary and a result summary, both
    truncated to bound payload size and avoid leaking large file contents.
    """
    args_preview = getattr(record, "arguments_preview", None) or {}
    output = getattr(record, "output", None)
    error = getattr(record, "error", None)
    return StreamEvent(
        event_type="tool_result",
        run_id=run_id,
        data={
            "tool_name": str(getattr(record, "tool_name", "") or ""),
            "success": bool(getattr(record, "success", False)),
            "latency_ms": getattr(record, "latency_ms", 0.0),
            "arguments": _trunc(args_preview, _MAX_ARGS_CHARS),
            "output": _trunc(output, _MAX_RESULT_CHARS),
            "error": _trunc(error, _MAX_TEXT_CHARS) if error else None,
        },
    )


def approval_to_event(run_id: str, record: Any) -> StreamEvent:
    """Convert a pending ApprovalRequestRecord into an approval_required event."""
    return StreamEvent(
        event_type="approval_required",
        run_id=run_id,
        data={
            "approval_id": str(getattr(record, "id", "") or ""),
            "tool_name": str(getattr(record, "resource_id", "") or ""),
            "action": str(getattr(record, "action", "") or ""),
            "risk_level": str(getattr(getattr(record, "risk_level", None), "value", "") or ""),
            "reason": _trunc(getattr(record, "reason", None), _MAX_TEXT_CHARS),
            "arguments": _trunc(getattr(record, "arguments_preview", None) or {}, _MAX_ARGS_CHARS),
        },
    )


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
    asyncio.get_event_loop().time()

    try:
        while True:
            try:
                # Wait for event with timeout for heartbeat
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)

                # Send event as SSE
                event_json = json.dumps(event.model_dump())
                yield f"event: {event.event_type}\n"
                yield f"data: {event_json}\n\n"

                asyncio.get_event_loop().time()

                # Close the stream once the run reaches a terminal state so
                # clients (CLI/HTTP) get a natural end-of-stream instead of
                # hanging on heartbeats forever.
                if event.event_type in TERMINAL_EVENT_TYPES:
                    logger.debug(f"Stream reached terminal event for run {run_id}")
                    return

            except TimeoutError:
                # Send heartbeat
                heartbeat = HeartbeatEvent(run_id=run_id)
                event_json = json.dumps(heartbeat.model_dump())
                yield "event: heartbeat\n"
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
        yield "event: error\n"
        yield f"data: {event_json}\n\n"


# B-4 FIX: /stream/health must be registered BEFORE /stream/{run_id}
# to prevent "health" from being captured as a run_id parameter.
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


@router.get("/model-config")
async def get_model_config(principal: PrincipalDependency) -> dict[str, Any]:
    """
    Report the active LLM/model configuration (no secrets).

    Used by CLI chat ``/model`` to show which backend and models the
    agent is currently routed to. API keys are never included.
    """
    enforce_scope(principal, "agent:read")

    config: dict[str, Any] = {
        "llm_backend": "unknown",
        "fallback_order": [],
        "openai_model": None,
        "deepseek_model": None,
        "router_backends": [],
    }
    try:
        from backend.app.settings import get_settings

        settings = get_settings()
        config.update(
            {
                "llm_backend": settings.llm_backend,
                "fallback_order": [b.strip() for b in settings.llm_fallback_order.split(",") if b.strip()],
                "openai_model": settings.openai_model,
                "deepseek_model": settings.deepseek_model,
                "openai_base_url": settings.openai_base_url,
                "deepseek_base_url": settings.deepseek_base_url,
            }
        )
    except Exception as exc:
        logger.debug(f"settings unavailable for model-config: {exc}")

    try:
        from backend.app.dependencies import get_agent

        router = getattr(get_agent(), "llm", None)
        backends = getattr(router, "_backends", None) or []
        config["router_backends"] = [
            {
                "name": getattr(b, "name", b.__class__.__name__),
                "type": b.__class__.__name__,
            }
            for b in backends
        ]
    except Exception as exc:
        logger.debug(f"router introspection failed for model-config: {exc}")

    return config


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
            terminal_seen = False
            # Send buffered events first
            for event in buffered_events:
                event_json = json.dumps(event.model_dump())
                yield f"event: {event.event_type}\n"
                yield f"data: {event_json}\n\n"
                if event.event_type in TERMINAL_EVENT_TYPES:
                    terminal_seen = True

            if terminal_seen:
                # Run already finished before we subscribed; nothing more to wait for.
                return

            # Stream new events
            async for chunk in _stream_events(run_id, queue):
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
    session_id: str | None = Body(default=None, max_length=200, description="Optional session id for multi-turn context"),
    *,
    agent: AgentDependency,
    principal: PrincipalDependency,
    run_store: RunStoreDependency,
) -> dict[str, Any]:
    """
    Create a new agent run with streaming support.

    Returns a run_id that can be used with /stream/{run_id} endpoint.
    While the agent executes in the background, every whitelisted
    AgentLoop trace event (iteration started, tool call completed, plan
    created, ...) is bridged onto the stream as a fine-grained SSE event,
    followed by tool_result details, approval_required events for pending
    approvals, and a final completion (or error) event that closes the
    stream.

    Args:
        task: The task to execute
        extra_context: Additional context for the task
        session_id: Optional session id (persisted multi-turn context)

    Returns:
        Dictionary with run_id, stream_url, trace_id and status
    """
    enforce_scope(principal, "agent:run")

    run_id = str(uuid4())
    context = _context_from_principal(principal)
    if session_id:
        context.session_id = session_id

    # Create initial event
    initial_event = MessageEvent(
        run_id=run_id,
        content=f"Starting execution of task: {task}",
        role="system",
        sequence=0,
    )
    event_store.add_event(run_id, initial_event)

    # Trace-event bridge: AgentLoop calls this callback (via its
    # event_callback hook) for every step; convert each whitelisted trace
    # event into an SSE StreamEvent on this run's channel.
    #
    # NOTE: AgentLoop keeps a single _event_callback slot. Concurrent runs
    # through other endpoints (which pass no callback) can overwrite the
    # slot mid-run; the trace_id guard below ensures this bridge never
    # forwards another run's events, and the run-level completion event is
    # always emitted from the returned result, so terminal state stays correct.
    def _on_trace_event(trace_event: TraceEvent) -> None:
        try:
            if getattr(trace_event, "trace_id", None) != context.trace_id:
                return
            stream_event = trace_to_stream_event(run_id, trace_event)
            if stream_event is not None:
                event_store.add_event(run_id, stream_event)
        except Exception as exc:  # bridging must never break the agent run
            logger.debug(f"trace bridge failed for run {run_id}: {exc}")

    # Start async execution in background
    async def run_agent_async():
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

        try:
            # Execute agent with the live trace-event bridge attached
            result = await agent.run(context, task, extra_context, event_callback=_on_trace_event)

            # Post-run tool details: arguments summary + result summary per call
            for tool_record in result.tool_calls:
                event_store.add_event(run_id, tool_call_to_result_event(run_id, tool_record))

            # Approval gate: surface pending tool approvals before completion.
            # Scope: tool approvals (resource_type == "tool") linked to this
            # tenant, or any approval linked to this run's trace. Stale
            # workflow-type approvals from other subsystems are not replayed
            # on every chat turn.
            approval_store = getattr(agent, "approval_store", None)
            pending_approvals: list[Any] = []
            if approval_store is not None:
                try:
                    candidates = list(
                        approval_store.list(limit=10, status=ApprovalStatus.PENDING, tenant_id=context.tenant_id)
                    )
                except TypeError:
                    try:
                        candidates = list(approval_store.list(limit=10, status=ApprovalStatus.PENDING))
                    except Exception as exc:
                        candidates = []
                        logger.debug(f"approval listing failed for run {run_id}: {exc}")
                except Exception as exc:
                    candidates = []
                    logger.debug(f"approval listing failed for run {run_id}: {exc}")
                pending_approvals = [
                    rec for rec in candidates
                    if str(getattr(rec, "resource_type", "") or "") == "tool"
                    or str(getattr(rec, "trace_id", "") or "") == context.trace_id
                ]
            if result.status == RunStatus.NEEDS_APPROVAL or pending_approvals:
                if not pending_approvals:
                    # Needs approval but store unavailable/unpopulated: generic notice
                    event_store.add_event(run_id, StreamEvent(
                        event_type="approval_required",
                        run_id=run_id,
                        data={"approval_id": None, "reason": "run is waiting for an approval decision"},
                    ))
                for approval_record in pending_approvals[:5]:
                    event_store.add_event(run_id, approval_to_event(run_id, approval_record))

            # Send completion event (terminal — closes open SSE streams)
            completion_event = CompletionEvent(
                run_id=run_id,
                status=result.status,
                result=result.answer,
                summary=result.execution_summary,
                sequence=sequence,
            )
            event_store.add_event(run_id, completion_event)

            # Save to run store (non-fatal: a persistence failure must not
            # append a spurious error event after the terminal completion)
            try:
                run_store.save(context, task, result)
            except Exception as save_exc:
                logger.warning(f"run_store.save failed for streaming run {run_id}: {save_exc}")

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
        "trace_id": context.trace_id,
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
    level: str = Query(default="info", pattern="^(debug|info|warning|error)$"),
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
    status: str = Query(..., pattern="^(pending|running|completed|failed)$"),
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

# B-4: /stream/health moved before /stream/{run_id} to fix route shadowing
