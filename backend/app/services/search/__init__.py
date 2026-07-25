"""Web search service module for X-Agent."""

from .cache import SearchCache
from .parser import SearchResultParser
from .search_engine import SearchEngine, SearchProvider, SearchResult

__all__ = [
    "SearchCache",
    "SearchEngine",
    "SearchProvider",
    "SearchResult",
    "SearchResultParser",
]
