"""Utility calculation functions.

This module provides a small set of pure, side-effect-free utility
functions for common arithmetic operations. Each function accepts
numeric arguments and returns a numeric result.
"""

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Return the sum of ``a`` and ``b``.

    Args:
        a: First addend.
        b: Second addend.

    Returns:
        The arithmetic sum ``a + b``.

    Raises:
        TypeError: If either argument is not a number.
    """
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Return the difference of ``a`` minus ``b``.

    Args:
        a: The minuend.
        b: The subtrahend.

    Returns:
        The arithmetic difference ``a - b``.

    Raises:
        TypeError: If either argument is not a number.
    """
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Return the product of ``a`` and ``b``.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        The arithmetic product ``a * b``.

    Raises:
        TypeError: If either argument is not a number.
    """
    return a * b


def divide(a: Number, b: Number) -> float:
    """Return the quotient of ``a`` divided by ``b``.

    Args:
        a: The dividend.
        b: The divisor.

    Returns:
        The arithmetic quotient ``a / b`` as a float.

    Raises:
        ZeroDivisionError: If ``b`` is zero.
        TypeError: If either argument is not a number.
    """
    return a / b
