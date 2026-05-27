"""
Memory deduplication integration module for X-Agent.

Integrates deduplication with the existing memory system, providing
automatic deduplication, monitoring, and optimization.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Optional

from backend.app.core.memory_deduplication_enhanced import (
    Memory,
    MemoryDeduplicatorEnhanced,
    DeduplicationResult,
)
from backend.app.core.memory_graph import MemoryGraph
from backend.app.core.memory_graph_enhanced import EnhancedMemoryGraph, MemoryNode, MemoryRelation

logger = logging.getLogger(__name__)


class MemoryDeduplicationService:
    """
    Service for managing memory deduplication in X-Agent.

    Provides automatic deduplication, incremental updates, and
    integration with memory graph and storage systems.
    """

    def __init__(
        self,
        vector_similarity_threshold: float = 0.95,
        hash_similarity_threshold: float = 0.9,
        time_window_hours: int = 24,
        auto_deduplicate: bool = True,
        dedup_interval_minutes: int = 60,
    ):
        """
        Initialize the deduplication service.

        Args:
            vector_similarity_threshold: Threshold for vector similarity
            hash_similarity_threshold: Threshold for hash similarity
            time_window_hours: Hours for time-window deduplication
            auto_deduplicate: Whether to enable automatic deduplication
            dedup_interval_minutes: Interval for automatic deduplication
        """
        self.deduplicator = MemoryDeduplicatorEnhanced(
            vector_similarity_threshold=vector_similarity_threshold,
            hash_similarity_threshold=hash_similarity_threshold,
            time_window_hours=time_window_hours,
        )
        self.auto_deduplicate = auto_deduplicate
        self.dedup_interval_minutes = dedup_interval_minutes
        self.last_dedup_time: datetime = datetime.now(UTC)

        # Statistics tracking
        self._total_deduplications = 0
        self._total_removed = 0
        self._total_memory_saved = 0

        # Graph integration
        self.memory_graph = MemoryGraph()
        self.enhanced_graph = EnhancedMemoryGraph()

    async def deduplicate_memories(
        self,
        memories: list[Memory],
        strategy: str = "combined",
        preserve_relationships: bool = True,
    ) -> DeduplicationResult:
        """
        Deduplicate a list of memories.

        Args:
            memories: List of memories to deduplicate
            strategy: Deduplication strategy to use
            preserve_relationships: Whether to preserve graph relationships

        Returns:
            DeduplicationResult with deduplication details
        """
        logger.info(f"Starting deduplication of {len(memories)} memories using {strategy} strategy")

        # Perform deduplication
        result = self.deduplicator.deduplicate(memories, strategy=strategy)

        # Update statistics
        self._total_deduplications += 1
        self._total_removed += len(result.removed_ids)
        if result.stats:
            self._total_memory_saved += result.stats.memory_saved_bytes

        # Preserve relationships if requested
        if preserve_relationships:
            await self._preserve_relationships(result, memories)

        logger.info(
            f"Deduplication complete: {result.original_count} -> {result.deduplicated_count} "
            f"memories, removed {len(result.removed_ids)}"
        )

        return result

    async def incremental_deduplicate(
        self,
        new_memories: list[Memory],
        existing_memories: list[Memory],
    ) -> DeduplicationResult:
        """
        Perform incremental deduplication.

        Args:
            new_memories: Newly added memories
            existing_memories: Existing memories to compare against

        Returns:
            DeduplicationResult with only new duplicates
        """
        logger.info(
            f"Starting incremental deduplication: {len(new_memories)} new vs "
            f"{len(existing_memories)} existing"
        )

        result = self.deduplicator.incremental_deduplicate(new_memories, existing_memories)

        self._total_deduplications += 1
        self._total_removed += len(result.removed_ids)
        if result.stats:
            self._total_memory_saved += result.stats.memory_saved_bytes

        logger.info(f"Incremental deduplication complete: removed {len(result.removed_ids)}")

        return result

    async def auto_deduplicate_if_needed(
        self,
        memories: list[Memory],
    ) -> Optional[DeduplicationResult]:
        """
        Automatically deduplicate if interval has passed.

        Args:
            memories: List of memories to potentially deduplicate

        Returns:
            DeduplicationResult if deduplication was performed, None otherwise
        """
        if not self.auto_deduplicate:
            return None

        now = datetime.now(UTC)
        time_since_last = (now - self.last_dedup_time).total_seconds() / 60

        if time_since_last >= self.dedup_interval_minutes:
            logger.info("Auto-deduplication triggered")
            result = await self.deduplicate_memories(memories, strategy="combined")
            self.last_dedup_time = now
            return result

        return None

    async def _preserve_relationships(
        self,
        result: DeduplicationResult,
        memories: list[Memory],
    ) -> None:
        """
        Preserve graph relationships when merging memories.

        Args:
            result: Deduplication result
            memories: Original memories
        """
        # Create mapping of removed IDs to kept IDs
        removed_to_kept = {}
        for kept_id, merge_info in result.merge_summary.items():
            for removed_id in merge_info.get("merged_ids", []):
                removed_to_kept[removed_id] = kept_id

        # Update graph relationships
        for removed_id, kept_id in removed_to_kept.items():
            # Find relations involving removed memory
            incoming = self.enhanced_graph.reverse_relations.get(removed_id, [])
            outgoing = self.enhanced_graph.relations.get(removed_id, [])

            # Redirect to kept memory
            for relation in incoming:
                new_relation = MemoryRelation(
                    source_id=relation.source_id,
                    target_id=kept_id,
                    relation_type=relation.relation_type,
                    strength=relation.strength,
                    metadata=relation.metadata,
                )
                self.enhanced_graph.add_relation(new_relation)

            for relation in outgoing:
                new_relation = MemoryRelation(
                    source_id=kept_id,
                    target_id=relation.target_id,
                    relation_type=relation.relation_type,
                    strength=relation.strength,
                    metadata=relation.metadata,
                )
                self.enhanced_graph.add_relation(new_relation)

        logger.debug(f"Preserved relationships for {len(removed_to_kept)} merged memories")

    def get_service_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        cache_stats = self.deduplicator.get_cache_stats()
        graph_stats = self.enhanced_graph.get_graph_stats()

        return {
            "total_deduplications": self._total_deduplications,
            "total_removed": self._total_removed,
            "total_memory_saved_bytes": self._total_memory_saved,
            "total_memory_saved_mb": self._total_memory_saved / (1024 * 1024),
            "last_dedup_time": self.last_dedup_time.isoformat(),
            "cache_stats": cache_stats,
            "graph_stats": graph_stats,
        }

    def export_deduplication_config(self) -> dict[str, Any]:
        """Export current deduplication configuration."""
        return {
            "vector_similarity_threshold": self.deduplicator.vector_similarity_threshold,
            "hash_similarity_threshold": self.deduplicator.hash_similarity_threshold,
            "time_window_hours": self.deduplicator.time_window_hours,
            "min_group_size": self.deduplicator.min_group_size,
            "auto_deduplicate": self.auto_deduplicate,
            "dedup_interval_minutes": self.dedup_interval_minutes,
        }


class MemoryDeduplicationMonitor:
    """
    Monitors memory deduplication performance and health.

    Tracks metrics, detects anomalies, and provides alerts.
    """

    def __init__(self, service: MemoryDeduplicationService):
        """
        Initialize the monitor.

        Args:
            service: MemoryDeduplicationService instance
        """
        self.service = service
        self.metrics: list[dict[str, Any]] = []
        self.logger = logger

    def record_deduplication(self, result: DeduplicationResult) -> None:
        """Record deduplication metrics."""
        metric = {
            "timestamp": datetime.now(UTC).isoformat(),
            "original_count": result.original_count,
            "deduplicated_count": result.deduplicated_count,
            "removed_count": len(result.removed_ids),
            "merged_groups": len(result.merged_groups),
        }

        if result.stats:
            metric.update({
                "processing_time": result.stats.processing_time,
                "memory_saved_bytes": result.stats.memory_saved_bytes,
                "vector_duplicates": result.stats.vector_duplicates,
                "hash_duplicates": result.stats.hash_duplicates,
            })

        self.metrics.append(metric)

    def get_metrics_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get metrics summary for the last N hours."""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics
            if datetime.fromisoformat(m["timestamp"]) > cutoff_time
        ]

        if not recent_metrics:
            return {
                "period_hours": hours,
                "deduplication_count": 0,
                "total_removed": 0,
                "avg_reduction_rate": 0.0,
            }

        total_removed = sum(m["removed_count"] for m in recent_metrics)
        total_original = sum(m["original_count"] for m in recent_metrics)
        avg_reduction = (
            (total_original - total_removed) / total_original * 100
            if total_original > 0 else 0
        )

        return {
            "period_hours": hours,
            "deduplication_count": len(recent_metrics),
            "total_removed": total_removed,
            "total_original": total_original,
            "avg_reduction_rate": avg_reduction,
            "avg_processing_time": (
                sum(m.get("processing_time", 0) for m in recent_metrics) / len(recent_metrics)
                if recent_metrics else 0
            ),
            "total_memory_saved_mb": (
                sum(m.get("memory_saved_bytes", 0) for m in recent_metrics) / (1024 * 1024)
            ),
        }

    def detect_anomalies(self) -> list[dict[str, Any]]:
        """Detect anomalies in deduplication metrics."""
        anomalies = []

        if len(self.metrics) < 2:
            return anomalies

        # Calculate average reduction rate
        reduction_rates = [
            (m["original_count"] - m["removed_count"]) / m["original_count"] * 100
            if m["original_count"] > 0 else 0
            for m in self.metrics[-10:]  # Last 10 deduplications
        ]

        if reduction_rates:
            avg_reduction = sum(reduction_rates) / len(reduction_rates)
            std_dev = (sum((r - avg_reduction) ** 2 for r in reduction_rates) / len(reduction_rates)) ** 0.5

            # Check for anomalies (> 2 std devs)
            for i, metric in enumerate(self.metrics[-10:]):
                reduction = reduction_rates[i]
                if abs(reduction - avg_reduction) > 2 * std_dev:
                    anomalies.append({
                        "timestamp": metric["timestamp"],
                        "type": "unusual_reduction_rate",
                        "value": reduction,
                        "expected": avg_reduction,
                        "deviation": abs(reduction - avg_reduction),
                    })

        return anomalies


# Global instances
deduplication_service: Optional[MemoryDeduplicationService] = None
deduplication_monitor: Optional[MemoryDeduplicationMonitor] = None


def initialize_deduplication_service(
    vector_similarity_threshold: float = 0.95,
    hash_similarity_threshold: float = 0.9,
    time_window_hours: int = 24,
    auto_deduplicate: bool = True,
    dedup_interval_minutes: int = 60,
) -> MemoryDeduplicationService:
    """Initialize the global deduplication service."""
    global deduplication_service, deduplication_monitor

    deduplication_service = MemoryDeduplicationService(
        vector_similarity_threshold=vector_similarity_threshold,
        hash_similarity_threshold=hash_similarity_threshold,
        time_window_hours=time_window_hours,
        auto_deduplicate=auto_deduplicate,
        dedup_interval_minutes=dedup_interval_minutes,
    )

    deduplication_monitor = MemoryDeduplicationMonitor(deduplication_service)

    logger.info("Memory deduplication service initialized")

    return deduplication_service


def get_deduplication_service() -> Optional[MemoryDeduplicationService]:
    """Get the global deduplication service."""
    return deduplication_service


def get_deduplication_monitor() -> Optional[MemoryDeduplicationMonitor]:
    """Get the global deduplication monitor."""
    return deduplication_monitor
