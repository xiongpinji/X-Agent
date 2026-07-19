"""Multi-Agent Collaboration (chat-room store) for X-Agent.

Only the in-memory chat-room CollaborationStore remains in this package;
it is used by api/collaboration.py, api/org.py and core/dispatch.py.

The task-collaboration framework (protocol / registry / dispatcher /
state_sync / aggregator / patterns / monitor / benchmarks / examples)
had zero production callers and was archived on 2026-07-19 to
archive/dead_code_2026-07-19/backend/app/core/collaboration/.
"""

from backend.app.core.collaboration.store import (
    CollaborationMessage,
    CollaborationRoom,
    CollaborationStore,
    collaboration_store,
)

__all__ = [
    "CollaborationMessage",
    "CollaborationRoom",
    "CollaborationStore",
    "collaboration_store",
]
