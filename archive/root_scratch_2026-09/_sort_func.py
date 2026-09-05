"""A simple sorting function module.

Provides a public ``sort`` function that works on any sequence of
comparable items by delegating to the built-in ``sorted``.
"""

from typing import List, Sequence, TypeVar

T = TypeVar("T")


def sort(items: Sequence[T]) -> List[T]:
    """Return a new list containing ``items`` sorted in ascending order.

    The input sequence is left unmodified.

    Args:
        items: A sequence of comparable items (e.g. numbers or strings).

    Returns:
        A new list with all elements of ``items`` sorted ascending.

    Raises:
        TypeError: If the items are not mutually comparable.
    """
    return sorted(items)
