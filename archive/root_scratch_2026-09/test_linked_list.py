"""Unit tests for the LinkedList implementation."""

import pytest

from linked_list import LinkedList


def test_empty_list():
    lst = LinkedList()
    assert len(lst) == 0
    assert lst.is_empty
    assert lst.head is None
    assert lst.tail is None
    assert list(lst) == []
    assert repr(lst) == "LinkedList([])"


def test_construction_from_iterable():
    lst = LinkedList([1, 2, 3])
    assert len(lst) == 3
    assert list(lst) == [1, 2, 3]
    assert lst.to_list() == [1, 2, 3]


def test_append_and_len():
    lst = LinkedList()
    lst.append(10)
    lst.append(20)
    lst.append(30)
    assert len(lst) == 3
    assert list(lst) == [10, 20, 30]
    assert lst.tail == 30


def test_prepend():
    lst = LinkedList()
    lst.prepend(3)
    lst.prepend(2)
    lst.prepend(1)
    assert list(lst) == [1, 2, 3]
    assert lst.head == 1


def test_insert_positions():
    lst = LinkedList([1, 3])
    lst.insert(1, 2)          # middle
    lst.insert(0, 0)          # front
    lst.insert(10, 4)         # beyond end -> append
    assert list(lst) == [0, 1, 2, 3, 4]


def test_insert_negative_index():
    lst = LinkedList([1, 2, 4])
    lst.insert(-1, 3)
    assert list(lst) == [1, 2, 3, 4]


def test_insert_out_of_range_negative():
    lst = LinkedList([1, 2])
    with pytest.raises(IndexError):
        lst.insert(-5, 99)


def test_pop_last():
    lst = LinkedList([1, 2, 3])
    assert lst.pop() == 3
    assert list(lst) == [1, 2]
    assert lst.tail == 2


def test_pop_index():
    lst = LinkedList([1, 2, 3, 4])
    assert lst.pop(1) == 2
    assert list(lst) == [1, 3, 4]
    assert lst.pop(0) == 1
    assert list(lst) == [3, 4]


def test_pop_negative_index():
    lst = LinkedList([1, 2, 3])
    assert lst.pop(-2) == 2
    assert list(lst) == [1, 3]


def test_pop_empty_raises():
    lst = LinkedList()
    with pytest.raises(IndexError):
        lst.pop()


def test_pop_out_of_range():
    lst = LinkedList([1, 2])
    with pytest.raises(IndexError):
        lst.pop(5)


def test_remove_value():
    lst = LinkedList([1, 2, 3, 2])
    lst.remove(2)
    assert list(lst) == [1, 3, 2]
    lst.remove(2)
    assert list(lst) == [1, 3]


def test_remove_head():
    lst = LinkedList([1, 2, 3])
    lst.remove(1)
    assert list(lst) == [2, 3]
    assert lst.head == 2


def test_remove_only_element():
    lst = LinkedList([1])
    lst.remove(1)
    assert lst.is_empty
    assert lst.head is None
    assert lst.tail is None


def test_remove_missing_raises():
    lst = LinkedList([1, 2])
    with pytest.raises(ValueError):
        lst.remove(99)


def test_remove_empty_raises():
    lst = LinkedList()
    with pytest.raises(ValueError):
        lst.remove(1)


def test_clear():
    lst = LinkedList([1, 2, 3])
    lst.clear()
    assert lst.is_empty
    assert len(lst) == 0
    assert list(lst) == []


def test_getitem():
    lst = LinkedList([10, 20, 30])
    assert lst[0] == 10
    assert lst[2] == 30
    assert lst[-1] == 30


def test_getitem_out_of_range():
    lst = LinkedList([1, 2])
    with pytest.raises(IndexError):
        _ = lst[5]
    with pytest.raises(IndexError):
        _ = lst[-3]


def test_contains():
    lst = LinkedList([1, 2, 3])
    assert 2 in lst
    assert 99 not in lst


def test_index():
    lst = LinkedList(["a", "b", "a"])
    assert lst.index("b") == 1
    assert lst.index("a") == 0
    with pytest.raises(ValueError):
        lst.index("z")


def test_find():
    lst = LinkedList([1, 3, 5, 8])
    assert lst.find(lambda x: x > 4) == 2
    assert lst.find(lambda x: x > 100) is None


def test_reversed():
    lst = LinkedList([1, 2, 3])
    assert list(reversed(lst)) == [3, 2, 1]


def test_repr():
    lst = LinkedList([1, "two", 3.0])
    assert repr(lst) == "LinkedList([1, 'two', 3.0])"


def test_large_list():
    lst = LinkedList(range(1000))
    assert len(lst) == 1000
    assert lst[0] == 0
    assert lst[999] == 999
    assert lst.head == 0
    assert lst.tail == 999
