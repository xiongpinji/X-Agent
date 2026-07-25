"""Context management system for X-Agent.

Provides unified context management including:
- Automatic token compression
- Session persistence and recovery
- Hybrid memory system integration
- Intelligent context retrieval
- Code repository indexing
"""

import contextlib

from backend.app.core.context.agent_integration import (
    AgentLoopContextBridge,
    fit_messages_to_token_budget,
)
from backend.app.core.context.code_index import (
    CodebaseIndex,
    CodeMatch,
    DependencyEdge,
    DependencyGraph,
    FileNode,
    IndexStats,
    get_codebase_index,
    set_codebase_index,
)
from backend.app.core.context.context_manager import ContextManager, ContextMetrics
from backend.app.core.context.session_recovery import (
    Message,
    SessionMetadata,
    SessionRecovery,
    SessionSnapshot,
    SessionState,
    SessionStats,
)

# Conditional imports for optional modules
with contextlib.suppress(ImportError):
    from backend.app.core.context.compression import (
        CompressedChunk,
        CompressedContext,
        ContextCompressor,
        KeyInfo,
    )

with contextlib.suppress(ImportError):
    from backend.app.core.context.retrieval import (
        ContextItem,
        ContextRetriever,
        RetrievalWeights,
    )

__all__ = [
    "AgentLoopContextBridge",
    "CodeMatch",
    "CodebaseIndex",
    "CompressedChunk",
    "CompressedContext",
    "ContextCompressor",
    "ContextItem",
    "ContextManager",
    "ContextMetrics",
    "ContextRetriever",
    "DependencyEdge",
    "DependencyGraph",
    "FileNode",
    "IndexStats",
    "KeyInfo",
    "Message",
    "RetrievalWeights",
    "SessionMetadata",
    "SessionRecovery",
    "SessionSnapshot",
    "SessionState",
    "SessionStats",
    "fit_messages_to_token_budget",
    "get_codebase_index",
    "set_codebase_index",
]
