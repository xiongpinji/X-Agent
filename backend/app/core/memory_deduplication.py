"""
Memory deduplication module for X-Agent.

Implements semantic similarity-based deduplication and automatic merging
of duplicate memories while preserving the most recent and relevant ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """Represents a single memory item."""

    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    relevance_score: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DeduplicationResult:
    """Result of deduplication operation."""

    original_count: int
    deduplicated_count: int
    merged_groups: list[list[str]] = field(default_factory=list)
    removed_ids: list[str] = field(default_factory=list)
    merge_summary: dict = field(default_factory=dict)


class MemoryDeduplicator:
    """
    Deduplicates memories based on semantic similarity.

    Automatically merges similar memories while preserving the most recent
    and relevant ones.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        min_group_size: int = 2,
        preserve_metadata: bool = True,
    ):
        """
        Initialize the deduplicator.

        Args:
            similarity_threshold: Minimum similarity score to consider memories as duplicates
            min_group_size: Minimum number of memories to form a group
            preserve_metadata: Whether to preserve metadata from all merged memories
        """
        self.similarity_threshold = similarity_threshold
        self.min_group_size = min_group_size
        self.preserve_metadata = preserve_metadata
        self.logger = logger

    def deduplicate(self, memories: list[Memory]) -> DeduplicationResult:
        """
        Deduplicate a list of memories.

        Args:
            memories: List of Memory objects to deduplicate

        Returns:
            DeduplicationResult containing deduplication statistics
        """
        if not memories:
            return DeduplicationResult(
                original_count=0,
                deduplicated_count=0,
            )

        # Build similarity matrix
        embeddings = self._extract_embeddings(memories)
        if embeddings is None or len(embeddings) == 0:
            self.logger.warning("No embeddings available for deduplication")
            return DeduplicationResult(
                original_count=len(memories),
                deduplicated_count=len(memories),
            )

        similarity_matrix = cosine_similarity(embeddings)

        # Find duplicate groups
        groups = self._find_duplicate_groups(similarity_matrix, memories)

        # Merge groups and create result
        result = self._merge_groups(groups, memories)

        self.logger.info(
            f"Deduplication complete: {result.original_count} -> {result.deduplicated_count} memories"
        )

        return result

    def _extract_embeddings(self, memories: list[Memory]) -> Optional[np.ndarray]:
        """Extract embeddings from memories."""
        embeddings = []
        for memory in memories:
            if memory.embedding is not None:
                embeddings.append(memory.embedding)
            else:
                # If no embedding, create a simple one from content
                embedding = self._create_simple_embedding(memory.content)
                embeddings.append(embedding)

        if not embeddings:
            return None

        return np.array(embeddings)

    def _create_simple_embedding(self, text: str) -> np.ndarray:
        """Create a simple embedding from text using TF-IDF-like approach."""
        # Simple word frequency-based embedding
        words = text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Create a fixed-size embedding (simplified)
        embedding = np.zeros(100)
        for i, (word, freq) in enumerate(sorted(word_freq.items())[:100]):
            embedding[i] = freq / len(words) if words else 0

        return embedding

    def _find_duplicate_groups(
        self,
        similarity_matrix: np.ndarray,
        memories: list[Memory],
    ) -> list[list[int]]:
        """Find groups of duplicate memories using similarity matrix."""
        n = len(memories)
        visited = set()
        groups = []

        for i in range(n):
            if i in visited:
                continue

            group = [i]
            visited.add(i)

            # Find all memories similar to this one
            for j in range(i + 1, n):
                if j in visited:
                    continue

                if similarity_matrix[i][j] >= self.similarity_threshold:
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
                "kept_reason": "highest relevance and recency",
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
        """Select the best memory from a group based on relevance and recency."""
        # Score based on relevance and recency
        best_memory = memories[0]
        best_score = self._calculate_memory_score(best_memory)

        for memory in memories[1:]:
            score = self._calculate_memory_score(memory)
            if score > best_score:
                best_score = score
                best_memory = memory

        return best_memory

    def _calculate_memory_score(self, memory: Memory) -> float:
        """Calculate a score for a memory based on relevance and recency."""
        # Combine relevance score with recency
        recency_weight = 0.3
        relevance_weight = 0.7

        # Recency: newer is better (0-1 scale)
        time_diff = (datetime.now() - memory.updated_at).total_seconds()
        recency_score = max(0, 1 - (time_diff / (30 * 24 * 3600)))  # 30 days decay

        # Combined score
        score = (relevance_weight * memory.relevance_score +
                recency_weight * recency_score)

        return score

    def batch_deduplicate(
        self,
        memory_batches: list[list[Memory]],
    ) -> list[DeduplicationResult]:
        """
        Deduplicate multiple batches of memories.

        Args:
            memory_batches: List of memory batches to deduplicate

        Returns:
            List of DeduplicationResult objects
        """
        results = []
        for batch in memory_batches:
            result = self.deduplicate(batch)
            results.append(result)

        return results

    def get_deduplication_stats(self, result: DeduplicationResult) -> dict:
        """Get statistics from deduplication result."""
        return {
            "original_count": result.original_count,
            "deduplicated_count": result.deduplicated_count,
            "reduction_rate": (
                (result.original_count - result.deduplicated_count) /
                result.original_count * 100
                if result.original_count > 0 else 0
            ),
            "merged_groups_count": len(result.merged_groups),
            "removed_count": len(result.removed_ids),
        }


# Global instance
memory_deduplicator = MemoryDeduplicator()
