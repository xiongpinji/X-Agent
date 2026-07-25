"""
Performance optimization and caching system for X-Agent.
Implements intelligent caching, LLM call optimization, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

T = TypeVar('T')


class CacheStrategy(StrEnum):
    """Cache eviction strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    key: str
    value: T
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float | None = None

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Update access time and count."""
        self.accessed_at = time.time()
        self.access_count += 1


class Cache(ABC, Generic[T]):
    """Abstract cache interface."""

    @abstractmethod
    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: T, ttl: float | None = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get cache size."""
        pass


class MemoryCache(Cache[T]):
    """In-memory cache with configurable eviction strategy."""

    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.entries: dict[str, CacheEntry[T]] = {}

    async def get(self, key: str) -> T | None:
        """Get value from cache."""
        entry = self.entries.get(key)
        if entry is None:
            return None

        if entry.is_expired():
            del self.entries[key]
            return None

        entry.touch()
        return entry.value

    async def set(self, key: str, value: T, ttl: float | None = None) -> None:
        """Set value in cache."""
        if len(self.entries) >= self.max_size:
            await self._evict()

        self.entries[key] = CacheEntry(key=key, value=value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.entries:
            del self.entries[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        self.entries.clear()

    async def size(self) -> int:
        """Get cache size."""
        return len(self.entries)

    async def _evict(self) -> None:
        """Evict entry based on strategy."""
        if not self.entries:
            return

        if self.strategy == CacheStrategy.LRU:
            # Remove least recently used
            key = min(self.entries.keys(),
                     key=lambda k: self.entries[k].accessed_at)
        elif self.strategy == CacheStrategy.LFU:
            # Remove least frequently used
            key = min(self.entries.keys(),
                     key=lambda k: self.entries[k].access_count)
        elif self.strategy == CacheStrategy.FIFO:
            # Remove first in
            key = min(self.entries.keys(),
                     key=lambda k: self.entries[k].created_at)
        else:
            # TTL: remove expired entries first
            for k, entry in list(self.entries.items()):
                if entry.is_expired():
                    del self.entries[k]
                    return
            # If no expired, use LRU
            key = min(self.entries.keys(),
                     key=lambda k: self.entries[k].accessed_at)

        del self.entries[key]


class QueryCache(Cache[Any]):
    """Specialized cache for database queries."""

    def __init__(self, max_size: int = 500):
        self.cache = MemoryCache[Any](max_size=max_size, strategy=CacheStrategy.LRU)

    async def get(self, key: str) -> Any | None:
        return await self.cache.get(key)

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        # Default TTL for queries: 5 minutes
        ttl = ttl or 300
        await self.cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        return await self.cache.delete(key)

    async def clear(self) -> None:
        await self.cache.clear()

    async def size(self) -> int:
        return await self.cache.size()

    @staticmethod
    def make_key(query: str, params: dict[str, Any]) -> str:
        """Generate cache key from query and parameters."""
        key_str = f"{query}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()


class LLMCallOptimizer:
    """Optimizes LLM API calls through batching and caching."""

    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.cache = MemoryCache[Any](max_size=1000)
        self.pending_calls: list[tuple[str, dict[str, Any]]] = []
        self.batch_lock = asyncio.Lock()

    async def call(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> str:
        """Make optimized LLM call."""
        # Check cache
        if use_cache:
            cache_key = self._make_cache_key(prompt, model, temperature)
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Add to batch
        async with self.batch_lock:
            self.pending_calls.append((prompt, {
                "model": model,
                "temperature": temperature,
            }))

            # Process batch if full or timeout
            if len(self.pending_calls) >= self.batch_size:
                results = await self._process_batch()
                return results[0] if results else ""

        # Wait for batch processing
        await asyncio.sleep(self.batch_timeout)

        async with self.batch_lock:
            if self.pending_calls:
                results = await self._process_batch()
                return results[0] if results else ""

        return ""

    async def _process_batch(self) -> list[str]:
        """Process pending batch of calls."""
        if not self.pending_calls:
            return []

        batch = self.pending_calls.copy()
        self.pending_calls.clear()

        # Simulate batch processing
        results = []
        for prompt, params in batch:
            result = f"Response to: {prompt[:50]}..."
            cache_key = self._make_cache_key(
                prompt,
                params.get("model", "gpt-4"),
                params.get("temperature", 0.7)
            )
            await self.cache.set(cache_key, result, ttl=3600)
            results.append(result)

        return results

    @staticmethod
    def _make_cache_key(prompt: str, model: str, temperature: float) -> str:
        """Generate cache key for LLM call."""
        key_str = f"{prompt}:{model}:{temperature}"
        return hashlib.md5(key_str.encode()).hexdigest()


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)


class PerformanceMonitor:
    """Monitors and tracks performance metrics."""

    def __init__(self):
        self.metrics: list[PerformanceMetric] = []
        self.timers: dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a timer."""
        self.timers[name] = time.time()

    def end_timer(self, name: str, unit: str = "ms") -> float | None:
        """End a timer and record metric."""
        if name not in self.timers:
            return None

        elapsed = time.time() - self.timers[name]
        if unit == "ms":
            elapsed *= 1000
        elif unit == "us":
            elapsed *= 1_000_000

        metric = PerformanceMetric(name=name, value=elapsed, unit=unit)
        self.metrics.append(metric)

        del self.timers[name]
        return elapsed

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {}
        )
        self.metrics.append(metric)

    def get_metrics(self, name: str | None = None) -> list[PerformanceMetric]:
        """Get recorded metrics."""
        if name is None:
            return self.metrics

        return [m for m in self.metrics if m.name == name]

    def get_average(self, name: str) -> float | None:
        """Get average value for metric."""
        metrics = self.get_metrics(name)
        if not metrics:
            return None

        return sum(m.value for m in metrics) / len(metrics)

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        summary = {}

        for metric in self.metrics:
            if metric.name not in summary:
                summary[metric.name] = {
                    "count": 0,
                    "total": 0,
                    "min": float('inf'),
                    "max": float('-inf'),
                    "unit": metric.unit,
                }

            summary[metric.name]["count"] += 1
            summary[metric.name]["total"] += metric.value
            summary[metric.name]["min"] = min(summary[metric.name]["min"], metric.value)
            summary[metric.name]["max"] = max(summary[metric.name]["max"], metric.value)

        # Calculate averages
        for name in summary:
            count = summary[name]["count"]
            summary[name]["average"] = summary[name]["total"] / count if count > 0 else 0

        return summary

    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()
        self.timers.clear()


def cached(ttl: float = 300, strategy: CacheStrategy = CacheStrategy.LRU):
    """Decorator for caching async function results."""
    cache = MemoryCache[Any](strategy=strategy)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Check cache
            cached_value = asyncio.run(cache.get(cache_key))
            if cached_value is not None:
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            asyncio.run(cache.set(cache_key, result, ttl=ttl))

            return result

        return wrapper

    return decorator


class ConnectionPool:
    """Manages connection pooling for database and external services."""

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.available: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self.in_use: set = set()

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        try:
            conn = self.available.get_nowait()
        except asyncio.QueueEmpty:
            if len(self.in_use) < self.max_connections:
                conn = self._create_connection()
            else:
                conn = await self.available.get()

        self.in_use.add(id(conn))
        return conn

    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        self.in_use.discard(id(conn))
        await self.available.put(conn)

    def _create_connection(self) -> Any:
        """Create a new connection."""
        # Placeholder for actual connection creation
        return {"id": id(object())}

    async def close_all(self) -> None:
        """Close all connections."""
        while not self.available.empty():
            try:
                self.available.get_nowait()
            except asyncio.QueueEmpty:
                break


# ============================================================================
# Additional caches and processors for test_functionality_integration
# ============================================================================

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Simple LRU cache with async interface."""

    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self._cache: dict[K, V] = {}
        self._order: list[K] = []

    async def get(self, key: K) -> V | None:
        if key not in self._cache:
            return None
        # Move to end (most recently used)
        self._order.remove(key)
        self._order.append(key)
        return self._cache[key]

    async def set(self, key: K, value: V) -> None:
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self.max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._order.append(key)

    async def get_stats(self) -> dict[str, Any]:
        return {"size": len(self._cache), "max_size": self.max_size}


class ResponseCache:
    """Cache for function responses keyed by (name, args, kwargs)."""

    def __init__(self, max_size: int = 100, ttl: float = 3600) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}

    def _make_key(self, name: str, args: tuple, kwargs: dict) -> str:
        key_str = f"{name}:{args}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(self, name: str, args: tuple, kwargs: dict) -> Any | None:
        key = self._make_key(name, args, kwargs)
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, created = entry
        if time.time() - created > self.ttl:
            del self._cache[key]
            return None
        return value

    async def set(self, name: str, args: tuple, kwargs: dict, result: Any) -> None:
        if len(self._cache) >= self.max_size:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        key = self._make_key(name, args, kwargs)
        self._cache[key] = (result, time.time())


class BatchProcessor(Generic[T]):
    """Batches items and processes them via a handler."""

    def __init__(self, batch_size: int = 10, timeout: float = 1.0) -> None:
        self.batch_size = batch_size
        self.timeout = timeout
        self._queue: asyncio.Queue[T] = asyncio.Queue()
        self._running = False

    async def add(self, item: T) -> None:
        await self._queue.put(item)

    async def process(self, handler: Callable[[list[T]], Any]) -> None:
        self._running = True
        while self._running:
            batch: list[T] = []
            try:
                # Collect up to batch_size items or until timeout
                deadline = time.time() + self.timeout
                while len(batch) < self.batch_size:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break
                    try:
                        item = await asyncio.wait_for(
                            self._queue.get(), timeout=remaining
                        )
                        batch.append(item)
                    except TimeoutError:
                        break
                if batch:
                    await handler(batch)
            except asyncio.CancelledError:
                break

    async def stop(self) -> None:
        self._running = False
