"""
高级记忆融合系统集成模块。

整合所有记忆融合组件，提供统一的API接口。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.app.core.memory.analytics import AnalyticsReport, MemoryAnalytics
from backend.app.core.memory.graph_enhancer import GraphEnhancer
from backend.app.core.memory.importance import (
    MemoryImportanceScorer,
)
from backend.app.core.memory.lifecycle import (
    MemoryLifecycleManager,
)
from backend.app.core.memory.merger import MemoryMerger
from backend.app.core.memory.retrieval_optimizer import (
    RetrieverOptimizer,
)

logger = logging.getLogger(__name__)


class AdvancedMemoryFusionSystem:
    """
    高级记忆融合系统。

    整合记忆合并、重要性评分、检索优化、图谱增强、
    生命周期管理和分析功能。
    """

    def __init__(
        self,
        enable_merger: bool = True,
        enable_importance_scoring: bool = True,
        enable_retrieval_optimization: bool = True,
        enable_graph_enhancement: bool = True,
        enable_lifecycle_management: bool = True,
        enable_analytics: bool = True,
    ):
        """
        初始化高级记忆融合系统。

        Args:
            enable_merger: 启用记忆合并
            enable_importance_scoring: 启用重要性评分
            enable_retrieval_optimization: 启用检索优化
            enable_graph_enhancement: 启用图谱增强
            enable_lifecycle_management: 启用生命周期管理
            enable_analytics: 启用分析
        """
        self.enable_merger = enable_merger
        self.enable_importance_scoring = enable_importance_scoring
        self.enable_retrieval_optimization = enable_retrieval_optimization
        self.enable_graph_enhancement = enable_graph_enhancement
        self.enable_lifecycle_management = enable_lifecycle_management
        self.enable_analytics = enable_analytics

        # 初始化各个组件
        self.merger = MemoryMerger() if enable_merger else None
        self.importance_scorer = (
            MemoryImportanceScorer() if enable_importance_scoring else None
        )
        self.retriever_optimizer = (
            RetrieverOptimizer() if enable_retrieval_optimization else None
        )
        self.graph_enhancer = (
            GraphEnhancer() if enable_graph_enhancement else None
        )
        self.lifecycle_manager = (
            MemoryLifecycleManager() if enable_lifecycle_management else None
        )
        self.analytics = MemoryAnalytics() if enable_analytics else None

        # 统计信息
        self._operation_count = 0
        self._last_operation_time = datetime.now(UTC)

    async def process_memories(
        self,
        memories: list[dict],
        embeddings: Any | None = None,
    ) -> dict[str, Any]:
        """
        处理记忆的完整流程。

        Args:
            memories: 记忆列表
            embeddings: 嵌入向量

        Returns:
            处理结果字典
        """
        result = {
            "original_count": len(memories),
            "processed_count": 0,
            "merge_stats": None,
            "importance_scores": {},
            "retrieval_stats": None,
            "graph_stats": None,
            "lifecycle_stats": None,
            "analytics_report": None,
        }

        # 1. 记忆合并
        if self.enable_merger and len(memories) > 1:
            merged_memories, merge_stats = await self.merger.merge_memories(
                memories, embeddings
            )
            result["merge_stats"] = merge_stats
            result["processed_count"] = len(merged_memories)
            memories = [
                {
                    "id": m.id,
                    "content": m.content,
                    "importance": m.importance,
                    "created_at": m.created_at,
                    "source_ids": m.source_ids,
                }
                for m in merged_memories
            ]
        else:
            result["processed_count"] = len(memories)

        # 2. 重要性评分
        if self.enable_importance_scoring:
            importance_scores = self.importance_scorer.batch_compute_importance(
                memories
            )
            result["importance_scores"] = {
                mid: {
                    "composite_score": scores.composite_score,
                    "access_frequency": scores.access_frequency_score,
                    "temporal_decay": scores.temporal_decay_score,
                    "association": scores.association_score,
                    "user_feedback": scores.user_feedback_score,
                }
                for mid, scores in importance_scores.items()
            }

        # 3. 图谱增强
        if self.enable_graph_enhancement:
            for mem in memories:
                self.graph_enhancer.add_memory_to_graph(
                    mem["id"],
                    mem["content"],
                    {"importance": mem.get("importance", 0.5)},
                )
            result["graph_stats"] = self.graph_enhancer.get_stats()

        # 4. 生命周期管理
        if self.enable_lifecycle_management:
            for mem in memories:
                await self.lifecycle_manager.process_memory_access(mem["id"])
            result["lifecycle_stats"] = self.lifecycle_manager.compute_stats()

        # 5. 分析
        if self.enable_analytics:
            for mem in memories:
                self.analytics.record_memory_event(
                    mem["id"],
                    "processed",
                    metadata={"importance": mem.get("importance", 0.5)},
                )

        self._operation_count += 1
        self._last_operation_time = datetime.now(UTC)

        logger.info(
            f"Processed {result['processed_count']} memories "
            f"(original: {result['original_count']})"
        )

        return result

    async def retrieve_memories(
        self,
        query: str,
        memories: list[dict],
        embeddings: Any | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        检索记忆。

        Args:
            query: 查询文本
            memories: 记忆列表
            embeddings: 嵌入向量
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        if not self.enable_retrieval_optimization:
            return memories[:top_k]

        results = await self.retriever_optimizer.hybrid_retrieve(
            query, memories, embeddings, top_k
        )

        # 记录检索事件
        if self.enable_analytics:
            for result in results:
                self.analytics.record_memory_event(
                    result.memory_id,
                    "retrieved",
                    metadata={"query": query, "rank": result.rank},
                )

        return [
            {
                "id": r.memory_id,
                "content": r.content,
                "score": r.score,
                "rank": r.rank,
                "vector_score": r.vector_score,
                "keyword_score": r.keyword_score,
            }
            for r in results
        ]

    async def cleanup_memories(self) -> dict[str, Any]:
        """
        清理过期的记忆。

        Returns:
            清理结果
        """
        if not self.enable_lifecycle_management:
            return {"skipped": True}

        cleanup_result = await self.lifecycle_manager.cleanup_expired_memories()
        return cleanup_result

    def get_system_stats(self) -> dict[str, Any]:
        """
        获取系统统计信息。

        Returns:
            统计信息字典
        """
        stats = {
            "operation_count": self._operation_count,
            "last_operation_time": self._last_operation_time.isoformat(),
        }

        if self.enable_merger and self.merger:
            stats["merge_history"] = len(self.merger.get_merge_history())

        if self.enable_importance_scoring and self.importance_scorer:
            stats["importance_weights"] = (
                self.importance_scorer.export_weights()
            )

        if self.enable_retrieval_optimization and self.retriever_optimizer:
            retrieval_stats = self.retriever_optimizer.get_stats()
            stats["retrieval_stats"] = {
                "query_count": retrieval_stats.query_count,
                "avg_latency_ms": retrieval_stats.avg_latency * 1000,
                "cache_hit_rate": retrieval_stats.cache_hit_rate,
            }

        if self.enable_graph_enhancement and self.graph_enhancer:
            graph_stats = self.graph_enhancer.get_stats()
            stats["graph_stats"] = {
                "node_count": graph_stats.node_count,
                "edge_count": graph_stats.edge_count,
                "density": graph_stats.density,
                "communities": graph_stats.communities,
            }

        if self.enable_lifecycle_management and self.lifecycle_manager:
            lifecycle_stats = self.lifecycle_manager.compute_stats()
            stats["lifecycle_stats"] = {
                "total_memories": lifecycle_stats.total_memories,
                "active_count": lifecycle_stats.active_count,
                "archived_count": lifecycle_stats.archived_count,
                "total_storage_mb": lifecycle_stats.total_storage_mb,
            }

        if self.enable_analytics and self.analytics:
            analytics_data = self.analytics.export_analytics()
            stats["analytics"] = analytics_data

        return stats

    def get_visualization_data(self) -> dict[str, Any]:
        """
        获取用于可视化的数据。

        Returns:
            可视化数据
        """
        data = {}

        if self.enable_graph_enhancement and self.graph_enhancer:
            data["graph"] = self.graph_enhancer.get_visualization_data()

        if self.enable_lifecycle_management and self.lifecycle_manager:
            lifecycle_stats = self.lifecycle_manager.compute_stats()
            data["lifecycle"] = {
                "active": lifecycle_stats.active_count,
                "warm": lifecycle_stats.warm_count,
                "cold": lifecycle_stats.cold_count,
                "archived": lifecycle_stats.archived_count,
            }

        if self.enable_analytics and self.analytics:
            quality_dist = self.analytics.get_quality_distribution()
            data["quality"] = quality_dist

        return data

    async def generate_report(
        self,
        memories: list[dict],
        period_days: int = 30,
    ) -> AnalyticsReport | None:
        """
        生成分析报告。

        Args:
            memories: 记忆列表
            period_days: 分析周期

        Returns:
            分析报告
        """
        if not self.enable_analytics:
            return None

        return self.analytics.generate_report(memories, period_days)

    def clear_caches(self) -> None:
        """清空所有缓存。"""
        if self.enable_merger and self.merger:
            self.merger.clear_cache()

        if self.enable_retrieval_optimization and self.retriever_optimizer:
            self.retriever_optimizer.clear_cache()

        logger.info("Cleared all caches")

    def reset_stats(self) -> None:
        """重置统计信息。"""
        self._operation_count = 0
        self._last_operation_time = datetime.now(UTC)

        if self.enable_retrieval_optimization and self.retriever_optimizer:
            self.retriever_optimizer.reset_stats()

        logger.info("Reset all statistics")
