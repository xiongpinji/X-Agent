"""A stack data structure implementation (LIFO).

A stack is a linear data structure that follows the Last-In-First-Out (LIFO)
principle: the most recently added element is the first one to be removed.

This module provides a generic, type-annotated Stack class backed by a Python
list, with the classic operations (push, pop, peek) plus a few conveniences
(size, is_empty, contains) and iteration support.

Example:
    >>> s = Stack()
    >>> s.push(1)
    >>> s.push(2)
    >>> s.peek()
    2
    >>> s.pop()
    2
"""

from __future__ import annotations

from typing import Generic, Iterator, List, Optional, TypeVar, Union

T = TypeVar("T")


class StackEmptyError(Exception):
    """Raised when attempting to pop or peek from an empty stack."""

    def __init__(self) -> None:
        super().__init__("Cannot pop/peek from an empty stack.")


class Stack(Generic[T]):
    """A generic stack (LIFO) container.

    Attributes:
        _items: Internal list holding the stack elements. The last element is
            considered the "top" of the stack.
    """

    __slots__ = ("_items",)

    def __init__(self, iterable: Optional[Iterable[T]] = None) -> None:
        """Initialize an empty stack, optionally seeding with an iterable.

        Args:
            iterable: Optional initial items. They are pushed in the iteration
                order, so the last item of the iterable ends up on top.
        """
        self._items: List[T] = []
        if iterable is not None:
            for item in iterable:
                self.push(item)

    def push(self, item: T) -> None:
        """Add an item to the top of the stack.

        Args:
            item: The element to add.
        """
        self._items.append(item)

    def pop(self) -> T:
        """Remove and return the top item of the stack.

        Returns:
            The top element.

        Raises:
            StackEmptyError: If the stack is empty.
        """
        if self.is_empty():
            raise StackEmptyError()
        return self._items.pop()

    def peek(self) -> T:
        """Return the top item without removing it.

        Returns:
            The top element.

        Raises:
            StackEmptyError: If the stack is empty.
        """
        if self.is_empty():
            raise StackEmptyError()
        return self._items[-1]

    def is_empty(self) -> bool:
        """Return True if the stack contains no elements."""
        return len(self._items) == 0

    def __len__(self) -> int:
        """Return the number of elements in the stack."""
        return len(self._items)

    def size(self) -> int:
        """Return the number of elements in the stack.

        Equivalent to ``len(stack)``.
        """
        return len(self._items)

    def clear(self) -> None:
        """Remove all elements from the stack."""
        self._items.clear()

    def contains(self, item: T) -> bool:
        """Return True if ``item`` is present anywhere in the stack."""
        return item in self._items

    def __contains__(self, item: object) -> bool:
        return item in self._items

    def __iter__(self) -> Iterator[T]:
        """Iterate from the top of the stack down to the bottom."""
        return iter(reversed(self._items))

    def __reversed__(self) -> Iterator[T]:
        """Iterate from the bottom of the stack up to the top."""
        return iter(self._items)

    def __repr__(self) -> str:
        contents = ", ".join(repr(item) for item in reversed(self._items))
        return f"Stack([{contents}])"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Stack):
            return NotImplemented
        # Compare top-to-bottom ordering.
        return list(self) == list(other)


# Convenience type alias for the union used in error handling.
StackValue = Union[T, None]
