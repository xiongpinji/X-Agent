"""Fibonacci sequence utility functions."""

from functools import lru_cache
from typing import Iterator, List


def fibonacci(n: int) -> int:
    """Return the nth Fibonacci number (0-indexed).

    fibonacci(0) == 0
    fibonacci(1) == 1
    fibonacci(2) == 1
    fibonacci(3) == 2
    ...

    Args:
        n: The index of the Fibonacci number to compute. Must be >= 0.

    Returns:
        The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@lru_cache(maxsize=None)
def fibonacci_recursive(n: int) -> int:
    """Return the nth Fibonacci number using memoized recursion.

    Args:
        n: The index of the Fibonacci number to compute. Must be >= 0.

    Returns:
        The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n < 2:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)


def fibonacci_sequence(n: int) -> List[int]:
    """Return a list of the first n Fibonacci numbers.

    Args:
        n: How many Fibonacci numbers to generate. Must be >= 0.

    Returns:
        A list of the first n Fibonacci numbers.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    return [fibonacci(i) for i in range(n)]


def fibonacci_generator() -> Iterator[int]:
    """Yield Fibonacci numbers indefinitely."""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b
