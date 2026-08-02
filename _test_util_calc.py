"""Pytest tests for the utility calculation module."""

import pytest

from _util_calc import add, divide, multiply, subtract


def test_add():
    assert add(2, 3) == 5


def test_add_floats():
    assert add(1.5, 2.5) == 4.0


def test_subtract():
    assert subtract(5, 3) == 2


def test_subtract_negative():
    assert subtract(3, 5) == -2


def test_multiply():
    assert multiply(3, 4) == 12


def test_multiply_zero():
    assert multiply(0, 10) == 0


def test_divide():
    assert divide(10, 2) == 5.0


def test_divide_zero_raises():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
