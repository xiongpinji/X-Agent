"""Web search API endpoints."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/search", tags=["search"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    num_results: int = Field(default=10, ge=1, le=100, description="Number of results")
    provider: str | None = Field(default=None, description="Search provider")


class SearchResultItem(BaseModel):
    """Search result item."""
    title: str
    url: str
    snippet: str
    domain: str
    content_type: str
    relevance: str
    date: str | None = None


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    results: list[SearchResultItem]
    total_results: int
    search_time_ms: float
    provider: str
    cached: bool


@router.post("/query", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    principal: PrincipalDependency,
) -> SearchResponse:
    """Execute web search.

    Args:
        request: Search request
        principal: Current user principal

    Returns:
        Search results
    """
    enforce_scope(principal, "search:read")

    # Basic in-memory search over provider catalog (real engine pluggable)
    start = time.perf_counter()
    provider = request.provider or "serper"

    # Simulated results from provider catalog for demonstration
    catalog = [
        SearchResultItem(
            title=f"Result for '{request.query}'",
            url=f"https://example.com/search?q={request.query.replace(' ', '+')}",
            snippet=f"Search results for: {request.query}",
            domain="example.com",
            content_type="web",
            relevance="high",
        ),
    ]
    results = catalog[: request.num_results]
    elapsed_ms = (time.perf_counter() - start) * 1000

    return SearchResponse(
        query=request.query,
        results=results,
        total_results=len(results),
        search_time_ms=round(elapsed_ms, 2),
        provider=provider,
        cached=False,
    )


@router.get("/providers")
async def list_providers(principal: PrincipalDependency) -> dict:
    """List available search providers.

    Args:
        principal: Current user principal

    Returns:
        Available providers
    """
    enforce_scope(principal, "search:read")

    return {
        "providers": [
            {
                "name": "serper",
                "description": "Serper.dev search API",
                "status": "active",
            },
            {
                "name": "serpapi",
                "description": "SerpAPI search engine",
                "status": "active",
            },
            {
                "name": "firecrawl",
                "description": "Firecrawl web scraping",
                "status": "active",
            },
        ]
    }


@router.get("/cache/stats")
async def get_cache_stats(principal: PrincipalDependency) -> dict:
    """Get search cache statistics.

    Args:
        principal: Current user principal

    Returns:
        Cache statistics
    """
    enforce_scope(principal, "search:read")

    # NOTE: Requires SearchCache service (Redis) integration for real stats
    return {
        "entries": 0,
        "total_size_bytes": 0,
        "ttl_seconds": 3600,
    }


@router.delete("/cache")
async def clear_cache(principal: PrincipalDependency) -> dict:
    """Clear search cache.

    Args:
        principal: Current user principal

    Returns:
        Cleared count
    """
    enforce_scope(principal, "search:write")

    # NOTE: Requires SearchCache service (Redis) integration for real cache ops
    return {"cleared": 0}
