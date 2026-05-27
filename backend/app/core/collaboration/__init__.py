"""Multi-Agent Collaboration System for X-Agent.

This package provides a comprehensive framework for coordinating multiple agents
to work together on complex tasks. It includes:

- Communication protocols for inter-agent messaging
- Agent registry for discovery and capability management
- Task dispatcher for distributing work across agents
- State synchronization for distributed state management
- Result aggregation for combining partial results
- Collaboration patterns (Pipeline, MapReduce, Master-Worker, P2P)
- Monitoring and performance tracking
"""

from backend.app.core.collaboration.protocol import (
    Message,
    MessageType,
    Request,
    Response,
    Event,
    MessageRouter,
)
from backend.app.core.collaboration.registry import (
    AgentCapability,
    AgentInfo,
    AgentRegistry,
)
from backend.app.core.collaboration.dispatcher import (
    Task,
    TaskDispatcher,
    DispatchStrategy,
)
from backend.app.core.collaboration.state_sync import (
    StateSnapshot,
    StateManager,
)
from backend.app.core.collaboration.aggregator import (
    ResultAggregator,
    AggregationStrategy,
)
from backend.app.core.collaboration.patterns import (
    CollaborationPattern,
    PipelinePattern,
    MapReducePattern,
    MasterWorkerPattern,
)
from backend.app.core.collaboration.monitor import (
    CollaborationMonitor,
    TaskMetrics,
)

__all__ = [
    "Message",
    "MessageType",
    "Request",
    "Response",
    "Event",
    "MessageRouter",
    "AgentCapability",
    "AgentInfo",
    "AgentRegistry",
    "Task",
    "TaskDispatcher",
    "DispatchStrategy",
    "StateSnapshot",
    "StateManager",
    "ResultAggregator",
    "AggregationStrategy",
    "CollaborationPattern",
    "PipelinePattern",
    "MapReducePattern",
    "MasterWorkerPattern",
    "CollaborationMonitor",
    "TaskMetrics",
]
