"""Search utility module providing substring and multi-query search helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, List, TypeVar

T = TypeVar("T")


def search(
    items: Sequence[str] | None,
    query: str,
    *,
    case_sensitive: bool = False,
    partial: bool = True,
) -> List[str]:
    """Return items that match the given query.

    By default matching is case-insensitive and partial (substring based).

    Args:
        items: Sequence of strings to search through. Must not be None.
        query: Non-empty substring or full value to search for.
        case_sensitive: When True, matching respects letter casing.
        partial: When True, substring matches are allowed; when False only
            exact whole-string matches are returned.

    Returns:
        A list of matching items in their original order.

    Raises:
        ValueError: If ``items`` is None or ``query`` is empty.
    """
    if items is None:
        raise ValueError("items must not be None")
    if not query:
        raise ValueError("query must not be empty")

    if not case_sensitive:
        needle = query.casefold()
    else:
        needle = query

    results: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        if not case_sensitive:
            haystack = item.casefold()
        else:
            haystack = item
        if partial:
            matched = needle in haystack
        else:
            matched = haystack == needle
        if matched:
            results.append(item)
    return results


def search_indices(
    items: Sequence[str] | None,
    query: str,
    *,
    case_sensitive: bool = False,
    partial: bool = True,
) -> List[int]:
    """Return the indices of items that match the given query.

    Args:
        items: Sequence of strings to search through. Must not be None.
        query: Non-empty substring or full value to search for.
        case_sensitive: When True, matching respects letter casing.
        partial: When True, substring matches are allowed; when False only
            exact whole-string matches are returned.

    Returns:
        A list of indices (in ascending order) of matching items.

    Raises:
        ValueError: If ``items`` is None or ``query`` is empty.
    """
    if items is None:
        raise ValueError("items must not be None")
    if not query:
        raise ValueError("query must not be empty")

    if not case_sensitive:
        needle = query.casefold()
    else:
        needle = query

    indices: List[int] = []
    for index, item in enumerate(items):
        if not isinstance(item, str):
            continue
        if not case_sensitive:
            haystack = item.casefold()
        else:
            haystack = item
        if partial:
            matched = needle in haystack
        else:
            matched = haystack == needle
        if matched:
            indices.append(index)
    return indices


def search_any(
    items: Sequence[str] | None,
    queries: Iterable[str],
    *,
    case_sensitive: bool = False,
    partial: bool = True,
) -> List[str]:
    """Return items that match any of the given queries.

    Args:
        items: Sequence of strings to search through. Must not be None.
        queries: Iterable of non-empty query strings. May be empty.
        case_sensitive: When True, matching respects letter casing.
        partial: When True, substring matches are allowed; when False only
            exact whole-string matches are returned.

    Returns:
        A list of matching items in their original order.

    Raises:
        ValueError: If ``items`` is None or any individual query is empty.
    """
    if items is None:
        raise ValueError("items must not be None")

    query_list = list(queries)
    if any(not q for q in query_list):
        raise ValueError("queries must not contain empty strings")

    if not case_sensitive:
        needles = [q.casefold() for q in query_list]
    else:
        needles = query_list

    results: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        if not case_sensitive:
            haystack = item.casefold()
        else:
            haystack = item
        for needle in needles:
            if partial:
                matched = needle in haystack
            else:
                matched = haystack == needle
            if matched:
                results.append(item)
                break
    return results
