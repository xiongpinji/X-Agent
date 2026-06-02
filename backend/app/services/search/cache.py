"""Search result caching with Redis backend."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel

from backend.app.services.search.search_engine import SearchResponse


class CacheEntry(BaseModel):
    """Cache entry with metadata."""
    response: SearchResponse
    created_at: datetime
    ttl_seconds: int


class SearchCache:
    """Redis-backed search result cache."""

    def __init__(self, redis_client, ttl_seconds: int = 3600):
        """Initialize cache.

        Args:
            redis_client: Redis client instance
            ttl_seconds: Time-to-live for cache entries
        """
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.prefix = "xagent:search:"

    def _make_key(self, query: str, provider: str) -> str:
        """Generate cache key from query and provider."""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()
        return f"{self.prefix}{provider}:{query_hash}"

    async def get(self, query: str, provider: str) -> Optional[SearchResponse]:
        """Get cached search result.

        Args:
            query: Search query
            provider: Search provider name

        Returns:
            Cached SearchResponse or None if not found/expired
        """
        key = self._make_key(query, provider)

        try:
            cached = await self.redis.get(key)
            if cached:
                data = json.loads(cached)
                return SearchResponse(**data)
        except Exception:
            pass

        return None

    async def set(self, query: str, provider: str, response: SearchResponse) -> bool:
        """Cache search result.

        Args:
            query: Search query
            provider: Search provider name
            response: SearchResponse to cache

        Returns:
            True if cached successfully
        """
        key = self._make_key(query, provider)

        try:
            data = response.model_dump_json()
            await self.redis.setex(
                key,
                self.ttl_seconds,
                data,
            )
            return True
        except Exception:
            return False

    async def invalidate(self, query: str, provider: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            query: Search query to invalidate
            provider: Specific provider to invalidate (None = all providers)

        Returns:
            Number of keys deleted
        """
        if provider:
            key = self._make_key(query, provider)
            return await self.redis.delete(key)
        else:
            # Invalidate all providers for this query
            query_hash = hashlib.md5(query.lower().encode()).hexdigest()
            pattern = f"{self.prefix}*:{query_hash}"
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0

    async def clear(self) -> int:
        """Clear all search cache.

        Returns:
            Number of keys deleted
        """
        keys = await self.redis.keys(f"{self.prefix}*")
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Cache stats including size and entry count
        """
        keys = await self.redis.keys(f"{self.prefix}*")
        total_size = 0

        for key in keys:
            size = await self.redis.strlen(key)
            total_size += size

        return {
            "entries": len(keys),
            "total_size_bytes": total_size,
            "ttl_seconds": self.ttl_seconds,
        }
