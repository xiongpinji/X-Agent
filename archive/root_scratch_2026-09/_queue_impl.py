"""A FIFO (First-In, First-Out) queue implementation.

This module provides a generic queue data structure with the standard
queue operations: enqueue, dequeue, peek, size, and emptiness checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


class QueueError(Exception):
    """Base exception raised by the Queue."""


class EmptyQueueError(QueueError):
    """Raised when operating on an empty queue."""


class Queue(Generic[T]):
    """A FIFO queue backed by a Python list.

    Items are added to the rear (``enqueue``) and removed from the front
    (``dequeue``), preserving insertion order.
    """

    __slots__ = ("_items",)

    def __init__(self, iterable: Optional[Iterable[T]] = None) -> None:
        """Initialize the queue.

        Args:
            iterable: Optional initial items, enqueued in order.
        """
        self._items: list[T] = list(iterable) if iterable is not None else []

    def enqueue(self, item: T) -> None:
        """Add an item to the rear of the queue.

        Args:
            item: The item to enqueue.
        """
        self._items.append(item)

    def dequeue(self) -> T:
        """Remove and return the item at the front of the queue.

        Returns:
            The front item.

        Raises:
            EmptyQueueError: If the queue is empty.
        """
        if self.is_empty():
            raise EmptyQueueError("Cannot dequeue from an empty queue.")
        return self._items.pop(0)

    def peek(self) -> T:
        """Return the front item without removing it.

        Returns:
            The front item.

        Raises:
            EmptyQueueError: If the queue is empty.
        """
        if self.is_empty():
            raise EmptyQueueError("Cannot peek at an empty queue.")
        return self._items[0]

    def is_empty(self) -> bool:
        """Return True if the queue contains no items."""
        return not self._items

    def __len__(self) -> int:
        """Return the number of items in the queue."""
        return len(self._items)

    def size(self) -> int:
        """Return the number of items in the queue."""
        return len(self._items)

    def clear(self) -> None:
        """Remove all items from the queue."""
        self._items.clear()

    def __iter__(self) -> Iterator[T]:
        """Iterate over items in FIFO order without consuming them."""
        return iter(self._items)

    def __repr__(self) -> str:
        return f"Queue({self._items!r})"
