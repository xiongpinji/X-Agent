"""Tests for the fibonacci module."""

import pytest

from fibonacci import fibonacci, fibonacci_generator, fibonacci_sequence


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 3),
        (5, 5),
        (6, 8),
        (7, 13),
        (10, 55),
        (20, 6765),
    ],
)
def test_fibonacci_values(n, expected):
    assert fibonacci(n) == expected


def test_fibonacci_negative_raises():
    with pytest.raises(ValueError):
        fibonacci(-1)


def test_fibonacci_non_integer_raises():
    with pytest.raises(TypeError):
        fibonacci(3.5)
    with pytest.raises(TypeError):
        fibonacci("5")


def test_fibonacci_sequence():
    assert fibonacci_sequence(7) == [0, 1, 1, 2, 3, 5, 8, 13]
    assert fibonacci_sequence(0) == [0]


def test_fibonacci_sequence_negative_raises():
    with pytest.raises(ValueError):
        fibonacci_sequence(-3)


def test_fibonacci_generator():
    gen = fibonacci_generator()
    first_eight = [next(gen) for _ in range(8)]
    assert first_eight == [0, 1, 1, 2, 3, 5, 8, 13]
