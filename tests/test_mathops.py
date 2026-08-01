"""Pytest test suite for the mathops.ops module."""

import pytest

from mathops.ops import add, divide, multiply, subtract


def test_add() -> None:
    """Test that add returns the correct sum."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
    assert add(2.5, 1.5) == 4.0


def test_subtract() -> None:
    """Test that subtract returns the correct difference."""
    assert subtract(5, 3) == 2
    assert subtract(3, 5) == -2
    assert subtract(0, 0) == 0
    assert subtract(5.5, 2.5) == 3.0


def test_multiply() -> None:
    """Test that multiply returns the correct product."""
    assert multiply(2, 3) == 6
    assert multiply(-2, 3) == -6
    assert multiply(0, 5) == 0
    assert multiply(2.5, 2) == 5.0


def test_divide() -> None:
    """Test that divide returns the correct quotient."""
    assert divide(6, 3) == 2
    assert divide(5, 2) == 2.5
    assert divide(-6, 3) == -2
    assert divide(1, 4) == 0.25


def test_divide_by_zero() -> None:
    """Test that divide raises ZeroDivisionError when dividing by zero."""
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
