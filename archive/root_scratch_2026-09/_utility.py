"""Utility functions module.

This module provides a small collection of reusable, well-typed utility
functions that can be imported by other parts of the codebase.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, TypeVar

T = TypeVar("T")


def add(a: float, b: float) -> float:
    """Return the sum of two numbers.

    Args:
        a: The first addend.
        b: The second addend.

    Returns:
        The sum ``a + b``.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of two numbers.

    Args:
        a: The minuend.
        b: The subtrahend.

    Returns:
        The difference ``a - b``.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers.

    Args:
        a: The first factor.
        b: The second factor.

    Returns:
        The product ``a * b``.
    """
    return a * b


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp ``value`` to lie within the inclusive ``[minimum, maximum]`` range.

    Args:
        value: The value to clamp.
        minimum: The lower bound.
        maximum: The upper bound.

    Returns:
        ``minimum`` if ``value < minimum``, ``maximum`` if
        ``value > maximum``, otherwise ``value``.
    """
    if minimum > maximum:
        raise ValueError("minimum must not be greater than maximum")
    return max(minimum, min(value, maximum))


def first_or_none(items: Iterable[T]) -> Optional[T]:
    """Return the first element of an iterable, or ``None`` if empty.

    Args:
        items: An iterable of items.

    Returns:
        The first element, or ``None`` if the iterable is empty.
    """
    for item in items:
        return item
    return None


def unique(items: Iterable[T]) -> List[T]:
    """Return the unique elements of an iterable, preserving first-seen order.

    Args:
        items: An iterable of possibly duplicate items.

    Returns:
        A list containing each element exactly once, in first-seen order.
    """
    seen: set = set()
    result: List[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
