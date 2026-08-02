"""A hash map (hash table) implementation using separate chaining.

This module provides a generic hash map data structure that maps keys to
values using an underlying array of buckets. Collisions are resolved via
separate chaining with Python lists. The map automatically resizes (grows)
when the load factor exceeds a configured threshold to maintain amortized
O(1) average-time operations.

The implementation supports arbitrary hashable keys (anything usable as a
Python dict key) and any value type.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

_DEFAULT_CAPACITY = 8
_DEFAULT_LOAD_FACTOR = 0.75
_GROWTH_FACTOR = 2


class _Bucket(Generic[K, V]):
    """A chain of key/value entries storing collided keys."""

    __slots__ = ("key", "value", "next")

    def __init__(self, key: K, value: V, nxt: "_Bucket[K, V] | None" = None) -> None:
        self.key = key
        self.value = value
        self.next = nxt


class _Sentinel:
    """Marker object used as a default value to detect missing keys."""

    _instance: "_Sentinel | None" = None

    def __new__(cls) -> "_Sentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _Sentinel()


class HashMap(MutableMapping[K, V], Generic[K, V]):
    """A hash map backed by an array of linked-list buckets.

    Keys must be hashable. Complexity:

    * ``put`` / ``get`` / ``delete``: average O(1), worst-case O(n).
    * ``__contains__``: average O(1).
    * ``__iter__``: O(n) over the current entries.
    """

    def __init__(
        self,
        capacity: int = _DEFAULT_CAPACITY,
        load_factor: float = _DEFAULT_LOAD_FACTOR,
    ) -> None:
        """Initialise an empty hash map.

        Args:
            capacity: Initial number of buckets. Must be positive.
            load_factor: Maximum ratio of entries to buckets before the map
                grows. Must be in the interval (0, 1].
        """
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        if not 0 < load_factor <= 1:
            raise ValueError("load_factor must be in the interval (0, 1]")

        self._capacity = capacity
        self._load_factor = load_factor
        self._size = 0
        self._table: list[_Bucket[K, V] | None] = [None] * capacity

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _index(self, key: K) -> int:
        """Return the bucket index for a given key."""
        return hash(key) % self._capacity

    def _find(
        self, key: K
    ) -> tuple[_Bucket[K, V] | None, _Bucket[K, V] | None]:
        """Locate the bucket holding ``key``.

        Returns a tuple ``(prev, node)`` where ``node`` is the entry whose
        key equals ``key`` (or ``None``) and ``prev`` is its predecessor
        (or ``None`` if ``node`` is the head of its chain).
        """
        head = self._table[self._index(key)]
        prev: _Bucket[K, V] | None = None
        node = head
        while node is not None:
            if node.key == key:
                return prev, node
            prev = node
            node = node.next
        return None, None

    def _needs_resize(self) -> bool:
        """Return ``True`` if the load factor threshold has been exceeded."""
        return self._size / self._capacity > self._load_factor

    def _resize(self) -> None:
        """Double the bucket count and rehash all existing entries."""
        old_table = self._table
        self._capacity *= _GROWTH_FACTOR
        self._table = [None] * self._capacity
        self._size = 0

        for head in old_table:
            node = head
            while node is not None:
                self._insert_internal(node.key, node.value)
                node = node.next

    def _insert_internal(self, key: K, value: V) -> None:
        """Insert a key/value pair without triggering a resize."""
        index = self._index(key)
        head = self._table[index]

        # Overwrite an existing key if present.
        node = head
        while node is not None:
            if node.key == key:
                node.value = value
                return
            node = node.next

        # Otherwise prepend a new entry to the chain.
        self._table[index] = _Bucket(key, value, head)
        self._size += 1

    # ------------------------------------------------------------------
    # MutableMapping protocol
    # ------------------------------------------------------------------
    def __setitem__(self, key: K, value: V) -> None:
        """Insert or update ``key`` with ``value``."""
        if self._needs_resize():
            self._resize()
        self._insert_internal(key, value)

    def __getitem__(self, key: K) -> V:
        """Return the value associated with ``key``.

        Raises:
            KeyError: If ``key`` is not present in the map.
        """
        _, node = self._find(key)
        if node is None:
            raise KeyError(key)
        return node.value

    def __delitem__(self, key: K) -> None:
        """Remove ``key`` and its associated value.

        Raises:
            KeyError: If ``key`` is not present in the map.
        """
        index = self._index(key)
        prev, node = self._find(key)
        if node is None:
            raise KeyError(key)

        if prev is None:
            self._table[index] = node.next
        else:
            prev.next = node.next
        node.next = None  # help the garbage collector
        self._size -= 1

    def __contains__(self, key: object) -> bool:
        """Return ``True`` if ``key`` exists in the map."""
        if not isinstance(key, Hashable):
            return False
        _, node = self._find(key)  # type: ignore[arg-type]
        return node is not None

    def __iter__(self) -> Iterator[K]:
        """Iterate over the keys currently in the map."""
        for head in self._table:
            node = head
            while node is not None:
                yield node.key
                node = node.next

    def __len__(self) -> int:
        """Return the number of key/value pairs in the map."""
        return self._size

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------
    def get(self, key: K, default: V | Any = None) -> V | Any:
        """Return the value for ``key`` or ``default`` if absent."""
        _, node = self._find(key)
        return node.value if node is not None else default

    def setdefault(self, key: K, default: V | Any = None) -> V | Any:
        """Return the value for ``key``, inserting ``default`` if absent."""
        _, node = self._find(key)
        if node is not None:
            return node.value
        self[key] = default  # type: ignore[assignment]
        return default

    def pop(self, key: K, default: V | Any = _MISSING) -> V | Any:
        """Remove and return the value for ``key``.

        Raises:
            KeyError: If ``key`` is absent and ``default`` is not provided.
        """
        _, node = self._find(key)
        if node is None:
            if default is _MISSING:
                raise KeyError(key)
            return default
        value = node.value
        del self[key]
        return value

    def keys(self) -> list[K]:
        """Return a list of all keys in the map."""
        return list(self)

    def values(self) -> list[V]:
        """Return a list of all values in the map."""
        return [self[key] for key in self]

    def items(self) -> list[tuple[K, V]]:
        """Return a list of ``(key, value)`` pairs in the map."""
        return [(key, self[key]) for key in self]

    def clear(self) -> None:
        """Remove all entries from the map."""
        self._table = [None] * self._capacity
        self._size = 0

    def capacity(self) -> int:
        """Return the current number of buckets."""
        return self._capacity

    def load_factor(self) -> float:
        """Return the current ratio of entries to buckets."""
        return self._size / self._capacity

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        body = ", ".join(f"{key!r}: {value!r}" for key, value in self.items())
        return f"{self.__class__.__name__}({{{body}}})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return NotImplemented
        if len(self) != len(other):
            return False
        for key, value in self.items():
            if key not in other or other[key] != value:
                return False
        return True


from collections.abc import Mapping  # noqa: E402  (imported for __eq__)
