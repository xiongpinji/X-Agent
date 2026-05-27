"""Web content extraction module."""

from __future__ import annotations

from typing import Any, Dict, Optional
import httpx
import re


class ContentExtractor:
    """Web content extractor."""

    def __init__(self, timeout: float = 10.0):
        """Initialize content extractor.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def extract(self, url: str) -> Dict[str, Any]:
        """Extract content from URL.

        Args:
            url: URL to extract from

        Returns:
            Extracted content
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
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
            }
        except Exception as e:
            return {
                "url": url,
                "error": str(e),
                "status": "failed",
            }

    def _extract_title(self, html: str) -> str:
        """Extract title from HTML.

        Args:
            html: HTML content

        Returns:
            Page title
        """
        match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback to h1
        match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_content(self, html: str) -> str:
        """Extract main content from HTML.

        Args:
            html: HTML content

        Returns:
            Extracted text content
        """
        # Remove script and style tags
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Extract text from paragraphs
        paragraphs = re.findall(r"<p[^>]*>([^<]+)</p>", html, re.IGNORECASE)
        if paragraphs:
            return "\n".join(paragraphs[:10])  # Return first 10 paragraphs

        # Fallback to all text
        text = re.sub(r"<[^>]+>", "", html)
        text = re.sub(r"\s+", " ", text)
        return text[:2000]  # Return first 2000 characters

    def _extract_metadata(self, html: str) -> Dict[str, str]:
        """Extract metadata from HTML.

        Args:
            html: HTML content

        Returns:
            Metadata dictionary
        """
        metadata = {}

        # Extract meta description
        match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.IGNORECASE)
        if match:
            metadata["description"] = match.group(1)

        # Extract meta keywords
        match = re.search(r'<meta\s+name="keywords"\s+content="([^"]+)"', html, re.IGNORECASE)
        if match:
            metadata["keywords"] = match.group(1)

        # Extract og:title
        match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE)
        if match:
            metadata["og_title"] = match.group(1)

        # Extract og:description
        match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.IGNORECASE)
        if match:
            metadata["og_description"] = match.group(1)

        return metadata

    async def close(self) -> None:
        """Close the client."""
        await self.client.aclose()
