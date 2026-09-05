"""Tests for the sort utility module."""

from _reg_sort import sort_items, sort_in_place


def test_sort_items_ascending():
    assert sort_items([3, 1, 2]) == [1, 2, 3]


def test_sort_items_descending():
    assert sort_items([3, 1, 2], reverse=True) == [3, 2, 1]


def test_sort_items_with_key():
    assert sort_items(["bbb", "a", "cc"], key=len) == ["a", "cc", "bbb"]


def test_sort_items_does_not_mutate_input():
    original = [3, 1, 2]
    sort_items(original)
    assert original == [3, 1, 2]


def test_sort_in_place_mutates_input():
    items = [3, 1, 2]
    result = sort_in_place(items)
    assert items == [1, 2, 3]
    assert result is items


def test_sort_empty_list():
    assert sort_items([]) == []
