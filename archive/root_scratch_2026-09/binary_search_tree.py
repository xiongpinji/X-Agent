"""Binary Search Tree implementation in Python.

A binary search tree (BST) is a node-based binary tree data structure where each
node has at most two children, referred to as the left child and the right child.
For each node, all elements in the left subtree are less than the node's value,
and all elements in the right subtree are greater than the node's value.

This module provides a ``BSTNode`` class representing a single node and a
``BinarySearchTree`` class providing the public API with operations such as
insertion, deletion, searching, and various traversals.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, List, Optional


class BSTNode:
    """A node in the binary search tree.

    Attributes:
        value: The value stored in the node.
        left: The left child node (or ``None``).
        right: The right child node (or ``None``).
    """

    __slots__ = ("value", "left", "right")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.left: Optional[BSTNode] = None
        self.right: Optional[BSTNode] = None

    def __repr__(self) -> str:
        return f"BSTNode(value={self.value!r})"


class BinarySearchTree:
    """A binary search tree supporting common operations.

    The tree maintains the BST invariant: for any node, all values in the left
    subtree are strictly less than the node's value and all values in the right
    subtree are strictly greater. Duplicate values are not stored.

    Args:
        values: An optional iterable of initial values to insert.
    """

    def __init__(self, values: Optional[Iterable[Any]] = None) -> None:
        self._root: Optional[BSTNode] = None
        self._size: int = 0
        if values is not None:
            for value in values:
                self.insert(value)

    def __len__(self) -> int:
        """Return the number of nodes in the tree."""
        return self._size

    def __bool__(self) -> bool:
        """Return ``True`` if the tree is non-empty."""
        return self._size > 0

    def __contains__(self, value: Any) -> bool:
        """Return ``True`` if ``value`` is present in the tree."""
        return self.search(value) is not None

    def __iter__(self) -> Iterator[Any]:
        """Iterate over values in in-order (ascending) order."""
        return self.inorder()

    def is_empty(self) -> bool:
        """Return ``True`` if the tree contains no nodes."""
        return self._root is None

    def insert(self, value: Any) -> bool:
        """Insert ``value`` into the tree.

        If ``value`` already exists, no insertion occurs.

        Returns:
            ``True`` if the value was newly inserted, ``False`` otherwise.
        """
        if self._root is None:
            self._root = BSTNode(value)
            self._size += 1
            return True

        node = self._root
        while node is not None:
            if value == node.value:
                return False
            if value < node.value:
                if node.left is None:
                    node.left = BSTNode(value)
                    self._size += 1
                    return True
                node = node.left
            else:
                if node.right is None:
                    node.right = BSTNode(value)
                    self._size += 1
                    return True
                node = node.right
        return False  # pragma: no cover - unreachable

    def search(self, value: Any) -> Optional[BSTNode]:
        """Return the node containing ``value``, or ``None`` if absent."""
        node = self._root
        while node is not None:
            if value == node.value:
                return node
            node = node.left if value < node.value else node.right
        return None

    def contains(self, value: Any) -> bool:
        """Return ``True`` if ``value`` is present in the tree."""
        return value in self

    def delete(self, value: Any) -> bool:
        """Delete ``value`` from the tree if present.

        Returns:
            ``True`` if the value was found and removed, ``False`` otherwise.
        """
        parent: Optional[BSTNode] = None
        node = self._root

        # Locate the node and its parent.
        while node is not None and node.value != value:
            parent = node
            node = node.left if value < node.value else node.right

        if node is None:
            return False

        # Case 1: node has two children -> replace with in-order successor.
        if node.left is not None and node.right is not None:
            successor_parent = node
            successor = node.right
            while successor.left is not None:
                successor_parent = successor
                successor = successor.left
            node.value = successor.value
            # Re-target deletion onto the successor.
            parent, node = successor_parent, successor

        # Case 2 & 3: node has zero or one child.
        child = node.left if node.left is not None else node.right

        if parent is None:
            self._root = child
        elif parent.left is node:
            parent.left = child
        else:
            parent.right = child

        self._size -= 1
        return True

    def min(self) -> Any:
        """Return the smallest value in the tree.

        Raises:
            ValueError: If the tree is empty.
        """
        if self._root is None:
            raise ValueError("min() called on an empty tree")
        node = self._root
        while node.left is not None:
            node = node.left
        return node.value

    def max(self) -> Any:
        """Return the largest value in the tree.

        Raises:
            ValueError: If the tree is empty.
        """
        if self._root is None:
            raise ValueError("max() called on an empty tree")
        node = self._root
        while node.right is not None:
            node = node.right
        return node.value

    def _min_node(self, node: BSTNode) -> BSTNode:
        """Return the node with the smallest value in the subtree rooted at node."""
        while node.left is not None:
            node = node.left
        return node

    def inorder(self) -> Iterator[Any]:
        """Yield values in ascending (left-root-right) order."""
        yield from self._inorder(self._root)

    def _inorder(self, node: Optional[BSTNode]) -> Iterator[Any]:
        if node is not None:
            yield from self._inorder(node.left)
            yield node.value
            yield from self._inorder(node.right)

    def preorder(self) -> Iterator[Any]:
        """Yield values in root-left-right order."""
        yield from self._preorder(self._root)

    def _preorder(self, node: Optional[BSTNode]) -> Iterator[Any]:
        if node is not None:
            yield node.value
            yield from self._preorder(node.left)
            yield from self._preorder(node.right)

    def postorder(self) -> Iterator[Any]:
        """Yield values in left-right-root order."""
        yield from self._postorder(self._root)

    def _postorder(self, node: Optional[BSTNode]) -> Iterator[Any]:
        if node is not None:
            yield from self._postorder(node.left)
            yield from self._postorder(node.right)
            yield node.value

    def to_list(self) -> List[Any]:
        """Return the values of the tree as a list in ascending order."""
        return list(self.inorder())

    def height(self) -> int:
        """Return the height of the tree (number of edges on the longest path).

        An empty tree has height ``-1``; a single-node tree has height ``0``.
        """
        return self._height(self._root)

    def _height(self, node: Optional[BSTNode]) -> int:
        if node is None:
            return -1
        return 1 + max(self._height(node.left), self._height(node.right))

    def clear(self) -> None:
        """Remove all nodes from the tree."""
        self._root = None
        self._size = 0

    def __repr__(self) -> str:
        return f"BinarySearchTree({self.to_list()!r})"
