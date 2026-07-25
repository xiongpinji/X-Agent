"""
Memory compression module for X-Agent.

Implements long-term memory compression, key information extraction,
and automatic cleanup of expired memories.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CompressedMemory:
    """Represents a compressed memory."""

    id: str
    original_content: str
    compressed_content: str
    key_points: list[str] = field(default_factory=list)
    compression_ratio: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class CompressionResult:
    """Result of memory compression operation."""

    total_memories: int
    compressed_count: int
    removed_count: int
    total_size_before: int
    total_size_after: int
    compression_ratio: float
    removed_ids: list[str] = field(default_factory=list)


class MemoryCompressor:
    """
    Compresses long-term memories and manages memory lifecycle.

    Automatically compresses old memories, extracts key information,
    and cleans up expired memories.
    """

    def __init__(
        self,
        retention_days: int = 30,
        compression_threshold_days: int = 7,
        min_compression_ratio: float = 0.5,
        key_points_limit: int = 5,
    ):
        """
        Initialize the memory compressor.

        Args:
            retention_days: Days to retain memories before cleanup
            compression_threshold_days: Days before compressing memory
            min_compression_ratio: Minimum compression ratio to accept
            key_points_limit: Maximum number of key points to extract
        """
        self.retention_days = retention_days
        self.compression_threshold_days = compression_threshold_days
        self.min_compression_ratio = min_compression_ratio
        self.key_points_limit = key_points_limit
        self.logger = logger
        self.compressed_memories: dict[str, CompressedMemory] = {}

    def compress_old_memories(
        self,
        memories: list[dict],
    ) -> CompressionResult:
        """
        Compress memories older than threshold.

        Args:
            memories: List of memory dictionaries with 'id', 'content', 'created_at'

        Returns:
            CompressionResult with compression statistics
        """
        now = datetime.now()
        compressed_count = 0
        removed_count = 0
        removed_ids = []
        total_size_before = 0
        total_size_after = 0

        for memory in memories:
            memory_id = memory.get("id")
            content = memory.get("content", "")
            created_at = memory.get("created_at")

            if not memory_id or not content:
                continue

            total_size_before += len(content.encode("utf-8"))

            # Check if memory should be compressed
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    created_at = datetime.now()

            age_days = (now - created_at).days

            if age_days >= self.compression_threshold_days:
                # Compress memory
                compressed = self._compress_memory(memory_id, content)
                self.compressed_memories[memory_id] = compressed
                total_size_after += len(compressed.compressed_content.encode("utf-8"))
                compressed_count += 1

                self.logger.debug(f"Compressed memory: {memory_id}")

        return CompressionResult(
            total_memories=len(memories),
            compressed_count=compressed_count,
            removed_count=removed_count,
            total_size_before=total_size_before,
            total_size_after=total_size_after,
            compression_ratio=(
                1 - (total_size_after / total_size_before)
                if total_size_before > 0 else 0
            ),
            removed_ids=removed_ids,
        )

    def cleanup_expired_memories(
        self,
        memories: list[dict],
    ) -> list[str]:
        """
        Clean up memories older than retention period.

        Args:
            memories: List of memory dictionaries

        Returns:
            List of removed memory IDs
        """
        now = datetime.now()
        removed_ids = []

        for memory in memories:
            memory_id = memory.get("id")
            created_at = memory.get("created_at")

            if not memory_id:
                continue

            # Parse created_at
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except (ValueError, TypeError):
                    created_at = datetime.now()

            age_days = (now - created_at).days

            if age_days >= self.retention_days:
                removed_ids.append(memory_id)
                self.logger.debug(f"Removed expired memory: {memory_id}")

        return removed_ids

    def _compress_memory(self, memory_id: str, content: str) -> CompressedMemory:
        """Compress a single memory."""
        # Extract key points
        key_points = self._extract_key_points(content)

        # Generate compressed content
        compressed_content = self._generate_compressed_content(content, key_points)

        # Calculate compression ratio
        original_size = len(content.encode("utf-8"))
        compressed_size = len(compressed_content.encode("utf-8"))
        compression_ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0

        return CompressedMemory(
            id=memory_id,
            original_content=content,
            compressed_content=compressed_content,
            key_points=key_points,
            compression_ratio=compression_ratio,
        )

    def _extract_key_points(self, content: str) -> list[str]:
        """Extract key points from content."""
        # Simple extraction based on sentence importance
        sentences = content.split(".")
        scored_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Score based on length and keywords
            score = self._score_sentence(sentence)
            scored_sentences.append((sentence, score))

        # Sort by score and take top key points
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        key_points = [s[0] for s in scored_sentences[:self.key_points_limit]]

        return key_points

    def _score_sentence(self, sentence: str) -> float:
        """Score a sentence for importance."""
        # Simple scoring based on keywords and length
        important_keywords = [
            "important", "critical", "key", "must", "should",
            "error", "failure", "success", "completed", "resolved"
        ]

        score = 0.0

        # Length score (prefer medium-length sentences)
        words = sentence.split()
        if 5 <= len(words) <= 30:
            score += 1.0

        # Keyword score
        sentence_lower = sentence.lower()
        for keyword in important_keywords:
            if keyword in sentence_lower:
                score += 0.5

        return score

    def _generate_compressed_content(
        self,
        content: str,
        key_points: list[str],
    ) -> str:
        """Generate compressed content from key points."""
        if not key_points:
            # Fallback: take first 50% of content
            return content[:len(content) // 2]

        # Combine key points with summary
        summary = " ".join(key_points)

        # Add metadata
        compressed = f"[COMPRESSED] {summary}"

        return compressed

    def get_compressed_memory(self, memory_id: str) -> CompressedMemory | None:
        """Get a compressed memory by ID."""
        return self.compressed_memories.get(memory_id)

    def decompress_memory(self, memory_id: str) -> str | None:
        """Get original content of a compressed memory."""
        compressed = self.compressed_memories.get(memory_id)
        if compressed:
            return compressed.original_content
        return None

    def update_access_time(self, memory_id: str) -> None:
        """Update last access time for a memory."""
        if memory_id in self.compressed_memories:
            compressed = self.compressed_memories[memory_id]
            compressed.last_accessed = datetime.now()
            compressed.access_count += 1

    def get_compression_stats(self) -> dict:
        """Get compression statistics."""
        if not self.compressed_memories:
            return {
                "total_compressed": 0,
                "avg_compression_ratio": 0.0,
                "total_original_size": 0,
                "total_compressed_size": 0,
            }

        compression_ratios = [
            m.compression_ratio for m in self.compressed_memories.values()
        ]
        original_sizes = [
            len(m.original_content.encode("utf-8"))
            for m in self.compressed_memories.values()
        ]
        compressed_sizes = [
            len(m.compressed_content.encode("utf-8"))
            for m in self.compressed_memories.values()
        ]

        return {
            "total_compressed": len(self.compressed_memories),
            "avg_compression_ratio": (
                sum(compression_ratios) / len(compression_ratios)
                if compression_ratios else 0
            ),
            "total_original_size": sum(original_sizes),
            "total_compressed_size": sum(compressed_sizes),
            "max_compression_ratio": max(compression_ratios) if compression_ratios else 0,
            "min_compression_ratio": min(compression_ratios) if compression_ratios else 0,
        }

    def batch_compress(
        self,
        memory_batches: list[list[dict]],
    ) -> list[CompressionResult]:
        """
        Compress multiple batches of memories.

        Args:
            memory_batches: List of memory batches

        Returns:
            List of CompressionResult objects
        """
        results = []
        for batch in memory_batches:
            result = self.compress_old_memories(batch)
            results.append(result)

        return results

    def export_compressed_memories(self) -> dict:
        """Export all compressed memories."""
        return {
            memory_id: {
                "id": memory.id,
                "original_content": memory.original_content,
                "compressed_content": memory.compressed_content,
                "key_points": memory.key_points,
                "compression_ratio": memory.compression_ratio,
                "created_at": memory.created_at.isoformat(),
                "last_accessed": memory.last_accessed.isoformat(),
                "access_count": memory.access_count,
                "metadata": memory.metadata,
            }
            for memory_id, memory in self.compressed_memories.items()
        }

    def import_compressed_memories(self, data: dict) -> None:
        """Import compressed memories from dictionary."""
        for memory_id, memory_data in data.items():
            compressed = CompressedMemory(
                id=memory_data["id"],
                original_content=memory_data["original_content"],
                compressed_content=memory_data["compressed_content"],
                key_points=memory_data.get("key_points", []),
                compression_ratio=memory_data.get("compression_ratio", 0.0),
                created_at=datetime.fromisoformat(memory_data["created_at"]),
                last_accessed=datetime.fromisoformat(memory_data["last_accessed"]),
                access_count=memory_data.get("access_count", 0),
                metadata=memory_data.get("metadata", {}),
            )
            self.compressed_memories[memory_id] = compressed


# Global instance
memory_compressor = MemoryCompressor()
