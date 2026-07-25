"""Search engine integration module."""

from __future__ import annotations

from typing import Any

import httpx


class SearchEngine:
    """Base search engine class."""

    async def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]]:
        """Search for results.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of search results
        """
        raise NotImplementedError


class GoogleSearch(SearchEngine):
    """Google Custom Search integration."""

    def __init__(self, api_key: str, cx: str):
        """Initialize Google Search.

        Args:
            api_key: Google API key
            cx: Custom search engine ID
        """
        self.api_key = api_key
        self.cx = cx
        self.client = httpx.AsyncClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]]:
        """Search using Google Custom Search API.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            List of search results
        """
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(num_results, 10),  # Google API max is 10
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet"),
                    "source": "google",
                })

            return results
        except Exception as e:
            raise RuntimeError(f"Google search failed: {e!s}")

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()


class DuckDuckGoSearch(SearchEngine):
    """DuckDuckGo search integration."""

    def __init__(self):
        """Initialize DuckDuckGo Search."""
        self.client = httpx.AsyncClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]]:
        """Search using DuckDuckGo.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            List of search results
        """
        # DuckDuckGo doesn't have an official API, so this is a placeholder
        # In production, use a library like duckduckgo-search
        return []

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()


class BingSearch(SearchEngine):
    """Bing Search integration."""

    def __init__(self, api_key: str):
        """Initialize Bing Search.

        Args:
            api_key: Bing Search API key
        """
        self.api_key = api_key
        self.client = httpx.AsyncClient()

    async def search(self, query: str, num_results: int = 10) -> list[dict[str, Any]]:
        """Search using Bing Search API.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            List of search results
        """
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {"q": query, "count": min(num_results, 50)}

        try:
            response = await self.client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("webPages", {}).get("value", []):
                results.append({
                    "title": item.get("name"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet"),
                    "source": "bing",
                })

            return results
        except Exception as e:
            raise RuntimeError(f"Bing search failed: {e!s}")

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()
