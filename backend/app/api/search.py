"""Search API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.search import SearchCache, ContentExtractor
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/search", tags=["search"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Initialize search components
search_cache = SearchCache(ttl=3600)
content_extractor = ContentExtractor(timeout=10.0)


@router.get("")
async def search(
    query: str = Query(..., min_length=1, max_length=500),
    num_results: int = Query(10, ge=1, le=50),
    search_type: str = Query("web", pattern="^(web|news|images)$"),
    use_cache: bool = Query(True),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Perform a search.

    Args:
        query: Search query
        num_results: Number of results to return
        search_type: Type of search (web, news, images)
        use_cache: Whether to use cached results
        principal: Current principal

    Returns:
        Search results
    """
    enforce_scope(principal, "search:read")

    # Check cache first
    if use_cache:
        cached_results = await search_cache.get(query, search_type)
        if cached_results:
            return {
                "query": query,
                "search_type": search_type,
                "results": cached_results,
                "count": len(cached_results),
                "from_cache": True,
            }

    # Placeholder for actual search implementation
    # In production, integrate with actual search engines
    results = []

    # Cache results
    await search_cache.set(query, results, search_type)

    return {
        "query": query,
        "search_type": search_type,
        "results": results,
        "count": len(results),
        "from_cache": False,
    }


@router.get("/extract")
async def extract_content(
    url: str = Query(..., min_length=1),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Extract content from URL.

    Args:
        url: URL to extract from
        principal: Current principal

    Returns:
        Extracted content
    """
    enforce_scope(principal, "search:read")

    try:
        result = await content_extractor.extract(url)
        return result
    except Exception as e:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Extraction failed: {str(e)}")


@router.get("/history")
async def get_search_history(
    limit: int = Query(50, ge=1, le=500),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Get search history.

    Args:
        limit: Maximum number of results
        principal: Current principal

    Returns:
        Search history
    """
    enforce_scope(principal, "search:read")

    # Placeholder for search history
    # In production, store search history in database
    return {
        "history": [],
        "count": 0,
        "limit": limit,
    }


@router.get("/cache/stats")
async def get_cache_stats(
    principal: PrincipalDependency,
) -> dict:
    """Get search cache statistics.

    Args:
        principal: Current principal

    Returns:
        Cache statistics
    """
    enforce_scope(principal, "search:read")

    stats = await search_cache.get_stats()
    return stats


@router.post("/cache/clear")
async def clear_cache(
    principal: PrincipalDependency,
) -> dict:
    """Clear search cache.

    Args:
        principal: Current principal

    Returns:
        Clear result
    """
    enforce_scope(principal, "search:write")

    await search_cache.clear()
    return {"status": "cleared"}


@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=50),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Get search suggestions.

    Args:
        query: Partial search query
        limit: Maximum number of suggestions
        principal: Current principal

    Returns:
        Search suggestions
    """
    enforce_scope(principal, "search:read")

    # Placeholder for search suggestions
    # In production, implement autocomplete logic
    return {
        "query": query,
        "suggestions": [],
        "count": 0,
    }
