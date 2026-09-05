"""Quicksort implementation module.

Provides a classic in-place quicksort using the Hoare partition scheme
with a median-of-three pivot selection to avoid worst-case behavior on
already-sorted input.
"""

from __future__ import annotations

from typing import List, MutableSequence, Optional, Sequence, TypeVar

T = TypeVar("T")


def _median_of_three(a: T, b: T, c: T) -> T:
    """Return the median of three comparable values."""
    if a < b:
        if b < c:
            return b
        return c if a < c else a
    if a < c:
        return a
    return b if b < c else c


def _partition(items: MutableSequence[T], low: int, high: int) -> int:
    """Partition ``items[low:high+1]`` in place using Hoare's scheme.

    Returns the final index of the pivot element.
    """
    mid = (low + high) // 2
    pivot = _median_of_three(items[low], items[mid], items[high])

    left = low - 1
    right = high + 1
    while True:
        left += 1
        while items[left] < pivot:
            left += 1
        right -= 1
        while items[right] > pivot:
            right -= 1
        if left >= right:
            return right
        items[left], items[right] = items[right], items[left]


def _quicksort(items: MutableSequence[T], low: int, high: int) -> None:
    """Recursively sort ``items[low:high+1]`` in place."""
    if low < high:
        partition_index = _partition(items, low, high)
        _quicksort(items, low, partition_index)
        _quicksort(items, partition_index + 1, high)


def quicksort(items: Sequence[T]) -> List[T]:
    """Return a new list containing the elements of ``items`` sorted ascending.

    The input sequence is not modified.

    Args:
        items: A sequence of comparable values.

    Returns:
        A new list with ``items`` sorted in ascending order.

    Examples:
        >>> quicksort([3, 1, 2])
        [1, 2, 3]
        >>> quicksort([])
        []
        >>> quicksort([5])
        [5]
    """
    result = list(items)
    if len(result) > 1:
        _quicksort(result, 0, len(result) - 1)
    return result
