"""
高级记忆融合系统性能基准测试。

测试各个模块的性能指标。
"""

import asyncio
import time
import numpy as np
from datetime import datetime, UTC
from backend.app.core.memory.merger import MemoryMerger
from backend.app.core.memory.importance import MemoryImportanceScorer
from backend.app.core.memory.retrieval_optimizer import RetrieverOptimizer
from backend.app.core.memory.graph_enhancer import GraphEnhancer
from backend.app.core.memory.lifecycle import MemoryLifecycleManager
from backend.app.core.memory.analytics import MemoryAnalytics
from backend.app.core.memory.fusion_system import AdvancedMemoryFusionSystem


class PerformanceBenchmark:
    """性能基准测试。"""

    def __init__(self):
        self.results = {}

    def generate_test_memories(self, count: int) -> list[dict]:
        """生成测试记忆。"""
        memories = []
        for i in range(count):
            memories.append({
                "id": f"mem_{i}",
                "content": f"Memory content about topic {i % 10}. "
                          f"This is a test memory with some details. "
                          f"It contains information about various topics.",
                "importance": 0.3 + (i % 10) * 0.07,
                "created_at": datetime.now(UTC),
                "access_count": i % 20,
                "metadata": {"source": "test"},
            })
        return memories

    def generate_embeddings(self, count: int, dim: int = 128) -> np.ndarray:
        """生成测试嵌入向量。"""
        return np.random.randn(count, dim).astype(np.float32)

    async def benchmark_merger(self, memory_counts: list[int]) -> dict:
        """基准测试记忆合并。"""
        print("\n=== 记忆合并性能测试 ===")
        results = {}

        merger = MemoryMerger()

        for count in memory_counts:
            memories = self.generate_test_memories(count)
            embeddings = self.generate_embeddings(count)

            start_time = time.time()
            merged, stats = await merger.merge_memories(memories, embeddings)
            elapsed = time.time() - start_time

            results[count] = {
                "original": count,
                "merged": stats.merged_count,
                "reduction": f"{stats.total_reduction:.1f}%",
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")

        return results

    def benchmark_importance_scorer(self, memory_counts: list[int]) -> dict:
        """基准测试重要性评分。"""
        print("\n=== 重要性评分性能测试 ===")
        results = {}

        scorer = MemoryImportanceScorer()

        for count in memory_counts:
            memories = self.generate_test_memories(count)

            start_time = time.time()
            scores = scorer.batch_compute_importance(memories)
            elapsed = time.time() - start_time

            results[count] = {
                "count": count,
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")

        return results

    async def benchmark_retriever(self, memory_counts: list[int]) -> dict:
        """基准测试检索优化。"""
        print("\n=== 检索优化性能测试 ===")
        results = {}

        optimizer = RetrieverOptimizer()

        for count in memory_counts:
            memories = self.generate_test_memories(count)
            embeddings = self.generate_embeddings(count)

            # 预热缓存
            await optimizer.hybrid_retrieve(
                "test query",
                memories,
                embeddings,
                top_k=10,
            )

            # 测试缓存命中
            start_time = time.time()
            for _ in range(10):
                await optimizer.hybrid_retrieve(
                    "test query",
                    memories,
                    embeddings,
                    top_k=10,
                    use_cache=True,
                )
            elapsed_cached = time.time() - start_time

            # 测试缓存未命中
            optimizer.clear_cache()
            start_time = time.time()
            for _ in range(10):
                await optimizer.hybrid_retrieve(
                    f"query_{np.random.randint(0, 1000)}",
                    memories,
                    embeddings,
                    top_k=10,
                    use_cache=True,
                )
            elapsed_uncached = time.time() - start_time

            stats = optimizer.get_stats()

            results[count] = {
                "count": count,
                "cached_time_ms": elapsed_cached * 1000,
                "uncached_time_ms": elapsed_uncached * 1000,
                "cache_hit_rate": f"{stats.cache_hit_rate:.1%}",
            }

            print(f"  {count} 条记忆 (缓存): {elapsed_cached*1000:.1f}ms")
            print(f"  {count} 条记忆 (无缓存): {elapsed_uncached*1000:.1f}ms")

        return results

    def benchmark_graph_enhancer(self, memory_counts: list[int]) -> dict:
        """基准测试图谱增强。"""
        print("\n=== 图谱增强性能测试 ===")
        results = {}

        for count in memory_counts:
            memories = self.generate_test_memories(count)
            enhancer = GraphEnhancer()

            start_time = time.time()
            for mem in memories:
                enhancer.add_memory_to_graph(
                    mem["id"],
                    mem["content"],
                    {"importance": mem["importance"]},
                )
            elapsed = time.time() - start_time

            stats = enhancer.get_stats()

            results[count] = {
                "count": count,
                "nodes": stats.node_count,
                "edges": stats.edge_count,
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")
            print(f"    节点: {stats.node_count}, 边: {stats.edge_count}")

        return results

    async def benchmark_lifecycle_manager(self, memory_counts: list[int]) -> dict:
        """基准测试生命周期管理。"""
        print("\n=== 生命周期管理性能测试 ===")
        results = {}

        for count in memory_counts:
            manager = MemoryLifecycleManager()

            start_time = time.time()
            for i in range(count):
                await manager.process_memory_access(f"mem_{i}")
            elapsed = time.time() - start_time

            stats = manager.compute_stats()

            results[count] = {
                "count": count,
                "active": stats.active_count,
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")

        return results

    def benchmark_analytics(self, memory_counts: list[int]) -> dict:
        """基准测试分析工具。"""
        print("\n=== 分析工具性能测试 ===")
        results = {}

        for count in memory_counts:
            memories = self.generate_test_memories(count)
            analytics = MemoryAnalytics()

            start_time = time.time()
            for mem in memories:
                analytics.assess_memory_quality(
                    mem["id"],
                    mem["content"],
                    access_count=mem["access_count"],
                    importance=mem["importance"],
                )
            elapsed = time.time() - start_time

            results[count] = {
                "count": count,
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")

        return results

    async def benchmark_full_system(self, memory_counts: list[int]) -> dict:
        """基准测试完整系统。"""
        print("\n=== 完整系统性能测试 ===")
        results = {}

        for count in memory_counts:
            memories = self.generate_test_memories(count)
            embeddings = self.generate_embeddings(count)
            system = AdvancedMemoryFusionSystem()

            start_time = time.time()
            result = await system.process_memories(memories, embeddings)
            elapsed = time.time() - start_time

            stats = system.get_system_stats()

            results[count] = {
                "count": count,
                "processed": result["processed_count"],
                "time_ms": elapsed * 1000,
                "throughput": count / elapsed,
            }

            print(f"  {count} 条记忆: {elapsed*1000:.1f}ms "
                  f"({count/elapsed:.0f} 条/秒)")

        return results

    async def run_all_benchmarks(self):
        """运行所有基准测试。"""
        print("=" * 50)
        print("高级记忆融合系统性能基准测试")
        print("=" * 50)

        memory_counts = [100, 500, 1000, 5000]

        self.results["merger"] = await self.benchmark_merger(memory_counts)
        self.results["importance"] = self.benchmark_importance_scorer(memory_counts)
        self.results["retriever"] = await self.benchmark_retriever(memory_counts)
        self.results["graph"] = self.benchmark_graph_enhancer(memory_counts)
        self.results["lifecycle"] = await self.benchmark_lifecycle_manager(memory_counts)
        self.results["analytics"] = self.benchmark_analytics(memory_counts)
        self.results["full_system"] = await self.benchmark_full_system(memory_counts)

        self.print_summary()

    def print_summary(self):
        """打印总结。"""
        print("\n" + "=" * 50)
        print("性能基准测试总结")
        print("=" * 50)

        for module, results in self.results.items():
            print(f"\n{module}:")
            for count, metrics in results.items():
                print(f"  {count} 条记忆:")
                for key, value in metrics.items():
                    if key != "count":
                        print(f"    {key}: {value}")


async def main():
    """主函数。"""
    benchmark = PerformanceBenchmark()
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
