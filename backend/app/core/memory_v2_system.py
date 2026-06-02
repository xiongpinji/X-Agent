"""Memory System V2 - Core Implementation

Three-tier hybrid memory architecture with automatic skill generation,
active memory consolidation, and mixed retrieval strategies.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    """Memory tier classification."""
    SKILL = "skill"          # Layer 1: Program memory (SKILL.md)
    NUDGE = "nudge"          # Layer 2: Active consolidation
    ARCHIVE = "archive"      # Layer 3: Long-term storage


class MemoryCategory(str, Enum):
    """Memory content category."""
    SKILL = "skill"
    PATTERN = "pattern"
    DECISION = "decision"
    FEEDBACK = "feedback"
    REFERENCE = "reference"


@dataclass
class ImportanceScore:
    """Memory importance scoring result."""
    total: float = 0.0
    access_frequency: float = 0.0
    freshness: float = 0.0
    content_quality: float = 0.0
    relationship_centrality: float = 0.0
    user_mark: float = 0.0
    execution_success: float = 0.0

    # Weights
    w_frequency: float = 0.25
    w_freshness: float = 0.20
    w_quality: float = 0.20
    w_centrality: float = 0.15
    w_mark: float = 0.15
    w_success: float = 0.05


@dataclass
class MemoryVersion:
    """Single version of a memory."""
    version: int
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    author_agent_id: str | None = None
    change_type: str = "create"  # create, update, merge, rollback
    change_summary: str = ""
    metadata: dict = field(default_factory=dict)


class MemoryV2Item(BaseModel):
    """Unified memory item for V2 system."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    agent_id: str | None = None

    # Content
    content: str
    summary: str = ""
    category: MemoryCategory = MemoryCategory.REFERENCE
    tier: MemoryTier = MemoryTier.NUDGE

    # Scoring
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    importance_score: ImportanceScore = Field(default_factory=ImportanceScore)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    # Relationships
    related_memory_ids: list[str] = Field(default_factory=list)
    source_memory_ids: list[str] = Field(default_factory=list)

    # Embedding
    embedding: list[float] = Field(default_factory=list)

    # Versioning
    current_version: int = 1
    versions: list[MemoryVersion] = Field(default_factory=list)

    # Access tracking
    access_count: int = 0
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Deduplication
    is_duplicate: bool = False
    duplicate_of: str | None = None
    merged_from: list[str] = Field(default_factory=list)


class MemoryV2System:
    """Core V2 memory system with three-tier architecture."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        enable_skill_generation: bool = True,
        enable_nudge_consolidation: bool = True,
        enable_hybrid_retrieval: bool = True,
    ):
        self.storage_path = Path(storage_path) if storage_path else None
        self.enable_skill_generation = enable_skill_generation
        self.enable_nudge_consolidation = enable_nudge_consolidation
        self.enable_hybrid_retrieval = enable_hybrid_retrieval

        # Storage
        self._memories: dict[str, MemoryV2Item] = {}
        self._tier_index: dict[MemoryTier, list[str]] = {
            tier: [] for tier in MemoryTier
        }

        # Caching
        self._cache: dict[str, MemoryV2Item] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_timestamps: dict[str, datetime] = {}

        # Statistics
        self._stats = {
            "total_stored": 0,
            "total_retrieved": 0,
            "total_deduplicated": 0,
            "total_consolidated": 0,
        }

        # Load from disk if available
        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    async def store(
        self,
        content: str,
        tenant_id: str,
        agent_id: str | None = None,
        category: MemoryCategory = MemoryCategory.REFERENCE,
        tier: MemoryTier | str = "auto",
        importance: float | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
        related_memory_ids: list[str] | None = None,
    ) -> str:
        """Store a memory item with automatic tier selection."""

        # Create memory item
        memory = MemoryV2Item(
            tenant_id=tenant_id,
            agent_id=agent_id,
            content=content,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
            related_memory_ids=related_memory_ids or [],
        )

        # Add initial version
        memory.versions.append(MemoryVersion(
            version=1,
            content=content,
            author_agent_id=agent_id,
            change_type="create",
            change_summary="Initial creation",
        ))

        # Detect and handle duplicates
        duplicates = await self._detect_duplicates(memory)
        if duplicates:
            memory = await self._merge_duplicates(memory, duplicates)
            self._stats["total_deduplicated"] += len(duplicates)

        # Calculate importance if not provided
        if importance is None:
            importance = await self._calculate_importance(memory)
        memory.importance = importance

        # Select tier if auto
        if tier == "auto":
            tier = self._select_tier(memory)
        memory.tier = MemoryTier(tier) if isinstance(tier, str) else tier

        # Store memory
        self._memories[memory.id] = memory
        self._tier_index[memory.tier].append(memory.id)
        self._stats["total_stored"] += 1

        # Save to disk
        if self.storage_path:
            self._save_to_disk(memory)

        logger.info(f"Stored memory {memory.id} in tier {memory.tier}")
        return memory.id

    async def retrieve(
        self,
        memory_id: str,
        tenant_id: str | None = None,
    ) -> MemoryV2Item | None:
        """Retrieve a memory by ID."""

        # Check cache first
        if memory_id in self._cache:
            if self._is_cache_valid(memory_id):
                return self._cache[memory_id]
            else:
                del self._cache[memory_id]

        # Get from storage
        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        # Check tenant access
        if tenant_id and memory.tenant_id != tenant_id:
            return None

        # Update access tracking
        memory.access_count += 1
        memory.last_accessed = datetime.now(UTC)
        self._stats["total_retrieved"] += 1

        # Update cache
        self._cache[memory_id] = memory
        self._cache_timestamps[memory_id] = datetime.now(UTC)

        return memory

    async def search(
        self,
        query: str,
        tenant_id: str,
        limit: int = 10,
        tier: MemoryTier | None = None,
        category: MemoryCategory | None = None,
    ) -> list[MemoryV2Item]:
        """Search memories using hybrid retrieval."""

        candidates = self._get_search_candidates(tenant_id, tier, category)

        # Score candidates
        scored = []
        for memory in candidates:
            score = await self._score_memory_for_query(memory, query)
            if score > 0:
                scored.append((memory, score))

        # Sort and return top-k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored[:limit]]

    async def consolidate(
        self,
        tenant_id: str,
        source_tier: MemoryTier = MemoryTier.NUDGE,
        target_tier: MemoryTier = MemoryTier.ARCHIVE,
        min_importance: float = 0.3,
        max_items: int = 50,
    ) -> dict[str, Any]:
        """Consolidate memories from source to target tier."""

        # Get candidates
        candidates = [
            self._memories[mid]
            for mid in self._tier_index.get(source_tier, [])
            if self._memories[mid].tenant_id == tenant_id
            and self._memories[mid].importance >= min_importance
        ]

        # Sort by importance
        candidates.sort(key=lambda m: m.importance, reverse=True)
        selected = candidates[:max_items]

        if not selected:
            return {"consolidated": 0, "target_tier": target_tier}

        # Create consolidated memory
        consolidated = await self._create_consolidated_memory(
            selected, tenant_id, target_tier
        )

        # Update tier index
        for memory in selected:
            if memory.id in self._tier_index[source_tier]:
                self._tier_index[source_tier].remove(memory.id)
            memory.tier = target_tier
            self._tier_index[target_tier].append(memory.id)

        self._stats["total_consolidated"] += len(selected)

        return {
            "consolidated": len(selected),
            "target_tier": target_tier,
            "consolidated_memory_id": consolidated.id,
        }

    async def update_version(
        self,
        memory_id: str,
        new_content: str,
        agent_id: str | None = None,
        change_summary: str = "",
    ) -> MemoryVersion | None:
        """Create a new version of a memory."""

        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        # Create new version
        new_version = MemoryVersion(
            version=memory.current_version + 1,
            content=new_content,
            author_agent_id=agent_id,
            change_type="update",
            change_summary=change_summary,
        )

        memory.versions.append(new_version)
        memory.current_version += 1
        memory.content = new_content
        memory.updated_at = datetime.now(UTC)

        # Recalculate importance
        memory.importance = await self._calculate_importance(memory)

        # Save to disk
        if self.storage_path:
            self._save_to_disk(memory)

        logger.info(f"Updated memory {memory_id} to version {new_version.version}")
        return new_version

    async def rollback_version(
        self,
        memory_id: str,
        target_version: int,
    ) -> MemoryVersion | None:
        """Rollback memory to a previous version."""

        memory = self._memories.get(memory_id)
        if memory is None:
            return None

        # Find target version
        target = None
        for v in memory.versions:
            if v.version == target_version:
                target = v
                break

        if target is None:
            return None

        # Create rollback version
        rollback = MemoryVersion(
            version=memory.current_version + 1,
            content=target.content,
            author_agent_id=None,
            change_type="rollback",
            change_summary=f"Rolled back to version {target_version}",
        )

        memory.versions.append(rollback)
        memory.current_version += 1
        memory.content = target.content
        memory.updated_at = datetime.now(UTC)

        # Save to disk
        if self.storage_path:
            self._save_to_disk(memory)

        logger.info(f"Rolled back memory {memory_id} to version {target_version}")
        return rollback

    def get_statistics(self) -> dict[str, Any]:
        """Get system statistics."""

        tier_counts = {
            tier: len(self._tier_index[tier])
            for tier in MemoryTier
        }

        return {
            **self._stats,
            "tier_counts": tier_counts,
            "cache_size": len(self._cache),
            "total_memories": len(self._memories),
        }

    # Private methods

    async def _detect_duplicates(
        self,
        memory: MemoryV2Item,
        threshold: float = 0.85,
    ) -> list[MemoryV2Item]:
        """Detect duplicate memories."""

        duplicates = []
        for existing in self._memories.values():
            if existing.tenant_id != memory.tenant_id:
                continue

            similarity = await self._calculate_similarity(memory, existing)
            if similarity > threshold:
                duplicates.append(existing)

        return duplicates

    async def _merge_duplicates(
        self,
        memory: MemoryV2Item,
        duplicates: list[MemoryV2Item],
    ) -> MemoryV2Item:
        """Merge duplicate memories."""

        # Keep the one with highest importance
        all_memories = [memory] + duplicates
        all_memories.sort(key=lambda m: m.importance, reverse=True)
        primary = all_memories[0]

        # Merge metadata
        for dup in all_memories[1:]:
            primary.merged_from.append(dup.id)
            primary.tags.extend(dup.tags)
            primary.related_memory_ids.extend(dup.related_memory_ids)

        # Remove duplicates
        for dup in duplicates:
            if dup.id in self._memories:
                del self._memories[dup.id]

        return primary

    async def _calculate_importance(
        self,
        memory: MemoryV2Item,
    ) -> float:
        """Calculate memory importance score."""

        score = ImportanceScore()

        # Access frequency (0-1)
        score.access_frequency = min(memory.access_count / 100, 1.0)

        # Freshness (0-1)
        days_old = (datetime.now(UTC) - memory.last_accessed).days
        score.freshness = 1.0 / (1.0 + days_old / 7)

        # Content quality (0-1)
        content_len = len(memory.content)
        score.content_quality = min(content_len / 1000, 1.0) * 0.5
        if "example" in memory.content.lower():
            score.content_quality += 0.3
        if "test" in memory.content.lower():
            score.content_quality += 0.2
        score.content_quality = min(score.content_quality, 1.0)

        # Relationship centrality (0-1)
        score.relationship_centrality = min(
            len(memory.related_memory_ids) / 10, 1.0
        )

        # User mark (0-1)
        score.user_mark = 1.0 if memory.metadata.get("starred") else 0.0

        # Execution success (0-1)
        total_exec = memory.metadata.get("total_executions", 0)
        if total_exec > 0:
            successful = memory.metadata.get("successful_executions", 0)
            score.execution_success = successful / total_exec
        else:
            score.execution_success = 0.5

        # Calculate total
        score.total = (
            score.w_frequency * score.access_frequency +
            score.w_freshness * score.freshness +
            score.w_quality * score.content_quality +
            score.w_centrality * score.relationship_centrality +
            score.w_mark * score.user_mark +
            score.w_success * score.execution_success
        )

        return min(score.total, 1.0)

    def _select_tier(self, memory: MemoryV2Item) -> MemoryTier:
        """Select appropriate tier for memory."""

        if memory.category == MemoryCategory.SKILL:
            return MemoryTier.SKILL

        if memory.importance >= 0.7:
            return MemoryTier.NUDGE

        return MemoryTier.ARCHIVE

    def _get_search_candidates(
        self,
        tenant_id: str,
        tier: MemoryTier | None = None,
        category: MemoryCategory | None = None,
    ) -> list[MemoryV2Item]:
        """Get candidate memories for search."""

        candidates = []
        for memory in self._memories.values():
            if memory.tenant_id != tenant_id:
                continue
            if tier and memory.tier != tier:
                continue
            if category and memory.category != category:
                continue
            candidates.append(memory)

        return candidates

    async def _score_memory_for_query(
        self,
        memory: MemoryV2Item,
        query: str,
    ) -> float:
        """Score memory relevance for query."""

        # Keyword matching
        query_terms = set(query.lower().split())
        content_terms = set(memory.content.lower().split())
        keyword_score = len(query_terms & content_terms) / len(query_terms)

        # Importance boost
        importance_boost = memory.importance * 0.2

        # Freshness boost
        days_old = (datetime.now(UTC) - memory.last_accessed).days
        freshness_boost = 1.0 / (1.0 + days_old / 7) * 0.1

        return keyword_score + importance_boost + freshness_boost

    async def _calculate_similarity(
        self,
        memory1: MemoryV2Item,
        memory2: MemoryV2Item,
    ) -> float:
        """Calculate similarity between two memories."""

        # Simple keyword-based similarity
        terms1 = set(memory1.content.lower().split())
        terms2 = set(memory2.content.lower().split())

        if not terms1 or not terms2:
            return 0.0

        intersection = len(terms1 & terms2)
        union = len(terms1 | terms2)

        return intersection / union if union > 0 else 0.0

    async def _create_consolidated_memory(
        self,
        memories: list[MemoryV2Item],
        tenant_id: str,
        target_tier: MemoryTier,
    ) -> MemoryV2Item:
        """Create a consolidated memory from multiple memories."""

        # Create summary
        summary_lines = ["Consolidated memory:"]
        for m in memories:
            excerpt = m.content[:100] + "..." if len(m.content) > 100 else m.content
            summary_lines.append(f"- {excerpt}")
        summary = "\n".join(summary_lines)

        # Create consolidated memory
        consolidated = MemoryV2Item(
            tenant_id=tenant_id,
            content=summary,
            category=MemoryCategory.REFERENCE,
            tier=target_tier,
            source_memory_ids=[m.id for m in memories],
            metadata={"kind": "consolidation"},
        )

        # Store
        self._memories[consolidated.id] = consolidated
        self._tier_index[target_tier].append(consolidated.id)

        return consolidated

    def _is_cache_valid(self, memory_id: str) -> bool:
        """Check if cache entry is still valid."""

        if memory_id not in self._cache_timestamps:
            return False

        age = datetime.now(UTC) - self._cache_timestamps[memory_id]
        return age < self._cache_ttl

    def _load_from_disk(self) -> None:
        """Load memories from disk."""

        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    memory = MemoryV2Item(**data)
                    self._memories[memory.id] = memory
                    self._tier_index[memory.tier].append(memory.id)

            logger.info(f"Loaded {len(self._memories)} memories from disk")
        except Exception as e:
            logger.error(f"Failed to load memories from disk: {e}")

    def _save_to_disk(self, memory: MemoryV2Item) -> None:
        """Save memory to disk."""

        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(memory.model_dump_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to save memory to disk: {e}")


# Global instance
memory_v2_system = MemoryV2System()
