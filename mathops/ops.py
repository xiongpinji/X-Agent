"""Basic arithmetic operations for the mathops module."""

from __future__ import annotations

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Return the sum of ``a`` and ``b``.

    Parameters
    ----------
    a : int or float
        The first operand.
    b : int or float
        The second operand.

    Returns
    -------
    int or float
        The result of ``a + b``.
    """
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Return the difference of ``a`` and ``b``.

    Parameters
    ----------
    a : int or float
        The first operand.
    b : int or float
        The second operand.

    Returns
    -------
    int or float
        The result of ``a - b``.
    """
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Return the product of ``a`` and ``b``.

    Parameters
    ----------
    a : int or float
        The first operand.
    b : int or float
        The second operand.

    Returns
    -------
    int or float
        The result of ``a * b``.
    """
    return a * b


def divide(a: Number, b: Number) -> float:
    """Return the quotient of ``a`` divided by ``b``.

    Parameters
    ----------
    a : int or float
        The dividend.
    b : int or float
        The divisor.

    Returns
    -------
    float
        The result of ``a / b``.

    Raises
    ------
    ZeroDivisionError
        If ``b`` is zero.
    """
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b
