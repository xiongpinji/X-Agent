"""Calculator core module.

This module provides the :class:`Calculator` class, which implements basic
arithmetic operations such as addition, subtraction, multiplication, division,
power, and square root. Division handles division by zero and square root
handles negative inputs by raising appropriate exceptions.
"""

from __future__ import annotations

import math
from typing import Union

from .history import History

Number = Union[int, float]


class Calculator:
    """A simple calculator supporting basic arithmetic operations.

    The calculator records every operation performed in a :class:`History`
    instance, storing the operation name, operands, result, and timestamp.

    Attributes:
        history: The history of all operations performed by this calculator.
    """

    def __init__(self) -> None:
        """Initialize a new calculator with an empty history."""
        self.history = History()

    def add(self, a: Number, b: Number) -> Number:
        """Return the sum of ``a`` and ``b``.

        Args:
            a: The first operand.
            b: The second operand.

        Returns:
            The sum of ``a`` and ``b``.
        """
        result = a + b
        self.history.record("add", (a, b), result)
        return result

    def subtract(self, a: Number, b: Number) -> Number:
        """Return the difference ``a - b``.

        Args:
            a: The first operand.
            b: The second operand.

        Returns:
            The difference between ``a`` and ``b``.
        """
        result = a - b
        self.history.record("subtract", (a, b), result)
        return result

    def multiply(self, a: Number, b: Number) -> Number:
        """Return the product of ``a`` and ``b``.

        Args:
            a: The first operand.
            b: The second operand.

        Returns:
            The product of ``a`` and ``b``.
        """
        result = a * b
        self.history.record("multiply", (a, b), result)
        return result

    def divide(self, a: Number, b: Number) -> Number:
        """Return the quotient ``a / b``.

        Args:
            a: The dividend.
            b: The divisor.

        Returns:
            The quotient of ``a`` divided by ``b``.

        Raises:
            ZeroDivisionError: If ``b`` is zero.
        """
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero.")
        result = a / b
        self.history.record("divide", (a, b), result)
        return result

    def power(self, a: Number, b: Number) -> Number:
        """Return ``a`` raised to the power of ``b``.

        Args:
            a: The base.
            b: The exponent.

        Returns:
            The value of ``a ** b``.
        """
        result = a ** b
        self.history.record("power", (a, b), result)
        return result

    def sqrt(self, a: Number) -> Number:
        """Return the square root of ``a``.

        Args:
            a: The number whose square root is computed.

        Returns:
            The square root of ``a``.

        Raises:
            ValueError: If ``a`` is negative.
        """
        if a < 0:
            raise ValueError("Cannot compute the square root of a negative number.")
        result = math.sqrt(a)
        self.history.record("sqrt", (a,), result)
        return result
