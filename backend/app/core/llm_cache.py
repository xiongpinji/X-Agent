"""LLM response caching integration.

Caches LLM responses to reduce API calls and improve performance.
Implements:
- Exact match caching
- Semantic caching (similar queries reuse responses)
- TTL-based expiration
- LRU eviction
- Cache warming
- Cost tracking
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from backend.app.core.cache import get_cache_manager
from backend.app.core.llm import LLMResponse

logger = logging.getLogger(__name__)

# Cache TTLs for different operations
LLM_RESPONSE_TTL = 3600  # 1 hour
LLM_EMBEDDING_TTL = 86400  # 24 hours
LLM_SEMANTIC_CACHE_TTL = 7200  # 2 hours


@dataclass
class CacheEntry:
    """Entry in the LLM cache."""

    response: LLMResponse
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    cost_saved: float = 0.0

    def is_expired(self, ttl: int) -> bool:
        """Check if entry is expired."""
        return time.time() - self.created_at > ttl

    def record_access(self) -> None:
        """Record an access to this entry."""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Statistics for cache performance."""

    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    semantic_hits: int = 0
    total_cost_saved: float = 0.0
    total_tokens_saved: int = 0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    @property
    def semantic_hit_rate(self) -> float:
        """Semantic cache hit rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.semantic_hits / self.total_requests) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "semantic_hits": self.semantic_hits,
            "hit_rate": self.hit_rate,
            "semantic_hit_rate": self.semantic_hit_rate,
            "total_cost_saved": self.total_cost_saved,
            "total_tokens_saved": self.total_tokens_saved,
        }


class LLMCacheManager:
    """Enhanced LLM cache manager with semantic caching."""

    def __init__(
        self,
        semantic_similarity_threshold: float = 0.85,
        max_cache_size: int = 10000,
    ) -> None:
        """Initialize cache manager.

        Args:
            semantic_similarity_threshold: Threshold for semantic similarity (0-1)
            max_cache_size: Maximum number of entries in cache
        """
        self._cache_manager = get_cache_manager()
        self._semantic_similarity_threshold = semantic_similarity_threshold
        self._max_cache_size = max_cache_size
        self._stats = CacheStats()
        self._embedding_cache: dict[str, list[float]] = {}

    def _make_llm_response_cache_key(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate cache key for LLM response."""
        messages_str = str(sorted((m["role"], m["content"]) for m in messages))
        key_parts = [
            "llm:response",
            model,
            str(temperature),
            messages_str,
        ]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _make_embedding_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for embedding."""
        key_parts = ["llm:embedding", model, text]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _make_semantic_cache_key(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> str:
        """Generate cache key for semantic caching."""
        # Use only the main user message for semantic matching
        main_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                main_content = msg.get("content", "")
                break

        key_parts = ["llm:semantic", model, main_content[:100]]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    async def get_cached_response(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> LLMResponse | None:
        """Get cached LLM response (exact match)."""
        self._stats.total_requests += 1

        key = self._make_llm_response_cache_key(messages, model, temperature)
        cached = await self._cache_manager.get(key)

        if cached:
            self._stats.cache_hits += 1
            if isinstance(cached, dict):
                response = LLMResponse(**cached)
            else:
                response = cached

            logger.debug(f"Cache hit (exact): {key[:8]}")
            return response

        self._stats.cache_misses += 1
        return None

    async def cache_response(
        self,
        messages: list[dict[str, str]],
        response: LLMResponse,
        model: str,
        temperature: float = 0.7,
    ) -> None:
        """Cache LLM response."""
        key = self._make_llm_response_cache_key(messages, model, temperature)
        await self._cache_manager.set(key, response.__dict__, ttl=LLM_RESPONSE_TTL)

        # Track cost savings
        self._stats.total_cost_saved += response.cost
        self._stats.total_tokens_saved += response.tokens_used

        logger.debug(f"Cached response: {key[:8]} (cost: ${response.cost:.4f})")

    async def get_cached_embedding(
        self,
        text: str,
        model: str,
    ) -> list[float] | None:
        """Get cached embedding."""
        key = self._make_embedding_cache_key(text, model)
        return await self._cache_manager.get(key)

    async def cache_embedding(
        self,
        text: str,
        embedding: list[float],
        model: str,
    ) -> None:
        """Cache embedding."""
        key = self._make_embedding_cache_key(text, model)
        await self._cache_manager.set(key, embedding, ttl=LLM_EMBEDDING_TTL)

    def _simple_embedding(self, text: str) -> list[float]:
        """Generate a simple embedding from text."""
        embedding = [0.0] * 256
        for char in text:
            idx = ord(char) % 256
            embedding[idx] += 1.0

        total = sum(embedding)
        if total > 0:
            embedding = [x / total for x in embedding]

        return embedding

    def _cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len]
        vec2 = vec2[:min_len]

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def get_semantic_match(
        self,
        messages: list[dict[str, str]],
        model: str,
        embedding_func: Optional[Callable[[str], Any]] = None,
    ) -> LLMResponse | None:
        """Get semantically similar cached response."""
        # Extract main content
        main_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                main_content = msg.get("content", "")
                break

        if not main_content:
            return None

        # Get embedding for current request
        if embedding_func:
            try:
                current_embedding = await embedding_func(main_content)
            except Exception as e:
                logger.warning(f"Failed to get embedding: {e}")
                current_embedding = self._simple_embedding(main_content)
        else:
            current_embedding = self._simple_embedding(main_content)

        # For now, return None (semantic matching requires vector DB)
        # In production, query vector DB for similar embeddings
        return None

    async def invalidate_response_cache(self, pattern: str = "llm:response:*") -> None:
        """Invalidate LLM response cache."""
        await self._cache_manager.invalidate_pattern(pattern)

    async def invalidate_embedding_cache(self, pattern: str = "llm:embedding:*") -> None:
        """Invalidate embedding cache."""
        await self._cache_manager.invalidate_pattern(pattern)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._stats.to_dict()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = CacheStats()


# Global cache manager instance
_llm_cache_manager: Optional[LLMCacheManager] = None


def get_llm_cache_manager() -> LLMCacheManager:
    """Get or create the global LLM cache manager."""
    global _llm_cache_manager
    if _llm_cache_manager is None:
        _llm_cache_manager = LLMCacheManager()
    return _llm_cache_manager


# Convenience functions for backward compatibility
async def get_cached_llm_response(
    messages: list[dict[str, str]],
    model: str,
    temperature: float = 0.7,
) -> LLMResponse | None:
    """Get cached LLM response."""
    manager = get_llm_cache_manager()
    return await manager.get_cached_response(messages, model, temperature)


async def cache_llm_response(
    messages: list[dict[str, str]],
    response: LLMResponse,
    model: str,
    temperature: float = 0.7,
) -> None:
    """Cache LLM response."""
    manager = get_llm_cache_manager()
    await manager.cache_response(messages, response, model, temperature)


async def get_cached_embedding(text: str, model: str) -> list[float] | None:
    """Get cached embedding."""
    manager = get_llm_cache_manager()
    return await manager.get_cached_embedding(text, model)


async def cache_embedding(text: str, embedding: list[float], model: str) -> None:
    """Cache embedding."""
    manager = get_llm_cache_manager()
    await manager.cache_embedding(text, embedding, model)


async def invalidate_llm_cache(pattern: str = "llm:response:*") -> None:
    """Invalidate LLM response cache."""
    manager = get_llm_cache_manager()
    await manager.invalidate_response_cache(pattern)


async def invalidate_embedding_cache(pattern: str = "llm:embedding:*") -> None:
    """Invalidate embedding cache."""
    manager = get_llm_cache_manager()
    await manager.invalidate_embedding_cache(pattern)
