"""Database query result caching.

Caches frequently accessed database query results.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.app.core.cache import get_cache_manager

logger = logging.getLogger(__name__)

# Cache TTLs for different query types
DB_QUERY_TTL = 600  # 10 minutes
DB_AGGREGATE_TTL = 1800  # 30 minutes
DB_USER_TTL = 3600  # 1 hour


def _make_query_cache_key(query_type: str, *args: Any, **kwargs: Any) -> str:
    """Generate cache key for database query."""
    key_parts = [f"db:{query_type}"]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_cached_query(query_type: str, *args: Any, **kwargs: Any) -> Any | None:
    """Get cached query result."""
    cache = get_cache_manager()
    key = _make_query_cache_key(query_type, *args, **kwargs)
    return await cache.get(key)


async def cache_query(
    query_type: str,
    result: Any,
    ttl: int | None = None,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Cache query result."""
    cache = get_cache_manager()
    key = _make_query_cache_key(query_type, *args, **kwargs)
    ttl = ttl or DB_QUERY_TTL
    await cache.set(key, result, ttl=ttl)


async def invalidate_query_cache(query_type: str, *args: Any, **kwargs: Any) -> None:
    """Invalidate cache for a specific query."""
    cache = get_cache_manager()
    key = _make_query_cache_key(query_type, *args, **kwargs)
    await cache.delete(key)


async def invalidate_query_pattern(pattern: str) -> None:
    """Invalidate cache for queries matching a pattern."""
    cache = get_cache_manager()
    await cache.invalidate_pattern(pattern)


# Specific query cache helpers

async def get_cached_user(user_id: str) -> dict[str, Any] | None:
    """Get cached user data."""
    return await get_cached_query("user", user_id)


async def cache_user(user_id: str, user_data: dict[str, Any]) -> None:
    """Cache user data."""
    await cache_query("user", user_data, ttl=DB_USER_TTL, user_id)


async def invalidate_user_cache(user_id: str) -> None:
    """Invalidate user cache."""
    await invalidate_query_cache("user", user_id)


async def get_cached_tenant(tenant_id: str) -> dict[str, Any] | None:
    """Get cached tenant data."""
    return await get_cached_query("tenant", tenant_id)


async def cache_tenant(tenant_id: str, tenant_data: dict[str, Any]) -> None:
    """Cache tenant data."""
    await cache_query("tenant", tenant_data, ttl=DB_USER_TTL, tenant_id)


async def invalidate_tenant_cache(tenant_id: str) -> None:
    """Invalidate tenant cache."""
    await invalidate_query_cache("tenant", tenant_id)


async def get_cached_api_key(api_key_id: str) -> dict[str, Any] | None:
    """Get cached API key data."""
    return await get_cached_query("api_key", api_key_id)


async def cache_api_key(api_key_id: str, key_data: dict[str, Any]) -> None:
    """Cache API key data."""
    await cache_query("api_key", key_data, ttl=DB_USER_TTL, api_key_id)


async def invalidate_api_key_cache(api_key_id: str) -> None:
    """Invalidate API key cache."""
    await invalidate_query_cache("api_key", api_key_id)


async def invalidate_all_user_caches(user_id: str) -> None:
    """Invalidate all caches related to a user."""
    await invalidate_query_pattern(f"db:user:*{user_id}*")
    await invalidate_query_pattern(f"db:api_key:*{user_id}*")
