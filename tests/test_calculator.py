"""Unit tests for the calculator module.

This test suite covers all arithmetic operations of the
:class:`~calculator.core.Calculator` class as well as the exception scenarios
(division by zero and square root of a negative number) and the history
recording behaviour.
"""

from __future__ import annotations

import unittest

from calculator import Calculator
from calculator.core import Number


class TestCalculator(unittest.TestCase):
    """Test cases for the Calculator class."""

    def setUp(self) -> None:
        """Create a fresh calculator instance for each test."""
        self.calc = Calculator()

    def test_add(self) -> None:
        """Addition should return the sum of two numbers."""
        self.assertEqual(self.calc.add(2, 3), 5)

    def test_add_negative(self) -> None:
        """Addition with negative numbers should work correctly."""
        self.assertEqual(self.calc.add(-2, 3), 1)

    def test_subtract(self) -> None:
        """Subtraction should return the difference of two numbers."""
        self.assertEqual(self.calc.subtract(10, 4), 6)

    def test_multiply(self) -> None:
        """Multiplication should return the product of two numbers."""
        self.assertEqual(self.calc.multiply(4, 5), 20)

    def test_divide(self) -> None:
        """Division should return the quotient of two numbers."""
        self.assertEqual(self.calc.divide(10, 4), 2.5)

    def test_divide_by_zero(self) -> None:
        """Division by zero should raise a ZeroDivisionError."""
        with self.assertRaises(ZeroDivisionError):
            self.calc.divide(10, 0)

    def test_power(self) -> None:
        """Power should return the base raised to the exponent."""
        self.assertEqual(self.calc.power(2, 10), 1024)

    def test_sqrt(self) -> None:
        """Square root should return the correct result for positive input."""
        self.assertEqual(self.calc.sqrt(16), 4.0)

    def test_sqrt_negative(self) -> None:
        """Square root of a negative number should raise a ValueError."""
        with self.assertRaises(ValueError):
            self.calc.sqrt(-9)

    def test_history_records_operation(self) -> None:
        """Performing an operation should record an entry in history."""
        self.calc.add(1, 2)
        entries = self.calc.history.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["operation"], "add")
        self.assertEqual(entries[0]["operands"], (1, 2))
        self.assertEqual(entries[0]["result"], 3)

    def test_history_multiple_records(self) -> None:
        """Multiple operations should append multiple history entries."""
        self.calc.add(1, 1)
        self.calc.multiply(2, 3)
        self.assertEqual(len(self.calc.history), 2)

    def test_history_clear(self) -> None:
        """Clearing the history should remove all entries."""
        self.calc.subtract(5, 1)
        self.calc.history.clear()
        self.assertEqual(len(self.calc.history), 0)


if __name__ == "__main__":
    unittest.main()
