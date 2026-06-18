"""Web search tool for X-Agent — gives agents ability to search the internet.

Backends (auto-selected):
1. DuckDuckGo (default, free, no API key needed)
2. SerpAPI (if XAGENT_SERPAPI_KEY configured)

Usage:
    results = await execute_web_search("FastAPI rate limiting best practices")
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    snippet: str
    url: str


@dataclass
class SearchCache:
    """Simple TTL cache for search results."""

    _store: dict[str, tuple[float, list[SearchResult]]] = field(default_factory=dict)
    ttl_seconds: int = 3600  # 1 hour

    def get(self, query: str) -> list[SearchResult] | None:
        """Retrieve cached results if not expired.

        Args:
            query: Search query string.

        Returns:
            List of cached SearchResult objects or None if not found/expired.
        """
        key = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()
        if key in self._store:
            ts, results = self._store[key]
            if time.time() - ts < self.ttl_seconds:
                return results
            del self._store[key]
        return None

    def set(self, query: str, results: list[SearchResult]) -> None:
        """Cache search results with TTL.

        Args:
            query: Search query string.
            results: List of SearchResult objects to cache.
        """
        key = hashlib.md5(query.encode(), usedforsecurity=False).hexdigest()
        self._store[key] = (time.time(), results)


_cache = SearchCache()


async def search_duckduckgo(
    query: str, max_results: int = 5
) -> list[SearchResult]:
    """Search using DuckDuckGo HTML (no API key needed).

    Args:
        query: Search query string.
        max_results: Maximum results to return.

    Returns:
        List of SearchResult objects.

    Raises:
        httpx.HTTPError: If the HTTP request fails.
    """
    url = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data={"q": query})
        resp.raise_for_status()

    results = []
    # DuckDuckGo lite returns results in specific HTML pattern
    links = re.findall(
        r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>',
        resp.text,
    )
    snippets = re.findall(
        r'<a class="result__snippet".*?>(.*?)</a>', resp.text, re.DOTALL
    )

    for i, (href, title) in enumerate(links[:max_results]):
        snippet = snippets[i].strip() if i < len(snippets) else ""
        # Clean HTML tags from snippet
        snippet = re.sub(r"<.*?>", "", snippet).strip()
        title = re.sub(r"<.*?>", "", title).strip()
        results.append(SearchResult(title=title, snippet=snippet, url=href))

    return results


async def search_serpapi(
    query: str, api_key: str, max_results: int = 5
) -> list[SearchResult]:
    """Search using SerpAPI (requires API key).

    Args:
        query: Search query string.
        api_key: SerpAPI API key.
        max_results: Maximum results to return.

    Returns:
        List of SearchResult objects.

    Raises:
        httpx.HTTPError: If the HTTP request fails.
    """
    url = "https://serpapi.com/search.json"
    params = {"q": query, "api_key": api_key, "num": max_results}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                url=item.get("link", ""),
            )
        )
    return results


async def execute_web_search(
    query: str, max_results: int = 5, serpapi_key: str | None = None
) -> list[SearchResult]:
    """Execute web search with caching and backend auto-selection.

    Attempts to use DuckDuckGo by default (free, no key needed).
    Falls back to SerpAPI if key is provided and DuckDuckGo fails.

    Args:
        query: Search query string.
        max_results: Maximum results to return (default 5).
        serpapi_key: Optional SerpAPI key (uses DuckDuckGo if not provided).

    Returns:
        List of SearchResult objects. Empty list on failure.
    """
    # Check cache
    cached = _cache.get(query)
    if cached is not None:
        logger.debug("Web search cache hit for: %s", query)
        return cached[:max_results]

    # Execute search
    try:
        if serpapi_key:
            results = await search_serpapi(query, serpapi_key, max_results)
        else:
            results = await search_duckduckgo(query, max_results)
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return []

    # Cache results
    _cache.set(query, results)
    return results


# Tool schema for registration with tool_registry
WEB_SEARCH_TOOL_SCHEMA = {
    "name": "web_search",
    "description": "Search the internet for information. Use for finding documentation, solutions, best practices, or current information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    "risk_level": "LOW",
}
