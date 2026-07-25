"""MCP search operation tools with permission control and audit logging."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SearchAuditLog:
    """Audit log for search operations."""

    def __init__(self, max_entries: int = 1000):
        """Initialize audit log.

        Args:
            max_entries: Maximum number of log entries to keep
        """
        self.max_entries = max_entries
        self.entries: list[dict[str, Any]] = []

    def log(
        self,
        operation: str,
        query: str,
        success: bool,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Log a search operation.

        Args:
            operation: Operation type (web_search, news_search)
            query: Search query
            success: Whether operation succeeded
            details: Additional details
            error: Error message if failed
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "query": query,
            "success": success,
            "details": details or {},
            "error": error,
        }
        self.entries.append(entry)

        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        log_level = logging.INFO if success else logging.WARNING
        logger.log(log_level, f"Audit: {operation} '{query}' - {success}")

    def get_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.entries[-limit:]

    def clear(self) -> None:
        """Clear all audit logs."""
        self.entries.clear()


class SearchPermissionChecker:
    """Permission checker for search operations."""

    def __init__(self, allowed_operations: dict[str, bool] | None = None):
        """Initialize permission checker.

        Args:
            allowed_operations: Dict of operation -> allowed (web_search, news_search)
        """
        self.allowed_operations = allowed_operations or {
            "web_search": True,
            "news_search": True,
        }

    def check_permission(self, operation: str) -> bool:
        """Check if operation is allowed.

        Args:
            operation: Operation type

        Returns:
            True if allowed, False otherwise
        """
        return self.allowed_operations.get(operation, False)

    def set_permission(self, operation: str, allowed: bool) -> None:
        """Set permission for an operation.

        Args:
            operation: Operation type
            allowed: Whether to allow the operation
        """
        self.allowed_operations[operation] = allowed


class SearchOperationTool:
    """Search operation tool for MCP with permission control and audit logging."""

    def __init__(
        self,
        api_key: str | None = None,
        search_engine_id: str | None = None,
        permission_checker: SearchPermissionChecker | None = None,
        audit_log: SearchAuditLog | None = None,
    ):
        """Initialize search operation tool.

        Args:
            api_key: Google Custom Search API key
            search_engine_id: Google Custom Search Engine ID
            permission_checker: Permission checker instance
            audit_log: Audit log instance
        """
        self.api_key = api_key or os.getenv("GOOGLE_SEARCH_API_KEY")
        self.search_engine_id = search_engine_id or os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.permission_checker = permission_checker or SearchPermissionChecker()
        self.audit_log = audit_log or SearchAuditLog()

    async def search(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Perform a search.

        Args:
            query: Search query
            num_results: Number of results to return
            search_type: Type of search (web, news, images)

        Returns:
            Search results
        """
        if search_type == "web":
            return await self.search_web(query, num_results)
        elif search_type == "news":
            return await self.search_news(query, num_results)
        else:
            return {
                "query": query,
                "search_type": search_type,
                "results": [],
                "total": 0,
                "error": f"Unsupported search type: {search_type}",
            }

    async def search_web(self, query: str, num_results: int = 10) -> dict[str, Any]:
        """Search the web using Google Custom Search API.

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            Web search results
        """
        if not self.permission_checker.check_permission("web_search"):
            error_msg = "Web search operation not allowed"
            self.audit_log.log("web_search", query, False, error=error_msg)
            return {
                "query": query,
                "search_type": "web",
                "results": [],
                "total": 0,
                "error": error_msg,
                "status": "permission_denied",
            }

        if not self.api_key or not self.search_engine_id:
            error_msg = "Google Search API credentials not configured"
            self.audit_log.log("web_search", query, False, error=error_msg)
            return {
                "query": query,
                "search_type": "web",
                "results": [],
                "total": 0,
                "error": error_msg,
            }

        try:
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": min(num_results, 10),  # Google API max is 10 per request
            }

            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()

            data = response.json()
            results = []

            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "display_link": item.get("displayLink", ""),
                })

            self.audit_log.log(
                "web_search",
                query,
                True,
                details={"results_count": len(results), "num_results": num_results},
            )

            return {
                "query": query,
                "search_type": "web",
                "results": results,
                "total": data.get("queries", {}).get("request", [{}])[0].get("totalResults", 0),
                "status": "success",
            }
        except Exception as e:
            self.audit_log.log("web_search", query, False, error=str(e))
            return {
                "query": query,
                "search_type": "web",
                "results": [],
                "total": 0,
                "error": str(e),
                "status": "failed",
            }

    async def search_news(self, query: str, num_results: int = 10) -> dict[str, Any]:
        """Search news (placeholder - requires news API).

        Args:
            query: Search query
            num_results: Number of results

        Returns:
            News search results
        """
        if not self.permission_checker.check_permission("news_search"):
            error_msg = "News search operation not allowed"
            self.audit_log.log("news_search", query, False, error=error_msg)
            return {
                "query": query,
                "search_type": "news",
                "results": [],
                "total": 0,
                "error": error_msg,
                "status": "permission_denied",
            }

        # Placeholder for news search
        # In production, integrate with NewsAPI or similar
        self.audit_log.log("news_search", query, True, details={"status": "not_implemented"})
        return {
            "query": query,
            "search_type": "news",
            "results": [],
            "total": 0,
            "status": "not_implemented",
        }

    async def extract_content(self, url: str) -> dict[str, Any]:
        """Extract content from URL.

        Args:
            url: URL to extract from

        Returns:
            Extracted content
        """
        try:
            response = await self.client.get(url, timeout=10.0, follow_redirects=True)
            response.raise_for_status()

            # Basic content extraction
            html = response.text
            title = self._extract_title(html)
            content = self._extract_content(html)
            metadata = self._extract_metadata(html)

            return {
                "url": url,
                "title": title,
                "content": content,
                "metadata": metadata,
                "status": "success",
                "content_length": len(content),
            }
        except httpx.TimeoutException:
            return {
                "url": url,
                "error": "Request timeout",
                "status": "failed",
            }
        except httpx.HTTPError as e:
            return {
                "url": url,
                "error": f"HTTP error: {e!s}",
                "status": "failed",
            }
        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "status": "failed",
            }

    def _extract_title(self, html: str) -> str:
        """Extract title from HTML."""
        import re

        # Try to extract from <title> tag
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Try to extract from <h1> tag
        match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return ""

    def _extract_content(self, html: str) -> str:
        """Extract main content from HTML."""
        import re

        # Remove script and style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Extract text from paragraphs and divs
        paragraphs = re.findall(r"<p[^>]*>([^<]+)</p>", html, re.IGNORECASE)
        if not paragraphs:
            # Fallback to divs
            paragraphs = re.findall(r"<div[^>]*>([^<]+)</div>", html, re.IGNORECASE)

        # Clean up text
        content = "\n".join(paragraphs[:10])  # Return first 10 paragraphs
        content = re.sub(r"\s+", " ", content)  # Normalize whitespace
        return content.strip()

    def _extract_metadata(self, html: str) -> dict[str, str]:
        """Extract metadata from HTML."""
        import re

        metadata = {}

        # Extract description
        match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.IGNORECASE)
        if match:
            metadata["description"] = match.group(1)

        # Extract keywords
        match = re.search(r'<meta\s+name="keywords"\s+content="([^"]*)"', html, re.IGNORECASE)
        if match:
            metadata["keywords"] = match.group(1)

        # Extract author
        match = re.search(r'<meta\s+name="author"\s+content="([^"]*)"', html, re.IGNORECASE)
        if match:
            metadata["author"] = match.group(1)

        # Extract language
        match = re.search(r'<html[^>]*lang="([^"]*)"', html, re.IGNORECASE)
        if match:
            metadata["language"] = match.group(1)

        return metadata

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()

    def get_audit_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get audit logs.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries
        """
        return self.audit_log.get_entries(limit)

    def set_permissions(self, permissions: dict[str, bool]) -> None:
        """Set permissions for operations.

        Args:
            permissions: Dict of operation -> allowed
        """
        for operation, allowed in permissions.items():
            self.permission_checker.set_permission(operation, allowed)

    def get_permissions(self) -> dict[str, bool]:
        """Get current permissions.

        Returns:
            Dict of operation -> allowed
        """
        return self.permission_checker.allowed_operations.copy()
