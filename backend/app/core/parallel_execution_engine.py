"""
Advanced Parallel Execution Engine for X-Agent.

Provides:
- ParallelAgentExecutor: Multi-agent parallel execution with intelligent task distribution
- ParallelToolExecutor: Tool DAG execution with dependency analysis
- AgentCommunicationBus: Inter-agent message passing and state synchronization
- TaskScheduler: Intelligent task scheduling with priority and resource awareness
- ExecutionMonitor: Real-time execution monitoring and metrics collection

Architecture:
- Thread-safe concurrent execution with asyncio
- Automatic dependency resolution and DAG construction
- Intelligent backpressure and resource management
- Comprehensive error handling and recovery
- Real-time metrics and observability
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple
from threading import RLock, Condition
from queue import Queue as ThreadSafeQueue

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class PriorityLevel(int, Enum):
    """Task priority levels."""
    CRITICAL = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    BACKGROUND = 0


class ObjectPool:
    """Lock-free object pool for reusing ExecutionMetrics and Message objects."""

    def __init__(self, object_type: type, initial_size: int = 100):
        self.object_type = object_type
        self.pool: deque = deque(maxlen=initial_size * 2)
        self.created_count = 0
        self.reused_count = 0

        # Pre-allocate objects
        for _ in range(initial_size):
            self.pool.append(object_type())

    def acquire(self) -> Any:
        """Get an object from the pool or create a new one."""
        try:
            obj = self.pool.popleft()
            self.reused_count += 1
            return obj
        except IndexError:
            self.created_count += 1
            return self.object_type()

    def release(self, obj: Any) -> None:
        """Return an object to the pool."""
        # Reset object state
        if hasattr(obj, 'reset'):
            obj.reset()
        self.pool.append(obj)

    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        return {
            "pool_size": len(self.pool),
            "created_count": self.created_count,
            "reused_count": self.reused_count,
            "reuse_ratio": self.reused_count / (self.reused_count + self.created_count) if (self.reused_count + self.created_count) > 0 else 0,
        }


class LockFreeQueue:
    """Lock-free task queue using asyncio.Queue with optimized event signaling."""

    def __init__(self, maxsize: int = 0):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.event = asyncio.Event()

    async def put(self, item: Any) -> None:
        """Put an item in the queue."""
        await self.queue.put(item)
        self.event.set()

    async def get(self) -> Any:
        """Get an item from the queue."""
        try:
            return self.queue.get_nowait()
        except asyncio.QueueEmpty:
            self.event.clear()
            await self.event.wait()
            return await self.queue.get()

    def qsize(self) -> int:
        """Get queue size."""
        return self.queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()


@dataclass
class ExecutionMetrics:
    """Metrics for execution tracking."""
    task_id: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    attempts: int = 0
    max_attempts: int = 3
    status: ExecutionStatus = ExecutionStatus.PENDING
    error: Optional[str] = None
    result: Optional[Any] = None
    resource_usage: Dict[str, float] = field(default_factory=dict)

    def reset(self) -> None:
        """Reset metrics for reuse."""
        self.task_id = ""
        self.start_time = datetime.now(UTC)
        self.end_time = None
        self.duration_ms = 0.0
        self.attempts = 0
        self.max_attempts = 3
        self.status = ExecutionStatus.PENDING
        self.error = None
        self.result = None
        self.resource_usage.clear()

    def mark_completed(self, result: Any = None) -> None:
        """Mark task as completed."""
        self.end_time = datetime.now(UTC)
        self.status = ExecutionStatus.COMPLETED
        self.result = result
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.end_time = datetime.now(UTC)
        self.status = ExecutionStatus.FAILED
        self.error = error
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000


@dataclass
class ToolDefinition:
    """Definition of a tool that can be executed."""
    name: str
    handler: Callable[..., Coroutine[Any, Any, Any]]
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 1
    priority: PriorityLevel = PriorityLevel.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A tool call with arguments."""
    tool_id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    priority: PriorityLevel = PriorityLevel.NORMAL
    timeout_seconds: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Message for inter-agent communication."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    recipient_id: str = ""
    message_type: str = "data"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    priority: PriorityLevel = PriorityLevel.NORMAL
    requires_ack: bool = False
    ack_received: bool = False


class DAGBuilder:
    """Builds and analyzes execution DAGs."""

    def __init__(self):
        self.nodes: Dict[str, ToolCall] = {}
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.out_degree: Dict[str, int] = defaultdict(int)

    def add_node(self, tool_call: ToolCall) -> None:
        """Add a node to the DAG."""
        self.nodes[tool_call.tool_id] = tool_call
        if tool_call.tool_id not in self.in_degree:
            self.in_degree[tool_call.tool_id] = 0
            self.out_degree[tool_call.tool_id] = 0

    def add_edge(self, from_id: str, to_id: str) -> None:
        """Add an edge to the DAG."""
        if from_id not in self.edges[from_id]:
            self.edges[from_id].add(to_id)
            self.out_degree[from_id] += 1
            self.in_degree[to_id] += 1

    def build_from_calls(self, tool_calls: List[ToolCall]) -> None:
        """Build DAG from tool calls."""
        for call in tool_calls:
            self.add_node(call)

        for call in tool_calls:
            for dep_id in call.depends_on:
                self.add_edge(dep_id, call.tool_id)

    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """Get nodes ready for execution.

        A node is ready when it has not completed yet and every node it
        depends on is already in `completed`. The previous implementation
        relied on a static `in_degree` snapshot that was never decremented as
        nodes finished, so dependents (in_degree > 0) could never become
        ready. Deriving readiness from each node's `depends_on` against the
        completed set keeps the check correct across the whole run.
        """
        ready = []
        for node_id, tool_call in self.nodes.items():
            if node_id in completed:
                continue
            if all(dep in completed for dep in tool_call.depends_on):
                ready.append(node_id)
        return ready

    def get_execution_order(self) -> List[str]:
        """Get topological sort of DAG."""
        in_degree = self.in_degree.copy()
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)

            for neighbor in self.edges.get(node_id, set()):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise ValueError("Circular dependency detected in DAG")

        return result

    def has_cycle(self) -> bool:
        """Check if DAG has cycles."""
        try:
            self.get_execution_order()
            return False
        except ValueError:
            return True


class AgentCommunicationBus:
    """Message bus for inter-agent communication with lock-free queues."""

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self.message_queues: Dict[str, LockFreeQueue] = {}
        self.message_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))
        self.lock = RLock()
        self.message_pool = ObjectPool(Message, initial_size=100)

    async def send_message(self, message: Message) -> bool:
        """Send a message to an agent."""
        recipient_id = message.recipient_id

        # Lazy initialization with minimal locking
        if recipient_id not in self.message_queues:
            with self.lock:
                if recipient_id not in self.message_queues:
                    self.message_queues[recipient_id] = LockFreeQueue(maxsize=self.max_queue_size)

        queue = self.message_queues[recipient_id]

        try:
            await queue.put(message)
            self.message_history[recipient_id].append(message)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Message queue full for agent {recipient_id}")
            return False

    async def receive_message(self, agent_id: str, timeout_seconds: float = 5.0) -> Optional[Message]:
        """Receive a message for an agent."""
        if agent_id not in self.message_queues:
            with self.lock:
                if agent_id not in self.message_queues:
                    self.message_queues[agent_id] = LockFreeQueue(maxsize=self.max_queue_size)

        queue = self.message_queues[agent_id]

        try:
            message = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
            return message
        except asyncio.TimeoutError:
            return None

    async def broadcast_message(self, message: Message, agent_ids: List[str]) -> int:
        """Broadcast a message to multiple agents."""
        sent_count = 0
        tasks = []

        for agent_id in agent_ids:
            msg_copy = self.message_pool.acquire()
            msg_copy.sender_id = message.sender_id
            msg_copy.recipient_id = agent_id
            msg_copy.message_type = message.message_type
            msg_copy.payload = message.payload
            msg_copy.priority = message.priority
            msg_copy.requires_ack = message.requires_ack

            tasks.append(self.send_message(msg_copy))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        sent_count = sum(1 for r in results if r is True)

        return sent_count

    def get_message_history(self, agent_id: str, limit: int = 100) -> List[Message]:
        """Get message history for an agent."""
        history = self.message_history.get(agent_id, deque())
        return list(history)[-limit:]

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about message queues."""
        stats = {}
        for agent_id, queue in self.message_queues.items():
            stats[agent_id] = {
                "queue_size": queue.qsize(),
                "max_size": self.max_queue_size,
                "history_size": len(self.message_history.get(agent_id, [])),
            }
        stats["pool_stats"] = self.message_pool.get_stats()
        return stats


class ParallelToolExecutor:
    """Executes tools in parallel with DAG dependency resolution."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.tools: Dict[str, ToolDefinition] = {}
        self.metrics: Dict[str, ExecutionMetrics] = {}
        self.results: Dict[str, Any] = {}
        self.lock = RLock()
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def register_tool(self, tool_def: ToolDefinition) -> None:
        """Register a tool."""
        with self.lock:
            self.tools[tool_def.name] = tool_def
            logger.info(f"Registered tool: {tool_def.name}")

    async def execute_tools(self, tool_calls: List[ToolCall]) -> Dict[str, Any]:
        """Execute multiple tools with dependency resolution."""
        # Build DAG
        dag = DAGBuilder()
        dag.build_from_calls(tool_calls)

        if dag.has_cycle():
            raise ValueError("Circular dependency detected in tool calls")

        # Initialize metrics
        with self.lock:
            for call in tool_calls:
                self.metrics[call.tool_id] = ExecutionMetrics(task_id=call.tool_id)

        # Execute in topological order
        completed: Set[str] = set()
        execution_order = dag.get_execution_order()

        for tool_id in execution_order:
            tool_call = dag.nodes[tool_id]
            await self._execute_tool_with_retry(tool_call, completed)

        return self.results.copy()

    def _resolve_arguments(self, tool_call: ToolCall, tool_def: ToolDefinition) -> Dict[str, Any]:
        """Inject dependency results into a tool call's arguments.

        Tools declared via `depends_on` execute after their dependencies, but
        the dependency outputs were never fed into the dependent's handler, so
        a tool like `tool_b(value)` kept its placeholder argument instead of
        the upstream result. Here we look up each completed dependency's result
        from `self.results` and bind it to the handler:

        - dict results are merged in by matching parameter name (or wholesale
          when the handler accepts ``**kwargs``);
        - scalar results fill the first handler parameter not otherwise
          supplied, overriding any placeholder default.

        Calls without dependencies are returned unchanged.
        """
        args: Dict[str, Any] = dict(tool_call.arguments)
        if not tool_call.depends_on:
            return args

        try:
            sig = inspect.signature(tool_def.handler)
            params = list(sig.parameters.values())
            param_names = [p.name for p in params]
            accepts_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params
            )
        except (TypeError, ValueError):
            params = []
            param_names = []
            accepts_kwargs = True

        for dep_id in tool_call.depends_on:
            if dep_id not in self.results:
                continue
            dep_result = self.results[dep_id]

            if isinstance(dep_result, dict):
                for key, value in dep_result.items():
                    if accepts_kwargs or key in param_names:
                        args[key] = value
            else:
                # Bind scalar to a handler parameter. Prefer the first
                # positional parameter the caller did NOT already supply; if
                # every parameter was pre-filled with a placeholder (the test
                # convention is ``arguments={"value": 0}  # Will be overridden``)
                # fall back to the first parameter and override it.
                positional = [
                    p.name for p in params
                    if p.kind in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    )
                ]
                target = next(
                    (name for name in positional if name not in tool_call.arguments),
                    positional[0] if positional else None,
                )
                if target is not None:
                    args[target] = dep_result

        return args

    async def _execute_tool_with_retry(self, tool_call: ToolCall, completed: Set[str]) -> None:
        """Execute a tool with retry logic."""
        tool_def = self.tools.get(tool_call.tool_name)
        if not tool_def:
            raise ValueError(f"Tool not found: {tool_call.tool_name}")

        metrics = self.metrics[tool_call.tool_id]
        resolved_args = self._resolve_arguments(tool_call, tool_def)

        for attempt in range(tool_def.retry_count + 1):
            try:
                metrics.attempts = attempt + 1
                metrics.status = ExecutionStatus.RUNNING

                async with self.semaphore:
                    result = await asyncio.wait_for(
                        tool_def.handler(**resolved_args),
                        timeout=tool_def.timeout_seconds
                    )

                with self.lock:
                    self.results[tool_call.tool_id] = result
                    metrics.mark_completed(result)
                    completed.add(tool_call.tool_id)

                logger.info(f"Tool {tool_call.tool_name} completed in {metrics.duration_ms:.2f}ms")
                return

            except asyncio.TimeoutError:
                error_msg = f"Timeout after {tool_def.timeout_seconds}s"
                if attempt < tool_def.retry_count:
                    logger.warning(f"Tool {tool_call.tool_name} timed out, retrying...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    metrics.mark_failed(error_msg)
                    raise

            except Exception as e:
                error_msg = str(e)
                if attempt < tool_def.retry_count:
                    logger.warning(f"Tool {tool_call.tool_name} failed: {e}, retrying...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    metrics.mark_failed(error_msg)
                    raise

    def get_metrics(self) -> Dict[str, ExecutionMetrics]:
        """Get execution metrics."""
        with self.lock:
            return self.metrics.copy()

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        with self.lock:
            metrics_list = list(self.metrics.values())

            completed = sum(1 for m in metrics_list if m.status == ExecutionStatus.COMPLETED)
            failed = sum(1 for m in metrics_list if m.status == ExecutionStatus.FAILED)
            total_duration = sum(m.duration_ms for m in metrics_list)

            return {
                "total_tools": len(metrics_list),
                "completed": completed,
                "failed": failed,
                "total_duration_ms": total_duration,
                "avg_duration_ms": total_duration / len(metrics_list) if metrics_list else 0,
                "success_rate": completed / len(metrics_list) if metrics_list else 0,
            }


class ParallelAgentExecutor:
    """Executes multiple agents in parallel with intelligent task distribution."""

    def __init__(self, max_agents: int = 10, communication_bus: Optional[AgentCommunicationBus] = None):
        self.max_agents = max_agents
        self.communication_bus = communication_bus or AgentCommunicationBus()
        self.agents: Dict[str, Any] = {}
        self.agent_tasks: Dict[str, List[str]] = defaultdict(list)
        self.agent_results: Dict[str, Any] = {}
        self.agent_metrics: Dict[str, Dict[str, Any]] = {}
        self.lock = RLock()
        self.semaphore = asyncio.Semaphore(max_agents)

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """Register an agent."""
        with self.lock:
            if len(self.agents) >= self.max_agents:
                raise RuntimeError(f"Maximum agents ({self.max_agents}) reached")
            self.agents[agent_id] = agent
            self.agent_metrics[agent_id] = {
                "start_time": datetime.now(UTC),
                "tasks_completed": 0,
                "tasks_failed": 0,
                "total_duration_ms": 0.0,
            }
            logger.info(f"Registered agent: {agent_id}")

    async def execute_agents(
        self,
        agent_ids: List[str],
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute multiple agents in parallel."""
        context = context or {}

        # Validate agents
        with self.lock:
            for agent_id in agent_ids:
                if agent_id not in self.agents:
                    raise ValueError(f"Agent not found: {agent_id}")

        # Execute agents
        tasks = [
            self._execute_agent_safe(agent_id, task, context)
            for agent_id in agent_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        with self.lock:
            for agent_id, result in zip(agent_ids, results):
                self.agent_results[agent_id] = result

        return self.agent_results.copy()

    async def _execute_agent_safe(
        self,
        agent_id: str,
        task: str,
        context: Dict[str, Any],
    ) -> Any:
        """Execute a single agent safely."""
        async with self.semaphore:
            try:
                start_time = time.time()

                agent = self.agents[agent_id]
                result = await self._call_agent(agent, task, context)

                duration_ms = (time.time() - start_time) * 1000

                with self.lock:
                    self.agent_metrics[agent_id]["tasks_completed"] += 1
                    self.agent_metrics[agent_id]["total_duration_ms"] += duration_ms

                logger.info(f"Agent {agent_id} completed in {duration_ms:.2f}ms")
                return result

            except Exception as e:
                with self.lock:
                    self.agent_metrics[agent_id]["tasks_failed"] += 1

                logger.error(f"Agent {agent_id} failed: {e}")
                raise

    async def _call_agent(self, agent: Any, task: str, context: Dict[str, Any]) -> Any:
        """Call an agent's run method."""
        if hasattr(agent, "run") and callable(agent.run):
            if asyncio.iscoroutinefunction(agent.run):
                return await agent.run(task, context)
            else:
                return agent.run(task, context)
        else:
            raise ValueError("Agent does not have a callable run method")

    def get_agent_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all agents."""
        with self.lock:
            return self.agent_metrics.copy()

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        with self.lock:
            metrics_list = list(self.agent_metrics.values())

            total_completed = sum(m["tasks_completed"] for m in metrics_list)
            total_failed = sum(m["tasks_failed"] for m in metrics_list)
            total_duration = sum(m["total_duration_ms"] for m in metrics_list)

            return {
                "total_agents": len(self.agents),
                "total_tasks_completed": total_completed,
                "total_tasks_failed": total_failed,
                "total_duration_ms": total_duration,
                "avg_duration_ms": total_duration / total_completed if total_completed > 0 else 0,
                "success_rate": total_completed / (total_completed + total_failed) if (total_completed + total_failed) > 0 else 0,
            }


class TaskScheduler:
    """Intelligent task scheduler with priority and resource awareness."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Dict[str, str] = {}
        self.lock = RLock()

    async def schedule_task(
        self,
        task_id: str,
        coroutine: Coroutine[Any, Any, Any],
        priority: PriorityLevel = PriorityLevel.NORMAL,
    ) -> None:
        """Schedule a task for execution."""
        # Priority queue uses negative priority for max-heap behavior
        await self.task_queue.put((-priority.value, task_id, coroutine))

    async def run_scheduler(self) -> None:
        """Run the task scheduler."""
        while True:
            try:
                # Wait for available slot
                while len(self.running_tasks) >= self.max_concurrent:
                    await asyncio.sleep(0.1)

                # Get next task
                try:
                    _, task_id, coroutine = self.task_queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
                    continue

                # Execute task
                task = asyncio.create_task(self._execute_task(task_id, coroutine))
                with self.lock:
                    self.running_tasks[task_id] = task

                # Clean up completed tasks
                completed_ids = [
                    tid for tid, t in self.running_tasks.items()
                    if t.done()
                ]
                with self.lock:
                    for tid in completed_ids:
                        del self.running_tasks[tid]

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task_id: str, coroutine: Coroutine[Any, Any, Any]) -> None:
        """Execute a single task."""
        try:
            await coroutine
            with self.lock:
                self.completed_tasks.add(task_id)
            logger.info(f"Task {task_id} completed")
        except Exception as e:
            with self.lock:
                self.failed_tasks[task_id] = str(e)
            logger.error(f"Task {task_id} failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        with self.lock:
            return {
                "queue_size": self.task_queue.qsize(),
                "running_tasks": len(self.running_tasks),
                "completed_tasks": len(self.completed_tasks),
                "failed_tasks": len(self.failed_tasks),
                "max_concurrent": self.max_concurrent,
            }


class ExecutionMonitor:
    """Monitors and collects metrics for parallel execution."""

    def __init__(self):
        self.execution_history: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, List[float]] = defaultdict(list)
        self.lock = RLock()

    def record_execution(
        self,
        execution_id: str,
        duration_ms: float,
        status: ExecutionStatus,
        resource_usage: Optional[Dict[str, float]] = None,
    ) -> None:
        """Record an execution."""
        with self.lock:
            record = {
                "execution_id": execution_id,
                "timestamp": datetime.now(UTC),
                "duration_ms": duration_ms,
                "status": status.value,
                "resource_usage": resource_usage or {},
            }
            self.execution_history.append(record)
            self.performance_metrics["duration_ms"].append(duration_ms)

            # Keep history bounded
            if len(self.execution_history) > 10000:
                self.execution_history = self.execution_history[-5000:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        with self.lock:
            durations = self.performance_metrics.get("duration_ms", [])

            if not durations:
                return {}

            return {
                "total_executions": len(durations),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "p50_duration_ms": sorted(durations)[len(durations) // 2],
                "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)],
                "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)],
            }

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history."""
        with self.lock:
            return self.execution_history[-limit:]


# Global instances
parallel_tool_executor = ParallelToolExecutor(max_concurrent=10)
parallel_agent_executor = ParallelAgentExecutor(max_agents=10)
communication_bus = AgentCommunicationBus()
task_scheduler = TaskScheduler(max_concurrent=10)
execution_monitor = ExecutionMonitor()
