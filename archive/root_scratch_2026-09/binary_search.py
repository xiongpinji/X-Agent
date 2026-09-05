"""Binary search implementation.

Provides iterative and recursive binary search functions that operate on
sorted sequences, returning the index of a target element or ``-1`` when the
element is not present.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def binary_search_iterative(seq: Sequence[T], target: T) -> int:
    """Return the index of ``target`` in the sorted ``seq`` via iteration.

    Args:
        seq: A non-empty, ascending-sorted sequence.
        target: The value to locate.

    Returns:
        The zero-based index of ``target`` if present, otherwise ``-1``.

    Complexity:
        Time: O(log n), Space: O(1).
    """
    low, high = 0, len(seq) - 1
    while low <= high:
        mid = (low + high) // 2
        if seq[mid] == target:
            return mid
        if seq[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


def binary_search_recursive(
    seq: Sequence[T], target: T, low: int = 0, high: int | None = None
) -> int:
    """Return the index of ``target`` in the sorted ``seq`` via recursion.

    Args:
        seq: A non-empty, ascending-sorted sequence.
        target: The value to locate.
        low: Lower bound of the search window (inclusive).
        high: Upper bound of the search window (inclusive); ``None`` means
            ``len(seq) - 1``.

    Returns:
        The zero-based index of ``target`` if present, otherwise ``-1``.

    Complexity:
        Time: O(log n), Space: O(log n) due to the call stack.
    """
    if high is None:
        high = len(seq) - 1

    if low > high:
        return -1

    mid = (low + high) // 2
    if seq[mid] == target:
        return mid
    if seq[mid] < target:
        return binary_search_recursive(seq, target, mid + 1, high)
    return binary_search_recursive(seq, target, low, mid - 1)


def lower_bound(seq: Sequence[T], target: T) -> int:
    """Return the first index where ``seq[index] >= target``.

    Args:
        seq: A non-empty, ascending-sorted sequence.
        target: The value to compare against.

    Returns:
        The index of the first element not less than ``target``, or
        ``len(seq)`` if every element is smaller.
    """
    low, high = 0, len(seq)
    while low < high:
        mid = (low + high) // 2
        if seq[mid] < target:
            low = mid + 1
        else:
            high = mid
    return low


def upper_bound(seq: Sequence[T], target: T) -> int:
    """Return the first index where ``seq[index] > target``.

    Args:
        seq: A non-empty, ascending-sorted sequence.
        target: The value to compare against.

    Returns:
        The index of the first element greater than ``target``, or
        ``len(seq)`` if every element is <= ``target``.
    """
    low, high = 0, len(seq)
    while low < high:
        mid = (low + high) // 2
        if seq[mid] <= target:
            low = mid + 1
        else:
            high = mid
    return low


def binary_search(seq: Sequence[T], target: T) -> int:
    """Public convenience wrapper around :func:`binary_search_iterative`.

    Args:
        seq: A non-empty, ascending-sorted sequence.
        target: The value to locate.

    Returns:
        The zero-based index of ``target`` if present, otherwise ``-1``.
    """
    return binary_search_iterative(seq, target)


__all__ = [
    "binary_search",
    "binary_search_iterative",
    "binary_search_recursive",
    "lower_bound",
    "upper_bound",
]
