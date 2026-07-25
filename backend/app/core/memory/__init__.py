"""
记忆融合系统包初始化模块。
"""

from backend.app.core.memory.analytics import (
    AnalyticsReport,
    CoverageAnalysis,
    MemoryAnalytics,
    MemoryQualityMetrics,
)
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem
from backend.app.core.memory.graph_enhancer import (
    Entity,
    GraphEnhancer,
    GraphStats,
    Relation,
)
from backend.app.core.memory.importance import (
    ImportanceScores,
    ImportanceWeights,
    MemoryImportanceScorer,
)
from backend.app.core.memory.lifecycle import (
    LifecycleEvent,
    LifecyclePolicy,
    LifecycleStats,
    MemoryLifecycleManager,
    MemoryState,
)
from backend.app.core.memory.merger import (
    MemoryMerger,
    MergedMemory,
    MergeStats,
)
from backend.app.core.memory.retrieval_optimizer import (
    RetrievalResult,
    RetrievalStats,
    RetrieverOptimizer,
)
from backend.app.core.memory.store import (
    InMemoryMemorySystem,
    MemoryConsolidationResult,
    MemoryExportBundle,
    MemoryItem,
    MemoryPollutionReport,
    MemoryRevision,
    MemoryRollbackResult,
    MemoryScope,
    MemorySearchHit,
    MemorySystem,
    MemoryUpdateResult,
    SessionRecord,
    memory_system,
)

__all__ = [
    # System
    "AdvancedMemoryFusionSystem",
    "AnalyticsReport",
    "CoverageAnalysis",
    "Entity",
    # Graph
    "GraphEnhancer",
    "GraphStats",
    "ImportanceScores",
    "ImportanceWeights",
    "InMemoryMemorySystem",
    "LifecycleEvent",
    "LifecyclePolicy",
    "LifecycleStats",
    # Analytics
    "MemoryAnalytics",
    "MemoryConsolidationResult",
    "MemoryExportBundle",
    # Importance
    "MemoryImportanceScorer",
    "MemoryItem",
    # Lifecycle
    "MemoryLifecycleManager",
    # Merger
    "MemoryMerger",
    "MemoryPollutionReport",
    "MemoryQualityMetrics",
    "MemoryRevision",
    "MemoryRollbackResult",
    # Store (L1-L10 core memory system)
    "MemoryScope",
    "MemorySearchHit",
    "MemoryState",
    "MemorySystem",
    "MemoryUpdateResult",
    "MergeStats",
    "MergedMemory",
    "Relation",
    "RetrievalResult",
    "RetrievalStats",
    # Retrieval
    "RetrieverOptimizer",
    "SessionRecord",
    "memory_system",
]
