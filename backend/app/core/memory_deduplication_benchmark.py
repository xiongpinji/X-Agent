"""
Performance testing and benchmarking for memory deduplication.

Tests deduplication algorithms with various memory sizes and configurations.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, UTC
from typing import Any

import numpy as np

from backend.app.core.memory_deduplication_enhanced import (
    Memory,
    MemoryDeduplicatorEnhanced,
    DeduplicationResult,
)


class DeduplicationBenchmark:
    """Benchmark suite for memory deduplication."""

    def __init__(self):
        self.results: list[dict[str, Any]] = []

    def generate_test_memories(
        self,
        count: int,
        duplicate_ratio: float = 0.3,
        seed: int = 42,
    ) -> list[Memory]:
        """
        Generate test memories with controlled duplication.

        Args:
            count: Number of memories to generate
            duplicate_ratio: Ratio of duplicates (0-1)
            seed: Random seed for reproducibility

        Returns:
            List of test Memory objects
        """
        np.random.seed(seed)
        memories = []

        # Generate base content
        base_contents = [
            "User logged in successfully from IP 192.168.1.1",
            "Database query executed in 45ms",
            "API endpoint /users returned 200 OK",
            "Cache hit for key user:123",
            "Background job completed successfully",
            "Error: Connection timeout after 30s",
            "Memory usage at 75% capacity",
            "New user registration from email@example.com",
            "File upload completed: document.pdf (2.5MB)",
            "Authentication token refreshed",
        ]

        # Generate memories
        for i in range(count):
            # Decide if this should be a duplicate
            if np.random.random() < duplicate_ratio and i > 0:
                # Create a duplicate with slight variation
                base_idx = np.random.randint(0, len(base_contents))
                content = base_contents[base_idx]
                # Add slight variation
                if np.random.random() > 0.5:
                    content += f" (variation {i})"
            else:
                # Create unique content
                base_idx = i % len(base_contents)
                content = f"{base_contents[base_idx]} - unique {i}"

            memory = Memory(
                id=f"mem_{i}",
                content=content,
                created_at=datetime.now(UTC) - timedelta(hours=np.random.randint(0, 24)),
                importance=np.random.random(),
                access_count=np.random.randint(0, 100),
            )
            memories.append(memory)

        return memories

    def benchmark_vector_deduplication(self, memory_counts: list[int]) -> dict[str, Any]:
        """Benchmark vector-based deduplication."""
        deduplicator = MemoryDeduplicatorEnhanced()
        results = {
            "strategy": "vector",
            "results": [],
        }

        for count in memory_counts:
            memories = self.generate_test_memories(count, duplicate_ratio=0.3)

            start_time = time.time()
            result = deduplicator.deduplicate(memories, strategy="vector")
            elapsed = time.time() - start_time

            stats = deduplicator.get_deduplication_stats(result)
            stats["memory_count"] = count
            stats["elapsed_time"] = elapsed
            stats["throughput"] = count / elapsed if elapsed > 0 else 0

            results["results"].append(stats)

        return results

    def benchmark_hash_deduplication(self, memory_counts: list[int]) -> dict[str, Any]:
        """Benchmark hash-based deduplication."""
        deduplicator = MemoryDeduplicatorEnhanced()
        results = {
            "strategy": "hash",
            "results": [],
        }

        for count in memory_counts:
            memories = self.generate_test_memories(count, duplicate_ratio=0.3)

            start_time = time.time()
            result = deduplicator.deduplicate(memories, strategy="hash")
            elapsed = time.time() - start_time

            stats = deduplicator.get_deduplication_stats(result)
            stats["memory_count"] = count
            stats["elapsed_time"] = elapsed
            stats["throughput"] = count / elapsed if elapsed > 0 else 0

            results["results"].append(stats)

        return results

    def benchmark_combined_deduplication(self, memory_counts: list[int]) -> dict[str, Any]:
        """Benchmark combined deduplication strategy."""
        deduplicator = MemoryDeduplicatorEnhanced()
        results = {
            "strategy": "combined",
            "results": [],
        }

        for count in memory_counts:
            memories = self.generate_test_memories(count, duplicate_ratio=0.3)

            start_time = time.time()
            result = deduplicator.deduplicate(memories, strategy="combined")
            elapsed = time.time() - start_time

            stats = deduplicator.get_deduplication_stats(result)
            stats["memory_count"] = count
            stats["elapsed_time"] = elapsed
            stats["throughput"] = count / elapsed if elapsed > 0 else 0

            results["results"].append(stats)

        return results

    def benchmark_incremental_deduplication(self) -> dict[str, Any]:
        """Benchmark incremental deduplication."""
        deduplicator = MemoryDeduplicatorEnhanced()

        # Generate initial memories
        existing_memories = self.generate_test_memories(1000, duplicate_ratio=0.2)

        results = {
            "strategy": "incremental",
            "results": [],
        }

        # Test with different batch sizes
        for batch_size in [10, 50, 100, 500]:
            new_memories = self.generate_test_memories(batch_size, duplicate_ratio=0.4)

            start_time = time.time()
            result = deduplicator.incremental_deduplicate(new_memories, existing_memories)
            elapsed = time.time() - start_time

            stats = deduplicator.get_deduplication_stats(result)
            stats["batch_size"] = batch_size
            stats["existing_count"] = len(existing_memories)
            stats["elapsed_time"] = elapsed
            stats["throughput"] = batch_size / elapsed if elapsed > 0 else 0

            results["results"].append(stats)

        return results

    def benchmark_batch_deduplication(self) -> dict[str, Any]:
        """Benchmark batch deduplication."""
        deduplicator = MemoryDeduplicatorEnhanced()

        # Generate batches
        batches = [
            self.generate_test_memories(100, duplicate_ratio=0.3),
            self.generate_test_memories(100, duplicate_ratio=0.3),
            self.generate_test_memories(100, duplicate_ratio=0.3),
            self.generate_test_memories(100, duplicate_ratio=0.3),
            self.generate_test_memories(100, duplicate_ratio=0.3),
        ]

        start_time = time.time()
        results_list = deduplicator.batch_deduplicate(batches, strategy="combined")
        elapsed = time.time() - start_time

        total_original = sum(r.original_count for r in results_list)
        total_deduplicated = sum(r.deduplicated_count for r in results_list)
        total_removed = sum(len(r.removed_ids) for r in results_list)

        return {
            "strategy": "batch",
            "batch_count": len(batches),
            "total_original": total_original,
            "total_deduplicated": total_deduplicated,
            "total_removed": total_removed,
            "reduction_rate": (
                (total_original - total_deduplicated) / total_original * 100
                if total_original > 0 else 0
            ),
            "elapsed_time": elapsed,
            "throughput": total_original / elapsed if elapsed > 0 else 0,
        }

    def benchmark_similarity_thresholds(self) -> dict[str, Any]:
        """Benchmark different similarity thresholds."""
        memories = self.generate_test_memories(500, duplicate_ratio=0.4)

        results = {
            "test": "similarity_thresholds",
            "results": [],
        }

        for threshold in [0.80, 0.85, 0.90, 0.95, 0.99]:
            deduplicator = MemoryDeduplicatorEnhanced(
                vector_similarity_threshold=threshold
            )

            start_time = time.time()
            result = deduplicator.deduplicate(memories, strategy="vector")
            elapsed = time.time() - start_time

            stats = deduplicator.get_deduplication_stats(result)
            stats["threshold"] = threshold
            stats["elapsed_time"] = elapsed

            results["results"].append(stats)

        return results

    def run_full_benchmark(self) -> dict[str, Any]:
        """Run complete benchmark suite."""
        print("Starting comprehensive deduplication benchmark...")

        benchmark_results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "vector_benchmark": self.benchmark_vector_deduplication([100, 500, 1000, 5000]),
            "hash_benchmark": self.benchmark_hash_deduplication([100, 500, 1000, 5000]),
            "combined_benchmark": self.benchmark_combined_deduplication([100, 500, 1000, 5000]),
            "incremental_benchmark": self.benchmark_incremental_deduplication(),
            "batch_benchmark": self.benchmark_batch_deduplication(),
            "threshold_benchmark": self.benchmark_similarity_thresholds(),
        }

        return benchmark_results

    def print_benchmark_results(self, results: dict[str, Any]) -> None:
        """Print benchmark results in a readable format."""
        print("\n" + "=" * 80)
        print("DEDUPLICATION BENCHMARK RESULTS")
        print("=" * 80)

        # Vector benchmark
        print("\n[VECTOR DEDUPLICATION]")
        for result in results["vector_benchmark"]["results"]:
            print(
                f"  Count: {result['memory_count']:5d} | "
                f"Reduction: {result['reduction_rate']:5.1f}% | "
                f"Time: {result['elapsed_time']:6.3f}s | "
                f"Throughput: {result['throughput']:7.0f} mem/s"
            )

        # Hash benchmark
        print("\n[HASH DEDUPLICATION]")
        for result in results["hash_benchmark"]["results"]:
            print(
                f"  Count: {result['memory_count']:5d} | "
                f"Reduction: {result['reduction_rate']:5.1f}% | "
                f"Time: {result['elapsed_time']:6.3f}s | "
                f"Throughput: {result['throughput']:7.0f} mem/s"
            )

        # Combined benchmark
        print("\n[COMBINED DEDUPLICATION]")
        for result in results["combined_benchmark"]["results"]:
            print(
                f"  Count: {result['memory_count']:5d} | "
                f"Reduction: {result['reduction_rate']:5.1f}% | "
                f"Time: {result['elapsed_time']:6.3f}s | "
                f"Throughput: {result['throughput']:7.0f} mem/s"
            )

        # Incremental benchmark
        print("\n[INCREMENTAL DEDUPLICATION]")
        for result in results["incremental_benchmark"]["results"]:
            print(
                f"  Batch: {result['batch_size']:5d} | "
                f"Reduction: {result['reduction_rate']:5.1f}% | "
                f"Time: {result['elapsed_time']:6.3f}s | "
                f"Throughput: {result['throughput']:7.0f} mem/s"
            )

        # Batch benchmark
        batch_result = results["batch_benchmark"]
        print("\n[BATCH DEDUPLICATION]")
        print(
            f"  Batches: {batch_result['batch_count']} | "
            f"Total: {batch_result['total_original']} | "
            f"Reduction: {batch_result['reduction_rate']:.1f}% | "
            f"Time: {batch_result['elapsed_time']:.3f}s | "
            f"Throughput: {batch_result['throughput']:.0f} mem/s"
        )

        # Threshold benchmark
        print("\n[SIMILARITY THRESHOLD ANALYSIS]")
        for result in results["threshold_benchmark"]["results"]:
            print(
                f"  Threshold: {result['threshold']:.2f} | "
                f"Reduction: {result['reduction_rate']:5.1f}% | "
                f"Time: {result['elapsed_time']:6.3f}s"
            )

        print("\n" + "=" * 80)


if __name__ == "__main__":
    benchmark = DeduplicationBenchmark()
    results = benchmark.run_full_benchmark()
    benchmark.print_benchmark_results(results)
