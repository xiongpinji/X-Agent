"""A small sort utility module.

Provides two functions:

* :func:`sort_items` -- returns a new sorted list without mutating the input.
* :func:`sort_in_place` -- sorts the given list in place and returns it.

Both functions support the standard ``reverse`` and ``key`` keyword arguments
that mirror Python's built-in :func:`sorted` / :meth:`list.sort`.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, TypeVar

T = TypeVar("T")


def sort_items(
    items: Sequence[T],
    *,
    key: Optional[Callable[[T], object]] = None,
    reverse: bool = False,
) -> List[T]:
    """Return a new list with ``items`` sorted.

    The original sequence is left untouched.

    Args:
        items: The sequence of items to sort.
        key: Optional function used to extract a comparison key from each item.
        reverse: If True, sort in descending order.

    Returns:
        A new list containing the sorted items.
    """
    return sorted(items, key=key, reverse=reverse)


def sort_in_place(
    items: List[T],
    *,
    key: Optional[Callable[[T], object]] = None,
    reverse: bool = False,
) -> List[T]:
    """Sort ``items`` in place and return the same list object.

    Args:
        items: The list to sort. It is mutated in place.
        key: Optional function used to extract a comparison key from each item.
        reverse: If True, sort in descending order.

    Returns:
        The same list instance that was passed in, now sorted.
    """
    items.sort(key=key, reverse=reverse)
    return items
