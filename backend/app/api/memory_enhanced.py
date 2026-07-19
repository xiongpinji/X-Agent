"""Enhanced memory API endpoints for hybrid memory system.

Endpoints (all under the /api/v1/memory/enhanced prefix, separated from the
primary memory API in backend/app/api/memory.py to avoid route conflicts):
- POST /api/v1/memory/enhanced/store - Store memory with auto-tiering
- POST /api/v1/memory/enhanced/recall - Recall memories
- POST /api/v1/memory/enhanced/search - Search memories
- POST /api/v1/memory/enhanced/relate - Create relationships
- GET /api/v1/memory/enhanced/related/{memory_id} - Get related memories
- POST /api/v1/memory/enhanced/merge - Merge memories
- GET /api/v1/memory/enhanced/stats - Memory statistics
- POST /api/v1/memory/enhanced/sync - Synchronize tiers
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.contracts import RunContext
from backend.app.core.hybrid_memory_system import HybridMemorySystem, Memory, MemoryTierStats
from backend.app.core.security import Principal
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/memory/enhanced", tags=["memory-enhanced"])

PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class StoreMemoryRequest(BaseModel):
    """Request to store memory."""

    content: str = Field(..., min_length=1, max_length=20_000)
    category: str = Field(default="reference")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    tier: str = Field(default="auto")


class StoreMemoryResponse(BaseModel):
    """Response from store memory."""

    id: str
    tier: str
    category: str
    importance: float
    degraded: bool = False
    note: str | None = None


class RecallMemoryRequest(BaseModel):
    """Request to recall memories."""

    query: str
    limit: int = Field(default=5, ge=1, le=50)


class RecallMemoryResponse(BaseModel):
    """Response from recall."""

    memories: list[Memory]
    count: int
    degraded: bool = False
    degraded_tiers: list[str] = Field(default_factory=list)


class SearchMemoryRequest(BaseModel):
    """Request to search memories."""

    query: str
    search_type: str = Field(default="hybrid")
    limit: int = Field(default=5, ge=1, le=50)


class SearchMemoryResponse(BaseModel):
    """Response from search."""

    memories: list[Memory]
    count: int
    search_type: str
    degraded: bool = False
    degraded_tiers: list[str] = Field(default_factory=list)


class RelateMemoriesRequest(BaseModel):
    """Request to relate memories."""

    memory_id1: str
    memory_id2: str
    relation: str


class RelateMemoriesResponse(BaseModel):
    """Response from relate."""

    success: bool
    relation: str


class MergeMemoriesRequest(BaseModel):
    """Request to merge memories."""

    memory_ids: list[str]
    strategy: str = Field(default="combine")


class MergeMemoriesResponse(BaseModel):
    """Response from merge."""

    merged_id: str
    source_count: int
    strategy: str
    degraded: bool = False
    note: str | None = None


class MemoryStatsResponse(BaseModel):
    """Memory statistics response."""

    hot_count: int
    cold_count: int
    graph_count: int
    total_count: int
    avg_importance: float
    last_sync: str | None
    degraded: bool = False
    degraded_tiers: list[str] = Field(default_factory=list)


# Dependency injection
def get_hybrid_memory_system() -> HybridMemorySystem:
    """Get hybrid memory system instance."""
    # This would be injected from app configuration
    from backend.app.core.cold_memory_store import ColdMemoryStore
    from backend.app.core.graph_memory_store import GraphMemoryStore
    from backend.app.core.hot_memory_store import HotMemoryStore
    from backend.app.core.memory_classifier import MemoryClassifier
    from backend.app.core.memory_merger import MemoryMerger

    cold_store = ColdMemoryStore()
    graph_store = GraphMemoryStore()
    system = HybridMemorySystem(
        hot_store=HotMemoryStore(),
        cold_store=cold_store,
        graph_store=graph_store,
        classifier=MemoryClassifier(),
        merger=MemoryMerger(),
    )
    # Tiers whose backends are not configured would otherwise silently
    # "succeed" without persisting anything; record them so endpoints can
    # fail explicitly or flag the response as degraded instead.
    degraded: list[str] = []
    if getattr(cold_store, "qdrant_client", None) is None:
        degraded.append("cold")
    if getattr(graph_store, "neo4j_driver", None) is None:
        degraded.append("graph")
    system.degraded_tiers = tuple(degraded)
    return system


def _degraded_tiers(hybrid_memory: HybridMemorySystem) -> tuple[str, ...]:
    """Return the tiers whose backends are unavailable for this system."""
    return tuple(getattr(hybrid_memory, "degraded_tiers", ()))


def _unavailable_tier_error(tier: str) -> HTTPException:
    """Build an explicit 503 for operations needing an unavailable tier."""
    return HTTPException(
        status_code=503,
        detail=f"Memory tier '{tier}' backend is not configured; the operation cannot be completed and would not persist.",
    )


HybridMemoryDependency = Annotated[HybridMemorySystem, Depends(get_hybrid_memory_system)]


def _context_from_principal(principal: Principal) -> RunContext:
    """Convert principal to run context."""
    return RunContext(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        agent_id=principal.agent_id or "",
        request_id=principal.request_id or "",
        trace_id=principal.trace_id or "",
    )


@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(
    request: StoreMemoryRequest,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> StoreMemoryResponse:
    """Store memory with automatic tier selection.

    The system automatically selects the appropriate tier (hot/cold/graph)
    based on memory characteristics like age, importance, and relationships.
    """
    try:
        from uuid import uuid4

        memory = Memory(
            id=str(uuid4()),
            content=request.content,
            category=request.category,
            importance=request.importance,
            tags=request.tags,
            metadata=request.metadata,
        )

        degraded = set(_degraded_tiers(hybrid_memory))
        requested_tier = request.tier
        if requested_tier in degraded:
            raise _unavailable_tier_error(requested_tier)

        # Auto-tiering may select a tier whose backend is not configured;
        # redirect to hot and flag the response instead of a silent no-op.
        effective_tier = requested_tier
        degraded_note: str | None = None
        if requested_tier == "auto":
            selected = hybrid_memory._select_tier(memory)
            if selected in degraded:
                effective_tier = "hot"
                degraded_note = f"Tier '{selected}' backend is not configured; stored in hot tier instead."

        context = _context_from_principal(principal)
        memory_id = await hybrid_memory.store(memory, tier=effective_tier, context=context)

        return StoreMemoryResponse(
            id=memory_id,
            tier=memory.tier,
            category=memory.category,
            importance=memory.importance,
            degraded=degraded_note is not None,
            note=degraded_note,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")


@router.post("/recall", response_model=RecallMemoryResponse)
async def recall_memory(
    request: RecallMemoryRequest,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> RecallMemoryResponse:
    """Recall memories using hybrid search.

    Searches across all tiers (hot, cold, graph) and combines results
    ranked by relevance.
    """
    try:
        context = _context_from_principal(principal)
        memories = await hybrid_memory.recall(
            request.query,
            limit=request.limit,
            context=context,
        )

        degraded = list(_degraded_tiers(hybrid_memory))
        return RecallMemoryResponse(
            memories=memories,
            count=len(memories),
            degraded=bool(degraded),
            degraded_tiers=degraded,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recall memories: {str(e)}")


@router.post("/search", response_model=SearchMemoryResponse)
async def search_memory(
    request: SearchMemoryRequest,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> SearchMemoryResponse:
    """Search memories with specified strategy.

    Supported search types:
    - hybrid: Search across all tiers
    - text: Fast text search in hot tier
    - semantic: Vector similarity search in cold tier
    - graph: Relationship-based search in graph tier
    """
    try:
        degraded = set(_degraded_tiers(hybrid_memory))
        if request.search_type == "semantic" and "cold" in degraded:
            raise _unavailable_tier_error("cold")
        if request.search_type == "graph" and "graph" in degraded:
            raise _unavailable_tier_error("graph")

        context = _context_from_principal(principal)
        memories = await hybrid_memory.search(
            request.query,
            search_type=request.search_type,
            limit=request.limit,
            context=context,
        )

        degraded_list = sorted(degraded)
        return SearchMemoryResponse(
            memories=memories,
            count=len(memories),
            search_type=request.search_type,
            degraded=bool(degraded_list),
            degraded_tiers=degraded_list,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")


@router.post("/relate", response_model=RelateMemoriesResponse)
async def relate_memories(
    request: RelateMemoriesRequest,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> RelateMemoriesResponse:
    """Create relationship between two memories.

    Relationships are stored in the graph tier and enable
    relationship-based queries and knowledge graph traversal.
    """
    try:
        if "graph" in _degraded_tiers(hybrid_memory):
            raise _unavailable_tier_error("graph")

        success = await hybrid_memory.relate(
            request.memory_id1,
            request.memory_id2,
            request.relation,
        )

        return RelateMemoriesResponse(
            success=success,
            relation=request.relation,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to relate memories: {str(e)}")


@router.get("/related/{memory_id}", response_model=RecallMemoryResponse)
async def get_related_memories(
    memory_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    *,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> RecallMemoryResponse:
    """Get memories related to a specific memory.

    Uses graph traversal to find related memories up to depth 2.
    """
    try:
        # For now, use recall with memory ID as query
        context = _context_from_principal(principal)
        memories = await hybrid_memory.recall(
            memory_id,
            limit=limit,
            context=context,
        )

        degraded = list(_degraded_tiers(hybrid_memory))
        return RecallMemoryResponse(
            memories=memories,
            count=len(memories),
            degraded=bool(degraded),
            degraded_tiers=degraded,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get related memories: {str(e)}")


@router.post("/merge", response_model=MergeMemoriesResponse)
async def merge_memories(
    request: MergeMemoriesRequest,
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> MergeMemoriesResponse:
    """Merge multiple memories into one.

    Supported strategies:
    - combine: Combine all content
    - keep_newest: Keep newest memory
    - keep_oldest: Keep oldest memory
    - keep_most_important: Keep most important memory
    """
    try:
        if len(request.memory_ids) < 2:
            raise ValueError("At least 2 memories required for merging")

        # Load memories
        memories: list[Memory] = []
        for memory_id in request.memory_ids:
            # This would load from the appropriate tier
            # For now, we'll create placeholder memories
            memories.append(Memory(id=memory_id, content=""))

        # Merge
        merged = await hybrid_memory.merger.merge(memories, strategy=request.strategy)

        # Store merged memory; auto-tiering may pick a tier whose backend is
        # not configured — redirect to hot and flag instead of a silent no-op.
        degraded = set(_degraded_tiers(hybrid_memory))
        effective_tier = "auto"
        degraded_note: str | None = None
        selected = hybrid_memory._select_tier(merged)
        if selected in degraded:
            effective_tier = "hot"
            degraded_note = f"Tier '{selected}' backend is not configured; stored in hot tier instead."

        context = _context_from_principal(principal)
        merged_id = await hybrid_memory.store(merged, tier=effective_tier, context=context)

        return MergeMemoriesResponse(
            merged_id=merged_id,
            source_count=len(request.memory_ids),
            strategy=request.strategy,
            degraded=degraded_note is not None,
            note=degraded_note,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to merge memories: {str(e)}")


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> MemoryStatsResponse:
    """Get memory system statistics.

    Returns counts and statistics for each tier.
    """
    try:
        stats = await hybrid_memory.get_stats()

        degraded = list(_degraded_tiers(hybrid_memory))
        return MemoryStatsResponse(
            hot_count=stats.hot_count,
            cold_count=stats.cold_count,
            graph_count=stats.graph_count,
            total_count=stats.total_count,
            avg_importance=stats.avg_importance,
            last_sync=stats.last_sync.isoformat() if stats.last_sync else None,
            degraded=bool(degraded),
            degraded_tiers=degraded,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/sync")
async def sync_tiers(
    hybrid_memory: HybridMemoryDependency,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Synchronize memories across tiers.

    Handles:
    - Hot to cold migration for old/low-importance memories
    - Cold to hot promotion for frequently accessed memories
    - Graph relationship updates
    - Deduplication across tiers
    """
    try:
        # Sync migrates hot memories to the cold tier; with no cold backend
        # the migration would not persist and the hot copy would be deleted.
        # Fail explicitly instead of silently losing data.
        degraded = set(_degraded_tiers(hybrid_memory))
        if "cold" in degraded:
            raise _unavailable_tier_error("cold")

        sync_stats = await hybrid_memory.sync_tiers()
        if degraded:
            sync_stats["degraded"] = True
            sync_stats["degraded_tiers"] = sorted(degraded)
        return sync_stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync tiers: {str(e)}")
