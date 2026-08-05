"""Multi-Agent Collaboration (chat-room store + runtime delegation) for X-Agent.

Live surface of this package:

- ``store``: chat-room CollaborationStore used by api/collaboration.py,
  api/org.py and core/dispatch.py. In-memory by default (dev-only); set
  ``XAGENT_COLLABORATION_STORE_PATH`` for durable JSON snapshot persistence.
- ``delegation``: runtime task delegation — capability matching + round-robin
  load balancing on top of agent_spawner (real sub-AgentLoops), with
  core.dispatch wired in for org-aware candidate ranking.
- ``orchestrator``: MultiAgentOrchestrator for structured multi-agent
  orchestration (parallel/sequential/hierarchical modes), used by
  api/multi_agent.py (P2-01，2026-08-04 决策：保留不挂载——G3 路由预算
  300/300 零余量，挂载需路由预算评审；有测试维护)。

The task-collaboration framework (protocol / registry / dispatcher /
state_sync / aggregator / patterns / monitor / benchmarks / examples)
had zero production callers and was archived on 2026-07-19 to
archive/dead_code_2026-07-19/backend/app/core/collaboration/. Do not resurrect
it; build on the live modules above.

P1-09 Collaboration Module Convergence Map
-------------------------------------------
Canonical modules (use these):

- ``core/collaboration/`` (THIS package)
    Rooms, delegation, orchestration.
- ``core/parallel_agent_executor.py``
    Independent parallel fan-out (used by api/parallel_agents.py).

Archived (P1-09 batch A, 2026-08-04 — zero production callers):

- ``core/task_dispatcher.py`` / ``core/agent_coordinator.py`` /
  ``core/parallel_executor.py`` / ``core/agent_recovery.py``
    幽灵协作模块（唯一引用方为测试/演示脚本），归档至
    archive/dead_code_2026-08/backend/app/core/，引用测试同步拆分随迁。

Archived (P1-09 batch C, 2026-08-04 — deprecated 簇闭环，零生产引用):

- ``core/parallel_execution_engine.py`` / ``core/parallel_execution_benchmark.py``
    Superseded by parallel_agent_executor.py；engine↔benchmark 互引闭环，无生产引用。
- ``core/advanced_features.py``（含 MultiAgentCoordinator / TaskScheduler /
  AdaptivePlanner / LearningEngine）
    唯一生产引用方为 engine（TaskScheduler），随 engine 一并归档。

Agent-to-agent 通信协议裁决（P1-09 批次 C）：
``core/agent_communication_bus.py`` 为唯一通信面，其 messages send/broadcast/
publish/stats 4 端点已挂载（api/parallel_agents.py 主 router）。
"""

from backend.app.core.collaboration.delegation import (
    CandidateSpec,
    CollaborationDelegator,
    DelegationError,
    DelegationRequest,
    DelegationResult,
    NoCapableAgentError,
    RoundRobinBalancer,
    delegate_subtask,
    delegator,
    get_delegator,
)
from backend.app.core.collaboration.store import (
    CollaborationMessage,
    CollaborationRoom,
    CollaborationStore,
    collaboration_store,
)

__all__ = [
    "CandidateSpec",
    "CollaborationDelegator",
    "CollaborationMessage",
    "CollaborationRoom",
    "CollaborationStore",
    "DelegationError",
    "DelegationRequest",
    "DelegationResult",
    "NoCapableAgentError",
    "RoundRobinBalancer",
    "collaboration_store",
    "delegate_subtask",
    "delegator",
    "get_delegator",
]
