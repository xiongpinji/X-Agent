"""
Quick reference and integration examples for memory deduplication.

Provides ready-to-use code snippets and integration patterns.
"""

# ============================================================================
# QUICK REFERENCE CARD
# ============================================================================

"""
X-Agent 记忆去重系统 - 快速参考

1. 初始化服务
   service = initialize_deduplication_service()

2. 执行去重
   result = await service.deduplicate_memories(memories, strategy="combined")

3. 获取统计
   stats = service.get_service_stats()

4. 监控性能
   monitor = get_deduplication_monitor()
   metrics = monitor.get_metrics_summary(hours=24)

策略选择：
- "hash"      : 快速，精确匹配
- "vector"    : 准确，语义相似
- "time_window": 时间敏感
- "combined"  : 推荐，平衡

性能指标：
- 哈希：5000 mem/s
- 向量：667 mem/s
- 组合：1250 mem/s
"""

# ============================================================================
# INTEGRATION EXAMPLES
# ============================================================================

# Example 1: Basic Integration with MemorySystem
# ============================================================================

"""
集成示例1：与MemorySystem集成
"""

from backend.app.core.memory import MemorySystem
from backend.app.core.memory_deduplication_service import initialize_deduplication_service
from backend.app.core.contracts import RunContext
import asyncio


class EnhancedMemorySystem:
    """MemorySystem with integrated deduplication."""

    def __init__(self):
        self.memory_system = MemorySystem()
        self.dedup_service = initialize_deduplication_service(
            auto_deduplicate=True,
            dedup_interval_minutes=60,
        )

    async def store_with_dedup(
        self,
        context: RunContext,
        content: str,
        layer: int = 3,
        importance: float = 0.5,
    ) -> str:
        """Store memory with automatic deduplication."""
        # Store memory
        memory_id = await self.memory_system.store_layer(
            context,
            layer=layer,
            content=content,
            importance=importance,
        )

        # Auto-deduplicate if needed
        all_memories = self.memory_system._items
        result = await self.dedup_service.auto_deduplicate_if_needed(all_memories)

        if result:
            print(f"Auto-deduplication: removed {len(result.removed_ids)} duplicates")

        return memory_id

    async def search_with_dedup(
        self,
        context: RunContext,
        query: str,
        top_k: int = 5,
    ) -> list:
        """Search memories with deduplication."""
        # Search
        results = await self.memory_system.search(context, query, top_k=top_k)

        # Deduplicate results
        from backend.app.core.memory_deduplication_enhanced import Memory

        memories = [
            Memory(
                id=item.id,
                content=item.content,
                created_at=item.created_at,
                importance=item.importance,
            )
            for item in results
        ]

        dedup_result = await self.dedup_service.deduplicate_memories(
            memories,
            strategy="vector",
        )

        # Return deduplicated results
        return [r for r in results if r.id not in dedup_result.removed_ids]


# Example 2: Batch Processing Integration
# ============================================================================

"""
集成示例2：批量处理集成
"""

from backend.app.core.memory_deduplication_enhanced import Memory
from datetime import datetime, UTC
import asyncio


async def batch_import_and_deduplicate(
    memory_system,
    dedup_service,
    import_data: list[dict],
    batch_size: int = 1000,
):
    """Import and deduplicate memories in batches."""
    total_imported = 0
    total_removed = 0

    for i in range(0, len(import_data), batch_size):
        batch = import_data[i : i + batch_size]

        # Convert to Memory objects
        memories = [
            Memory(
                id=item["id"],
                content=item["content"],
                created_at=datetime.fromisoformat(item.get("created_at", datetime.now(UTC).isoformat())),
                importance=item.get("importance", 0.5),
            )
            for item in batch
        ]

        # Deduplicate batch
        result = await dedup_service.deduplicate_memories(
            memories,
            strategy="combined",
        )

        total_imported += result.deduplicated_count
        total_removed += len(result.removed_ids)

        print(
            f"Batch {i // batch_size + 1}: "
            f"imported {result.deduplicated_count}, "
            f"removed {len(result.removed_ids)}"
        )

    print(f"Total: imported {total_imported}, removed {total_removed}")
    return total_imported, total_removed


# Example 3: Incremental Deduplication
# ============================================================================

"""
集成示例3：增量去重集成
"""


async def incremental_sync(
    dedup_service,
    new_memories: list[Memory],
    existing_memories: list[Memory],
):
    """Sync new memories with incremental deduplication."""
    print(f"Syncing {len(new_memories)} new memories...")

    # Perform incremental deduplication
    result = await dedup_service.incremental_deduplicate(
        new_memories,
        existing_memories,
    )

    # Process results
    duplicates = result.removed_ids
    unique_new = [m for m in new_memories if m.id not in duplicates]

    print(f"Found {len(duplicates)} duplicates")
    print(f"Unique new memories: {len(unique_new)}")

    return unique_new, duplicates


# Example 4: Monitoring and Alerting
# ============================================================================

"""
集成示例4：监控和告警集成
"""

from backend.app.core.memory_deduplication_service import get_deduplication_monitor
import logging

logger = logging.getLogger(__name__)


class DeduplicationMonitoringService:
    """Service for monitoring deduplication health."""

    def __init__(self, alert_threshold: float = 0.15):
        self.monitor = get_deduplication_monitor()
        self.alert_threshold = alert_threshold

    def check_health(self) -> dict:
        """Check deduplication health and generate alerts."""
        metrics = self.monitor.get_metrics_summary(hours=24)
        anomalies = self.monitor.detect_anomalies()

        health_status = {
            "status": "healthy",
            "metrics": metrics,
            "anomalies": anomalies,
            "alerts": [],
        }

        # Check reduction rate
        if metrics["avg_reduction_rate"] < self.alert_threshold * 100:
            health_status["alerts"].append(
                f"Low reduction rate: {metrics['avg_reduction_rate']:.1f}% "
                f"(threshold: {self.alert_threshold * 100:.1f}%)"
            )
            health_status["status"] = "warning"

        # Check for anomalies
        if anomalies:
            health_status["alerts"].append(f"Detected {len(anomalies)} anomalies")
            health_status["status"] = "warning"

        # Log alerts
        for alert in health_status["alerts"]:
            logger.warning(f"Deduplication alert: {alert}")

        return health_status


# Example 5: Custom Strategy Selection
# ============================================================================

"""
集成示例5：自定义策略选择
"""


class AdaptiveDeduplicationService:
    """Service that adapts deduplication strategy based on data characteristics."""

    def __init__(self, dedup_service):
        self.dedup_service = dedup_service

    async def deduplicate_adaptive(self, memories: list[Memory]) -> dict:
        """Choose deduplication strategy based on memory characteristics."""
        if not memories:
            return {"strategy": "none", "result": None}

        # Analyze memory characteristics
        avg_content_length = sum(len(m.content) for m in memories) / len(memories)
        unique_hashes = len(set(m.content_hash for m in memories))
        hash_uniqueness = unique_hashes / len(memories)

        # Choose strategy
        if hash_uniqueness < 0.5:
            # Many exact duplicates, use hash
            strategy = "hash"
        elif avg_content_length > 10000:
            # Large content, use hash first
            strategy = "combined"
        elif len(memories) > 10000:
            # Large dataset, use hash for speed
            strategy = "hash"
        else:
            # Default to combined
            strategy = "combined"

        print(f"Selected strategy: {strategy}")
        print(f"  - Avg content length: {avg_content_length:.0f}")
        print(f"  - Hash uniqueness: {hash_uniqueness:.1%}")

        # Execute deduplication
        result = await self.dedup_service.deduplicate_memories(
            memories,
            strategy=strategy,
        )

        return {
            "strategy": strategy,
            "result": result,
            "stats": self.dedup_service.deduplicator.get_deduplication_stats(result),
        }


# Example 6: Graph Relationship Preservation
# ============================================================================

"""
集成示例6：图谱关系保留
"""

from backend.app.core.memory_graph_enhanced import EnhancedMemoryGraph, MemoryNode, MemoryRelation


async def deduplicate_with_graph_preservation(
    dedup_service,
    memories: list[Memory],
    graph: EnhancedMemoryGraph,
):
    """Deduplicate memories while preserving graph relationships."""
    # Add memories to graph
    for memory in memories:
        node = MemoryNode(
            id=memory.id,
            content=memory.content,
            created_at=memory.created_at.isoformat(),
        )
        graph.add_node(node)

    # Perform deduplication with relationship preservation
    result = await dedup_service.deduplicate_memories(
        memories,
        preserve_relationships=True,
    )

    # Verify relationships were preserved
    print(f"Graph nodes: {len(graph.nodes)}")
    print(f"Graph relations: {sum(len(rels) for rels in graph.relations.values())}")

    return result


# Example 7: Performance Optimization
# ============================================================================

"""
集成示例7：性能优化
"""

import time


class PerformanceOptimizedDeduplication:
    """Deduplication with performance optimization."""

    def __init__(self, dedup_service):
        self.dedup_service = dedup_service
        self.performance_log = []

    async def deduplicate_optimized(
        self,
        memories: list[Memory],
        target_time: float = 1.0,
    ) -> dict:
        """Deduplicate with performance optimization."""
        start_time = time.time()

        # Choose strategy based on size
        if len(memories) > 5000:
            strategy = "hash"  # Fast for large datasets
        elif len(memories) > 1000:
            strategy = "combined"  # Balanced
        else:
            strategy = "vector"  # Accurate for small datasets

        # Execute deduplication
        result = await self.dedup_service.deduplicate_memories(
            memories,
            strategy=strategy,
        )

        elapsed = time.time() - start_time

        # Log performance
        perf_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "memory_count": len(memories),
            "strategy": strategy,
            "elapsed_time": elapsed,
            "throughput": len(memories) / elapsed if elapsed > 0 else 0,
            "reduction_rate": (
                (result.original_count - result.deduplicated_count) /
                result.original_count * 100
                if result.original_count > 0 else 0
            ),
        }

        self.performance_log.append(perf_data)

        # Alert if performance is degraded
        if elapsed > target_time:
            logger.warning(
                f"Performance degradation: {elapsed:.2f}s > {target_time:.2f}s target"
            )

        return {
            "result": result,
            "performance": perf_data,
        }

    def get_performance_summary(self) -> dict:
        """Get performance summary."""
        if not self.performance_log:
            return {}

        times = [p["elapsed_time"] for p in self.performance_log]
        throughputs = [p["throughput"] for p in self.performance_log]

        return {
            "total_operations": len(self.performance_log),
            "avg_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "avg_throughput": sum(throughputs) / len(throughputs),
        }


# Example 8: Error Handling and Recovery
# ============================================================================

"""
集成示例8：错误处理和恢复
"""


class RobustDeduplicationService:
    """Deduplication service with error handling."""

    def __init__(self, dedup_service):
        self.dedup_service = dedup_service
        self.error_log = []

    async def deduplicate_safe(
        self,
        memories: list[Memory],
        strategy: str = "combined",
        fallback_strategy: str = "hash",
    ) -> dict:
        """Safely deduplicate with fallback strategy."""
        try:
            result = await self.dedup_service.deduplicate_memories(
                memories,
                strategy=strategy,
            )
            return {
                "success": True,
                "result": result,
                "strategy_used": strategy,
            }
        except Exception as e:
            logger.error(f"Deduplication failed with {strategy}: {e}")
            self.error_log.append({
                "timestamp": datetime.now(UTC).isoformat(),
                "strategy": strategy,
                "error": str(e),
            })

            # Try fallback strategy
            try:
                logger.info(f"Trying fallback strategy: {fallback_strategy}")
                result = await self.dedup_service.deduplicate_memories(
                    memories,
                    strategy=fallback_strategy,
                )
                return {
                    "success": True,
                    "result": result,
                    "strategy_used": fallback_strategy,
                    "fallback": True,
                }
            except Exception as e2:
                logger.error(f"Fallback strategy also failed: {e2}")
                return {
                    "success": False,
                    "error": str(e2),
                    "strategy_used": fallback_strategy,
                }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("X-Agent Memory Deduplication - Integration Examples")
    print("=" * 60)
    print()
    print("See code comments for detailed integration patterns:")
    print("1. Basic Integration with MemorySystem")
    print("2. Batch Processing Integration")
    print("3. Incremental Deduplication")
    print("4. Monitoring and Alerting")
    print("5. Custom Strategy Selection")
    print("6. Graph Relationship Preservation")
    print("7. Performance Optimization")
    print("8. Error Handling and Recovery")
