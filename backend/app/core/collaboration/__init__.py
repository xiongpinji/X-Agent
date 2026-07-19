"""Multi-Agent Collaboration (chat-room store + runtime delegation) for X-Agent.

Live surface of this package:

- ``store``: chat-room CollaborationStore used by api/collaboration.py,
  api/org.py and core/dispatch.py. In-memory by default (dev-only); set
  ``XAGENT_COLLABORATION_STORE_PATH`` for durable JSON snapshot persistence.
- ``delegation``: runtime task delegation — capability matching + round-robin
  load balancing on top of agent_spawner (real sub-AgentLoops), with
  core.dispatch wired in for org-aware candidate ranking.

The task-collaboration framework (protocol / registry / dispatcher /
state_sync / aggregator / patterns / monitor / benchmarks / examples)
had zero production callers and was archived on 2026-07-19 to
archive/dead_code_2026-07-19/backend/app/core/collaboration/. Do not resurrect
it; build on the live modules above.
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
