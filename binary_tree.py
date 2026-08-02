"""A binary tree implementation with common tree operations.

This module provides a `BinaryTreeNode` and a `BinaryTree` class supporting
insertion, traversal (inorder, preorder, postorder, level-order), searching,
deletion, height/depth computation, and other standard binary tree utilities.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Callable, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")


class BinaryTreeNode(Generic[T]):
    """A single node in a binary tree.

    Attributes:
        value: The value stored in this node.
        left: Reference to the left child node (or None).
        right: Reference to the right child node (or None).
    """

    __slots__ = ("value", "left", "right")

    def __init__(self, value: T) -> None:
        self.value = value
        self.left: Optional[BinaryTreeNode[T]] = None
        self.right: Optional[BinaryTreeNode[T]] = None

    def __repr__(self) -> str:
        return f"BinaryTreeNode({self.value!r})"


class BinaryTree(Generic[T]):
    """A basic binary tree (non-self-balancing).

    This tree does not enforce any ordering of values; insertion is performed
    in level order (breadth-first) so that the tree stays "complete" as values
    are added. For an ordered structure, subclass and override `insert`.
    """

    def __init__(self, root: Optional[BinaryTreeNode[T]] = None) -> None:
        self.root = root

    # ------------------------------------------------------------------ #
    # Basic properties
    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        """Return True if the tree has no nodes."""
        return self.root is None

    def size(self) -> int:
        """Return the total number of nodes in the tree."""
        return self._size_recursive(self.root)

    def _size_recursive(self, node: Optional[BinaryTreeNode[T]]) -> int:
        if node is None:
            return 0
        return 1 + self._size_recursive(node.left) + self._size_recursive(node.right)

    def height(self) -> int:
        """Return the height (number of edges on the longest root-to-leaf path).

        An empty tree has height -1; a single-node tree has height 0.
        """
        return self._height_recursive(self.root)

    def _height_recursive(self, node: Optional[BinaryTreeNode[T]]) -> int:
        if node is None:
            return -1
        return 1 + max(self._height_recursive(node.left), self._height_recursive(node.right))

    # ------------------------------------------------------------------ #
    # Insertion (level order / breadth-first)
    # ------------------------------------------------------------------ #
    def insert(self, value: T) -> BinaryTreeNode[T]:
        """Insert a value into the tree at the first available position.

        Uses a level-order (breadth-first) traversal to find the first node
        with a missing child and attaches the new node there.

        Returns:
            The newly created node.
        """
        new_node = BinaryTreeNode(value)
        if self.root is None:
            self.root = new_node
            return new_node

        queue: deque[BinaryTreeNode[T]] = deque([self.root])
        while queue:
            current = queue.popleft()
            if current.left is None:
                current.left = new_node
                return new_node
            if current.right is None:
                current.right = new_node
                return new_node
            queue.append(current.left)
            queue.append(current.right)

        # Unreachable for a valid tree, but keeps static analyzers happy.
        raise RuntimeError("Could not locate an insertion position")

    # ------------------------------------------------------------------ #
    # Traversals
    # ------------------------------------------------------------------ #
    def inorder(self) -> List[T]:
        """Return node values in inorder (left, node, right) order."""
        result: List[T] = []
        self._inorder_recursive(self.root, result)
        return result

    def _inorder_recursive(self, node: Optional[BinaryTreeNode[T]], out: List[T]) -> None:
        if node is None:
            return
        self._inorder_recursive(node.left, out)
        out.append(node.value)
        self._inorder_recursive(node.right, out)

    def preorder(self) -> List[T]:
        """Return node values in preorder (node, left, right) order."""
        result: List[T] = []
        self._preorder_recursive(self.root, result)
        return result

    def _preorder_recursive(self, node: Optional[BinaryTreeNode[T]], out: List[T]) -> None:
        if node is None:
            return
        out.append(node.value)
        self._preorder_recursive(node.left, out)
        self._preorder_recursive(node.right, out)

    def postorder(self) -> List[T]:
        """Return node values in postorder (left, right, node) order."""
        result: List[T] = []
        self._postorder_recursive(self.root, result)
        return result

    def _postorder_recursive(self, node: Optional[BinaryTreeNode[T]], out: List[T]) -> None:
        if node is None:
            return
        self._postorder_recursive(node.left, out)
        self._postorder_recursive(node.right, out)
        out.append(node.value)

    def level_order(self) -> List[T]:
        """Return node values in level-order (breadth-first) order."""
        if self.root is None:
            return []
        result: List[T] = []
        queue: deque[BinaryTreeNode[T]] = deque([self.root])
        while queue:
            current = queue.popleft()
            result.append(current.value)
            if current.left is not None:
                queue.append(current.left)
            if current.right is not None:
                queue.append(current.right)
        return result

    def __iter__(self) -> Iterator[T]:
        """Iterate over node values in level-order."""
        return iter(self.level_order())

    # ------------------------------------------------------------------ #
    # Searching
    # ------------------------------------------------------------------ #
    def contains(self, value: T) -> bool:
        """Return True if a node with the given value exists in the tree."""
        return self.find(value) is not None

    def find(self, value: T) -> Optional[BinaryTreeNode[T]]:
        """Return the first node whose value equals the given value, else None."""
        if self.root is None:
            return None
        queue: deque[BinaryTreeNode[T]] = deque([self.root])
        while queue:
            current = queue.popleft()
            if current.value == value:
                return current
            if current.left is not None:
                queue.append(current.left)
            if current.right is not None:
                queue.append(current.right)
        return None

    # ------------------------------------------------------------------ #
    # Deletion
    # ------------------------------------------------------------------ #
    def delete(self, value: T) -> bool:
        """Delete the first node with the given value from the tree.

        The node is replaced by the deepest, rightmost node in the tree to
        maintain a complete structure.

        Returns:
            True if a node was deleted, False otherwise.
        """
        if self.root is None:
            return False

        target = self.find(value)
        if target is None:
            return False

        # Locate the deepest, rightmost node and its parent.
        parent: Optional[BinaryTreeNode[T]] = None
        current: Optional[BinaryTreeNode[T]] = self.root
        queue: deque[tuple[Optional[BinaryTreeNode[T]], BinaryTreeNode[T]]] = deque(
            [(None, self.root)]
        )
        while queue:
            parent, current = queue.popleft()
            if current.left is not None:
                queue.append((current, current.left))
            if current.right is not None:
                queue.append((current, current.right))

        # `current` is the deepest rightmost node.
        assert current is not None
        target.value = current.value

        # Detach `current` from its parent.
        if parent is not None:
            if parent.left is current:
                parent.left = None
            elif parent.right is current:
                parent.right = None
        else:
            # The tree had only one node.
            self.root = None
        return True

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #
    def is_leaf(self, node: Optional[BinaryTreeNode[T]]) -> bool:
        """Return True if the node is a leaf (no children)."""
        return node is not None and node.left is None and node.right is None

    def leaves(self) -> List[T]:
        """Return the values of all leaf nodes in level order."""
        if self.root is None:
            return []
        result: List[T] = []
        queue: deque[BinaryTreeNode[T]] = deque([self.root])
        while queue:
            current = queue.popleft()
            if current.left is None and current.right is None:
                result.append(current.value)
            if current.left is not None:
                queue.append(current.left)
            if current.right is not None:
                queue.append(current.right)
        return result

    def to_list(self) -> List[T]:
        """Return the tree flattened into a list in level order."""
        return self.level_order()

    def map(self, func: Callable[[T], Any]) -> "BinaryTree[Any]":
        """Return a new tree with `func` applied to every node value."""
        if self.root is None:
            return BinaryTree()
        new_tree = BinaryTree(BinaryTreeNode(func(self.root.value)))
        queue: deque[tuple[BinaryTreeNode[T], BinaryTreeNode[Any]]] = deque(
            [(self.root, new_tree.root)]
        )
        while queue:
            old_node, new_node = queue.popleft()
            assert new_node is not None
            if old_node.left is not None:
                new_node.left = BinaryTreeNode(func(old_node.left.value))
                queue.append((old_node.left, new_node.left))
            if old_node.right is not None:
                new_node.right = BinaryTreeNode(func(old_node.right.value))
                queue.append((old_node.right, new_node.right))
        return new_tree

    def __repr__(self) -> str:
        return f"BinaryTree({self.level_order()!r})"


def build_tree(values: List[T]) -> BinaryTree[T]:
    """Build a binary tree from a list of values using level-order insertion."""
    tree = BinaryTree()
    for value in values:
        tree.insert(value)
    return tree


if __name__ == "__main__":
    # Simple demonstration.
    tree = build_tree([1, 2, 3, 4, 5, 6, 7])
    print("Tree:", tree)
    print("Size:", tree.size())
    print("Height:", tree.height())
    print("Inorder:", tree.inorder())
    print("Preorder:", tree.preorder())
    print("Postorder:", tree.postorder())
    print("Level-order:", tree.level_order())
    print("Contains 5:", tree.contains(5))
    print("Leaves:", tree.leaves())
    tree.delete(4)
    print("After deleting 4:", tree.level_order())
