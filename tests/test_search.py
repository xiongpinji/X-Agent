"""Search system tests."""

import pytest
from backend.app.core.search import SearchCache, ContentExtractor


@pytest.mark.asyncio
async def test_search_cache_initialization():
    """Test search cache initialization."""
    cache = SearchCache(ttl=3600)
    assert cache.ttl == 3600


@pytest.mark.asyncio
async def test_cache_set_and_get():
    """Test caching and retrieving results."""
    cache = SearchCache(ttl=3600)

    results = [
        {"title": "Result 1", "url": "http://example.com/1"},
        {"title": "Result 2", "url": "http://example.com/2"},
    ]

    await cache.set("test query", results, "web")
    cached = await cache.get("test query", "web")

    assert cached is not None
    assert len(cached) == 2
    assert cached[0]["title"] == "Result 1"


@pytest.mark.asyncio
async def test_cache_miss():
    """Test cache miss."""
    cache = SearchCache(ttl=3600)

    result = await cache.get("nonexistent", "web")
    assert result is None


@pytest.mark.asyncio
async def test_cache_different_search_types():
    """Test caching different search types."""
    cache = SearchCache(ttl=3600)

    web_results = [{"title": "Web Result"}]
    news_results = [{"title": "News Result"}]

    await cache.set("test", web_results, "web")
    await cache.set("test", news_results, "news")

    web_cached = await cache.get("test", "web")
    news_cached = await cache.get("test", "news")

    assert web_cached[0]["title"] == "Web Result"
    assert news_cached[0]["title"] == "News Result"


@pytest.mark.asyncio
async def test_cache_clear():
    """Test clearing cache."""
    cache = SearchCache(ttl=3600)

    await cache.set("query1", [{"title": "Result 1"}], "web")
    await cache.set("query2", [{"title": "Result 2"}], "web")

    await cache.clear()

    result1 = await cache.get("query1", "web")
    result2 = await cache.get("query2", "web")

    assert result1 is None
    assert result2 is None


@pytest.mark.asyncio
async def test_cache_stats():
    """Test cache statistics."""
    cache = SearchCache(ttl=3600)

    await cache.set("query1", [{"title": "Result 1"}], "web")
    await cache.set("query2", [{"title": "Result 2"}], "web")

    stats = await cache.get_stats()
    assert stats["total_entries"] == 2
    assert stats["ttl"] == 3600


@pytest.mark.asyncio
async def test_cleanup_expired():
    """Test cleanup of expired entries."""
    cache = SearchCache(ttl=0)  # Immediate expiration

    await cache.set("query", [{"title": "Result"}], "web")

    # Wait a bit for expiration
    import time
    time.sleep(0.1)

    result = await cache.get("query", "web")
    assert result is None


@pytest.mark.asyncio
async def test_content_extractor_initialization():
    """Test content extractor initialization."""
    extractor = ContentExtractor(timeout=10.0)
    assert extractor.timeout == 10.0


@pytest.mark.asyncio
async def test_extract_title():
    """Test title extraction."""
    extractor = ContentExtractor()

    html = "<html><head><title>Test Page</title></head></html>"
    title = extractor._extract_title(html)

    assert title == "Test Page"


@pytest.mark.asyncio
async def test_extract_title_fallback():
    """Test title extraction fallback to h1."""
    extractor = ContentExtractor()

    html = "<html><body><h1>Heading Title</h1></body></html>"
    title = extractor._extract_title(html)

    assert title == "Heading Title"


@pytest.mark.asyncio
async def test_extract_content():
    """Test content extraction."""
    extractor = ContentExtractor()

    html = """
    <html>
    <body>
        <p>First paragraph</p>
        <p>Second paragraph</p>
        <script>console.log('ignored')</script>
        <p>Third paragraph</p>
    </body>
    </html>
    """

    content = extractor._extract_content(html)
    assert "First paragraph" in content
    assert "Second paragraph" in content
    assert "console.log" not in content


@pytest.mark.asyncio
async def test_extract_metadata():
    """Test metadata extraction."""
    extractor = ContentExtractor()

    html = """
    <html>
    <head>
        <meta name="description" content="Test description">
        <meta name="keywords" content="test, keywords">
        <meta property="og:title" content="OG Title">
    </head>
    </html>
    """

    metadata = extractor._extract_metadata(html)
    assert metadata["description"] == "Test description"
    assert metadata["keywords"] == "test, keywords"
    assert metadata["og_title"] == "OG Title"


@pytest.mark.asyncio
async def test_extract_metadata_empty():
    """Test metadata extraction with no metadata."""
    extractor = ContentExtractor()

    html = "<html><head></head></html>"
    metadata = extractor._extract_metadata(html)

    assert len(metadata) == 0


@pytest.mark.asyncio
async def test_cache_key_generation():
    """Test cache key generation."""
    cache = SearchCache()

    key1 = cache._get_cache_key("test query", "web")
    key2 = cache._get_cache_key("test query", "web")
    key3 = cache._get_cache_key("test query", "news")

    assert key1 == key2
    assert key1 != key3


@pytest.mark.asyncio
async def test_search_cache_with_special_characters():
    """Test cache with special characters in query."""
    cache = SearchCache(ttl=3600)

    query = "test & special <chars> 中文"
    results = [{"title": "Result"}]

    await cache.set(query, results, "web")
    cached = await cache.get(query, "web")

    assert cached is not None
    assert len(cached) == 1
