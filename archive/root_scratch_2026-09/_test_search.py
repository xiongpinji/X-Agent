"""Tests for the search utility module."""

import pytest

from _search import search, search_any, search_indices


class TestSearch:
    def test_partial_match_finds_substrings(self):
        items = ["apple", "banana", "apricot"]
        assert search(items, "ap") == ["apple", "apricot"]

    def test_no_match_returns_empty(self):
        assert search(["cat", "dog"], "fish") == []

    def test_empty_items_returns_empty(self):
        assert search([], "x") == []

    def test_case_insensitive_by_default(self):
        assert search(["Apple", "apple", "APPLES"], "apple") == [
            "Apple",
            "apple",
            "APPLES",
        ]

    def test_case_sensitive(self):
        assert search(["Apple", "apple"], "apple", case_sensitive=True) == ["apple"]

    def test_exact_match_when_partial_false(self):
        assert search(["dog", "doggy", "cat"], "dog", partial=False) == ["dog"]

    def test_preserves_order(self):
        items = ["zzz", "aaa", "bbb", "zzz"]
        assert search(items, "zzz") == ["zzz", "zzz"]

    def test_empty_query_raises(self):
        with pytest.raises(ValueError):
            search(["a", "b"], "")

    def test_none_items_raises(self):
        with pytest.raises(ValueError):
            search(None, "a")  # type: ignore[arg-type]


class TestSearchIndices:
    def test_returns_indices_of_matches(self):
        assert search_indices(["foo", "bar", "foobar"], "foo") == [0, 2]

    def test_no_matches_returns_empty(self):
        assert search_indices(["a", "b"], "z") == []


class TestSearchAny:
    def test_matches_any_query(self):
        items = ["apple", "banana", "cherry"]
        assert search_any(items, ["ban", "cher"]) == ["banana", "cherry"]

    def test_order_preserved(self):
        items = ["z", "x", "y", "x"]
        assert search_any(items, ["x"]) == ["x", "x"]

    def test_empty_queries_returns_empty(self):
        assert search_any(["a", "b"], []) == []
