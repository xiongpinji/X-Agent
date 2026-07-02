"""Search result caching module."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import hashlib
import json
import time


class SearchCache:
    """In-memory search result cache."""

    def __init__(self, ttl: int = 3600):
        """Initialize search cache.

        Args:
            ttl: Time to live for cache entries in seconds
        """
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    def _get_cache_key(self, query: str, search_type: str = "web") -> str:
        """Generate cache key.

        Args:
            query: Search query
            search_type: Type of search

        Returns:
            Cache key
        """
        key_str = f"{search_type}:{query}"
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    async def get(self, query: str, search_type: str = "web") -> Optional[List[Dict[str, Any]]]:
        """Get cached search results.

        Args:
            query: Search query
            search_type: Type of search

        Returns:
            Cached results or None if expired/not found
        """
        key = self._get_cache_key(query, search_type)

        if key not in self.cache:
            return None

        entry = self.cache[key]
        if time.time() > entry["expires_at"]:
            del self.cache[key]
            return None

        return entry["results"]

    async def set(
        self,
        query: str,
        results: List[Dict[str, Any]],
        search_type: str = "web",
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            results: Search results to cache
            search_type: Type of search
        """
        key = self._get_cache_key(query, search_type)
        self.cache[key] = {
            "results": results,
            "expires_at": time.time() + self.ttl,
            "created_at": time.time(),
        }

    async def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry["expires_at"]
        ]

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        await self.cleanup_expired()

        return {
            "total_entries": len(self.cache),
            "ttl": self.ttl,
            "cache_size_bytes": len(json.dumps(self.cache).encode()),
        }


class RedisSearchCache:
    """Redis-based search result cache."""

    def __init__(self, redis_client: Any, ttl: int = 3600):
        """Initialize Redis search cache.

        Args:
            redis_client: Redis client instance
            ttl: Time to live for cache entries in seconds
        """
        self.redis = redis_client
        self.ttl = ttl

    def _get_cache_key(self, query: str, search_type: str = "web") -> str:
        """Generate cache key.

        Args:
            query: Search query
            search_type: Type of search

        Returns:
            Cache key
        """
        key_str = f"search:{search_type}:{query}"
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    async def get(self, query: str, search_type: str = "web") -> Optional[List[Dict[str, Any]]]:
        """Get cached search results.

        Args:
            query: Search query
            search_type: Type of search

        Returns:
            Cached results or None if not found
        """
        key = self._get_cache_key(query, search_type)
        data = await self.redis.get(key)

        if data is None:
            return None

        return json.loads(data)

    async def set(
        self,
        query: str,
        results: List[Dict[str, Any]],
        search_type: str = "web",
    ) -> None:
        """Cache search results.

        Args:
            query: Search query
            results: Search results to cache
            search_type: Type of search
        """
        key = self._get_cache_key(query, search_type)
        await self.redis.setex(key, self.ttl, json.dumps(results))

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self.redis.flushdb()

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        info = await self.redis.info()
        return {
            "used_memory": info.get("used_memory_human"),
            "ttl": self.ttl,
            "db_size": await self.redis.dbsize(),
        }
