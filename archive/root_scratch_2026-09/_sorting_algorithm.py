"""A comprehensive sorting algorithm module.

This module provides implementations of several classic sorting algorithms,
each with type annotations, docstrings, and support for custom key functions
and reverse ordering.

Algorithms included:
    - quicksort
    - mergesort
    - heapsort
    - insertion_sort
    - bubble_sort
    - selection_sort
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, TypeVar

T = TypeVar("T")


def _make_key(
    key: Optional[Callable[[Any], Any]], reverse: bool
) -> Callable[[Any], Any]:
    """Build a comparison key wrapper honoring the reverse flag.

    Args:
        key: Optional user-supplied key function.
        reverse: If True, negate the comparison result.

    Returns:
        A key function suitable for use in sorting.
    """
    base = key if key is not None else (lambda x: x)

    if reverse:
        return lambda x: -base(x)
    return base


def quicksort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the quicksort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n log n) average, O(n^2) worst case.
    Space complexity: O(log n) average for the recursion stack.
    """
    values = list(items)
    if len(values) <= 1:
        return values

    compare = _make_key(key, reverse)

    pivot = values[len(values) // 2]
    pivot_key = compare(pivot)

    less: List[Any] = []
    equal: List[Any] = []
    greater: List[Any] = []

    for item in values:
        item_key = compare(item)
        if item_key < pivot_key:
            less.append(item)
        elif item_key > pivot_key:
            greater.append(item)
        else:
            equal.append(item)

    return (
        quicksort(less, key=key, reverse=reverse)
        + equal
        + quicksort(greater, key=key, reverse=reverse)
    )


def mergesort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the mergesort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n log n) in all cases.
    Space complexity: O(n) for the auxiliary arrays.
    """
    values = list(items)
    if len(values) <= 1:
        return values

    compare = _make_key(key, reverse)
    mid = len(values) // 2

    left = mergesort(values[:mid], key=key, reverse=reverse)
    right = mergesort(values[mid:], key=key, reverse=reverse)

    return _merge(left, right, compare)


def _merge(left: List[Any], right: List[Any], compare: Callable[[Any], Any]) -> List[Any]:
    """Merge two sorted lists into a single sorted list.

    Args:
        left: First sorted list.
        right: Second sorted list.
        compare: Key function used for ordering.

    Returns:
        A merged, sorted list.
    """
    result: List[Any] = []
    i = j = 0

    while i < len(left) and j < len(right):
        if compare(left[i]) <= compare(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


def heapsort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the heapsort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n log n) in all cases.
    Space complexity: O(1) auxiliary (in-place on a copy).
    """
    values = list(items)
    compare = _make_key(key, reverse)
    n = len(values)

    def _sift_down(start: int, end: int) -> None:
        """Restore the heap property for the subtree rooted at 'start'."""
        root = start
        while True:
            child = 2 * root + 1
            if child > end:
                break
            if child + 1 <= end and compare(values[child]) < compare(values[child + 1]):
                child += 1
            if compare(values[root]) < compare(values[child]):
                values[root], values[child] = values[child], values[root]
                root = child
            else:
                break

    # Build max heap.
    for start in range(n // 2 - 1, -1, -1):
        _sift_down(start, n - 1)

    # Extract elements one by one.
    for end in range(n - 1, 0, -1):
        values[end], values[0] = values[0], values[end]
        _sift_down(0, end - 1)

    return values


def insertion_sort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the insertion sort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n^2) average/worst, O(n) best (already sorted).
    Space complexity: O(1) auxiliary.
    """
    values = list(items)
    compare = _make_key(key, reverse)

    for i in range(1, len(values)):
        current = values[i]
        current_key = compare(current)
        j = i - 1
        while j >= 0 and compare(values[j]) > current_key:
            values[j + 1] = values[j]
            j -= 1
        values[j + 1] = current

    return values


def bubble_sort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the bubble sort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n^2) average/worst, O(n) best (already sorted).
    Space complexity: O(1) auxiliary.
    """
    values = list(items)
    compare = _make_key(key, reverse)
    n = len(values)

    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if compare(values[j]) > compare(values[j + 1]):
                values[j], values[j + 1] = values[j + 1], values[j]
                swapped = True
        if not swapped:
            break

    return values


def selection_sort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> List[Any]:
    """Sort a sequence using the selection sort algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.

    Time complexity: O(n^2) in all cases.
    Space complexity: O(1) auxiliary.
    """
    values = list(items)
    compare = _make_key(key, reverse)
    n = len(values)

    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            if compare(values[j]) < compare(values[min_idx]):
                min_idx = j
        if min_idx != i:
            values[i], values[min_idx] = values[min_idx], values[i]

    return values


# Convenience alias for the default sort to use.
def sort(
    items: Sequence[Any],
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
    algorithm: str = "quicksort",
) -> List[Any]:
    """Sort a sequence using a selectable algorithm.

    Args:
        items: The sequence of items to sort.
        key: Optional key function used to extract a comparison key.
        reverse: If True, sort in descending order.
        algorithm: One of "quicksort", "mergesort", "heapsort",
            "insertion_sort", "bubble_sort", or "selection_sort".

    Returns:
        A new list containing the sorted items.

    Raises:
        ValueError: If an unknown algorithm name is provided.
    """
    strategies = {
        "quicksort": quicksort,
        "mergesort": mergesort,
        "heapsort": heapsort,
        "insertion_sort": insertion_sort,
        "bubble_sort": bubble_sort,
        "selection_sort": selection_sort,
    }

    if algorithm not in strategies:
        raise ValueError(
            f"Unknown algorithm {algorithm!r}. "
            f"Choose from {sorted(strategies)}"
        )

    return strategies[algorithm](items, key=key, reverse=reverse)
