"""Tests for the Queue implementation."""

import pytest

from queue import EmptyQueueError, Queue


def test_initialization_empty() -> None:
    q: Queue[int] = Queue()
    assert q.is_empty()
    assert len(q) == 0


def test_initialization_with_iterable() -> None:
    q = Queue([1, 2, 3])
    assert len(q) == 3
    assert not q.is_empty()


def test_enqueue_and_size() -> None:
    q = Queue()
    q.enqueue("a")
    q.enqueue("b")
    q.enqueue("c")
    assert len(q) == 3
    assert q.size() == 3


def test_fifo_order() -> None:
    q = Queue()
    for item in [1, 2, 3, 4]:
        q.enqueue(item)
    assert [q.dequeue() for _ in range(4)] == [1, 2, 3, 4]


def test_peek_does_not_remove() -> None:
    q = Queue([10, 20])
    assert q.peek() == 10
    assert len(q) == 2
    assert q.peek() == 10


def test_dequeue_empty_raises() -> None:
    q: Queue[int] = Queue()
    with pytest.raises(EmptyQueueError):
        q.dequeue()


def test_peek_empty_raises() -> None:
    q: Queue[int] = Queue()
    with pytest.raises(EmptyQueueError):
        q.peek()


def test_clear() -> None:
    q = Queue([1, 2, 3])
    q.clear()
    assert q.is_empty()
    assert len(q) == 0


def test_iteration_preserves_order() -> None:
    q = Queue([5, 6, 7])
    assert list(q) == [5, 6, 7]
    assert len(q) == 3  # iteration should not consume


def test_repr() -> None:
    q = Queue([1, 2])
    assert repr(q) == "Queue([1, 2])"


def test_round_trip_many_items() -> None:
    q = Queue()
    n = 1000
    for i in range(n):
        q.enqueue(i)
    assert len(q) == n
    for i in range(n):
        assert q.dequeue() == i
    assert q.is_empty()
