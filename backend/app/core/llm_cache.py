"""LLM response caching integration.

Caches LLM responses to reduce API calls and improve performance.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.app.core.cache import get_cache_manager
from backend.app.core.llm import LLMResponse

logger = logging.getLogger(__name__)

# Cache TTLs for different operations
LLM_RESPONSE_TTL = 3600  # 1 hour
LLM_EMBEDDING_TTL = 86400  # 24 hours


def _make_llm_response_cache_key(
    messages: list[dict[str, str]],
    model: str,
    temperature: float = 0.7,
) -> str:
    """Generate cache key for LLM response."""
    # Create a deterministic key from messages and model
    messages_str = str(sorted((m["role"], m["content"]) for m in messages))
    key_parts = [
        "llm:response",
        model,
        str(temperature),
        messages_str,
    ]
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def _make_embedding_cache_key(text: str, model: str) -> str:
    """Generate cache key for embedding."""
    key_parts = ["llm:embedding", model, text]
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


async def get_cached_llm_response(
    messages: list[dict[str, str]],
    model: str,
    temperature: float = 0.7,
) -> LLMResponse | None:
    """Get cached LLM response."""
    cache = get_cache_manager()
    key = _make_llm_response_cache_key(messages, model, temperature)
    cached = await cache.get(key)
    if cached:
        return LLMResponse(**cached)
    return None


async def cache_llm_response(
    messages: list[dict[str, str]],
    response: LLMResponse,
    model: str,
    temperature: float = 0.7,
) -> None:
    """Cache LLM response."""
    cache = get_cache_manager()
    key = _make_llm_response_cache_key(messages, model, temperature)
    await cache.set(key, response.__dict__, ttl=LLM_RESPONSE_TTL)


async def get_cached_embedding(text: str, model: str) -> list[float] | None:
    """Get cached embedding."""
    cache = get_cache_manager()
    key = _make_embedding_cache_key(text, model)
    return await cache.get(key)


async def cache_embedding(text: str, embedding: list[float], model: str) -> None:
    """Cache embedding."""
    cache = get_cache_manager()
    key = _make_embedding_cache_key(text, model)
    await cache.set(key, embedding, ttl=LLM_EMBEDDING_TTL)


async def invalidate_llm_cache(pattern: str = "llm:response:*") -> None:
    """Invalidate LLM response cache."""
    cache = get_cache_manager()
    await cache.invalidate_pattern(pattern)


async def invalidate_embedding_cache(pattern: str = "llm:embedding:*") -> None:
    """Invalidate embedding cache."""
    cache = get_cache_manager()
    await cache.invalidate_pattern(pattern)
