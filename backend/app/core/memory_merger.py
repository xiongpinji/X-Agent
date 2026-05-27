"""Memory merger for deduplication and conflict resolution.

Features:
- Duplicate memory merging
- Conflict resolution strategies
- Information supplementation
- Version management
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.app.core.hybrid_memory_system import Memory


class MemoryMerger:
    """Merge and deduplicate memories with conflict resolution."""

    def __init__(self) -> None:
        self.merge_strategies = {
            "keep_newest": self._merge_keep_newest,
            "keep_oldest": self._merge_keep_oldest,
            "keep_most_important": self._merge_keep_most_important,
            "combine": self._merge_combine,
        }

    async def merge(
        self,
        memories: list[Memory],
        strategy: str = "combine",
    ) -> Memory:
        """Merge multiple memories into one.

        Args:
            memories: List of memories to merge
            strategy: Merge strategy

        Returns:
            Merged memory
        """
        if not memories:
            raise ValueError("Cannot merge empty list of memories")

        if len(memories) == 1:
            return memories[0]

        # Select merge strategy
        merge_func = self.merge_strategies.get(strategy, self._merge_combine)
        return merge_func(memories)

    async def resolve_conflicts(
        self,
        memories: list[Memory],
    ) -> Memory:
        """Resolve conflicts between memories.

        Args:
            memories: List of conflicting memories

        Returns:
            Resolved memory
        """
        if not memories:
            raise ValueError("Cannot resolve conflicts in empty list")

        if len(memories) == 1:
            return memories[0]

        # Use combine strategy for conflict resolution
        return self._merge_combine(memories)

    async def supplement(
        self,
        base: Memory,
        additions: list[Memory],
    ) -> Memory:
        """Supplement base memory with additional information.

        Args:
            base: Base memory
            additions: Additional memories to supplement with

        Returns:
            Supplemented memory
        """
        if not additions:
            return base

        # Combine content
        content_parts = [base.content]
        for addition in additions:
            if addition.content and addition.content not in base.content:
                content_parts.append(addition.content)

        supplemented = Memory(
            id=base.id,
            content="\n\n".join(content_parts),
            category=base.category,
            importance=max(base.importance, max(a.importance for a in additions)),
            tier=base.tier,
            tags=self._merge_tags(base.tags, *[a.tags for a in additions]),
            metadata=self._merge_metadata(base.metadata, *[a.metadata for a in additions]),
            created_at=min(base.created_at, min(a.created_at for a in additions)),
            updated_at=datetime.now(UTC),
            access_count=base.access_count + sum(a.access_count for a in additions),
            related_ids=self._merge_related_ids(base.related_ids, *[a.related_ids for a in additions]),
        )

        return supplemented

    def _merge_keep_newest(self, memories: list[Memory]) -> Memory:
        """Keep the newest memory."""
        newest = max(memories, key=lambda m: m.created_at)
        return Memory(
            id=newest.id,
            content=newest.content,
            category=newest.category,
            importance=max(m.importance for m in memories),
            tier=newest.tier,
            tags=self._merge_tags(newest.tags, *[m.tags for m in memories if m.id != newest.id]),
            metadata=self._merge_metadata(newest.metadata, *[m.metadata for m in memories if m.id != newest.id]),
            created_at=min(m.created_at for m in memories),
            updated_at=datetime.now(UTC),
            access_count=sum(m.access_count for m in memories),
            related_ids=self._merge_related_ids(newest.related_ids, *[m.related_ids for m in memories if m.id != newest.id]),
        )

    def _merge_keep_oldest(self, memories: list[Memory]) -> Memory:
        """Keep the oldest memory."""
        oldest = min(memories, key=lambda m: m.created_at)
        return Memory(
            id=oldest.id,
            content=oldest.content,
            category=oldest.category,
            importance=max(m.importance for m in memories),
            tier=oldest.tier,
            tags=self._merge_tags(oldest.tags, *[m.tags for m in memories if m.id != oldest.id]),
            metadata=self._merge_metadata(oldest.metadata, *[m.metadata for m in memories if m.id != oldest.id]),
            created_at=oldest.created_at,
            updated_at=datetime.now(UTC),
            access_count=sum(m.access_count for m in memories),
            related_ids=self._merge_related_ids(oldest.related_ids, *[m.related_ids for m in memories if m.id != oldest.id]),
        )

    def _merge_keep_most_important(self, memories: list[Memory]) -> Memory:
        """Keep the most important memory."""
        most_important = max(memories, key=lambda m: m.importance)
        return Memory(
            id=most_important.id,
            content=most_important.content,
            category=most_important.category,
            importance=most_important.importance,
            tier=most_important.tier,
            tags=self._merge_tags(most_important.tags, *[m.tags for m in memories if m.id != most_important.id]),
            metadata=self._merge_metadata(most_important.metadata, *[m.metadata for m in memories if m.id != most_important.id]),
            created_at=min(m.created_at for m in memories),
            updated_at=datetime.now(UTC),
            access_count=sum(m.access_count for m in memories),
            related_ids=self._merge_related_ids(most_important.related_ids, *[m.related_ids for m in memories if m.id != most_important.id]),
        )

    def _merge_combine(self, memories: list[Memory]) -> Memory:
        """Combine all memories into one."""
        # Use first memory as base
        base = memories[0]

        # Combine content
        content_parts = [m.content for m in memories if m.content]
        combined_content = "\n\n".join(content_parts)

        # Combine metadata
        combined_metadata = {}
        for memory in memories:
            combined_metadata.update(memory.metadata)

        # Add merge history
        combined_metadata["merged_from"] = [m.id for m in memories]
        combined_metadata["merge_count"] = len(memories)
        combined_metadata["merged_at"] = datetime.now(UTC).isoformat()

        return Memory(
            id=base.id,
            content=combined_content,
            category=base.category,
            importance=max(m.importance for m in memories),
            tier=base.tier,
            tags=self._merge_tags(*[m.tags for m in memories]),
            metadata=combined_metadata,
            created_at=min(m.created_at for m in memories),
            updated_at=datetime.now(UTC),
            access_count=sum(m.access_count for m in memories),
            related_ids=self._merge_related_ids(*[m.related_ids for m in memories]),
        )

    @staticmethod
    def _merge_tags(*tag_lists: list[str]) -> list[str]:
        """Merge tag lists, removing duplicates."""
        merged: dict[str, int] = {}
        for tags in tag_lists:
            for tag in tags:
                merged[tag] = merged.get(tag, 0) + 1

        # Sort by frequency
        sorted_tags = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, _ in sorted_tags[:20]]

    @staticmethod
    def _merge_metadata(*metadata_dicts: dict[str, Any]) -> dict[str, Any]:
        """Merge metadata dictionaries."""
        merged: dict[str, Any] = {}
        for metadata in metadata_dicts:
            for key, value in metadata.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    # Merge lists
                    merged[key] = list(set(merged[key] + value))
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    # Merge dicts recursively
                    merged[key].update(value)

        return merged

    @staticmethod
    def _merge_related_ids(*id_lists: list[str]) -> list[str]:
        """Merge related ID lists, removing duplicates."""
        merged = list(set(id for ids in id_lists for id in ids))
        return merged[:50]  # Limit to 50 related IDs

    def detect_merge_candidates(
        self,
        memories: list[Memory],
        similarity_threshold: float = 0.8,
    ) -> list[list[Memory]]:
        """Detect groups of similar memories that could be merged.

        Args:
            memories: List of memories to analyze
            similarity_threshold: Minimum similarity for grouping

        Returns:
            List of memory groups
        """
        groups: list[list[Memory]] = []
        used_ids = set()

        for i, memory1 in enumerate(memories):
            if memory1.id in used_ids:
                continue

            group = [memory1]
            used_ids.add(memory1.id)

            for memory2 in memories[i + 1 :]:
                if memory2.id in used_ids:
                    continue

                similarity = self._content_similarity(memory1.content, memory2.content)
                if similarity >= similarity_threshold:
                    group.append(memory2)
                    used_ids.add(memory2.id)

            if len(group) > 1:
                groups.append(group)

        return groups

    @staticmethod
    def _content_similarity(content1: str, content2: str) -> float:
        """Calculate content similarity."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0
