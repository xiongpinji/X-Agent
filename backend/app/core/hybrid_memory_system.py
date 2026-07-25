"""Hybrid memory system combining hot (filesystem), cold (vector), and graph storage.

Architecture (as actually implemented):
- Hot tier: Fast filesystem-based Markdown storage for recent/important memories
- Cold tier: Vector database (Qdrant) for semantic search and long-term storage.
  Requires an injected ``qdrant_client``; without one ``ColdMemoryStore`` is a
  no-op degraded tier (see api/memory_enhanced.py ``degraded_tiers`` surfacing).
- Graph tier: Neo4j for relationship management. Requires an injected driver
  (or ``GraphMemoryStore.create_driver``); without one it is an explicit no-op
  degraded tier (``GraphMemoryStore.available == False``).
- Classifier: Automatic categorization and importance scoring
- Merger: Deduplication and conflict resolution

Model unification (P1-13): the tier-local ``Memory`` model is one of three
legacy memory representations; use ``Memory.to_canonical()`` /
``Memory.from_canonical()`` to interoperate with the canonical model in
``backend.app.core.memory_dedup_adapter``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.contracts import RunContext
from backend.app.core.embeddings import EmbeddingModel
from backend.app.core.memory_dedup_adapter import (
    CanonicalMemory,
    canonical_from_hybrid_memory,
    hybrid_memory_from_canonical,
)


class Memory(BaseModel):
    """Unified memory representation across all tiers."""

    id: str
    content: str
    category: str = "reference"  # user, feedback, project, reference
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tier: str = "hot"  # hot, cold, graph
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    embedding: list[float] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    related_ids: list[str] = Field(default_factory=list)

    def to_canonical(self) -> CanonicalMemory:
        """Convert to the canonical cross-subsystem memory model."""
        return canonical_from_hybrid_memory(self)

    @classmethod
    def from_canonical(cls, canonical: CanonicalMemory) -> Memory:
        """Build a tier Memory from the canonical model."""
        return hybrid_memory_from_canonical(canonical)


class MemoryTierStats(BaseModel):
    """Statistics for each memory tier."""

    hot_count: int = 0
    cold_count: int = 0
    graph_count: int = 0
    total_count: int = 0
    hot_size_mb: float = 0.0
    avg_importance: float = 0.0
    last_sync: datetime | None = None


class HybridMemorySystem:
    """Three-tier memory system with intelligent routing and auto-tiering.

    Features:
    - Automatic tier selection based on query type and memory characteristics
    - Hot data auto-degradation to cold storage based on age/access patterns
    - Unified query interface across all tiers
    - Memory synchronization and consistency
    - Deduplication and conflict resolution
    """

    def __init__(
        self,
        hot_store: Any,  # HotMemoryStore
        cold_store: Any,  # ColdMemoryStore
        graph_store: Any,  # GraphMemoryStore
        classifier: Any,  # MemoryClassifier
        merger: Any,  # MemoryMerger
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.hot_store = hot_store
        self.cold_store = cold_store
        self.graph_store = graph_store
        self.classifier = classifier
        self.merger = merger
        self.embedding_model = embedding_model

        # Configuration
        self.hot_tier_max_age_days = 7
        self.hot_tier_max_size_mb = 100
        self.hot_tier_importance_threshold = 0.6
        self.cold_tier_similarity_threshold = 0.7

        # Caching
        self._memory_cache: dict[str, Memory] = {}
        self._cache_ttl_seconds = 300

    async def store(
        self,
        memory: Memory,
        tier: str = "auto",
        context: RunContext | None = None,
    ) -> str:
        """Store memory with automatic tier selection.

        Args:
            memory: Memory to store
            tier: Target tier ("auto", "hot", "cold", "graph")
            context: Optional run context for metadata

        Returns:
            Memory ID
        """
        # Classify if not already classified
        if memory.category == "reference":
            memory.category = self.classifier.classify(memory)

        # Score importance
        memory.importance = self.classifier.score_importance(memory)

        # Detect duplicates
        duplicates = await self._detect_duplicates(memory)
        if duplicates:
            merged = await self.merger.merge([memory, *duplicates])
            memory = merged

        # Select tier
        if tier == "auto":
            tier = self._select_tier(memory)

        # Store in selected tier
        memory_id = None
        if tier in ("hot", "auto"):
            memory_id = await self.hot_store.save(memory)
            memory.tier = "hot"
        elif tier == "cold":
            if not memory.embedding and self.embedding_model:
                memory.embedding = await self._embed(memory.content)
            memory_id = await self.cold_store.store(memory, memory.embedding)
            memory.tier = "cold"
        elif tier == "graph":
            memory_id = await self.graph_store.add_node(memory)
            memory.tier = "graph"

        # Update cache
        if memory_id:
            memory.id = memory_id
            self._memory_cache[memory_id] = memory

        return memory_id or memory.id

    async def recall(
        self,
        query: str,
        limit: int = 5,
        context: RunContext | None = None,
    ) -> list[Memory]:
        """Recall memories using hybrid search.

        Searches across all tiers and combines results.

        Args:
            query: Search query
            limit: Maximum results to return
            context: Optional run context

        Returns:
            List of memories ranked by relevance
        """
        results: list[tuple[Memory, float]] = []

        # Hot tier: fast text search
        hot_results = await self.hot_store.search(query)
        for mem in hot_results[:limit]:
            score = self._calculate_relevance_score(mem, query, "hot")
            results.append((mem, score))

        # Cold tier: semantic search
        if self.embedding_model:
            query_embedding = await self._embed(query)
            cold_results = await self.cold_store.search(
                query_embedding,
                limit=limit,
            )
            for mem in cold_results:
                if mem.id not in [r[0].id for r in results]:
                    score = self._calculate_relevance_score(mem, query, "cold")
                    results.append((mem, score))

        # Graph tier: relationship-based search
        graph_results = await self.graph_store.find_related(query, depth=2)
        for mem in graph_results:
            if mem.id not in [r[0].id for r in results]:
                score = self._calculate_relevance_score(mem, query, "graph")
                results.append((mem, score))

        # Sort by relevance and return top results
        results.sort(key=lambda x: x[1], reverse=True)
        return [mem for mem, _ in results[:limit]]

    async def search(
        self,
        query: str,
        search_type: str = "hybrid",
        limit: int = 5,
        context: RunContext | None = None,
    ) -> list[Memory]:
        """Search memories with specified strategy.

        Args:
            query: Search query
            search_type: "hybrid", "text", "semantic", "graph"
            limit: Maximum results
            context: Optional run context

        Returns:
            List of matching memories
        """
        if search_type == "hybrid":
            return await self.recall(query, limit, context)

        if search_type == "text":
            results = await self.hot_store.search(query)
            return results[:limit]

        if search_type == "semantic":
            if not self.embedding_model:
                return []
            query_embedding = await self._embed(query)
            results = await self.cold_store.search(query_embedding, limit)
            return results

        if search_type == "graph":
            results = await self.graph_store.find_related(query, depth=2)
            return results[:limit]

        return []

    async def relate(
        self,
        memory_id1: str,
        memory_id2: str,
        relation: str,
    ) -> bool:
        """Create relationship between two memories.

        Args:
            memory_id1: First memory ID
            memory_id2: Second memory ID
            relation: Relationship type (e.g., "related_to", "depends_on")

        Returns:
            Success status
        """
        try:
            await self.graph_store.add_relation(memory_id1, memory_id2, relation)
            return True
        except Exception:
            return False

    async def sync_tiers(self) -> dict[str, Any]:
        """Synchronize memories across tiers.

        Handles:
        - Hot to cold migration for old/low-importance memories
        - Cold to hot promotion for frequently accessed memories
        - Graph relationship updates
        - Deduplication across tiers

        Returns:
            Sync statistics
        """
        stats = {
            "migrated_to_cold": 0,
            "promoted_to_hot": 0,
            "deduplicated": 0,
            "errors": 0,
        }

        try:
            # Get all hot memories
            hot_memories = await self.hot_store.list_by_category("all")

            for memory in hot_memories:
                # Check if should migrate to cold
                age_days = (datetime.now(UTC) - memory.created_at).days
                if (
                    age_days > self.hot_tier_max_age_days
                    or memory.importance < 0.3
                ):
                    try:
                        if not memory.embedding and self.embedding_model:
                            memory.embedding = await self._embed(memory.content)
                        await self.cold_store.store(memory, memory.embedding)
                        await self.hot_store.delete(memory.id)
                        stats["migrated_to_cold"] += 1
                    except Exception:
                        stats["errors"] += 1

            # Get frequently accessed cold memories
            cold_memories = await self.cold_store.search_by_metadata(
                {"access_count": {">": 5}}
            )
            for memory in cold_memories:
                if memory.importance >= self.hot_tier_importance_threshold:
                    try:
                        await self.hot_store.save(memory)
                        stats["promoted_to_hot"] += 1
                    except Exception:
                        stats["errors"] += 1

            # Rebuild indexes
            await self.hot_store.rebuild_index()

        except Exception:
            stats["errors"] += 1

        stats["timestamp"] = datetime.now(UTC).isoformat()
        return stats

    async def get_stats(self) -> MemoryTierStats:
        """Get statistics about memory usage across tiers."""
        hot_count = len(await self.hot_store.list_by_category("all"))
        cold_count = await self.cold_store.count()
        graph_count = await self.graph_store.count()

        return MemoryTierStats(
            hot_count=hot_count,
            cold_count=cold_count,
            graph_count=graph_count,
            total_count=hot_count + cold_count + graph_count,
            last_sync=datetime.now(UTC),
        )

    def _select_tier(self, memory: Memory) -> str:
        """Select appropriate tier for memory storage.

        Rules:
        - Hot: Recent, high-importance, frequently accessed
        - Cold: Older, semantic search needed
        - Graph: Relationship-heavy, knowledge graph
        """
        age_days = (datetime.now(UTC) - memory.created_at).days

        # Prefer hot for recent, important memories
        if age_days < 7 and memory.importance >= 0.6:
            return "hot"

        # Use cold for older or less important memories
        if age_days > 30 or memory.importance < 0.3:
            return "cold"

        # Use graph for relationship-heavy content
        if len(memory.related_ids) > 3 or memory.category == "project":
            return "graph"

        # Default to hot for recent memories
        if age_days < 7:
            return "hot"

        return "cold"

    def _calculate_relevance_score(
        self,
        memory: Memory,
        query: str,
        tier: str,
    ) -> float:
        """Calculate relevance score for a memory."""
        score = 0.0

        # Base score from importance
        score += memory.importance * 0.3

        # Text similarity
        query_terms = set(query.lower().split())
        content_terms = set(memory.content.lower().split())
        overlap = len(query_terms & content_terms)
        score += min(overlap / max(len(query_terms), 1), 1.0) * 0.4

        # Freshness bonus
        age_days = (datetime.now(UTC) - memory.accessed_at).days
        freshness = 1.0 / (1.0 + age_days)
        score += freshness * 0.2

        # Tier-specific adjustments
        if tier == "hot":
            score *= 1.1  # Boost hot tier results
        elif tier == "graph":
            score *= 0.9  # Slight penalty for graph tier

        return score

    async def _detect_duplicates(self, memory: Memory) -> list[Memory]:
        """Detect potential duplicate memories."""
        duplicates = []

        # Check hot store
        hot_results = await self.hot_store.search(memory.content[:50])
        for result in hot_results:
            if result.id != memory.id:
                similarity = self._text_similarity(memory.content, result.content)
                if similarity > 0.8:
                    duplicates.append(result)

        # Check cold store if embedding available
        if self.embedding_model and not memory.embedding:
            memory.embedding = await self._embed(memory.content)

        if memory.embedding:
            cold_results = await self.cold_store.search(
                memory.embedding,
                limit=5,
            )
            for result in cold_results:
                if result.id != memory.id and result not in duplicates:
                    if result.embedding:
                        similarity = self._embedding_similarity(
                            memory.embedding,
                            result.embedding,
                        )
                        if similarity > self.cold_tier_similarity_threshold:
                            duplicates.append(result)

        return duplicates

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        if not self.embedding_model:
            return []
        result = self.embedding_model.embed(text)
        if asyncio.iscoroutine(result):
            return await result
        return result

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _embedding_similarity(emb1: list[float], emb2: list[float]) -> float:
        """Calculate cosine similarity between embeddings."""
        if not emb1 or not emb2 or len(emb1) != len(emb2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(emb1, emb2, strict=False))
        magnitude1 = sum(a * a for a in emb1) ** 0.5
        magnitude2 = sum(b * b for b in emb2) ** 0.5
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)
