"""
Event Emitter for Streaming API

Provides utilities for emitting events to the streaming API during agent execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional
from functools import wraps

from backend.app.api.streaming import (
    event_store,
    MessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    ProgressEvent,
    ErrorEvent,
    LogEvent,
    MetricEvent,
    TaskStatusEvent,
)

logger = logging.getLogger(__name__)


class StreamEventEmitter:
    """Utility class for emitting streaming events."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.step_count = 0
        self.total_steps = 0

    def emit_message(
        self,
        content: str,
        role: str = "assistant",
    ) -> None:
        """Emit a message event."""
        event = MessageEvent(
            run_id=self.run_id,
            content=content,
            role=role,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted message event for run {self.run_id}")

    def emit_tool_call(
        self,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
    ) -> None:
        """Emit a tool call event."""
        event = ToolCallEvent(
            run_id=self.run_id,
            tool_name=tool_name,
            tool_id=tool_id,
            arguments=arguments,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted tool_call event for run {self.run_id}: {tool_name}")

    def emit_tool_result(
        self,
        tool_id: str,
        tool_name: str,
        result: Any,
        success: bool = True,
    ) -> None:
        """Emit a tool result event."""
        event = ToolResultEvent(
            run_id=self.run_id,
            tool_id=tool_id,
            tool_name=tool_name,
            result=result,
            success=success,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted tool_result event for run {self.run_id}: {tool_name}")

    def emit_progress(
        self,
        overall_progress: float,
        current_step: str,
        total_steps: int,
        completed_steps: int,
        estimated_time_remaining: Optional[int] = None,
    ) -> None:
        """Emit a progress event."""
        event = ProgressEvent(
            run_id=self.run_id,
            overall_progress=overall_progress,
            current_step=current_step,
            total_steps=total_steps,
            completed_steps=completed_steps,
        )
        # Add estimated time if provided
        if estimated_time_remaining is not None:
            event.estimated_time_remaining = estimated_time_remaining

        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted progress event for run {self.run_id}: {overall_progress:.1%}")

    def emit_error(
        self,
        error_code: str,
        error_message: str,
        error_details: Optional[dict[str, Any]] = None,
        recoverable: bool = False,
    ) -> None:
        """Emit an error event."""
        event = ErrorEvent(
            run_id=self.run_id,
            error_code=error_code,
            error_message=error_message,
            error_details=error_details or {},
            recoverable=recoverable,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted error event for run {self.run_id}: {error_code}")

    def emit_log(
        self,
        message: str,
        level: str = "info",
        source: str = "agent",
    ) -> None:
        """Emit a log event."""
        event = LogEvent(
            run_id=self.run_id,
            level=level,
            message=message,
            source=source,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted log event for run {self.run_id}: {level}")

    def emit_metric(
        self,
        metric_name: str,
        metric_value: float | int | str,
        unit: str = "",
    ) -> None:
        """Emit a metric event."""
        event = MetricEvent(
            run_id=self.run_id,
            metric_name=metric_name,
            metric_value=metric_value,
            unit=unit,
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted metric event for run {self.run_id}: {metric_name}")

    def emit_task_status(
        self,
        task_id: str,
        status: str,
        title: str = "",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit a task status event."""
        event = TaskStatusEvent(
            run_id=self.run_id,
            task_id=task_id,
            status=status,
            title=title,
            details=details or {},
        )
        event_store.add_event(self.run_id, event)
        logger.debug(f"Emitted task_status event for run {self.run_id}: {task_id}")

    def set_total_steps(self, total: int) -> None:
        """Set the total number of steps."""
        self.total_steps = total

    def update_progress(self, completed: int, current_step: str = "") -> None:
        """Update progress with step count."""
        self.step_count = completed
        if self.total_steps > 0:
            progress = completed / self.total_steps
            self.emit_progress(
                overall_progress=progress,
                current_step=current_step,
                total_steps=self.total_steps,
                completed_steps=completed,
            )


def stream_event(event_type: str) -> Callable:
    """
    Decorator for automatically emitting stream events.

    Usage:
        @stream_event("tool_execution")
        async def execute_tool(emitter: StreamEventEmitter, tool_name: str, args: dict):
            # Automatically emits tool_call and tool_result events
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            emitter = kwargs.get("emitter")
            if not emitter or not isinstance(emitter, StreamEventEmitter):
                return await func(*args, **kwargs)

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return wrapper

    return decorator


# Global emitter instance (should be created per run)
_emitter: Optional[StreamEventEmitter] = None


def get_emitter(run_id: str) -> StreamEventEmitter:
    """Get or create the global emitter for a run."""
    global _emitter
    if _emitter is None or _emitter.run_id != run_id:
        _emitter = StreamEventEmitter(run_id)
    return _emitter


def set_emitter(emitter: StreamEventEmitter) -> None:
    """Set the global emitter."""
    global _emitter
    _emitter = emitter
