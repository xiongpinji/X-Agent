"""
记忆融合系统包初始化模块。
"""

from backend.app.core.memory.store import (
    MemoryScope,
    MemoryRevision,
    MemoryItem,
    SessionRecord,
    MemorySearchHit,
    MemoryConsolidationResult,
    MemoryUpdateResult,
    MemoryRollbackResult,
    MemoryPollutionReport,
    MemoryExportBundle,
    MemorySystem,
    memory_system,
    InMemoryMemorySystem,
)
from backend.app.core.memory.merger import (
    MemoryMerger,
    MergedMemory,
    MergeStats,
)
from backend.app.core.memory.importance import (
    MemoryImportanceScorer,
    ImportanceScores,
    ImportanceWeights,
)
from backend.app.core.memory.retrieval_optimizer import (
    RetrieverOptimizer,
    RetrievalResult,
    RetrievalStats,
)
from backend.app.core.memory.graph_enhancer import (
    GraphEnhancer,
    Entity,
    Relation,
    GraphStats,
)
from backend.app.core.memory.lifecycle import (
    MemoryLifecycleManager,
    MemoryState,
    LifecyclePolicy,
    LifecycleEvent,
    LifecycleStats,
)
from backend.app.core.memory.analytics import (
    MemoryAnalytics,
    MemoryQualityMetrics,
    CoverageAnalysis,
    AnalyticsReport,
)
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem

__all__ = [
    # Store (L1-L10 core memory system)
    "MemoryScope",
    "MemoryRevision",
    "MemoryItem",
    "SessionRecord",
    "MemorySearchHit",
    "MemoryConsolidationResult",
    "MemoryUpdateResult",
    "MemoryRollbackResult",
    "MemoryPollutionReport",
    "MemoryExportBundle",
    "MemorySystem",
    "memory_system",
    "InMemoryMemorySystem",
    # Merger
    "MemoryMerger",
    "MergedMemory",
    "MergeStats",
    # Importance
    "MemoryImportanceScorer",
    "ImportanceScores",
    "ImportanceWeights",
    # Retrieval
    "RetrieverOptimizer",
    "RetrievalResult",
    "RetrievalStats",
    # Graph
    "GraphEnhancer",
    "Entity",
    "Relation",
    "GraphStats",
    # Lifecycle
    "MemoryLifecycleManager",
    "MemoryState",
    "LifecyclePolicy",
    "LifecycleEvent",
    "LifecycleStats",
    # Analytics
    "MemoryAnalytics",
    "MemoryQualityMetrics",
    "CoverageAnalysis",
    "AnalyticsReport",
    # System
    "AdvancedMemoryFusionSystem",
]
