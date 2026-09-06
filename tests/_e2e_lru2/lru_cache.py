"""Thread-safe LRU (Least Recently Used) cache implementation."""

import threading
from collections import OrderedDict
from typing import Any, Optional


class LRUCache:
    """A thread-safe LRU cache.

    All public operations are guarded by a lock. The cache evicts the
    least-recently-used entry once its size exceeds ``capacity``.
    """

    def __init__(self, capacity: int = 128) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self._capacity: int = capacity
        self._data: "OrderedDict[Any, Any]" = OrderedDict()
        self._lock = threading.RLock()
        self._hits: int = 0
        self._misses: int = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def get(self, key: Any) -> Optional[Any]:
        """Return the value for ``key`` (refreshing its recency) or ``None``."""
        with self._lock:
            if key in self._data:
                self._hits += 1
                # Move to the end to mark it as most recently used.
                self._data.move_to_end(key)
                return self._data[key]
            self._misses += 1
            return None

    def put(self, key: Any, value: Any) -> None:
        """Insert or overwrite ``key`` with ``value``.

        Overwriting an existing key does not count toward eviction. When the
        cache exceeds capacity the least recently used entry is evicted.
        """
        with self._lock:
            if key in self._data:
                # Overwrite in place; recency is refreshed.
                self._data[key] = value
                self._data.move_to_end(key)
                return
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._capacity:
                # Pop the oldest (least recently used) item.
                self._data.popitem(last=False)

    def delete(self, key: Any) -> bool:
        """Remove ``key`` if present. Returns ``True`` if it was removed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def stats(self) -> dict:
        """Return usage statistics as a dictionary."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total else 0.0
            return {
                "size": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._data

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"LRUCache(capacity={self._capacity}, size={len(self._data)})"
            )
