"""X-Agent built-in tools (web search, etc.)."""
from backend.app.core.tools_builtin.web_search import (
    execute_web_search,
    WEB_SEARCH_TOOL_SCHEMA,
    SearchResult,
)

__all__ = ["execute_web_search", "WEB_SEARCH_TOOL_SCHEMA", "SearchResult"]
