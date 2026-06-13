"""Tests for web search tool."""
from __future__ import annotations

import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from backend.app.core.tools_builtin.web_search import (
    execute_web_search,
    search_duckduckgo,
    search_serpapi,
    SearchResult,
    SearchCache,
    _cache,
)

try:
    import respx
    HAS_RESPX = True
except ImportError:
    HAS_RESPX = False



class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self) -> None:
        """Test SearchResult object creation."""
        result = SearchResult(
            title="Test Title", snippet="Test snippet", url="https://example.com"
        )
        assert result.title == "Test Title"
        assert result.snippet == "Test snippet"
        assert result.url == "https://example.com"


class TestSearchCache:
    """Tests for SearchCache."""

    def test_cache_get_miss(self) -> None:
        """Test cache miss returns None."""
        cache = SearchCache()
        result = cache.get("nonexistent query")
        assert result is None

    def test_cache_set_and_get(self) -> None:
        """Test cache set and retrieval."""
        cache = SearchCache()
        results = [SearchResult("Title", "Snippet", "https://example.com")]
        cache.set("test query", results)

        cached = cache.get("test query")
        assert cached == results
        assert len(cached) == 1
        assert cached[0].title == "Title"

    def test_cache_expiration(self) -> None:
        """Test cache expiration based on TTL."""
        cache = SearchCache(ttl_seconds=1)
        results = [SearchResult("Title", "Snippet", "https://example.com")]
        cache.set("test query", results)

        # Should be in cache immediately
        assert cache.get("test query") is not None

        # Should expire after TTL
        import time

        time.sleep(1.1)
        assert cache.get("test query") is None

    def test_cache_different_queries_isolated(self) -> None:
        """Test different queries are cached separately."""
        cache = SearchCache()
        results1 = [SearchResult("Title1", "Snippet1", "https://example1.com")]
        results2 = [SearchResult("Title2", "Snippet2", "https://example2.com")]

        cache.set("query1", results1)
        cache.set("query2", results2)

        assert cache.get("query1") == results1
        assert cache.get("query2") == results2


@pytest.mark.asyncio
async def test_search_duckduckgo_returns_results() -> None:
    """Test DuckDuckGo search returns results."""
    html_response = """
    <html>
    <a rel="nofollow" class="result__a" href="https://example.com">Example Title</a>
    <a class="result__snippet">Example snippet text here</a>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        results = await search_duckduckgo("test query", max_results=5)

        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].url == "https://example.com"


@pytest.mark.asyncio
async def test_search_duckduckgo_respects_max_results() -> None:
    """Test DuckDuckGo respects max_results parameter."""
    html_response = """
    <html>
    <a rel="nofollow" class="result__a" href="https://example1.com">Title1</a>
    <a class="result__snippet">Snippet1</a>
    <a rel="nofollow" class="result__a" href="https://example2.com">Title2</a>
    <a class="result__snippet">Snippet2</a>
    <a rel="nofollow" class="result__a" href="https://example3.com">Title3</a>
    <a class="result__snippet">Snippet3</a>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        results = await search_duckduckgo("test query", max_results=2)
        assert len(results) <= 2


@pytest.mark.asyncio
async def test_search_serpapi_returns_results() -> None:
    """Test SerpAPI search returns results."""
    api_response = {
        "organic_results": [
            {
                "title": "Result 1",
                "snippet": "This is result 1",
                "link": "https://example1.com",
            },
            {
                "title": "Result 2",
                "snippet": "This is result 2",
                "link": "https://example2.com",
            },
        ]
    }

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=api_response)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        results = await search_serpapi("test query", "test-key", max_results=5)

        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example1.com"
        assert results[1].title == "Result 2"


@pytest.mark.asyncio
async def test_search_serpapi_respects_max_results() -> None:
    """Test SerpAPI respects max_results parameter."""
    api_response = {
        "organic_results": [
            {
                "title": f"Result {i}",
                "snippet": f"Snippet {i}",
                "link": f"https://example{i}.com",
            }
            for i in range(10)
        ]
    }

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=api_response)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        results = await search_serpapi("test query", "test-key", max_results=3)
        assert len(results) == 3


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_RESPX, reason="respx not installed")
async def test_execute_web_search_uses_cache() -> None:
    """Test execute_web_search uses cache on hit."""
    cached_results = [SearchResult("Cached", "Cached snippet", "https://cached.com")]

    # Clear and populate cache
    _cache._store.clear()
    import hashlib

    key = hashlib.md5("test query".encode()).hexdigest()
    _cache._store[key] = (time.time(), cached_results)

    with respx.mock:
        # Should not make any HTTP calls due to cache hit
        results = await execute_web_search("test query")

        assert results == cached_results
        # Verify no HTTP calls were made
        assert len(respx.calls) == 0


@pytest.mark.asyncio
async def test_execute_web_search_duckduckgo_backend() -> None:
    """Test execute_web_search uses DuckDuckGo by default."""
    html_response = """
    <html>
    <a rel="nofollow" class="result__a" href="https://example.com">Example</a>
    <a class="result__snippet">Example snippet</a>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Clear cache for this test
        _cache._store.clear()

        results = await execute_web_search("test query without serpapi key")

        assert len(results) > 0
        assert isinstance(results[0], SearchResult)


@pytest.mark.asyncio
async def test_execute_web_search_serpapi_backend() -> None:
    """Test execute_web_search uses SerpAPI when key provided."""
    api_response = {
        "organic_results": [
            {
                "title": "SerpAPI Result",
                "snippet": "From SerpAPI",
                "link": "https://serpapi.com/result",
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=api_response)
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # Clear cache for this test
        _cache._store.clear()

        results = await execute_web_search("test query", serpapi_key="test-api-key")

        assert len(results) == 1
        assert results[0].title == "SerpAPI Result"


@pytest.mark.asyncio
async def test_execute_web_search_timeout_returns_empty() -> None:
    """Test execute_web_search returns empty list on timeout."""

    async def timeout_mock(*args, **kwargs):
        raise httpx.TimeoutException("Request timed out")

    with patch("backend.app.core.tools_builtin.web_search.search_duckduckgo", timeout_mock):
        # Clear cache for this test
        _cache._store.clear()

        results = await execute_web_search("test query")

        assert results == []


@pytest.mark.asyncio
async def test_execute_web_search_network_error_returns_empty() -> None:
    """Test execute_web_search returns empty list on network error."""

    async def error_mock(*args, **kwargs):
        raise httpx.ConnectError("Network error")

    with patch("backend.app.core.tools_builtin.web_search.search_duckduckgo", error_mock):
        # Clear cache for this test
        _cache._store.clear()

        results = await execute_web_search("test query")

        assert results == []


@pytest.mark.asyncio
async def test_execute_web_search_caches_results() -> None:
    """Test execute_web_search caches search results."""
    html_response = """
    <html>
    <a rel="nofollow" class="result__a" href="https://example.com">Title</a>
    <a class="result__snippet">Snippet</a>
    </html>
    """

    mock_response = MagicMock()
    mock_response.text = html_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        # Clear cache for this test
        _cache._store.clear()

        # First call should make HTTP request
        results1 = await execute_web_search("cache test query")
        first_call_count = mock_post.call_count

        # Second call should use cache (no additional HTTP call)
        results2 = await execute_web_search("cache test query")
        second_call_count = mock_post.call_count

        # Verify only one HTTP call was made (second call used cache)
        assert first_call_count == 1
        assert second_call_count == 1  # No new call

        assert results1 == results2


def test_web_search_tool_schema() -> None:
    """Test WEB_SEARCH_TOOL_SCHEMA is properly configured."""
    from backend.app.core.tools_builtin.web_search import WEB_SEARCH_TOOL_SCHEMA

    assert WEB_SEARCH_TOOL_SCHEMA["name"] == "web_search"
    assert "parameters" in WEB_SEARCH_TOOL_SCHEMA
    assert "query" in WEB_SEARCH_TOOL_SCHEMA["parameters"]["properties"]
    assert "max_results" in WEB_SEARCH_TOOL_SCHEMA["parameters"]["properties"]
    assert "query" in WEB_SEARCH_TOOL_SCHEMA["parameters"]["required"]
    assert WEB_SEARCH_TOOL_SCHEMA["risk_level"] == "LOW"
