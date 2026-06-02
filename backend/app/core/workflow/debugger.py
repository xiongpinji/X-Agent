"""Workflow Debugger and Execution Tracing

Implements debugging capabilities:
- Breakpoint management
- Single-step execution
- Variable inspection
- Execution history
- Performance analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Callable, Awaitable
from uuid import uuid4


class BreakpointType(StrEnum):
    LINE = "line"
    CONDITIONAL = "conditional"
    EXCEPTION = "exception"
    WATCH = "watch"


class ExecutionState(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass
class Breakpoint:
    """Breakpoint definition"""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: BreakpointType = BreakpointType.LINE
    node_id: str = ""
    condition: str | None = None
    hit_count: int = 0
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ExecutionFrame:
    """Single execution frame"""
    node_id: str
    node_type: str
    id: str = field(default_factory=lambda: str(uuid4()))
    state: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class WatchExpression:
    """Watch expression for debugging"""
    id: str = field(default_factory=lambda: str(uuid4()))
    expression: str = ""
    current_value: Any = None
    previous_value: Any = None
    changed: bool = False
    last_evaluated: datetime | None = None


class BreakpointManager:
    """Manages breakpoints"""

    def __init__(self):
        self.breakpoints: dict[str, Breakpoint] = {}
        self.breakpoint_hits: list[dict[str, Any]] = []

    def add_breakpoint(
        self,
        node_id: str,
        breakpoint_type: BreakpointType = BreakpointType.LINE,
        condition: str | None = None,
    ) -> Breakpoint:
        """Add breakpoint"""
        breakpoint = Breakpoint(
            type=breakpoint_type,
            node_id=node_id,
            condition=condition,
        )
        self.breakpoints[breakpoint.id] = breakpoint
        return breakpoint

    def remove_breakpoint(self, breakpoint_id: str) -> bool:
        """Remove breakpoint"""
        return self.breakpoints.pop(breakpoint_id, None) is not None

    def enable_breakpoint(self, breakpoint_id: str) -> bool:
        """Enable breakpoint"""
        bp = self.breakpoints.get(breakpoint_id)
        if bp:
            bp.enabled = True
            return True
        return False

    def disable_breakpoint(self, breakpoint_id: str) -> bool:
        """Disable breakpoint"""
        bp = self.breakpoints.get(breakpoint_id)
        if bp:
            bp.enabled = False
            return True
        return False

    def get_breakpoints_for_node(self, node_id: str) -> list[Breakpoint]:
        """Get breakpoints for node"""
        return [bp for bp in self.breakpoints.values() if bp.node_id == node_id and bp.enabled]

    def should_break(
        self,
        node_id: str,
        context: dict[str, Any],
    ) -> bool:
        """Check if should break at node"""
        breakpoints = self.get_breakpoints_for_node(node_id)
        for bp in breakpoints:
            if bp.type == BreakpointType.LINE:
                return True
            elif bp.type == BreakpointType.CONDITIONAL and bp.condition:
                from .data_flow import ExpressionEvaluator
                result = ExpressionEvaluator.evaluate(bp.condition, context)
                if result:
                    return True
        return False

    def record_hit(self, breakpoint_id: str, context: dict[str, Any]) -> None:
        """Record breakpoint hit"""
        bp = self.breakpoints.get(breakpoint_id)
        if bp:
            bp.hit_count += 1
            self.breakpoint_hits.append({
                "breakpoint_id": breakpoint_id,
                "node_id": bp.node_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "context_keys": list(context.keys()),
            })


class ExecutionTracer:
    """Traces workflow execution"""

    def __init__(self):
        self.frames: list[ExecutionFrame] = []
        self.current_frame: ExecutionFrame | None = None
        self.execution_start: datetime | None = None
        self.execution_end: datetime | None = None

    def start_frame(
        self,
        node_id: str,
        node_type: str,
        inputs: dict[str, Any],
    ) -> ExecutionFrame:
        """Start execution frame"""
        frame = ExecutionFrame(
            node_id=node_id,
            node_type=node_type,
            inputs=inputs,
        )
        self.frames.append(frame)
        self.current_frame = frame
        if self.execution_start is None:
            self.execution_start = datetime.now(UTC)
        return frame

    def end_frame(
        self,
        output: Any = None,
        error: str | None = None,
    ) -> ExecutionFrame | None:
        """End execution frame"""
        if self.current_frame is None:
            return None

        self.current_frame.output = output
        self.current_frame.error = error
        self.current_frame.duration_ms = (
            datetime.now(UTC) - self.current_frame.timestamp
        ).total_seconds() * 1000

        frame = self.current_frame
        if len(self.frames) > 1:
            self.current_frame = self.frames[-2]
        else:
            self.current_frame = None
            self.execution_end = datetime.now(UTC)

        return frame

    def get_call_stack(self) -> list[ExecutionFrame]:
        """Get current call stack"""
        return self.frames.copy()

    def get_frame_by_node(self, node_id: str) -> ExecutionFrame | None:
        """Get frame by node ID"""
        for frame in reversed(self.frames):
            if frame.node_id == node_id:
                return frame
        return None

    def get_execution_summary(self) -> dict[str, Any]:
        """Get execution summary"""
        total_duration = 0.0
        if self.execution_start and self.execution_end:
            total_duration = (self.execution_end - self.execution_start).total_seconds() * 1000

        return {
            "total_frames": len(self.frames),
            "total_duration_ms": total_duration,
            "frames_with_errors": len([f for f in self.frames if f.error]),
            "average_frame_duration_ms": (
                total_duration / len(self.frames) if self.frames else 0
            ),
            "slowest_frame": self._get_slowest_frame(),
            "execution_start": self.execution_start.isoformat() if self.execution_start else None,
            "execution_end": self.execution_end.isoformat() if self.execution_end else None,
        }

    def _get_slowest_frame(self) -> dict[str, Any] | None:
        """Get slowest frame"""
        if not self.frames:
            return None
        slowest = max(self.frames, key=lambda f: f.duration_ms)
        return {
            "node_id": slowest.node_id,
            "node_type": slowest.node_type,
            "duration_ms": slowest.duration_ms,
        }


class WorkflowDebugger:
    """Debugger for workflows"""

    def __init__(self):
        self.breakpoint_manager = BreakpointManager()
        self.execution_tracer = ExecutionTracer()
        self.watch_expressions: dict[str, WatchExpression] = {}
        self.state: ExecutionState = ExecutionState.STOPPED
        self.pause_reason: str | None = None

    async def debug_execute(
        self,
        workflow_id: str,
        executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
        context: dict[str, Any],
    ) -> Any:
        """Execute workflow with debugging"""
        self.state = ExecutionState.RUNNING

        try:
            result = await executor(workflow_id, context)
            self.state = ExecutionState.COMPLETED
            return result
        except Exception as e:
            self.state = ExecutionState.STOPPED
            self.pause_reason = str(e)
            raise

    def add_watch(self, expression: str) -> WatchExpression:
        """Add watch expression"""
        watch = WatchExpression(expression=expression)
        self.watch_expressions[watch.id] = watch
        return watch

    def remove_watch(self, watch_id: str) -> bool:
        """Remove watch expression"""
        return self.watch_expressions.pop(watch_id, None) is not None

    def evaluate_watches(self, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate all watch expressions"""
        from .data_flow import ExpressionEvaluator

        results = {}
        for watch_id, watch in self.watch_expressions.items():
            try:
                new_value = ExpressionEvaluator.evaluate(watch.expression, context)
                watch.previous_value = watch.current_value
                watch.current_value = new_value
                watch.changed = watch.previous_value != new_value
                watch.last_evaluated = datetime.now(UTC)
                results[watch_id] = {
                    "expression": watch.expression,
                    "value": new_value,
                    "changed": watch.changed,
                }
            except Exception as e:
                results[watch_id] = {
                    "expression": watch.expression,
                    "error": str(e),
                }

        return results

    def get_debug_info(self) -> dict[str, Any]:
        """Get debug information"""
        return {
            "state": self.state,
            "pause_reason": self.pause_reason,
            "breakpoints": len(self.breakpoint_manager.breakpoints),
            "breakpoint_hits": len(self.breakpoint_manager.breakpoint_hits),
            "execution_frames": len(self.execution_tracer.frames),
            "watch_expressions": len(self.watch_expressions),
            "execution_summary": self.execution_tracer.get_execution_summary(),
            "call_stack": [
                {
                    "node_id": f.node_id,
                    "node_type": f.node_type,
                    "duration_ms": f.duration_ms,
                }
                for f in self.execution_tracer.get_call_stack()
            ],
        }

    def get_variable_snapshot(self, context: dict[str, Any]) -> dict[str, Any]:
        """Get snapshot of variables"""
        return {
            "variables": context.copy(),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_performance_report(self) -> dict[str, Any]:
        """Get performance analysis report"""
        frames = self.execution_tracer.frames
        if not frames:
            return {}

        node_stats = {}
        for frame in frames:
            if frame.node_id not in node_stats:
                node_stats[frame.node_id] = {
                    "count": 0,
                    "total_ms": 0.0,
                    "min_ms": float("inf"),
                    "max_ms": 0.0,
                }

            stats = node_stats[frame.node_id]
            stats["count"] += 1
            stats["total_ms"] += frame.duration_ms
            stats["min_ms"] = min(stats["min_ms"], frame.duration_ms)
            stats["max_ms"] = max(stats["max_ms"], frame.duration_ms)

        # Calculate averages
        for stats in node_stats.values():
            stats["avg_ms"] = stats["total_ms"] / stats["count"]

        return {
            "total_frames": len(frames),
            "node_statistics": node_stats,
            "slowest_nodes": sorted(
                node_stats.items(),
                key=lambda x: x[1]["max_ms"],
                reverse=True,
            )[:10],
        }
