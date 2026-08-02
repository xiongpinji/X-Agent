"""Graph traversal algorithms.

This module provides implementations of common graph traversal algorithms:
- Breadth-First Search (BFS) using an iterative queue-based approach.
- Depth-First Search (DFS) using both recursive and iterative approaches.
- Path finding between two nodes.

The graph is represented as an adjacency list: a mapping from a node to an
iterable of its neighbours. Nodes may be any hashable type.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any, Hashable, Optional

Node = Hashable


def bfs_traverse(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
) -> list[Node]:
    """Traverse a graph in breadth-first order starting from ``start``.

    BFS visits all nodes at the present depth before moving on to nodes at
    the next depth level. It uses a queue to track nodes that are yet to be
    explored and a set to avoid revisiting nodes.

    Args:
        graph: The graph as an adjacency list.
        start: The node from which to begin the traversal.

    Returns:
        A list of nodes in the order they were visited.

    Raises:
        KeyError: If ``start`` is not a key present in ``graph``.
    """
    if start not in graph:
        raise KeyError(f"start node {start!r} is not present in the graph")

    visited: set[Node] = set()
    order: list[Node] = []
    queue: deque[Node] = deque([start])

    visited.add(start)

    while queue:
        node = queue.popleft()
        order.append(node)

        for neighbour in graph.get(node, ()):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

    return order


def dfs_traverse_recursive(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
) -> list[Node]:
    """Traverse a graph in depth-first order using recursion.

    DFS explores as far as possible along each branch before backtracking.

    Args:
        graph: The graph as an adjacency list.
        start: The node from which to begin the traversal.

    Returns:
        A list of nodes in the order they were visited.

    Raises:
        KeyError: If ``start`` is not a key present in ``graph``.
    """
    if start not in graph:
        raise KeyError(f"start node {start!r} is not present in the graph")

    visited: set[Node] = set()
    order: list[Node] = []

    def _visit(node: Node) -> None:
        visited.add(node)
        order.append(node)
        for neighbour in graph.get(node, ()):
            if neighbour not in visited:
                _visit(neighbour)

    _visit(start)
    return order


def dfs_traverse_iterative(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
) -> list[Node]:
    """Traverse a graph in depth-first order using an explicit stack.

    This is the iterative equivalent of :func:`dfs_traverse_recursive`,
    avoiding Python's recursion limit for deep graphs.

    Args:
        graph: The graph as an adjacency list.
        start: The node from which to begin the traversal.

    Returns:
        A list of nodes in the order they were visited.

    Raises:
        KeyError: If ``start`` is not a key present in ``graph``.
    """
    if start not in graph:
        raise KeyError(f"start node {start!r} is not present in the graph")

    visited: set[Node] = set()
    order: list[Node] = []
    stack: list[Node] = [start]

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)

        # Push neighbours in reverse order so that the first neighbour is
        # processed first, matching the recursive DFS ordering.
        for neighbour in reversed(list(graph.get(node, ()))):
            if neighbour not in visited:
                stack.append(neighbour)

    return order


def dfs_traverse(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
    *,
    recursive: bool = False,
) -> list[Node]:
    """Convenience wrapper for depth-first traversal.

    Args:
        graph: The graph as an adjacency list.
        start: The node from which to begin the traversal.
        recursive: If ``True`` use the recursive implementation, otherwise
            use the iterative stack-based implementation.

    Returns:
        A list of nodes in the order they were visited.
    """
    if recursive:
        return dfs_traverse_recursive(graph, start)
    return dfs_traverse_iterative(graph, start)


def find_path(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
    goal: Node,
) -> Optional[list[Node]]:
    """Find a path from ``start`` to ``goal`` using BFS.

    BFS guarantees the returned path is one of the shortest paths (in terms
    of the number of edges) when the graph is unweighted.

    Args:
        graph: The graph as an adjacency list.
        start: The starting node.
        goal: The target node.

    Returns:
        A list of nodes forming a path from ``start`` to ``goal``, or ``None``
        if ``goal`` is unreachable from ``start`` / does not exist.
    """
    if start not in graph:
        raise KeyError(f"start node {start!r} is not present in the graph")

    # parent[node] = the node from which ``node`` was first discovered.
    parent: dict[Node, Optional[Node]] = {start: None}
    queue: deque[Node] = deque([start])

    while queue:
        node = queue.popleft()
        if node == goal:
            # Reconstruct the path by walking back through parents.
            path: list[Node] = []
            current: Optional[Node] = node
            while current is not None:
                path.append(current)
                current = parent[current]
            path.reverse()
            return path

        for neighbour in graph.get(node, ()):
            if neighbour not in parent:
                parent[neighbour] = node
                queue.append(neighbour)

    return None


def shortest_path_length(
    graph: Mapping[Node, Iterable[Node]],
    start: Node,
    goal: Node,
) -> Optional[int]:
    """Return the number of edges on the shortest path between two nodes.

    Args:
        graph: The graph as an adjacency list.
        start: The starting node.
        goal: The target node.

    Returns:
        The minimum number of edges between ``start`` and ``goal``, or ``None``
        if ``goal`` is unreachable.
    """
    path = find_path(graph, start, goal)
    if path is None:
        return None
    # Number of edges equals the number of nodes minus one.
    return len(path) - 1


def connected_components(
    graph: Mapping[Node, Iterable[Node]],
) -> list[list[Node]]:
    """Return the connected components of an undirected graph.

    Nodes are grouped into components such that every node in a component is
    reachable from every other node in the same component.

    Args:
        graph: The graph as an adjacency list.

    Returns:
        A list of components, where each component is a list of nodes.
    """
    visited: set[Node] = set()
    components: list[list[Node]] = []

    for node in graph:
        if node in visited:
            continue
        component = bfs_traverse(graph, node)
        visited.update(component)
        components.append(component)

    return components
