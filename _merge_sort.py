"""Merge sort implementation.

Provides a stable divide-and-conquer sorting algorithm with O(n log n)
worst-case time complexity.

Public API:
    - ``merge_sort``: returns a new sorted list, leaving the input untouched.
    - ``merge_sort_in_place``: sorts a list in place, mutating the input.
"""

from typing import Any, List, Optional, Callable


def _less(a: Any, b: Any, key: Optional[Callable[[Any], Any]]) -> bool:
    """Return ``True`` if ``a`` should come before ``b``.

    When ``key`` is provided, comparisons are performed on ``key(a)`` and
    ``key(b)`` instead of the raw items. Strict inequality keeps the sort
    stable (equal elements retain their original relative order).
    """
    if key is not None:
        return key(a) < key(b)
    return a < b


def merge(left: List[Any], right: List[Any],
          key: Optional[Callable[[Any], Any]] = None) -> List[Any]:
    """Merge two already-sorted sequences into a single sorted list."""
    result: List[Any] = []
    i = j = 0
    while i < len(left) and j < len(right):
        if _less(left[i], right[j], key):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def _merge_sort_rec(items: List[Any],
                    key: Optional[Callable[[Any], Any]]) -> List[Any]:
    """Recursive divide-and-conquer core of the merge sort."""
    n = len(items)
    if n <= 1:
        return items[:]
    mid = n // 2
    left = _merge_sort_rec(items[:mid], key)
    right = _merge_sort_rec(items[mid:], key)
    return merge(left, right, key)


def merge_sort(items: List[Any],
               key: Optional[Callable[[Any], Any]] = None,
               reverse: bool = False) -> List[Any]:
    """Return a new list with the elements of ``items`` sorted ascending.

    The input sequence is never mutated. Provide ``key`` to sort by a
    computed attribute, and ``reverse=True`` for descending order.
    """
    result = _merge_sort_rec(list(items), key)
    if reverse:
        result.reverse()
    return result


def merge_sort_in_place(items: List[Any],
                        key: Optional[Callable[[Any], Any]] = None,
                        reverse: bool = False) -> None:
    """Sort ``items`` in place, mutating the input list.

    Returns ``None``; the sorted result is written back into ``items``.
    """
    sorted_items = merge_sort(items, key=key, reverse=reverse)
    items[:] = sorted_items
