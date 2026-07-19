"""Search result parsing and content extraction."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel

from backend.app.services.search.search_engine import SearchResult, SearchResponse


class ParsedContent(BaseModel):
    """Parsed content from search result."""
    title: str
    url: str
    domain: str
    snippet: str
    content_type: str  # "article", "news", "product", "documentation", etc.
    relevance_score: float  # 0-1
    key_entities: list[str]  # Named entities found in snippet
    metadata: dict


class SearchResultParser:
    """Parse and enrich search results."""

    # Content type patterns
    PATTERNS = {
        "news": r"(news|breaking|latest|update|report|announced?)",
        "product": r"(product|buy|price|shop|store|amazon|ebay)",
        "documentation": r"(docs?|documentation|guide|tutorial|reference|api)",
        "academic": r"(research|paper|study|journal|conference|arxiv)",
        "social": r"(twitter|facebook|reddit|instagram|linkedin|tiktok)",
        "video": r"(youtube|video|watch|stream|vimeo)",
    }

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain
        except Exception:
            return ""

    @staticmethod
    def extract_entities(text: str) -> list[str]:
        """Extract potential named entities from text."""
        # Simple entity extraction using capitalization patterns
        words = text.split()
        entities = []

        for i, word in enumerate(words):
            # Look for capitalized words (potential proper nouns)
            if word and word[0].isupper() and len(word) > 2:
                # Avoid common words
                if word not in {"The", "A", "An", "In", "On", "At", "By", "For"}:
                    entities.append(word.rstrip(".,;:!?"))

        return list(set(entities))[:10]  # Return top 10 unique entities

    @classmethod
    def detect_content_type(cls, title: str, snippet: str) -> str:
        """Detect content type from title and snippet."""
        combined = f"{title} {snippet}".lower()

        for content_type, pattern in cls.PATTERNS.items():
            if re.search(pattern, combined):
                return content_type

        return "general"

    @classmethod
    def calculate_relevance(
        cls,
        query: str,
        title: str,
        snippet: str,
    ) -> float:
        """Calculate relevance score (0-1) for result."""
        query_terms = set(query.lower().split())
        combined = f"{title} {snippet}".lower()

        # Count query term matches
        matches = sum(1 for term in query_terms if term in combined)
        base_score = min(matches / len(query_terms), 1.0) if query_terms else 0.5

        # Boost for exact phrase match
        if query.lower() in combined:
            base_score = min(base_score + 0.2, 1.0)

        # Boost for title match
        if query.lower() in title.lower():
            base_score = min(base_score + 0.1, 1.0)

        return base_score

    @classmethod
    def parse_result(
        cls,
        result: SearchResult,
        query: str,
    ) -> ParsedContent:
        """Parse and enrich a single search result.

        Args:
            result: SearchResult to parse
            query: Original search query

        Returns:
            ParsedContent with enriched information
        """
        domain = cls.extract_domain(result.url)
        content_type = cls.detect_content_type(result.title, result.snippet)
        relevance = cls.calculate_relevance(query, result.title, result.snippet)
        entities = cls.extract_entities(result.snippet)

        return ParsedContent(
            title=result.title,
            url=result.url,
            domain=domain,
            snippet=result.snippet,
            content_type=content_type,
            relevance_score=relevance,
            key_entities=entities,
            metadata={
                "position": result.position,
                "source": result.source,
                "date": result.date,
                **result.metadata,
            },
        )

    @classmethod
    def parse_response(
        cls,
        response: SearchResponse,
    ) -> list[ParsedContent]:
        """Parse all results in a search response.

        Args:
            response: SearchResponse to parse

        Returns:
            List of ParsedContent sorted by relevance
        """
        parsed = [
            cls.parse_result(result, response.query)
            for result in response.results
        ]

        # Sort by relevance score descending
        parsed.sort(key=lambda x: x.relevance_score, reverse=True)

        return parsed

    @staticmethod
    def clean_snippet(snippet: str, max_length: int = 500) -> str:
        """Clean and truncate snippet.

        Args:
            snippet: Raw snippet text
            max_length: Maximum length

        Returns:
            Cleaned snippet
        """
        # Remove extra whitespace
        cleaned = " ".join(snippet.split())

        # Truncate with ellipsis if needed
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].rsplit(" ", 1)[0] + "..."

        return cleaned

    @staticmethod
    def format_for_display(parsed: ParsedContent) -> dict:
        """Format parsed content for display.

        Args:
            parsed: ParsedContent to format

        Returns:
            Display-ready dictionary
        """
        return {
            "title": parsed.title,
            "url": parsed.url,
            "domain": parsed.domain,
            "snippet": parsed.snippet,
            "type": parsed.content_type,
            "relevance": f"{parsed.relevance_score:.1%}",
            "entities": parsed.key_entities,
            "date": parsed.metadata.get("date"),
        }
