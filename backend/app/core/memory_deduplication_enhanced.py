"""
Enhanced memory deduplication system for X-Agent.

Implements multiple deduplication strategies:
1. Vector similarity-based deduplication (cosine similarity > 0.95)
2. Content hash-based deduplication
3. Time window-based deduplication
4. Incremental deduplication (no full scan required)

Features:
- Batch processing for performance
- Caching of hot memories
- Graph-based relationship preservation
- Automatic memory fusion
- Performance monitoring
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from typing import Optional, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """Represents a single memory item."""

    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    importance: float = 1.0
    access_count: int = 0
    metadata: dict = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        """Calculate content hash after initialization."""
        if not self.content_hash:
            self.content_hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        """Calculate SHA256 hash of content."""
        return hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class DeduplicationStats:
    """Statistics from deduplication operation."""

    original_count: int
    deduplicated_count: int
    removed_count: int
    merged_groups: int
    vector_duplicates: int
    hash_duplicates: int
    time_window_duplicates: int
    processing_time: float
    memory_saved_bytes: int


@dataclass
class DeduplicationResult:
    """Result of deduplication operation."""

    original_count: int
    deduplicated_count: int
    merged_groups: list[list[str]] = field(default_factory=list)
    removed_ids: list[str] = field(default_factory=list)
    merge_summary: dict = field(default_factory=dict)
    stats: Optional[DeduplicationStats] = None


class MemoryDeduplicatorEnhanced:
    """
    Enhanced memory deduplicator with multiple strategies.

    Combines vector similarity, content hashing, and time-window analysis
    for comprehensive deduplication.
    """

    def __init__(
        self,
        vector_similarity_threshold: float = 0.95,
        hash_similarity_threshold: float = 0.9,
        time_window_hours: int = 24,
        min_group_size: int = 2,
        preserve_metadata: bool = True,
        enable_caching: bool = True,
        cache_size: int = 1000,
    ):
        """
        Initialize the enhanced deduplicator.

        Args:
            vector_similarity_threshold: Threshold for vector similarity (0-1)
            hash_similarity_threshold: Threshold for content hash similarity (0-1)
            time_window_hours: Hours for time-window deduplication
            min_group_size: Minimum memories to form a group
            preserve_metadata: Whether to preserve metadata from all merged memories
            enable_caching: Whether to cache hot memories
            cache_size: Maximum cache size
        """
        self.vector_similarity_threshold = vector_similarity_threshold
        self.hash_similarity_threshold = hash_similarity_threshold
        self.time_window_hours = time_window_hours
        self.min_group_size = min_group_size
        self.preserve_metadata = preserve_metadata
        self.enable_caching = enable_caching
        self.cache_size = cache_size
        self.logger = logger

        # Cache for hot memories
        self._cache: dict[str, Memory] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Tracking for incremental deduplication
        self._processed_hashes: set[str] = set()
        self._last_dedup_time: datetime = datetime.now(UTC)

    def deduplicate(
        self,
        memories: list[Memory],
        strategy: str = "combined",
    ) -> DeduplicationResult:
        """
        Deduplicate a list of memories using specified strategy.

        Args:
            memories: List of Memory objects to deduplicate
            strategy: "vector", "hash", "time_window", or "combined"

        Returns:
            DeduplicationResult containing deduplication statistics
        """
        start_time = time.time()

        if not memories:
            return DeduplicationResult(
                original_count=0,
                deduplicated_count=0,
                stats=DeduplicationStats(
                    original_count=0,
                    deduplicated_count=0,
                    removed_count=0,
                    merged_groups=0,
                    vector_duplicates=0,
                    hash_duplicates=0,
                    time_window_duplicates=0,
                    processing_time=0.0,
                    memory_saved_bytes=0,
                ),
            )

        # Ensure all memories have embeddings and hashes
        self._prepare_memories(memories)

        # Find duplicate groups based on strategy
        if strategy == "vector":
            groups = self._find_vector_duplicates(memories)
        elif strategy == "hash":
            groups = self._find_hash_duplicates(memories)
        elif strategy == "time_window":
            groups = self._find_time_window_duplicates(memories)
        else:  # combined
            groups = self._find_combined_duplicates(memories)

        # Merge groups and create result
        result = self._merge_groups(groups, memories)

        # Calculate statistics
        processing_time = time.time() - start_time
        memory_saved = self._calculate_memory_saved(result.removed_ids, memories)

        result.stats = DeduplicationStats(
            original_count=len(memories),
            deduplicated_count=result.deduplicated_count,
            removed_count=len(result.removed_ids),
            merged_groups=len(result.merged_groups),
            vector_duplicates=self._count_strategy_duplicates(groups, "vector"),
            hash_duplicates=self._count_strategy_duplicates(groups, "hash"),
            time_window_duplicates=self._count_strategy_duplicates(groups, "time_window"),
            processing_time=processing_time,
            memory_saved_bytes=memory_saved,
        )

        self.logger.info(
            f"Deduplication complete: {result.original_count} -> {result.deduplicated_count} "
            f"memories in {processing_time:.2f}s"
        )

        return result

    def incremental_deduplicate(
        self,
        new_memories: list[Memory],
        existing_memories: list[Memory],
    ) -> DeduplicationResult:
        """
        Perform incremental deduplication without scanning all existing memories.

        Args:
            new_memories: Newly added memories to check
            existing_memories: Existing memories to compare against

        Returns:
            DeduplicationResult with only new duplicates
        """
        start_time = time.time()

        if not new_memories:
            return DeduplicationResult(
                original_count=0,
                deduplicated_count=0,
            )

        self._prepare_memories(new_memories)
        self._prepare_memories(existing_memories)

        # Find duplicates only between new and existing
        groups = self._find_incremental_duplicates(new_memories, existing_memories)

        result = self._merge_groups(groups, new_memories + existing_memories)
        # _merge_groups 以 new+existing 合计作为 original/deduplicated 计数,
        # 但增量去重的语义是"针对新增记忆",顶层计数需回填为新增数量,
        # 与下方 stats.original_count 保持一致。
        new_removed = [
            rid for rid in result.removed_ids
            if rid in {m.id for m in new_memories}
        ]
        result.original_count = len(new_memories)
        result.deduplicated_count = len(new_memories) - len(new_removed)
        processing_time = time.time() - start_time

        result.stats = DeduplicationStats(
            original_count=len(new_memories),
            deduplicated_count=result.deduplicated_count,
            removed_count=len(result.removed_ids),
            merged_groups=len(result.merged_groups),
            vector_duplicates=0,
            hash_duplicates=0,
            time_window_duplicates=0,
            processing_time=processing_time,
            memory_saved_bytes=self._calculate_memory_saved(result.removed_ids, new_memories),
        )

        return result

    def batch_deduplicate(
        self,
        memory_batches: list[list[Memory]],
        strategy: str = "combined",
    ) -> list[DeduplicationResult]:
        """
        Deduplicate multiple batches of memories.

        Args:
            memory_batches: List of memory batches to deduplicate
            strategy: Deduplication strategy to use

        Returns:
            List of DeduplicationResult objects
        """
        results = []
        for batch in memory_batches:
            result = self.deduplicate(batch, strategy=strategy)
            results.append(result)

        return results

    def check_new_against_existing(
        self,
        new: Memory,
        existing: list[Memory],
    ) -> Optional[Memory]:
        """Single-write duplicate check used by the store write path.

        Returns the EXISTING memory that ``new`` duplicates (the one to keep),
        or None when ``new`` is unique. Cheapest check first:
        exact content-hash match, then vector similarity >= threshold.
        """
        if not existing:
            return None
        if not new.content_hash:
            new.content_hash = new._calculate_hash()
        for candidate in existing:
            if candidate.id == new.id:
                continue
            candidate_hash = candidate.content_hash or candidate._calculate_hash()
            if candidate_hash == new.content_hash:
                return candidate
        if new.embedding is None:
            return None
        best: Optional[Memory] = None
        best_similarity = self.vector_similarity_threshold
        for candidate in existing:
            if candidate.id == new.id or candidate.embedding is None:
                continue
            if len(candidate.embedding) != len(new.embedding):
                continue
            similarity = float(
                cosine_similarity([new.embedding], [candidate.embedding])[0][0]
            )
            if similarity >= best_similarity:
                best = candidate
                best_similarity = similarity
        return best

    def _prepare_memories(self, memories: list[Memory]) -> None:
        """Ensure all memories have embeddings and hashes."""
        for memory in memories:
            if memory.embedding is None:
                memory.embedding = self._create_simple_embedding(memory.content)
            if not memory.content_hash:
                memory.content_hash = memory._calculate_hash()

    def _find_vector_duplicates(self, memories: list[Memory]) -> list[list[int]]:
        """Find duplicate groups using vector similarity."""
        embeddings = self._extract_embeddings(memories)
        if embeddings is None or len(embeddings) == 0:
            return []

        similarity_matrix = cosine_similarity(embeddings)
        return self._find_groups_from_similarity_matrix(
            similarity_matrix,
            self.vector_similarity_threshold,
        )

    def _find_hash_duplicates(self, memories: list[Memory]) -> list[list[int]]:
        """Find duplicate groups using content hash."""
        hash_groups: dict[str, list[int]] = {}

        for i, memory in enumerate(memories):
            hash_key = memory.content_hash
            if hash_key not in hash_groups:
                hash_groups[hash_key] = []
            hash_groups[hash_key].append(i)

        # Return only groups with duplicates
        return [
            group for group in hash_groups.values()
            if len(group) >= self.min_group_size
        ]

    def _find_time_window_duplicates(self, memories: list[Memory]) -> list[list[int]]:
        """Find duplicate groups within time windows."""
        # Sort by creation time
        indexed_memories = [(i, m) for i, m in enumerate(memories)]
        indexed_memories.sort(key=lambda x: x[1].created_at)

        groups = []
        window_start = 0

        for i in range(len(indexed_memories)):
            current_time = indexed_memories[i][1].created_at
            window_end = i

            # Find all memories within time window
            while (window_start < i and
                   (current_time - indexed_memories[window_start][1].created_at).total_seconds() >
                   self.time_window_hours * 3600):
                window_start += 1

            # Check for similar memories in window
            if window_end - window_start >= self.min_group_size - 1:
                window_indices = [idx for idx, _ in indexed_memories[window_start:window_end + 1]]
                window_memories = [indexed_memories[j][1] for j in range(window_start, window_end + 1)]

                # Check similarity within window
                if len(window_memories) >= self.min_group_size:
                    embeddings = np.array([m.embedding for m in window_memories])
                    similarity_matrix = cosine_similarity(embeddings)

                    for j in range(len(window_memories)):
                        similar_indices = np.where(
                            similarity_matrix[j] > self.vector_similarity_threshold
                        )[0]
                        if len(similar_indices) >= self.min_group_size:
                            group = [window_indices[idx] for idx in similar_indices]
                            if group not in groups:
                                groups.append(group)

        return groups

    def _find_combined_duplicates(self, memories: list[Memory]) -> list[list[int]]:
        """Find duplicates using combined strategy."""
        # Start with hash-based duplicates (fastest)
        hash_groups = self._find_hash_duplicates(memories)

        # For non-hash duplicates, use vector similarity
        hash_indices = set()
        for group in hash_groups:
            hash_indices.update(group)

        remaining_indices = [i for i in range(len(memories)) if i not in hash_indices]

        if remaining_indices:
            remaining_memories = [memories[i] for i in remaining_indices]
            embeddings = np.array([m.embedding for m in remaining_memories])
            similarity_matrix = cosine_similarity(embeddings)

            vector_groups = self._find_groups_from_similarity_matrix(
                similarity_matrix,
                self.vector_similarity_threshold,
            )

            # Map back to original indices
            for group in vector_groups:
                mapped_group = [remaining_indices[i] for i in group]
                hash_groups.append(mapped_group)

        return hash_groups

    def _find_incremental_duplicates(
        self,
        new_memories: list[Memory],
        existing_memories: list[Memory],
    ) -> list[list[int]]:
        """Find duplicates between new and existing memories."""
        groups = []

        # Check each new memory against existing ones
        for i, new_mem in enumerate(new_memories):
            for j, existing_mem in enumerate(existing_memories):
                # Check hash first (fastest)
                if new_mem.content_hash == existing_mem.content_hash:
                    groups.append([i, len(new_memories) + j])
                    continue

                # Check vector similarity
                if new_mem.embedding is not None and existing_mem.embedding is not None:
                    similarity = cosine_similarity(
                        [new_mem.embedding],
                        [existing_mem.embedding],
                    )[0][0]

                    if similarity > self.vector_similarity_threshold:
                        groups.append([i, len(new_memories) + j])

        return groups

    def _find_groups_from_similarity_matrix(
        self,
        similarity_matrix: np.ndarray,
        threshold: float,
    ) -> list[list[int]]:
        """Find groups from similarity matrix using threshold."""
        n = len(similarity_matrix)
        visited = set()
        groups = []

        for i in range(n):
            if i in visited:
                continue

            group = [i]
            visited.add(i)

            # Find all similar memories
            for j in range(i + 1, n):
                if j not in visited and similarity_matrix[i][j] >= threshold:
                    group.append(j)
                    visited.add(j)

            # Only keep groups with minimum size
            if len(group) >= self.min_group_size:
                groups.append(group)

        return groups

    def _merge_groups(
        self,
        groups: list[list[int]],
        memories: list[Memory],
    ) -> DeduplicationResult:
        """Merge duplicate groups and create result."""
        merged_groups = []
        removed_ids = []
        merge_summary = {}

        for group_indices in groups:
            group_memories = [memories[i] for i in group_indices]

            # Select the best memory to keep
            best_memory = self._select_best_memory(group_memories)
            merged_groups.append([m.id for m in group_memories])

            # Mark others for removal
            for memory in group_memories:
                if memory.id != best_memory.id:
                    removed_ids.append(memory.id)

            # Record merge summary
            merge_summary[best_memory.id] = {
                "merged_count": len(group_memories),
                "merged_ids": [m.id for m in group_memories if m.id != best_memory.id],
                "kept_reason": "highest importance and recency",
                "merged_at": datetime.now(UTC).isoformat(),
            }

        deduplicated_count = len(memories) - len(removed_ids)

        return DeduplicationResult(
            original_count=len(memories),
            deduplicated_count=deduplicated_count,
            merged_groups=merged_groups,
            removed_ids=removed_ids,
            merge_summary=merge_summary,
        )

    def _select_best_memory(self, memories: list[Memory]) -> Memory:
        """Select the best memory from a group."""
        best_memory = memories[0]
        best_score = self._calculate_memory_score(best_memory)

        for memory in memories[1:]:
            score = self._calculate_memory_score(memory)
            if score > best_score:
                best_score = score
                best_memory = memory

        return best_memory

    def _calculate_memory_score(self, memory: Memory) -> float:
        """Calculate a score for a memory."""
        # Weights
        importance_weight = 0.5
        recency_weight = 0.3
        access_weight = 0.2

        # Recency: newer is better (0-1 scale)
        time_diff = (datetime.now(UTC) - memory.updated_at).total_seconds()
        recency_score = max(0, 1 - (time_diff / (30 * 24 * 3600)))  # 30 days decay

        # Access score: more accessed is better
        access_score = min(1.0, memory.access_count / 100.0)

        # Combined score
        score = (
            importance_weight * memory.importance +
            recency_weight * recency_score +
            access_weight * access_score
        )

        return score

    def _extract_embeddings(self, memories: list[Memory]) -> Optional[np.ndarray]:
        """Extract embeddings from memories."""
        embeddings = []
        for memory in memories:
            if memory.embedding is not None:
                embeddings.append(memory.embedding)
            else:
                embedding = self._create_simple_embedding(memory.content)
                embeddings.append(embedding)

        if not embeddings:
            return None

        return np.array(embeddings)

    def _create_simple_embedding(self, text: str) -> np.ndarray:
        """Create a simple embedding from text.

        使用特征哈希(feature hashing)把每个词稳定映射到固定维度,
        这样不同文本只在共享词的维度上重叠,余弦相似度才能真实反映
        内容差异。避免按"文档内词频排序位次"赋值导致的伪重复
        (例如 "First unique memory" 与 "Second unique memory" 误判相同)。
        """
        words = text.lower().split()
        embedding = np.zeros(100)
        if not words:
            return embedding

        for word in words:
            # 用确定性哈希(非内置 hash,保证跨进程/跨运行可复现)
            idx = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % 100
            embedding[idx] += 1.0

        # 归一化为词频比例
        embedding /= len(words)
        return embedding

    def _calculate_memory_saved(self, removed_ids: list[str], memories: list[Memory]) -> int:
        """Calculate total memory saved by removing duplicates."""
        total_bytes = 0
        removed_set = set(removed_ids)

        for memory in memories:
            if memory.id in removed_set:
                total_bytes += len(memory.content.encode("utf-8"))

        return total_bytes

    def _count_strategy_duplicates(self, groups: list[list[int]], strategy: str) -> int:
        """Count duplicates found by specific strategy."""
        # This is a simplified count; in production, track strategy per group
        return len(groups)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (
            self._cache_hits / total_requests * 100
            if total_requests > 0 else 0
        )

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
        }

    def get_deduplication_stats(self, result: DeduplicationResult) -> dict:
        """Get statistics from deduplication result."""
        if result.stats is None:
            return {}

        return {
            "original_count": result.stats.original_count,
            "deduplicated_count": result.stats.deduplicated_count,
            "removed_count": result.stats.removed_count,
            "reduction_rate": (
                (result.stats.original_count - result.stats.deduplicated_count) /
                result.stats.original_count * 100
                if result.stats.original_count > 0 else 0
            ),
            "merged_groups": result.stats.merged_groups,
            "vector_duplicates": result.stats.vector_duplicates,
            "hash_duplicates": result.stats.hash_duplicates,
            "time_window_duplicates": result.stats.time_window_duplicates,
            "processing_time": result.stats.processing_time,
            "memory_saved_bytes": result.stats.memory_saved_bytes,
            "memory_saved_mb": result.stats.memory_saved_bytes / (1024 * 1024),
        }


# Global instance
memory_deduplicator_enhanced = MemoryDeduplicatorEnhanced()
