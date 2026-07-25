"""Tool result caching with TTL and LRU eviction."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """A single cache entry."""

    key: str
    value: Any
    created_at: float
    ttl: int  # Time to live in seconds
    access_count: int = 0
    last_accessed: float = 0.0

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() - self.created_at >= self.ttl

    def touch(self) -> None:
        """Update last access time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Statistics about cache performance."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0
    expirations: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_misses / self.total_requests


class ToolResultCache:
    """Cache for tool execution results with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default time-to-live in seconds
        """
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._stats = CacheStats(max_size=max_size)

    async def get(self, tool_name: str, args: dict[str, Any]) -> Any | None:
        """Get a cached result.

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool

        Returns:
            Cached result or None if not found or expired
        """
        key = self._make_key(tool_name, args)
        self._stats.total_requests += 1

        if key not in self._cache:
            self._stats.cache_misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if entry.is_expired():
            del self._cache[key]
            self._stats.expirations += 1
            self._stats.cache_misses += 1
            return None

        # Cache hit
        entry.touch()
        self._stats.cache_hits += 1
        return entry.value

    async def set(
        self, tool_name: str, args: dict[str, Any], result: Any, ttl: int | None = None
    ) -> None:
        """Cache a tool result.

        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            result: Result to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        key = self._make_key(tool_name, args)
        ttl = self._default_ttl if ttl is None else ttl

        # Check if we need to evict
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict_lru()

        entry = CacheEntry(
            key=key,
            value=result,
            created_at=time.time(),
            ttl=ttl,
        )
        self._cache[key] = entry

    async def invalidate(self, tool_name: str | None = None, args: dict[str, Any] | None = None) -> None:
        """Invalidate cache entries.

        Args:
            tool_name: If provided, only invalidate entries for this tool
            args: If provided, only invalidate entries with these exact args
        """
        if tool_name is None:
            # Clear entire cache
            self._cache.clear()
            return

        if args is None:
            # Clear all entries for this tool
            keys_to_delete = [
                key for key in self._cache if key.startswith(f"{tool_name}:")
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return

        # Clear specific entry
        key = self._make_key(tool_name, args)
        if key in self._cache:
            del self._cache[key]

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.current_size = len(self._cache)
        return self._stats

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats(max_size=self._max_size)

    def _make_key(self, tool_name: str, args: dict[str, Any]) -> str:
        """Generate a cache key from tool name and arguments.

        Args:
            tool_name: Name of the tool
            args: Arguments dictionary

        Returns:
            Cache key
        """
        # Sort args for consistent hashing
        sorted_args = json.dumps(args, sort_keys=True, default=str)
        args_hash = hashlib.sha256(sorted_args.encode()).hexdigest()[:16]
        return f"{tool_name}:{args_hash}"

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return

        # Find LRU entry (least recently accessed, or oldest if never accessed)
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].last_accessed, self._cache[k].created_at),
        )

        del self._cache[lru_key]
        self._stats.evictions += 1

    def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
            self._stats.expirations += 1
