"""Canonical memory model + adapters unifying the repo's three memory models.

The codebase historically grew three incompatible memory representations:

1. ``backend.app.core.memory.store.MemoryItem`` (pydantic) — the L1-L10
   tenant-scoped model used by the main :class:`MemorySystem` write/read path.
2. ``backend.app.core.memory_deduplication_enhanced.Memory`` (dataclass) — the
   model the ~1.6k-line dedup engine family operates on (numpy embeddings,
   content_hash, access_count).
3. ``backend.app.core.hybrid_memory_system.Memory`` (pydantic) — the
   hot/cold/graph tier model (category/tier/accessed_at/related_ids).

``CanonicalMemory`` is the single normative shape for cross-subsystem memory
operations (dedup, fusion, migration). Adapters convert losslessly in both
directions where the target supports the fields; subsystem-specific extras are
carried in ``extras`` so no information is silently dropped.

Import-cycle note: this module is imported by ``memory/store.py``; therefore it
must NOT import ``backend.app.core.memory`` or ``hybrid_memory_system`` at
module level. Conversions are duck-typed; constructors for foreign models are
imported lazily inside functions.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.app.core.hybrid_memory_system import Memory as HybridMemory
    from backend.app.core.memory.store import MemoryItem
    from backend.app.core.memory_deduplication_enhanced import Memory as DedupMemory

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass
class CanonicalMemory:
    """Normative memory representation shared across store/dedup/hybrid."""

    id: str
    tenant_id: str = ""
    content: str = ""
    layer: int = 3
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    agent_id: str | None = None
    session_id: str | None = None
    share_scope: str = "private"
    visibility: str = "private"
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    access_count: int = 0
    # subsystem-specific leftovers (tier/category/related_ids/scope extras...)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return normalized_content_hash(self.content)


def normalized_content_hash(content: str) -> str:
    """SHA-256 over whitespace-normalized, case-folded content."""
    normalized = " ".join(str(content).split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Adapters: foreign model -> canonical
# ---------------------------------------------------------------------------


def canonical_from_store_item(item: MemoryItem) -> CanonicalMemory:
    """Adapt ``memory.store.MemoryItem`` (L1-L10 pydantic model)."""
    scope = getattr(item, "scope", None)
    return CanonicalMemory(
        id=item.id,
        tenant_id=item.tenant_id,
        content=item.content,
        layer=item.layer,
        importance=item.importance,
        tags=list(item.tags),
        metadata=dict(item.metadata),
        embedding=list(item.embedding or []),
        agent_id=item.agent_id,
        session_id=getattr(item, "session_id", None),
        share_scope=getattr(scope, "share_scope", "private") if scope else "private",
        visibility=getattr(scope, "visibility", "private") if scope else "private",
        created_at=_aware(item.created_at),
        updated_at=_aware(item.created_at),
        extras={
            "revisions": [getattr(r, "revision_id", str(r)) for r in getattr(item, "revisions", [])],
        },
    )


def canonical_from_dedup_memory(memory: DedupMemory) -> CanonicalMemory:
    """Adapt ``memory_deduplication_enhanced.Memory`` (dataclass)."""
    embedding = memory.embedding
    return CanonicalMemory(
        id=memory.id,
        tenant_id=str(memory.metadata.get("tenant_id", "")),
        content=memory.content,
        layer=int(memory.metadata.get("layer", 3)),
        importance=float(memory.importance),
        tags=list(memory.metadata.get("tags", [])),
        metadata=dict(memory.metadata),
        embedding=[float(v) for v in embedding] if embedding is not None else [],
        created_at=_aware(memory.created_at),
        updated_at=_aware(memory.updated_at),
        access_count=int(memory.access_count),
        extras={"content_hash": memory.content_hash},
    )


def canonical_from_hybrid_memory(memory: HybridMemory) -> CanonicalMemory:
    """Adapt ``hybrid_memory_system.Memory`` (hot/cold/graph tier model)."""
    return CanonicalMemory(
        id=memory.id,
        tenant_id=str(memory.metadata.get("tenant_id", "")),
        content=memory.content,
        layer=int(memory.metadata.get("layer", 3)),
        importance=float(memory.importance),
        tags=list(memory.tags),
        metadata=dict(memory.metadata),
        embedding=list(memory.embedding or []),
        created_at=_aware(memory.created_at),
        updated_at=_aware(memory.updated_at),
        access_count=int(memory.access_count),
        extras={
            "category": memory.category,
            "tier": memory.tier,
            "related_ids": list(memory.related_ids),
            "accessed_at": memory.accessed_at.isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Adapters: canonical -> foreign model
# ---------------------------------------------------------------------------


def dedup_memory_from_canonical(canonical: CanonicalMemory) -> DedupMemory:
    """Build a ``memory_deduplication_enhanced.Memory`` for the dedup engine."""
    import numpy as np

    from backend.app.core.memory_deduplication_enhanced import Memory as DedupMemory

    metadata = dict(canonical.metadata)
    metadata.setdefault("tenant_id", canonical.tenant_id)
    metadata.setdefault("layer", canonical.layer)
    metadata.setdefault("tags", list(canonical.tags))
    return DedupMemory(
        id=canonical.id,
        content=canonical.content,
        embedding=np.asarray(canonical.embedding, dtype=float) if canonical.embedding else None,
        created_at=canonical.created_at,
        updated_at=canonical.updated_at,
        importance=canonical.importance,
        access_count=canonical.access_count,
        metadata=metadata,
    )


def hybrid_memory_from_canonical(canonical: CanonicalMemory) -> HybridMemory:
    """Build a ``hybrid_memory_system.Memory`` (lazy import: avoids store cycle)."""
    from backend.app.core.hybrid_memory_system import Memory as HybridMemory

    metadata = dict(canonical.metadata)
    metadata.setdefault("tenant_id", canonical.tenant_id)
    metadata.setdefault("layer", canonical.layer)
    return HybridMemory(
        id=canonical.id,
        content=canonical.content,
        category=canonical.extras.get("category", "reference"),
        importance=canonical.importance,
        tier=canonical.extras.get("tier", "hot"),
        tags=list(canonical.tags),
        metadata=metadata,
        embedding=list(canonical.embedding),
        created_at=canonical.created_at,
        updated_at=canonical.updated_at,
        access_count=canonical.access_count,
        related_ids=list(canonical.extras.get("related_ids", [])),
    )


# ---------------------------------------------------------------------------
# Write-path dedup orchestration
# ---------------------------------------------------------------------------


class WritePathDeduper:
    """Incremental duplicate check for the main store write path.

    Two stages, cheapest first:
    1. exact normalized-content hash match (no embeddings needed);
    2. vector similarity via the existing ``MemoryDeduplicatorEnhanced``
       engine (this is what wires the repo's dedup code into writes).
    """

    def __init__(
        self,
        vector_threshold: float = 0.95,
        engine: Any | None = None,
    ) -> None:
        self.vector_threshold = vector_threshold
        if engine is None:
            from backend.app.core.memory_deduplication_enhanced import (
                MemoryDeduplicatorEnhanced,
            )

            engine = MemoryDeduplicatorEnhanced(vector_similarity_threshold=vector_threshold)
        self._engine = engine
        self.merged_writes = 0

    @staticmethod
    def content_hash(content: str) -> str:
        return normalized_content_hash(content)

    def find_duplicate(
        self,
        new: CanonicalMemory,
        existing: list[CanonicalMemory],
    ) -> CanonicalMemory | None:
        """Return the existing memory ``new`` duplicates, or None."""
        if not existing:
            return None
        new_hash = new.content_hash
        for candidate in existing:
            if candidate.id != new.id and candidate.content_hash == new_hash:
                return candidate
        if not new.embedding:
            return None
        vector_candidates = [
            candidate
            for candidate in existing
            if candidate.id != new.id
            and candidate.embedding
            and len(candidate.embedding) == len(new.embedding)
        ]
        if not vector_candidates:
            return None
        kept = self._engine.check_new_against_existing(
            dedup_memory_from_canonical(new),
            [dedup_memory_from_canonical(candidate) for candidate in vector_candidates],
        )
        if kept is None:
            return None
        return next(
            (candidate for candidate in vector_candidates if candidate.id == kept.id),
            None,
        )

    def note_merge(self) -> None:
        self.merged_writes += 1
