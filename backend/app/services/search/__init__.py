"""Web search service module for X-Agent."""

from .search_engine import SearchEngine, SearchResult, SearchProvider
from .cache import SearchCache
from .parser import SearchResultParser

__all__ = [
    "SearchEngine",
    "SearchResult",
    "SearchProvider",
    "SearchCache",
    "SearchResultParser",
]
