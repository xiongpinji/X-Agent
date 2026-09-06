"""Thread-safe LRU (Least Recently Used) cache implementation.

This module provides a thread-safe LRUCache class backed by an
``OrderedDict``.  All mutating and querying operations are protected by a
single re-entrant lock so that concurrent access from multiple threads stays
consistent.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Optional


class LRUCache:
    """A thread-safe LRU cache with a fixed capacity.

    Parameters
    ----------
    capacity : int
        Maximum number of items the cache may hold.  When an insertion would
        exceed this limit the least recently used entry is evicted.  Defaults
        to 128.
    """

    def __init__(self, capacity: int = 128) -> None:
        if not isinstance(capacity, int):
            raise TypeError("capacity must be an int")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._data: "OrderedDict[Any, Any]" = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # -- public API ---------------------------------------------------------

    def get(self, key: Any) -> Optional[Any]:
        """Return the value for *key* or ``None`` if it is not cached.

        A successful lookup refreshes the recency of *key*.
        """
        with self._lock:
            if key in self._data:
                value = self._data.pop(key)
                self._data[key] = value  # move to the most-recent position
                self._hits += 1
                return value
            self._misses += 1
            return None

    def put(self, key: Any, value: Any) -> None:
        """Insert or replace *key* with *value*.

        If *key* already exists its value is updated without eviction.
        Otherwise, when the cache is at capacity the least recently used item
        is evicted to make room.
        """
        with self._lock:
            if key in self._data:
                self._data.pop(key)  # remove old entry, re-insert as newest
            elif len(self._data) >= self._capacity:
                # Evict the least recently used item.
                self._data.popitem(last=False)
            self._data[key] = value

    def delete(self, key: Any) -> bool:
        """Remove *key* from the cache if present.

        Returns ``True`` when an entry was removed, ``False`` otherwise.
        """
        with self._lock:
            if key in self._data:
                self._data.pop(key)
                return True
            return False

    def stats(self) -> Dict[str, Any]:
        """Return a snapshot of cache statistics.

        The returned mapping contains ``size``, ``hits``, ``misses`` and
        ``hit_rate``.  ``hit_rate`` is the fraction of lookups that hit and is
        ``0.0`` when no lookups have been performed yet.
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total else 0.0
            return {
                "size": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
            }

    # -- dunder helpers -----------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._data
