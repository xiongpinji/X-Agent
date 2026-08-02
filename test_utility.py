"""Unit tests for the project's utility modules.

This module contains comprehensive unit tests covering the utility functions
defined in ``_util_calc.py``, ``_utility.py``, ``_sorting_algorithm.py``,
and related helper modules. The tests are written using the standard library's
``unittest`` framework so that they can be run with either ``pytest`` or the
built-in ``python -m unittest`` runner.
"""

from __future__ import annotations

import math
import unittest
from typing import Any, Callable, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
try:
    from _util_calc import add, subtract, multiply, divide, modulo, power
    from _utility import clamp, is_even, is_odd, factorial, gcd, lcm
    from _sorting_algorithm import (
        bubble_sort,
        insertion_sort,
        merge_sort,
        quick_sort,
        selection_sort,
    )
except ImportError:  # pragma: no cover - fallback for isolated runs
    add = subtract = multiply = divide = modulo = power = None  # type: ignore
    clamp = is_even = is_odd = factorial = gcd = lcm = None  # type: ignore
    bubble_sort = insertion_sort = merge_sort = quick_sort = selection_sort = None  # type: ignore


# ---------------------------------------------------------------------------
# Arithmetic helpers
# ---------------------------------------------------------------------------
class TestArithmetic(unittest.TestCase):
    """Unit tests for basic arithmetic helper functions."""

    def test_add(self) -> None:
        """Test that add() returns the sum of its two operands."""
        if add is None:
            self.skipTest("_util_calc.add not available")
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(1.5, 2.25), 3.75)

    def test_subtract(self) -> None:
        """Test that subtract() returns the difference of its operands."""
        if subtract is None:
            self.skipTest("_util_calc.subtract not available")
        self.assertEqual(subtract(10, 4), 6)
        self.assertEqual(subtract(0, 5), -5)
        self.assertEqual(subtract(3.5, 1.25), 2.25)

    def test_multiply(self) -> None:
        """Test that multiply() returns the product of its operands."""
        if multiply is None:
            self.skipTest("_util_calc.multiply not available")
        self.assertEqual(multiply(3, 4), 12)
        self.assertEqual(multiply(-2, 5), -10)
        self.assertEqual(multiply(0, 99), 0)
        self.assertEqual(multiply(1.5, 2.0), 3.0)

    def test_divide(self) -> None:
        """Test that divide() returns the quotient of its operands."""
        if divide is None:
            self.skipTest("_util_calc.divide not available")
        self.assertEqual(divide(10, 2), 5)
        self.assertAlmostEqual(divide(7, 2), 3.5)
        self.assertEqual(divide(-8, 4), -2)

    def test_divide_by_zero_raises(self) -> None:
        """Test that divide() raises ZeroDivisionError on a zero divisor."""
        if divide is None:
            self.skipTest("_util_calc.divide not available")
        with self.assertRaises(ZeroDivisionError):
            divide(1, 0)

    def test_modulo(self) -> None:
        """Test that modulo() returns the remainder of integer division."""
        if modulo is None:
            self.skipTest("_util_calc.modulo not available")
        self.assertEqual(modulo(10, 3), 1)
        self.assertEqual(modulo(16, 4), 0)
        self.assertEqual(modulo(-5, 2), 1)

    def test_power(self) -> None:
        """Test that power() returns base raised to the exponent."""
        if power is None:
            self.skipTest("_util_calc.power not available")
        self.assertEqual(power(2, 3), 8)
        self.assertEqual(power(5, 0), 1)
        self.assertEqual(power(2, -1), 0.5)


# ---------------------------------------------------------------------------
# Numeric utilities
# ---------------------------------------------------------------------------
class TestNumericUtilities(unittest.TestCase):
    """Unit tests for numeric utility helpers."""

    def test_clamp_within_range(self) -> None:
        """Test that clamp() returns the value when it is within bounds."""
        if clamp is None:
            self.skipTest("_utility.clamp not available")
        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)

    def test_clamp_below_range(self) -> None:
        """Test that clamp() returns the lower bound when value is too small."""
        if clamp is None:
            self.skipTest("_utility.clamp not available")
        self.assertEqual(clamp(-3, 0, 10), 0)
        self.assertEqual(clamp(-100, -5, 5), -5)

    def test_clamp_above_range(self) -> None:
        """Test that clamp() returns the upper bound when value is too large."""
        if clamp is None:
            self.skipTest("_utility.clamp not available")
        self.assertEqual(clamp(15, 0, 10), 10)
        self.assertEqual(clamp(100, -5, 5), 5)

    def test_is_even(self) -> None:
        """Test that is_even() returns True for even numbers."""
        if is_even is None:
            self.skipTest("_utility.is_even not available")
        self.assertTrue(is_even(0))
        self.assertTrue(is_even(2))
        self.assertTrue(is_even(-4))

    def test_is_even_odd_input(self) -> None:
        """Test that is_even() returns False for odd numbers."""
        if is_even is None:
            self.skipTest("_utility.is_even not available")
        self.assertFalse(is_even(1))
        self.assertFalse(is_even(3))
        self.assertFalse(is_even(-5))

    def test_is_odd(self) -> None:
        """Test that is_odd() returns True for odd numbers."""
        if is_odd is None:
            self.skipTest("_utility.is_odd not available")
        self.assertTrue(is_odd(1))
        self.assertTrue(is_odd(7))
        self.assertTrue(is_odd(-3))

    def test_is_odd_even_input(self) -> None:
        """Test that is_odd() returns False for even numbers."""
        if is_odd is None:
            self.skipTest("_utility.is_odd not available")
        self.assertFalse(is_odd(0))
        self.assertFalse(is_odd(2))
        self.assertFalse(is_odd(-6))

    def test_factorial(self) -> None:
        """Test that factorial() returns the factorial of a non-negative int."""
        if factorial is None:
            self.skipTest("_utility.factorial not available")
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative_raises(self) -> None:
        """Test that factorial() raises ValueError for negative input."""
        if factorial is None:
            self.skipTest("_utility.factorial not available")
        with self.assertRaises(ValueError):
            factorial(-1)

    def test_gcd(self) -> None:
        """Test that gcd() returns the greatest common divisor."""
        if gcd is None:
            self.skipTest("_utility.gcd not available")
        self.assertEqual(gcd(12, 8), 4)
        self.assertEqual(gcd(17, 13), 1)
        self.assertEqual(gcd(0, 5), 5)
        self.assertEqual(gcd(48, 18), 6)

    def test_lcm(self) -> None:
        """Test that lcm() returns the least common multiple."""
        if lcm is None:
            self.skipTest("_utility.lcm not available")
        self.assertEqual(lcm(4, 6), 12)
        self.assertEqual(lcm(3, 5), 15)
        self.assertEqual(lcm(0, 5), 0)


# ---------------------------------------------------------------------------
# Sorting algorithms
# ---------------------------------------------------------------------------
def _assert_sorted(result: Sequence[Any], original: Sequence[Any]) -> None:
    """Assert that ``result`` is a sorted permutation of ``original``."""
    if len(result) != len(original):
        raise AssertionError("length mismatch between result and original")
    if sorted(result) != sorted(original):
        raise AssertionError("result is not a permutation of original")
    for prev, nxt in zip(result, result[1:]):
        if prev > nxt:
            raise AssertionError(f"result not sorted: {prev} > {nxt}")


class TestSortingAlgorithms(unittest.TestCase):
    """Unit tests for the sorting algorithm implementations."""

    _UNSORTED = [5, 2, 9, 1, 5, 6]
    _SORTED = [1, 2, 5, 5, 6, 9]
    _EMPTY: List[int] = []
    _SINGLETON = [42]
    _NEGATIVES = [3, -1, 0, -7, 2]

    def _check_sort(self, sort_func: Callable[[Sequence[Any]], List[Any]]) -> None:
        """Run a battery of assertions against a given sort function."""
        self.assertEqual(sort_func(self._UNSORTED), self._SORTED)
        self.assertEqual(sort_func(self._EMPTY), [])
        self.assertEqual(sort_func(self._SINGLETON), [42])
        self.assertEqual(sort_func(self._NEGATIVES), sorted(self._NEGATIVES))
        # Verify stability/permutation without mutating the input list.
        _assert_sorted(sort_func(list(self._UNSORTED)), self._UNSORTED)

    def test_bubble_sort(self) -> None:
        """Test bubble_sort() against a variety of inputs."""
        if bubble_sort is None:
            self.skipTest("_sorting_algorithm.bubble_sort not available")
        self._check_sort(bubble_sort)

    def test_insertion_sort(self) -> None:
        """Test insertion_sort() against a variety of inputs."""
        if insertion_sort is None:
            self.skipTest("_sorting_algorithm.insertion_sort not available")
        self._check_sort(insertion_sort)

    def test_selection_sort(self) -> None:
        """Test selection_sort() against a variety of inputs."""
        if selection_sort is None:
            self.skipTest("_sorting_algorithm.selection_sort not available")
        self._check_sort(selection_sort)

    def test_merge_sort(self) -> None:
        """Test merge_sort() against a variety of inputs."""
        if merge_sort is None:
            self.skipTest("_sorting_algorithm.merge_sort not available")
        self._check_sort(merge_sort)

    def test_quick_sort(self) -> None:
        """Test quick_sort() against a variety of inputs."""
        if quick_sort is None:
            self.skipTest("_sorting_algorithm.quick_sort not available")
        self._check_sort(quick_sort)

    def test_do_not_mutate_input(self) -> None:
        """Test that sort functions do not mutate the input list in place."""
        for sort_func in (bubble_sort, insertion_sort, selection_sort,
                          merge_sort, quick_sort):
            if sort_func is None:
                continue
            original = list(self._UNSORTED)
            sort_func(original)
            self.assertEqual(original, self._UNSORTED,
                             f"{sort_func.__name__} mutated its input")


if __name__ == "__main__":
    unittest.main(verbosity=2)
