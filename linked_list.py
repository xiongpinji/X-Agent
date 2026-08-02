"""A singly-linked list implementation in Python.

This module provides a classic singly-linked list data structure with a
Node class and a LinkedList class supporting common operations such as
insertion, deletion, search, traversal, and iteration.
"""

from __future__ import annotations

from typing import Any, Generic, Iterator, Optional, TypeVar

T = TypeVar("T")


class Node(Generic[T]):
    """A single node in the linked list.

    Attributes:
        data: The value stored in this node.
        next: A reference to the next node, or None for the tail.
    """

    __slots__ = ("data", "next")

    def __init__(self, data: T, next: Optional["Node[T]"] = None) -> None:
        """Initialize a node with the given data and optional next pointer.

        Args:
            data: The value to store in the node.
            next: The next node in the list, or None.
        """
        self.data = data
        self.next = next

    def __repr__(self) -> str:
        return f"Node({self.data!r})"


class LinkedList(Generic[T]):
    """A singly-linked list.

    Supports prepending, appending, insertion at an index, deletion,
    searching, indexing, length queries, and iteration.
    """

    def __init__(self, values: Optional[Iterable[T]] = None) -> None:
        """Initialize an empty list, or one populated from ``values``.

        Args:
            values: An optional iterable of initial values.
        """
        self._head: Optional[Node[T]] = None
        self._size: int = 0
        if values is not None:
            for value in values:
                self.append(value)

    # ------------------------------------------------------------------
    # Basic properties
    # ------------------------------------------------------------------
    @property
    def head(self) -> Optional[Node[T]]:
        """Return the first node in the list (or None if empty)."""
        return self._head

    def __len__(self) -> int:
        """Return the number of elements in the list."""
        return self._size

    def is_empty(self) -> bool:
        """Return True if the list contains no elements."""
        return self._size == 0

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------
    def prepend(self, data: T) -> None:
        """Insert ``data`` at the front of the list (O(1)).

        Args:
            data: The value to insert.
        """
        self._head = Node(data, self._head)
        self._size += 1

    def append(self, data: T) -> None:
        """Insert ``data`` at the end of the list.

        Args:
            data: The value to insert.
        """
        new_node = Node(data)
        if self._head is None:
            self._head = new_node
        else:
            current = self._head
            while current.next is not None:
                current = current.next
            current.next = new_node
        self._size += 1

    def insert(self, index: int, data: T) -> None:
        """Insert ``data`` at the given zero-based ``index``.

        Args:
            index: Position at which to insert. May be negative to index
                from the end. Values beyond the current length append.
            data: The value to insert.

        Raises:
            TypeError: If ``index`` is not an integer.
        """
        if not isinstance(index, int):
            raise TypeError("index must be an integer")

        if index <= 0:
            self.prepend(data)
            return

        if index >= self._size:
            self.append(data)
            return

        current = self._head
        for _ in range(index - 1):
            current = current.next  # type: ignore[union-attr]
        assert current is not None
        current.next = Node(data, current.next)
        self._size += 1

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------
    def pop(self, index: int = -1) -> T:
        """Remove and return the element at ``index`` (default: last).

        Args:
            index: Zero-based index of the element to remove. Negative
                values index from the end.

        Returns:
            The value that was removed.

        Raises:
            IndexError: If the list is empty or the index is out of range.
        """
        if self._size == 0:
            raise IndexError("pop from empty linked list")

        if not isinstance(index, int):
            raise TypeError("index must be an integer")

        # Normalize negative index.
        if index < 0:
            index += self._size
        if index < 0 or index >= self._size:
            raise IndexError("pop index out of range")

        if index == 0:
            assert self._head is not None
            value = self._head.data
            self._head = self._head.next
        else:
            current = self._head
            for _ in range(index - 1):
                current = current.next  # type: ignore[union-attr]
            assert current is not None and current.next is not None
            value = current.next.data
            current.next = current.next.next

        self._size -= 1
        return value

    def remove(self, data: T) -> None:
        """Remove the first occurrence of ``data`` from the list.

        Args:
            data: The value to remove.

        Raises:
            ValueError: If ``data`` is not present in the list.
        """
        if self._head is None:
            raise ValueError("linked list.remove(x): x not in list")

        if self._head.data == data:
            self._head = self._head.next
            self._size -= 1
            return

        current = self._head
        while current.next is not None:
            if current.next.data == data:
                current.next = current.next.next
                self._size -= 1
                return
            current = current.next

        raise ValueError("linked list.remove(x): x not in list")

    def clear(self) -> None:
        """Remove all elements from the list."""
        self._head = None
        self._size = 0

    # ------------------------------------------------------------------
    # Access / search
    # ------------------------------------------------------------------
    def __getitem__(self, index: int) -> T:
        """Return the element at ``index`` (supports negative indices).

        Args:
            index: Zero-based index of the element.

        Returns:
            The value at the given index.

        Raises:
            IndexError: If the index is out of range.
        """
        node = self._node_at(index)
        return node.data

    def _node_at(self, index: int) -> Node[T]:
        """Return the node at ``index`` without removing it.

        Args:
            index: Zero-based index (negative counts from the end).

        Returns:
            The node at the given index.

        Raises:
            IndexError: If the index is out of range.
        """
        if self._size == 0:
            raise IndexError("index out of range")

        if not isinstance(index, int):
            raise TypeError("indices must be integers")

        if index < 0:
            index += self._size
        if index < 0 or index >= self._size:
            raise IndexError("index out of range")

        current = self._head
        for _ in range(index):
            current = current.next  # type: ignore[union-attr]
        assert current is not None
        return current

    def index(self, data: T) -> int:
        """Return the index of the first occurrence of ``data``.

        Args:
            data: The value to search for.

        Returns:
            Zero-based index of the first match.

        Raises:
            ValueError: If ``data`` is not present in the list.
        """
        current = self._head
        i = 0
        while current is not None:
            if current.data == data:
                return i
            current = current.next
            i += 1
        raise ValueError(f"{data!r} is not in linked list")

    def contains(self, data: T) -> bool:
        """Return True if ``data`` is present in the list."""
        try:
            self.index(data)
            return True
        except ValueError:
            return False

    def __contains__(self, data: T) -> bool:
        """Support the ``in`` operator."""
        return self.contains(data)

    # ------------------------------------------------------------------
    # Iteration / representation
    # ------------------------------------------------------------------
    def __iter__(self) -> Iterator[T]:
        """Yield each element in the list from head to tail."""
        current = self._head
        while current is not None:
            yield current.data
            current = current.next

    def to_list(self) -> list[T]:
        """Return a Python list containing all elements in order."""
        return list(self)

    def __repr__(self) -> str:
        """Return a string like ``LinkedList([1, 2, 3])``."""
        return f"LinkedList({self.to_list()!r})"

    def __eq__(self, other: object) -> bool:
        """Compare two linked lists by their contents."""
        if not isinstance(other, LinkedList):
            return NotImplemented
        return self.to_list() == other.to_list()
