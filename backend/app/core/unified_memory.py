"""Unified memory system with vector and graph storage integration."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.app.core.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memories."""
    FACT = "fact"
    EXPERIENCE = "experience"
    SKILL = "skill"
    RELATIONSHIP = "relationship"
    GOAL = "goal"


class MemoryRelevance(Enum):
    """Relevance levels for memory retrieval."""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    MINIMAL = 1


@dataclass
class MemoryRecord:
    """A single memory record."""
    id: str
    content: str
    memory_type: MemoryType
    created_at: datetime
    updated_at: datetime
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    version: int = 1
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "embedding": self.embedding,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score,
            "version": self.version,
            "tags": self.tags,
        }


@dataclass
class MemoryRelationship:
    """Relationship between memories."""
    source_id: str
    target_id: str
    relationship_type: str
    strength: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryValidator:
    """Validate memory integrity and detect pollution."""

    @staticmethod
    def validate_record(record: MemoryRecord) -> tuple[bool, list[str]]:
        """Validate a memory record."""
        errors = []

        if not record.id or not record.id.strip():
            errors.append("Memory ID is empty")

        if not record.content or not record.content.strip():
            errors.append("Memory content is empty")

        if len(record.content) > 100000:
            errors.append("Memory content exceeds maximum length (100KB)")

        if record.relevance_score < 0 or record.relevance_score > 1:
            errors.append("Relevance score must be between 0 and 1")

        if record.version < 1:
            errors.append("Version must be >= 1")

        return len(errors) == 0, errors

    @staticmethod
    def detect_pollution(record: MemoryRecord, existing_records: list[MemoryRecord]) -> bool:
        """Detect if memory is polluted (duplicate or conflicting)."""
        for existing in existing_records:
            # Check for exact duplicates
            if record.content == existing.content:
                return True

            # Check for high similarity (simple hash-based)
            if MemoryValidator._similarity_score(record.content, existing.content) > 0.9:
                return True

        return False

    @staticmethod
    def _similarity_score(text1: str, text2: str) -> float:
        """Calculate simple similarity score."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0


class MemoryConflictResolver:
    """Resolve conflicts between memory versions."""

    @staticmethod
    def resolve_conflict(
        record1: MemoryRecord,
        record2: MemoryRecord,
    ) -> MemoryRecord:
        """Resolve conflict between two memory versions."""
        # Prefer more recent version
        if record1.updated_at > record2.updated_at:
            return record1
        elif record2.updated_at > record1.updated_at:
            return record2

        # If same timestamp, prefer higher relevance
        if record1.relevance_score > record2.relevance_score:
            return record1
        else:
            return record2


class MemoryGovernance:
    """Memory governance and lifecycle management."""

    def __init__(self) -> None:
        self.retention_days = 365
        self.max_memory_size = 1000000  # 1MB
        self.current_size = 0
        self._lock = asyncio.Lock()

    async def should_retain(self, record: MemoryRecord) -> bool:
        """Check if memory should be retained."""
        age = datetime.now() - record.updated_at
        return age.days < self.retention_days

    async def check_capacity(self, new_size: int) -> bool:
        """Check if adding new memory would exceed capacity."""
        async with self._lock:
            return self.current_size + new_size <= self.max_memory_size

    async def update_size(self, delta: int) -> None:
        """Update current memory size."""
        async with self._lock:
            self.current_size = max(0, self.current_size + delta)


class UnifiedMemorySystem:
    """Unified memory system integrating vector and graph storage.

    When an ``EmbeddingProvider`` is supplied (via constructor or
    ``set_embedding_provider``), memories are automatically embedded on store
    and retrieval uses cosine-similarity over real vectors.  If the provider
    is unavailable or embedding fails, the system degrades gracefully to
    keyword-based retrieval (never crashes).
    """

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.validator = MemoryValidator()
        self.conflict_resolver = MemoryConflictResolver()
        self.governance = MemoryGovernance()
        self.memories: dict[str, MemoryRecord] = {}
        self.relationships: dict[str, list[MemoryRelationship]] = {}
        self._lock = asyncio.Lock()
        self._embedding_provider: EmbeddingProvider | None = embedding_provider
        self._embedding_degraded = False
        self._embedding_degraded_reason: str | None = None

    # ------------------------------------------------------------------
    # Embedding provider management
    # ------------------------------------------------------------------

    def set_embedding_provider(self, provider: EmbeddingProvider) -> None:
        """Attach or replace the embedding provider at runtime."""
        self._embedding_provider = provider
        self._embedding_degraded = False
        self._embedding_degraded_reason = None
        logger.info(
            "UnifiedMemorySystem: embedding provider attached (backend=%s)",
            getattr(provider, "backend", "unknown"),
        )

    @property
    def embedding_enabled(self) -> bool:
        """Whether real embeddings are active (not degraded)."""
        return self._embedding_provider is not None and not self._embedding_degraded

    @property
    def embedding_status(self) -> dict[str, Any]:
        """Return embedding subsystem status for observability."""
        if self._embedding_provider is None:
            return {"enabled": False, "backend": None, "degraded": False}
        return {
            "enabled": True,
            "backend": getattr(self._embedding_provider, "resolved_backend", "unknown"),
            "degraded": self._embedding_degraded,
            "degraded_reason": self._embedding_degraded_reason,
        }

    async def _embed_text(self, text: str) -> list[float] | None:
        """Embed text using the provider; returns None on failure (graceful)."""
        if self._embedding_provider is None:
            return None
        try:
            return await self._embedding_provider.embed(text)
        except Exception as exc:
            if not self._embedding_degraded:
                self._embedding_degraded = True
                self._embedding_degraded_reason = str(exc)
                logger.warning(
                    "UnifiedMemorySystem: embedding failed (%s); "
                    "degrading to keyword-based retrieval.",
                    exc,
                )
            return None

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    async def store_memory(
        self,
        content: str,
        memory_type: MemoryType,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Store a new memory.

        If no explicit ``embedding`` is provided and an embedding provider is
        attached, the content is automatically embedded using the configured
        real embedding backend (OpenAI, sentence-transformers, etc.).
        """
        memory_id = self._generate_id(content)
        now = datetime.now()

        # Auto-embed if no explicit embedding provided
        if embedding is None:
            embedding = await self._embed_text(content)

        record = MemoryRecord(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            created_at=now,
            updated_at=now,
            embedding=embedding,
            metadata=metadata or {},
            tags=tags or [],
        )

        # Validate
        is_valid, errors = self.validator.validate_record(record)
        if not is_valid:
            raise ValueError(f"Invalid memory: {', '.join(errors)}")

        # Check for pollution
        async with self._lock:
            existing = list(self.memories.values())
            if self.validator.detect_pollution(record, existing):
                logger.warning(f"Potential memory pollution detected for: {content[:50]}")

            # Check capacity
            content_size = len(content.encode("utf-8"))
            if not await self.governance.check_capacity(content_size):
                logger.error("Memory capacity exceeded")
                raise RuntimeError("Memory capacity exceeded")

            # Store
            self.memories[memory_id] = record
            await self.governance.update_size(content_size)

        logger.info(f"Memory stored: {memory_id} ({memory_type.value})")
        return record

    async def retrieve_memories(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        top_k: int = 5,
    ) -> list[MemoryRecord]:
        """Retrieve relevant memories using hybrid vector + keyword scoring.

        When real embeddings are available, uses cosine similarity between the
        query embedding and stored memory embeddings.  Falls back to keyword
        overlap scoring when embeddings are unavailable or degraded.
        """
        async with self._lock:
            candidates = list(self.memories.values())

        # Filter by type
        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]

        if not candidates:
            return []

        # Try vector-based retrieval first
        query_embedding = await self._embed_text(query)
        use_vector = (
            query_embedding is not None
            and any(m.embedding for m in candidates)
        )

        if use_vector:
            # Hybrid scoring: 0.7 * cosine_similarity + 0.3 * keyword_overlap
            query_words = set(query.lower().split())
            for record in candidates:
                vector_score = 0.0
                if record.embedding and query_embedding:
                    vector_score = self._cosine_similarity(
                        query_embedding, record.embedding
                    )
                # Normalize cosine from [-1,1] to [0,1]
                vector_score = (vector_score + 1.0) / 2.0

                content_words = set(record.content.lower().split())
                keyword_score = (
                    len(query_words & content_words) / len(query_words)
                    if query_words
                    else 0.0
                )
                record.relevance_score = 0.7 * vector_score + 0.3 * keyword_score
        else:
            # Fallback: keyword-only scoring
            query_words = set(query.lower().split())
            for record in candidates:
                content_words = set(record.content.lower().split())
                overlap = len(query_words & content_words)
                record.relevance_score = (
                    overlap / len(query_words) if query_words else 0.0
                )

        # Sort by relevance and return top-k
        candidates.sort(key=lambda m: m.relevance_score, reverse=True)
        return candidates[:top_k]

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        strength: float = 1.0,
    ) -> MemoryRelationship:
        """Create relationship between memories."""
        async with self._lock:
            if source_id not in self.memories or target_id not in self.memories:
                raise ValueError("Source or target memory not found")

            rel = MemoryRelationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type=relationship_type,
                strength=strength,
            )

            if source_id not in self.relationships:
                self.relationships[source_id] = []

            self.relationships[source_id].append(rel)

        logger.info(f"Relationship created: {source_id} -> {target_id} ({relationship_type})")
        return rel

    async def get_related_memories(
        self,
        memory_id: str,
        relationship_type: str | None = None,
    ) -> list[MemoryRecord]:
        """Get memories related to a given memory."""
        async with self._lock:
            relationships = self.relationships.get(memory_id, [])

            if relationship_type:
                relationships = [
                    r for r in relationships if r.relationship_type == relationship_type
                ]

            related_ids = [r.target_id for r in relationships]
            return [self.memories[mid] for mid in related_ids if mid in self.memories]

    async def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Update an existing memory.

        When content changes and an embedding provider is available, the
        embedding is automatically regenerated.
        """
        async with self._lock:
            if memory_id not in self.memories:
                raise ValueError(f"Memory {memory_id} not found")

            record = self.memories[memory_id]
            old_size = len(record.content.encode("utf-8"))

            if content is not None:
                record.content = content
                # Re-embed on content change
                new_embedding = await self._embed_text(content)
                if new_embedding is not None:
                    record.embedding = new_embedding
            if metadata is not None:
                record.metadata.update(metadata)
            if tags is not None:
                record.tags = tags

            record.updated_at = datetime.now()
            record.version += 1

            # Update size tracking
            new_size = len(record.content.encode("utf-8"))
            await self.governance.update_size(new_size - old_size)

        logger.info(f"Memory updated: {memory_id} (v{record.version})")
        return record

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory."""
        async with self._lock:
            if memory_id in self.memories:
                record = self.memories.pop(memory_id)
                size = len(record.content.encode("utf-8"))
                await self.governance.update_size(-size)

                # Clean up relationships
                if memory_id in self.relationships:
                    del self.relationships[memory_id]

        logger.info(f"Memory deleted: {memory_id}")

    async def get_memory_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        async with self._lock:
            type_counts = {}
            embedded_count = 0
            for record in self.memories.values():
                type_name = record.memory_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
                if record.embedding:
                    embedded_count += 1

            return {
                "total_memories": len(self.memories),
                "total_relationships": sum(len(rels) for rels in self.relationships.values()),
                "memory_size_bytes": self.governance.current_size,
                "type_distribution": type_counts,
                "capacity_used_percent": (
                    self.governance.current_size / self.governance.max_memory_size * 100
                ),
                "embedded_memories": embedded_count,
                "embedding": self.embedding_status,
            }

    @staticmethod
    def _generate_id(content: str) -> str:
        """Generate unique ID for memory."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Factory: build a UnifiedMemorySystem wired with real embeddings
# ---------------------------------------------------------------------------


def build_unified_memory_system(
    *,
    embedding_backend: str = "auto",
    openai_api_key: str | None = None,
    openai_embedding_model: str = "text-embedding-3-small",
    openai_embedding_dimensions: int | None = None,
    embedding_dim: int = 384,
) -> UnifiedMemorySystem:
    """Create a UnifiedMemorySystem with real embedding support.

    Graceful degradation: if the embedding provider cannot be constructed
    (missing deps, no API key, etc.), the system is still returned but
    operates in keyword-only mode (no crash).
    """
    provider = None
    try:
        from backend.app.core.embeddings import EmbeddingProvider

        provider = EmbeddingProvider(
            backend=embedding_backend,
            model=openai_embedding_model,
            dimensions=openai_embedding_dimensions or embedding_dim,
            openai_api_key=openai_api_key,
        )
        logger.info(
            "UnifiedMemorySystem: embedding provider created (backend=%s, model=%s)",
            embedding_backend,
            openai_embedding_model,
        )
    except Exception as exc:
        logger.warning(
            "UnifiedMemorySystem: failed to create embedding provider (%s); "
            "running in keyword-only mode.",
            exc,
        )

    return UnifiedMemorySystem(embedding_provider=provider)


# Global instance (keyword-only by default; use build_unified_memory_system
# or get_unified_memory() from dependencies for the embedding-wired version)
unified_memory = UnifiedMemorySystem()
