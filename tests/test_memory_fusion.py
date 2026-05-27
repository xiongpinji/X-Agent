"""
高级记忆融合系统测试套件。

测试所有记忆融合组件的功能。
"""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
import numpy as np

from backend.app.core.memory.merger import MemoryMerger, MergedMemory
from backend.app.core.memory.importance import (
    MemoryImportanceScorer,
    ImportanceWeights,
)
from backend.app.core.memory.retrieval_optimizer import RetrieverOptimizer
from backend.app.core.memory.graph_enhancer import GraphEnhancer
from backend.app.core.memory.lifecycle import (
    MemoryLifecycleManager,
    MemoryState,
    LifecyclePolicy,
)
from backend.app.core.memory.analytics import MemoryAnalytics
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem


class TestMemoryMerger:
    """测试记忆合并模块。"""

    def test_merge_similar_memories(self):
        """测试合并相似的记忆。"""
        merger = MemoryMerger(similarity_threshold=0.8)

        memories = [
            {
                "id": "mem1",
                "content": "Python is a programming language",
                "importance": 0.8,
                "created_at": datetime.now(UTC),
                "access_count": 5,
            },
            {
                "id": "mem2",
                "content": "Python is used for programming",
                "importance": 0.7,
                "created_at": datetime.now(UTC),
                "access_count": 3,
            },
        ]

        # 创建嵌入向量
        embeddings = np.array([
            np.random.randn(128),
            np.random.randn(128),
        ])

        merged, stats = asyncio.run(
            merger.merge_memories(memories, embeddings)
        )

        assert len(merged) <= len(memories)
        assert stats.original_count == 2
        assert stats.total_reduction >= 0

    def test_merge_stats(self):
        """测试合并统计信息。"""
        merger = MemoryMerger()

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory content {i}",
                "importance": 0.5,
                "created_at": datetime.now(UTC),
            }
            for i in range(5)
        ]

        merged, stats = asyncio.run(
            merger.merge_memories(memories)
        )

        assert stats.original_count == 5
        assert stats.merged_count > 0
        assert stats.processing_time >= 0


class TestMemoryImportanceScorer:
    """测试记忆重要性评分模块。"""

    def test_compute_importance(self):
        """测试计算重要性。"""
        scorer = MemoryImportanceScorer()

        scores = scorer.compute_importance(
            memory_id="mem1",
            created_at=datetime.now(UTC) - timedelta(days=1),
            access_count=10,
            association_count=5,
            user_feedback=0.5,
        )

        assert 0 <= scores.composite_score <= 1
        assert 0 <= scores.access_frequency_score <= 1
        assert 0 <= scores.temporal_decay_score <= 1
        assert 0 <= scores.association_score <= 1
        assert 0 <= scores.user_feedback_score <= 1

    def test_adjust_weights(self):
        """测试调整权重。"""
        scorer = MemoryImportanceScorer()

        original_weights = scorer.weights.access_frequency_weight

        scorer.adjust_weights(access_frequency_weight=0.5)

        assert scorer.weights.access_frequency_weight == 0.5
        assert abs(
            sum([
                scorer.weights.access_frequency_weight,
                scorer.weights.temporal_decay_weight,
                scorer.weights.association_weight,
                scorer.weights.user_feedback_weight,
            ]) - 1.0
        ) < 0.01

    def test_batch_compute_importance(self):
        """测试批量计算重要性。"""
        scorer = MemoryImportanceScorer()

        memories = [
            {
                "id": f"mem{i}",
                "created_at": datetime.now(UTC),
                "access_count": i * 2,
            }
            for i in range(5)
        ]

        scores = scorer.batch_compute_importance(memories)

        assert len(scores) == 5
        assert all(0 <= s.composite_score <= 1 for s in scores.values())


class TestRetrieverOptimizer:
    """测试检索优化模块。"""

    def test_hybrid_retrieve(self):
        """测试混合检索。"""
        optimizer = RetrieverOptimizer()

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory about topic {i}",
                "metadata": {},
            }
            for i in range(10)
        ]

        embeddings = np.random.randn(10, 128)

        results = asyncio.run(
            optimizer.hybrid_retrieve(
                "topic",
                memories,
                embeddings,
                top_k=5,
            )
        )

        assert len(results) <= 5
        assert all(0 <= r.score <= 1 for r in results)
        assert all(r.rank > 0 for r in results)

    def test_cache_functionality(self):
        """测试缓存功能。"""
        optimizer = RetrieverOptimizer(cache_size=10)

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory {i}",
                "metadata": {},
            }
            for i in range(5)
        ]

        # 第一次查询
        results1 = asyncio.run(
            optimizer.hybrid_retrieve("test", memories, top_k=3)
        )
        cache_misses_1 = optimizer.stats.cache_misses

        # 第二次相同查询
        results2 = asyncio.run(
            optimizer.hybrid_retrieve("test", memories, top_k=3)
        )
        cache_hits_1 = optimizer.stats.cache_hits

        assert cache_hits_1 > 0
        assert len(results1) == len(results2)


class TestGraphEnhancer:
    """测试图谱增强模块。"""

    def test_add_memory_to_graph(self):
        """测试添加记忆到图谱。"""
        enhancer = GraphEnhancer()

        enhancer.add_memory_to_graph(
            "mem1",
            "This is about Python programming",
            {"importance": 0.8},
        )

        assert "mem1" in enhancer.entities
        assert enhancer.stats.node_count > 0

    def test_find_related_memories(self):
        """测试查找相关记忆。"""
        enhancer = GraphEnhancer()

        for i in range(5):
            enhancer.add_memory_to_graph(
                f"mem{i}",
                f"Memory about topic {i}",
            )

        related = enhancer.find_related_memories("mem0", depth=2, limit=3)

        assert len(related) <= 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in related)

    def test_detect_communities(self):
        """测试社区检测。"""
        enhancer = GraphEnhancer()

        for i in range(10):
            enhancer.add_memory_to_graph(f"mem{i}", f"Memory {i}")

        communities = enhancer.detect_communities()

        assert len(communities) > 0
        assert all(isinstance(c, list) for c in communities)


class TestMemoryLifecycleManager:
    """测试生命周期管理模块。"""

    def test_process_memory_access(self):
        """测试处理记忆访问。"""
        manager = MemoryLifecycleManager()

        asyncio.run(manager.process_memory_access("mem1"))

        assert "mem1" in manager.memory_states
        assert manager.memory_states["mem1"] == MemoryState.ACTIVE

    def test_state_transitions(self):
        """测试状态转换。"""
        manager = MemoryLifecycleManager()

        # 创建记忆
        asyncio.run(manager.process_memory_access("mem1"))

        # 更新元数据
        manager.update_memory_metadata("mem1", importance=0.9)

        # 检查状态
        state = manager.get_memory_state("mem1")
        assert state in [MemoryState.ACTIVE, MemoryState.WARM, MemoryState.COLD]

    def test_archive_and_restore(self):
        """测试归档和恢复。"""
        manager = MemoryLifecycleManager()

        asyncio.run(manager.process_memory_access("mem1"))
        asyncio.run(manager.archive_memory("mem1", "Testing"))

        assert manager.get_memory_state("mem1") == MemoryState.ARCHIVED

        asyncio.run(manager.restore_memory("mem1", "Testing"))

        assert manager.get_memory_state("mem1") == MemoryState.ACTIVE

    def test_compute_stats(self):
        """测试计算统计信息。"""
        manager = MemoryLifecycleManager()

        for i in range(5):
            asyncio.run(manager.process_memory_access(f"mem{i}"))

        stats = manager.compute_stats()

        assert stats.total_memories == 5
        assert stats.active_count > 0


class TestMemoryAnalytics:
    """测试分析模块。"""

    def test_assess_memory_quality(self):
        """测试评估记忆质量。"""
        analytics = MemoryAnalytics()

        metrics = analytics.assess_memory_quality(
            "mem1",
            "This is a comprehensive memory with details and context",
            access_count=10,
            importance=0.8,
        )

        assert 0 <= metrics.overall_quality <= 1
        assert 0 <= metrics.completeness <= 1
        assert 0 <= metrics.accuracy <= 1

    def test_analyze_coverage(self):
        """测试分析覆盖度。"""
        analytics = MemoryAnalytics()

        memories = [
            {"content": "system architecture details"},
            {"content": "user interaction patterns"},
            {"content": "error handling mechanisms"},
        ]

        coverage = analytics.analyze_coverage(memories)

        assert coverage.total_topics > 0
        assert coverage.covered_topics >= 0
        assert 0 <= coverage.coverage_percentage <= 100

    def test_generate_report(self):
        """测试生成报告。"""
        analytics = MemoryAnalytics()

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory {i}",
                "created_at": datetime.now(UTC),
            }
            for i in range(10)
        ]

        report = analytics.generate_report(memories, period_days=30)

        assert report.total_memories == 10
        assert report.avg_quality >= 0
        assert len(report.recommendations) >= 0


class TestAdvancedMemoryFusionSystem:
    """测试高级记忆融合系统。"""

    def test_system_initialization(self):
        """测试系统初始化。"""
        system = AdvancedMemoryFusionSystem()

        assert system.merger is not None
        assert system.importance_scorer is not None
        assert system.retriever_optimizer is not None
        assert system.graph_enhancer is not None
        assert system.lifecycle_manager is not None
        assert system.analytics is not None

    def test_process_memories(self):
        """测试处理记忆。"""
        system = AdvancedMemoryFusionSystem()

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory content {i}",
                "importance": 0.5,
                "created_at": datetime.now(UTC),
            }
            for i in range(5)
        ]

        result = asyncio.run(system.process_memories(memories))

        assert result["original_count"] == 5
        assert result["processed_count"] > 0
        assert result["merge_stats"] is not None
        assert len(result["importance_scores"]) > 0

    def test_retrieve_memories(self):
        """测试检索记忆。"""
        system = AdvancedMemoryFusionSystem()

        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory about topic {i}",
            }
            for i in range(10)
        ]

        results = asyncio.run(
            system.retrieve_memories("topic", memories, top_k=5)
        )

        assert len(results) <= 5
        assert all("id" in r and "score" in r for r in results)

    def test_get_system_stats(self):
        """测试获取系统统计信息。"""
        system = AdvancedMemoryFusionSystem()

        stats = system.get_system_stats()

        assert "operation_count" in stats
        assert "last_operation_time" in stats
        assert stats["operation_count"] >= 0

    def test_cleanup_memories(self):
        """测试清理记忆。"""
        system = AdvancedMemoryFusionSystem()

        result = asyncio.run(system.cleanup_memories())

        assert isinstance(result, dict)

    def test_clear_caches(self):
        """测试清空缓存。"""
        system = AdvancedMemoryFusionSystem()

        system.clear_caches()

        # 验证缓存已清空
        assert len(system.retriever_optimizer._cache) == 0

    def test_reset_stats(self):
        """测试重置统计信息。"""
        system = AdvancedMemoryFusionSystem()

        system._operation_count = 100
        system.reset_stats()

        assert system._operation_count == 0


class TestIntegration:
    """集成测试。"""

    def test_end_to_end_workflow(self):
        """测试端到端工作流。"""
        system = AdvancedMemoryFusionSystem()

        # 创建记忆
        memories = [
            {
                "id": f"mem{i}",
                "content": f"Memory about Python programming {i}",
                "importance": 0.5 + i * 0.1,
                "created_at": datetime.now(UTC),
                "access_count": i,
            }
            for i in range(10)
        ]

        # 处理记忆
        process_result = asyncio.run(system.process_memories(memories))
        assert process_result["processed_count"] > 0

        # 检索记忆
        retrieval_result = asyncio.run(
            system.retrieve_memories("Python", memories, top_k=5)
        )
        assert len(retrieval_result) > 0

        # 生成报告
        report = asyncio.run(system.generate_report(memories))
        assert report is not None
        assert report.total_memories > 0

        # 获取统计信息
        stats = system.get_system_stats()
        assert stats["operation_count"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
