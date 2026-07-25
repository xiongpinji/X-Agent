"""Memory system caching integration.

Adds caching layer to memory search and retrieval operations.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.app.core.cache import get_cache_manager
from backend.app.core.memory import MemoryItem, MemorySearchHit

logger = logging.getLogger(__name__)

# Cache TTLs for different operations
MEMORY_SEARCH_TTL = 300  # 5 minutes
MEMORY_ITEM_TTL = 600  # 10 minutes
MEMORY_SESSION_TTL = 1800  # 30 minutes


def _make_search_cache_key(
    tenant_id: str,
    query: str,
    layers: list[int] | None = None,
    top_k: int = 5,
) -> str:
    """Generate cache key for memory search."""
    key_parts = [
        "memory:search",
        tenant_id,
        query,
        str(sorted(layers or [])),
        str(top_k),
    ]
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def _make_item_cache_key(memory_id: str) -> str:
    """Generate cache key for memory item."""
    return f"memory:item:{memory_id}"


def _make_session_cache_key(session_id: str) -> str:
    """Generate cache key for session."""
    return f"memory:session:{session_id}"


async def get_cached_memory_item(memory_id: str) -> MemoryItem | None:
    """Get memory item from cache."""
    cache = get_cache_manager()
    key = _make_item_cache_key(memory_id)
    return await cache.get(key)


async def cache_memory_item(item: MemoryItem) -> None:
    """Cache a memory item."""
    cache = get_cache_manager()
    key = _make_item_cache_key(item.id)
    await cache.set(key, item.model_dump(mode="json"), ttl=MEMORY_ITEM_TTL)


async def invalidate_memory_item_cache(memory_id: str) -> None:
    """Invalidate cache for a memory item."""
    cache = get_cache_manager()
    key = _make_item_cache_key(memory_id)
    await cache.delete(key)


async def get_cached_search_results(
    tenant_id: str,
    query: str,
    layers: list[int] | None = None,
    top_k: int = 5,
) -> list[MemorySearchHit] | None:
    """Get cached search results."""
    cache = get_cache_manager()
    key = _make_search_cache_key(tenant_id, query, layers, top_k)
    cached = await cache.get(key)
    if cached:
        return [MemorySearchHit(**hit) for hit in cached]
    return None


async def cache_search_results(
    tenant_id: str,
    query: str,
    results: list[MemorySearchHit],
    layers: list[int] | None = None,
    top_k: int = 5,
) -> None:
    """Cache search results."""
    cache = get_cache_manager()
    key = _make_search_cache_key(tenant_id, query, layers, top_k)
    serialized = [hit.model_dump(mode="json") for hit in results]
    await cache.set(key, serialized, ttl=MEMORY_SEARCH_TTL)


async def invalidate_search_cache(tenant_id: str, pattern: str = "memory:search:*") -> None:
    """Invalidate search cache for a tenant."""
    cache = get_cache_manager()
    await cache.invalidate_pattern(pattern)


async def get_cached_session(session_id: str) -> dict[str, Any] | None:
    """Get cached session."""
    cache = get_cache_manager()
    key = _make_session_cache_key(session_id)
    return await cache.get(key)


async def cache_session(session_id: str, session_data: dict[str, Any]) -> None:
    """Cache session data."""
    cache = get_cache_manager()
    key = _make_session_cache_key(session_id)
    await cache.set(key, session_data, ttl=MEMORY_SESSION_TTL)


async def invalidate_session_cache(session_id: str) -> None:
    """Invalidate cache for a session."""
    cache = get_cache_manager()
    key = _make_session_cache_key(session_id)
    await cache.delete(key)
