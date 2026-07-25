"""Advanced memory fusion with deduplication, graph association, and compression."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from backend.app.core.embeddings import DeterministicEmbeddingModel, EmbeddingModel
from backend.app.core.memory_graph import MemoryGraph


@dataclass
class Memory:
    """Represents a single memory item."""
    id: str
    content: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    importance: float = 1.0
    access_count: int = 0


@dataclass
class MemoryCluster:
    """Represents a cluster of similar memories."""
    id: str
    memories: list[Memory] = field(default_factory=list)
    representative: Memory | None = None
    similarity_threshold: float = 0.85


class MemoryFusion:
    """Advanced memory fusion system with deduplication and compression."""

    def __init__(
        self,
        embedding_model: EmbeddingModel | None = None,
        similarity_threshold: float = 0.85,
        compression_ratio: float = 0.7,
    ):
        """Initialize memory fusion system.

        Args:
            embedding_model: Embedding model for vector operations
            similarity_threshold: Threshold for considering memories as duplicates
            compression_ratio: Target ratio for memory compression (0-1)
        """
        self.embedding_model = embedding_model or DeterministicEmbeddingModel()
        self.similarity_threshold = similarity_threshold
        self.compression_ratio = compression_ratio
        self.memory_graph = MemoryGraph()
        self._memory_cache: dict[str, Memory] = {}

    async def add_memory(self, memory: Memory) -> Memory:
        """Add a memory with embedding generation."""
        if not memory.embedding:
            embedding = self.embedding_model.embed(memory.content)
            if isinstance(embedding, list):
                memory.embedding = embedding
            else:
                memory.embedding = await embedding

        self.memory_graph.add_text(memory.content)
        self._memory_cache[memory.id] = memory
        return memory

    async def deduplicate(self, memories: list[Memory]) -> list[Memory]:
        """Remove duplicate memories using similarity analysis.

        Args:
            memories: List of memories to deduplicate

        Returns:
            List of unique memories after deduplication
        """
        if not memories:
            return []

        # Generate embeddings for all memories
        for memory in memories:
            if not memory.embedding:
                embedding = self.embedding_model.embed(memory.content)
                if isinstance(embedding, list):
                    memory.embedding = embedding
                else:
                    memory.embedding = await embedding

        # Calculate similarity matrix
        embeddings = np.array([m.embedding for m in memories])
        similarities = self._cosine_similarity_matrix(embeddings)

        # Find unique memories using clustering
        unique_memories = []
        seen = set()

        for i, _memory in enumerate(memories):
            if i in seen:
                continue

            # Find similar memories
            similar_indices = np.where(similarities[i] > self.similarity_threshold)[0]

            # Merge similar memories
            merged_memory = await self._merge_similar_memories(
                [memories[j] for j in similar_indices]
            )

            unique_memories.append(merged_memory)
            for j in similar_indices:
                seen.add(j)

        return unique_memories

    async def compress_memories(self, memories: list[Memory]) -> list[Memory]:
        """Compress memories by removing redundant information.

        Args:
            memories: List of memories to compress

        Returns:
            Compressed list of memories
        """
        if not memories:
            return []

        # Sort by importance and access count
        sorted_memories = sorted(
            memories,
            key=lambda m: (m.importance, m.access_count),
            reverse=True
        )

        # Calculate target size
        target_size = max(1, int(len(sorted_memories) * self.compression_ratio))

        # Keep top memories and compress others
        kept_memories = sorted_memories[:target_size]
        compressed_memories = sorted_memories[target_size:]

        # Merge compressed memories into clusters
        if compressed_memories:
            clusters = await self._cluster_memories(compressed_memories)
            for cluster in clusters:
                if cluster.representative:
                    kept_memories.append(cluster.representative)

        return kept_memories

    async def associate_memories(self, memory: Memory) -> list[Memory]:
        """Find related memories using graph association.

        Args:
            memory: Memory to find associations for

        Returns:
            List of related memories
        """
        # Extract terms from memory content
        terms = set(MemoryGraph.extract_terms(memory.content))

        # Find related terms using graph
        related_terms = self.memory_graph.related_terms(terms)

        # Find memories containing related terms
        related_memories = []
        for cached_memory in self._memory_cache.values():
            if cached_memory.id == memory.id:
                continue

            cached_terms = set(MemoryGraph.extract_terms(cached_memory.content))
            if cached_terms & related_terms:
                related_memories.append(cached_memory)

        return related_memories

    async def _merge_similar_memories(self, memories: list[Memory]) -> Memory:
        """Merge similar memories into a single representative memory.

        Args:
            memories: List of similar memories to merge

        Returns:
            Merged representative memory
        """
        if not memories:
            raise ValueError("Cannot merge empty memory list")

        if len(memories) == 1:
            return memories[0]

        # Use the memory with highest importance as base
        base_memory = max(memories, key=lambda m: m.importance)

        # Merge metadata
        merged_metadata = {}
        for memory in memories:
            merged_metadata.update(memory.metadata)

        # Combine content
        combined_content = " | ".join([m.content for m in memories])

        # Create merged memory
        merged = Memory(
            id=base_memory.id,
            content=combined_content,
            embedding=base_memory.embedding,
            metadata=merged_metadata,
            created_at=min(m.created_at for m in memories),
            importance=max(m.importance for m in memories),
            access_count=sum(m.access_count for m in memories),
        )

        return merged

    async def _cluster_memories(self, memories: list[Memory]) -> list[MemoryCluster]:
        """Cluster similar memories together.

        Args:
            memories: List of memories to cluster

        Returns:
            List of memory clusters
        """
        if not memories:
            return []

        # Generate embeddings
        for memory in memories:
            if not memory.embedding:
                embedding = self.embedding_model.embed(memory.content)
                if isinstance(embedding, list):
                    memory.embedding = embedding
                else:
                    memory.embedding = await embedding

        # Simple clustering using similarity
        clusters: list[MemoryCluster] = []
        used = set()

        for i, memory in enumerate(memories):
            if i in used:
                continue

            cluster = MemoryCluster(id=f"cluster_{i}")
            cluster.memories.append(memory)
            used.add(i)

            # Find similar memories
            embeddings = np.array([m.embedding for m in memories])
            similarities = self._cosine_similarity_matrix(embeddings)

            for j in range(i + 1, len(memories)):
                if j not in used and similarities[i][j] > self.similarity_threshold:
                    cluster.memories.append(memories[j])
                    used.add(j)

            # Create representative
            if cluster.memories:
                cluster.representative = max(
                    cluster.memories,
                    key=lambda m: m.importance
                )

            clusters.append(cluster)

        return clusters

    @staticmethod
    def _cosine_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity matrix for embeddings.

        Args:
            embeddings: Array of embeddings (n_samples, n_features)

        Returns:
            Similarity matrix (n_samples, n_samples)
        """
        # Normalize embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / (norms + 1e-10)

        # Calculate cosine similarity
        similarity = np.dot(normalized, normalized.T)
        return similarity

    def get_memory_stats(self) -> dict[str, Any]:
        """Get statistics about cached memories.

        Returns:
            Dictionary with memory statistics
        """
        memories = list(self._memory_cache.values())

        if not memories:
            return {
                "total_memories": 0,
                "avg_importance": 0.0,
                "avg_access_count": 0,
            }

        return {
            "total_memories": len(memories),
            "avg_importance": sum(m.importance for m in memories) / len(memories),
            "avg_access_count": sum(m.access_count for m in memories) / len(memories),
            "total_content_length": sum(len(m.content) for m in memories),
        }


# Global instance
memory_fusion = MemoryFusion()
