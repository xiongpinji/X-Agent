"""Web search API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/search", tags=["search"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    num_results: int = Field(default=10, ge=1, le=100, description="Number of results")
    provider: Optional[str] = Field(default=None, description="Search provider")


class SearchResultItem(BaseModel):
    """Search result item."""
    title: str
    url: str
    snippet: str
    domain: str
    content_type: str
    relevance: str
    date: Optional[str] = None


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

    # TODO: Implement search engine integration
    # This is a placeholder that will be connected to the SearchEngine service

    return SearchResponse(
        query=request.query,
        results=[],
        total_results=0,
        search_time_ms=0.0,
        provider=request.provider or "serper",
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

    # TODO: Connect to SearchCache service
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

    # TODO: Connect to SearchCache service
    return {"cleared": 0}
