"""Pytest tests for the add_numbers function in _test_fix_demo.py."""

from _test_fix_demo import add_numbers


def test_add_numbers_positive():
    assert add_numbers(2, 3) == 5


def test_add_numbers_negative():
    assert add_numbers(-1, -2) == -3


def test_add_numbers_mixed():
    assert add_numbers(-5, 10) == 5


def test_add_numbers_zero():
    assert add_numbers(0, 0) == 0


def test_add_numbers_float():
    assert add_numbers(1.5, 2.5) == 4.0
