"""Memory V2 - Nudge Memory Layer (Active Consolidation)

Periodic automatic memory consolidation, deduplication, and maintenance.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationTask:
    """A consolidation task to be executed."""

    task_id: str
    task_type: str  # consolidate, deduplicate, compress, archive
    tenant_id: str
    created_at: datetime
    scheduled_at: datetime
    status: str = "pending"  # pending, running, completed, failed
    result: dict = None
    error: str | None = None


class NudgeConfig(BaseModel):
    """Configuration for nudge memory layer."""

    # Consolidation
    consolidation_enabled: bool = True
    consolidation_schedule: str = "0 2 * * *"  # Daily at 2 AM
    consolidation_batch_size: int = 100
    consolidation_min_importance: float = 0.3

    # Deduplication
    deduplication_enabled: bool = True
    deduplication_schedule: str = "0 3 * * 0"  # Weekly on Sunday at 3 AM
    deduplication_similarity_threshold: float = 0.85

    # Compression
    compression_enabled: bool = True
    compression_schedule: str = "0 4 * * *"  # Daily at 4 AM
    compression_ratio_target: float = 0.8

    # Archival
    archival_enabled: bool = True
    archival_schedule: str = "0 5 * * 0"  # Weekly on Sunday at 5 AM
    archival_age_days: int = 30
    archival_importance_threshold: float = 0.2

    # Eviction
    eviction_enabled: bool = True
    eviction_schedule: str = "0 6 * * *"  # Daily at 6 AM
    eviction_storage_limit_mb: int = 500
    eviction_min_importance: float = 0.1
    eviction_max_age_days: int = 30


class NudgeMemoryLayer:
    """Layer 2: Active Memory Consolidation - Periodic automatic maintenance."""

    def __init__(
        self,
        config: NudgeConfig | None = None,
        memory_system: Any = None,  # MemoryV2System
    ):
        self.config = config or NudgeConfig()
        self.memory_system = memory_system
        self._tasks: dict[str, ConsolidationTask] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the nudge memory layer."""

        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Nudge memory layer started")

    async def stop(self) -> None:
        """Stop the nudge memory layer."""

        if not self._running:
            return

        self._running = False
        if self._worker_task:
            await self._worker_task
        logger.info("Nudge memory layer stopped")

    async def consolidate(
        self,
        tenant_id: str,
        batch_size: int | None = None,
        min_importance: float | None = None,
    ) -> dict[str, Any]:
        """Consolidate memories for a tenant."""

        if not self.memory_system:
            raise ValueError("Memory system not configured")

        batch_size = batch_size or self.config.consolidation_batch_size
        min_importance = min_importance or self.config.consolidation_min_importance

        logger.info(f"Starting consolidation for tenant {tenant_id}")

        # Get candidates
        candidates = self._get_consolidation_candidates(
            tenant_id, batch_size, min_importance
        )

        if not candidates:
            return {"consolidated": 0, "reason": "no_candidates"}

        # Consolidate
        result = await self.memory_system.consolidate(
            tenant_id=tenant_id,
            max_items=len(candidates),
            min_importance=min_importance,
        )

        logger.info(f"Consolidated {result.get('consolidated', 0)} memories")
        return result

    async def deduplicate(
        self,
        tenant_id: str,
        similarity_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Deduplicate memories for a tenant."""

        if not self.memory_system:
            raise ValueError("Memory system not configured")

        similarity_threshold = (
            similarity_threshold or self.config.deduplication_similarity_threshold
        )

        logger.info(f"Starting deduplication for tenant {tenant_id}")

        # Find duplicates
        duplicates = await self._find_duplicates(tenant_id, similarity_threshold)

        if not duplicates:
            return {"deduplicated": 0, "reason": "no_duplicates"}

        # Merge duplicates
        merged_count = 0
        for group in duplicates:
            await self._merge_duplicate_group(group)
            merged_count += len(group) - 1

        logger.info(f"Deduplicated {merged_count} memories")
        return {"deduplicated": merged_count, "groups": len(duplicates)}

    async def compress(
        self,
        tenant_id: str,
        ratio_target: float | None = None,
    ) -> dict[str, Any]:
        """Compress memories for a tenant."""

        if not self.memory_system:
            raise ValueError("Memory system not configured")

        ratio_target = ratio_target or self.config.compression_ratio_target

        logger.info(f"Starting compression for tenant {tenant_id}")

        # Get all memories
        memories = self._get_tenant_memories(tenant_id)

        if not memories:
            return {"compressed": 0, "reason": "no_memories"}

        # Compress
        compressed_count = 0
        for memory in memories:
            original_size = len(memory.content)
            compressed_content = await self._compress_content(memory.content)
            compressed_size = len(compressed_content)

            if compressed_size < original_size * ratio_target:
                memory.content = compressed_content
                compressed_count += 1

        logger.info(f"Compressed {compressed_count} memories")
        return {"compressed": compressed_count}

    async def archive(
        self,
        tenant_id: str,
        age_days: int | None = None,
        importance_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Archive old memories for a tenant."""

        if not self.memory_system:
            raise ValueError("Memory system not configured")

        age_days = age_days or self.config.archival_age_days
        importance_threshold = (
            importance_threshold or self.config.archival_importance_threshold
        )

        logger.info(f"Starting archival for tenant {tenant_id}")

        # Get candidates
        cutoff_date = datetime.now(UTC) - timedelta(days=age_days)
        candidates = self._get_archival_candidates(
            tenant_id, cutoff_date, importance_threshold
        )

        if not candidates:
            return {"archived": 0, "reason": "no_candidates"}

        # Archive
        archived_count = 0
        for memory in candidates:
            await self._archive_memory(memory)
            archived_count += 1

        logger.info(f"Archived {archived_count} memories")
        return {"archived": archived_count}

    async def evict(
        self,
        tenant_id: str,
        storage_limit_mb: int | None = None,
        min_importance: float | None = None,
        max_age_days: int | None = None,
    ) -> dict[str, Any]:
        """Evict memories when storage limit is exceeded."""

        if not self.memory_system:
            raise ValueError("Memory system not configured")

        storage_limit_mb = storage_limit_mb or self.config.eviction_storage_limit_mb
        min_importance = min_importance or self.config.eviction_min_importance
        max_age_days = max_age_days or self.config.eviction_max_age_days

        logger.info(f"Starting eviction for tenant {tenant_id}")

        # Check storage usage
        current_usage_mb = self._get_storage_usage(tenant_id)

        if current_usage_mb <= storage_limit_mb:
            return {"evicted": 0, "reason": "under_limit"}

        # Get candidates
        target_size_mb = storage_limit_mb * 0.8
        candidates = self._get_eviction_candidates(
            tenant_id, min_importance, max_age_days
        )

        if not candidates:
            return {"evicted": 0, "reason": "no_candidates"}

        # Evict
        evicted_count = 0
        freed_mb = 0.0

        for memory in candidates:
            memory_size_mb = len(memory.content) / (1024 * 1024)
            await self._evict_memory(memory)
            evicted_count += 1
            freed_mb += memory_size_mb

            if current_usage_mb - freed_mb <= target_size_mb:
                break

        logger.info(f"Evicted {evicted_count} memories, freed {freed_mb:.2f} MB")
        return {"evicted": evicted_count, "freed_mb": freed_mb}

    async def schedule_task(
        self,
        task_type: str,
        tenant_id: str,
        scheduled_at: datetime | None = None,
        params: dict | None = None,
    ) -> str:
        """Schedule a consolidation task."""

        task_id = str(uuid4())
        task = ConsolidationTask(
            task_id=task_id,
            task_type=task_type,
            tenant_id=tenant_id,
            created_at=datetime.now(UTC),
            scheduled_at=scheduled_at or datetime.now(UTC),
        )

        self._tasks[task_id] = task
        await self._task_queue.put((task, params or {}))

        logger.info(f"Scheduled task {task_id} ({task_type}) for tenant {tenant_id}")
        return task_id

    def get_task_status(self, task_id: str) -> ConsolidationTask | None:
        """Get status of a consolidation task."""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> list[ConsolidationTask]:
        """List consolidation tasks."""

        tasks = list(self._tasks.values())

        if tenant_id:
            tasks = [t for t in tasks if t.tenant_id == tenant_id]

        if status:
            tasks = [t for t in tasks if t.status == status]

        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def get_statistics(self) -> dict[str, Any]:
        """Get nudge layer statistics."""

        tasks = list(self._tasks.values())
        completed = [t for t in tasks if t.status == "completed"]
        failed = [t for t in tasks if t.status == "failed"]

        return {
            "total_tasks": len(tasks),
            "completed_tasks": len(completed),
            "failed_tasks": len(failed),
            "pending_tasks": len([t for t in tasks if t.status == "pending"]),
            "running_tasks": len([t for t in tasks if t.status == "running"]),
            "queue_size": self._task_queue.qsize(),
        }

    # Private methods

    async def _worker_loop(self) -> None:
        """Main worker loop for processing consolidation tasks."""

        while self._running:
            try:
                # Get next task with timeout
                task, params = await asyncio.wait_for(
                    self._task_queue.get(), timeout=60.0
                )

                # Update task status
                task.status = "running"

                # Execute task
                try:
                    if task.task_type == "consolidate":
                        result = await self.consolidate(task.tenant_id, **params)
                    elif task.task_type == "deduplicate":
                        result = await self.deduplicate(task.tenant_id, **params)
                    elif task.task_type == "compress":
                        result = await self.compress(task.tenant_id, **params)
                    elif task.task_type == "archive":
                        result = await self.archive(task.tenant_id, **params)
                    elif task.task_type == "evict":
                        result = await self.evict(task.tenant_id, **params)
                    else:
                        raise ValueError(f"Unknown task type: {task.task_type}")

                    task.status = "completed"
                    task.result = result

                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    logger.error(f"Task {task.task_id} failed: {e}")

            except asyncio.TimeoutError:
                # No task available, continue
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)

    def _get_consolidation_candidates(
        self,
        tenant_id: str,
        batch_size: int,
        min_importance: float,
    ) -> list[Any]:
        """Get candidates for consolidation."""

        if not self.memory_system:
            return []

        memories = self._get_tenant_memories(tenant_id)
        candidates = [
            m for m in memories
            if m.importance >= min_importance
            and "consolidated" not in m.tags
        ]

        candidates.sort(key=lambda m: m.importance, reverse=True)
        return candidates[:batch_size]

    async def _find_duplicates(
        self,
        tenant_id: str,
        similarity_threshold: float,
    ) -> list[list[Any]]:
        """Find duplicate memories."""

        memories = self._get_tenant_memories(tenant_id)
        groups: list[list[Any]] = []

        for i, mem1 in enumerate(memories):
            found_group = False
            for group in groups:
                if mem1 in group:
                    found_group = True
                    break

            if found_group:
                continue

            group = [mem1]
            for mem2 in memories[i + 1 :]:
                if mem2 in group:
                    continue

                similarity = await self._calculate_similarity(mem1, mem2)
                if similarity > similarity_threshold:
                    group.append(mem2)

            if len(group) > 1:
                groups.append(group)

        return groups

    async def _merge_duplicate_group(self, group: list[Any]) -> None:
        """Merge a group of duplicate memories."""

        if not group:
            return

        # Keep the one with highest importance
        primary = max(group, key=lambda m: m.importance)

        # Mark others as duplicates
        for memory in group:
            if memory.id != primary.id:
                memory.is_duplicate = True
                memory.duplicate_of = primary.id

    async def _compress_content(self, content: str) -> str:
        """Compress memory content."""

        # Simple compression: remove extra whitespace and normalize
        lines = content.split("\n")
        compressed_lines = [line.strip() for line in lines if line.strip()]
        return "\n".join(compressed_lines)

    def _get_archival_candidates(
        self,
        tenant_id: str,
        cutoff_date: datetime,
        importance_threshold: float,
    ) -> list[Any]:
        """Get candidates for archival."""

        memories = self._get_tenant_memories(tenant_id)
        candidates = [
            m for m in memories
            if m.created_at < cutoff_date
            and m.importance < importance_threshold
        ]

        return sorted(candidates, key=lambda m: m.created_at)

    async def _archive_memory(self, memory: Any) -> None:
        """Archive a memory."""

        memory.tier = "archive"
        logger.debug(f"Archived memory {memory.id}")

    def _get_eviction_candidates(
        self,
        tenant_id: str,
        min_importance: float,
        max_age_days: int,
    ) -> list[Any]:
        """Get candidates for eviction."""

        memories = self._get_tenant_memories(tenant_id)
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        candidates = [
            m for m in memories
            if m.importance < min_importance
            and m.last_accessed < cutoff_date
        ]

        candidates.sort(key=lambda m: m.importance)
        return candidates

    async def _evict_memory(self, memory: Any) -> None:
        """Evict a memory."""

        if self.memory_system and memory.id in self.memory_system._memories:
            del self.memory_system._memories[memory.id]
        logger.debug(f"Evicted memory {memory.id}")

    def _get_tenant_memories(self, tenant_id: str) -> list[Any]:
        """Get all memories for a tenant."""

        if not self.memory_system:
            return []

        return [
            m for m in self.memory_system._memories.values()
            if m.tenant_id == tenant_id
        ]

    async def _calculate_similarity(self, mem1: Any, mem2: Any) -> float:
        """Calculate similarity between two memories."""

        terms1 = set(mem1.content.lower().split())
        terms2 = set(mem2.content.lower().split())

        if not terms1 or not terms2:
            return 0.0

        intersection = len(terms1 & terms2)
        union = len(terms1 | terms2)

        return intersection / union if union > 0 else 0.0

    def _get_storage_usage(self, tenant_id: str) -> float:
        """Get storage usage for a tenant in MB."""

        memories = self._get_tenant_memories(tenant_id)
        total_bytes = sum(len(m.content.encode("utf-8")) for m in memories)
        return total_bytes / (1024 * 1024)


# Global instance
nudge_memory_layer = NudgeMemoryLayer()
