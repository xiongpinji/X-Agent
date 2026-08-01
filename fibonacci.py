def fibonacci(n: int) -> int:
    """Return the nth Fibonacci number.

    Uses an iterative approach to compute the Fibonacci sequence.
    fibonacci(0) returns 0, fibonacci(1) returns 1.

    Args:
        n: A non-negative integer index into the Fibonacci sequence.

    Returns:
        The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    if n == 0:
        return 0
    if n == 1:
        return 1

    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
