"""Context management system for X-Agent.

Provides unified context management including:
- Automatic token compression
- Session persistence and recovery
- Hybrid memory system integration
- Intelligent context retrieval
- Code repository indexing
"""

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
from backend.app.core.context.agent_integration import (
    AgentLoopContextBridge,
    fit_messages_to_token_budget,
)

# Conditional imports for optional modules
try:
    from backend.app.core.context.compression import (
        CompressedChunk,
        CompressedContext,
        ContextCompressor,
        KeyInfo,
    )
except ImportError:
    pass

try:
    from backend.app.core.context.retrieval import (
        ContextItem,
        ContextRetriever,
        RetrievalWeights,
    )
except ImportError:
    pass

__all__ = [
    "AgentLoopContextBridge",
    "fit_messages_to_token_budget",
    "CodebaseIndex",
    "CodeMatch",
    "DependencyEdge",
    "DependencyGraph",
    "FileNode",
    "IndexStats",
    "get_codebase_index",
    "set_codebase_index",
    "ContextManager",
    "ContextMetrics",
    "Message",
    "SessionMetadata",
    "SessionRecovery",
    "SessionSnapshot",
    "SessionState",
    "SessionStats",
]
