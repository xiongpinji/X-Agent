"""Search engine abstraction supporting multiple providers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field


class SearchProvider(str, Enum):
    """Supported search providers."""
    SERPER = "serper"
    SERPAPI = "serpapi"
    FIRECRAWL = "firecrawl"
    GOOGLE = "google"
    BING = "bing"


class SearchResult(BaseModel):
    """Individual search result."""
    title: str = Field(..., description="Result title")
    url: str = Field(..., description="Result URL")
    snippet: str = Field(..., description="Result snippet/description")
    position: int = Field(..., description="Position in results")
    source: str = Field(default="", description="Source domain")
    date: Optional[str] = Field(default=None, description="Publication date")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    query: str = Field(..., description="Original search query")
    results: list[SearchResult] = Field(default_factory=list, description="Search results")
    total_results: int = Field(default=0, description="Total results found")
    search_time_ms: float = Field(default=0.0, description="Search execution time")
    provider: str = Field(..., description="Search provider used")
    cached: bool = Field(default=False, description="Whether result was cached")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class BaseSearchProvider(ABC):
    """Abstract base class for search providers."""

    def __init__(self, api_key: str, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @abstractmethod
    async def search(self, query: str, num_results: int = 10, **kwargs) -> SearchResponse:
        """Execute search query."""
        pass

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class SerperProvider(BaseSearchProvider):
    """Serper.dev search provider."""

    async def search(self, query: str, num_results: int = 10, **kwargs) -> SearchResponse:
        """Search using Serper API."""
        start_time = time.time()

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "q": query,
            "num": min(num_results, 100),
            "page": kwargs.get("page", 1),
        }

        try:
            response = await self.client.post(
                "https://google.serper.dev/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for idx, item in enumerate(data.get("organic", [])[:num_results], 1):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=idx,
                    source=item.get("domain", ""),
                    date=item.get("date"),
                    metadata={"sitelinks": item.get("sitelinks", [])},
                ))

            search_time = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                results=results,
                total_results=data.get("searchParameters", {}).get("page", 0) * num_results,
                search_time_ms=search_time,
                provider="serper",
            )
        except Exception as e:
            raise RuntimeError(f"Serper search failed: {str(e)}")


class SerpAPIProvider(BaseSearchProvider):
    """SerpAPI search provider."""

    async def search(self, query: str, num_results: int = 10, **kwargs) -> SearchResponse:
        """Search using SerpAPI."""
        start_time = time.time()

        params = {
            "q": query,
            "api_key": self.api_key,
            "num": min(num_results, 100),
            "engine": kwargs.get("engine", "google"),
        }

        try:
            response = await self.client.get(
                "https://serpapi.com/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for idx, item in enumerate(data.get("organic_results", [])[:num_results], 1):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=idx,
                    source=item.get("domain", ""),
                    date=item.get("date"),
                    metadata={"rich_snippet": item.get("rich_snippet")},
                ))

            search_time = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                results=results,
                total_results=data.get("search_information", {}).get("total_results", 0),
                search_time_ms=search_time,
                provider="serpapi",
            )
        except Exception as e:
            raise RuntimeError(f"SerpAPI search failed: {str(e)}")


class FirecrawlProvider(BaseSearchProvider):
    """Firecrawl web scraping provider."""

    async def search(self, query: str, num_results: int = 10, **kwargs) -> SearchResponse:
        """Search and scrape using Firecrawl."""
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "url": kwargs.get("url", ""),
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
        }

        try:
            response = await self.client.post(
                "https://api.firecrawl.dev/v1/scrape",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Firecrawl returns scraped content, convert to search-like format
            results = [SearchResult(
                title=kwargs.get("url", ""),
                url=kwargs.get("url", ""),
                snippet=data.get("markdown", "")[:500],
                position=1,
                source=kwargs.get("url", ""),
                metadata={
                    "markdown": data.get("markdown", ""),
                    "html": data.get("html", ""),
                    "metadata": data.get("metadata", {}),
                },
            )]

            search_time = (time.time() - start_time) * 1000
            return SearchResponse(
                query=query,
                results=results,
                total_results=1,
                search_time_ms=search_time,
                provider="firecrawl",
            )
        except Exception as e:
            raise RuntimeError(f"Firecrawl scrape failed: {str(e)}")


class SearchEngine:
    """Main search engine orchestrator."""

    def __init__(self, providers: dict[SearchProvider, str]):
        """Initialize search engine with provider API keys.

        Args:
            providers: Dict mapping SearchProvider to API key
        """
        self.providers: dict[SearchProvider, BaseSearchProvider] = {}
        self.default_provider = SearchProvider.SERPER

        for provider, api_key in providers.items():
            if provider == SearchProvider.SERPER:
                self.providers[provider] = SerperProvider(api_key)
            elif provider == SearchProvider.SERPAPI:
                self.providers[provider] = SerpAPIProvider(api_key)
            elif provider == SearchProvider.FIRECRAWL:
                self.providers[provider] = FirecrawlProvider(api_key)

    async def search(
        self,
        query: str,
        num_results: int = 10,
        provider: Optional[SearchProvider] = None,
        **kwargs
    ) -> SearchResponse:
        """Execute search with specified provider.

        Args:
            query: Search query
            num_results: Number of results to return
            provider: Search provider to use (defaults to SERPER)
            **kwargs: Additional provider-specific arguments

        Returns:
            SearchResponse with results
        """
        provider = provider or self.default_provider

        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not configured")

        return await self.providers[provider].search(query, num_results, **kwargs)

    async def search_multi(
        self,
        query: str,
        num_results: int = 10,
        providers: Optional[list[SearchProvider]] = None,
    ) -> list[SearchResponse]:
        """Execute search across multiple providers in parallel.

        Args:
            query: Search query
            num_results: Number of results per provider
            providers: List of providers to use

        Returns:
            List of SearchResponse from each provider
        """
        providers = providers or [self.default_provider]

        tasks = [
            self.search(query, num_results, provider=p)
            for p in providers
            if p in self.providers
        ]

        return await asyncio.gather(*tasks, return_exceptions=False)

    async def close(self):
        """Close all provider connections."""
        for provider in self.providers.values():
            await provider.close()
