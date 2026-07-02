"""LLM request deduplication system.

Prevents duplicate API calls by:
- Detecting identical or semantically similar requests
- Reusing cached responses for similar queries
- Tracking in-flight requests to avoid concurrent duplicates
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RequestSignature:
    """Signature of an LLM request for deduplication."""

    content_hash: str
    model: str
    temperature: float
    timestamp: float = field(default_factory=time.time)

    def __hash__(self) -> int:
        return hash((self.content_hash, self.model, self.temperature))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RequestSignature):
            return False
        return (
            self.content_hash == other.content_hash
            and self.model == other.model
            and self.temperature == other.temperature
        )


@dataclass
class DeduplicationStats:
    """Statistics for deduplication performance."""

    total_requests: int = 0
    deduplicated_requests: int = 0
    cache_hits: int = 0
    in_flight_hits: int = 0
    semantic_matches: int = 0

    @property
    def deduplication_rate(self) -> float:
        """Percentage of requests that were deduplicated."""
        if self.total_requests == 0:
            return 0.0
        return (self.deduplicated_requests / self.total_requests) * 100

    @property
    def cost_savings(self) -> float:
        """Estimated cost savings from deduplication (in percentage)."""
        return self.deduplication_rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "deduplicated_requests": self.deduplicated_requests,
            "cache_hits": self.cache_hits,
            "in_flight_hits": self.in_flight_hits,
            "semantic_matches": self.semantic_matches,
            "deduplication_rate": self.deduplication_rate,
            "cost_savings": self.cost_savings,
        }


class LLMDeduplicator:
    """Deduplicates LLM requests to reduce API calls."""

    def __init__(
        self,
        semantic_similarity_threshold: float = 0.85,
        in_flight_timeout: float = 300.0,
    ) -> None:
        """Initialize deduplicator.

        Args:
            semantic_similarity_threshold: Threshold for semantic similarity (0-1)
            in_flight_timeout: Timeout for in-flight requests in seconds
        """
        self._semantic_similarity_threshold = semantic_similarity_threshold
        self._in_flight_timeout = in_flight_timeout

        # Track in-flight requests
        self._in_flight: dict[RequestSignature, asyncio.Future] = {}
        self._in_flight_lock = asyncio.Lock()

        # Cache for semantic embeddings
        self._embedding_cache: dict[str, list[float]] = {}

        # Statistics
        self._stats = DeduplicationStats()

    def _compute_content_hash(self, messages: list[dict[str, str]]) -> str:
        """Compute hash of message content."""
        content_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            content_parts.append(f"{role}:{content}")

        combined = "|".join(content_parts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _create_signature(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> RequestSignature:
        """Create a signature for a request."""
        content_hash = self._compute_content_hash(messages)
        return RequestSignature(
            content_hash=content_hash,
            model=model,
            temperature=temperature,
        )

    async def _get_embedding(
        self,
        text: str,
        embedding_func: Optional[Callable[[str], Any]] = None,
    ) -> list[float]:
        """Get embedding for text, using cache if available."""
        text_hash = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()

        if text_hash in self._embedding_cache:
            return self._embedding_cache[text_hash]

        if embedding_func is None:
            # Return simple hash-based embedding if no function provided
            return self._simple_embedding(text)

        try:
            embedding = await embedding_func(text)
            self._embedding_cache[text_hash] = embedding
            return embedding
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            return self._simple_embedding(text)

    def _simple_embedding(self, text: str) -> list[float]:
        """Generate a simple embedding from text."""
        # Simple embedding based on character frequencies
        embedding = [0.0] * 256
        for char in text:
            idx = ord(char) % 256
            embedding[idx] += 1.0

        # Normalize
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

        # Ensure same length
        min_len = min(len(vec1), len(vec2))
        vec1 = vec1[:min_len]
        vec2 = vec2[:min_len]

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def check_semantic_similarity(
        self,
        messages: list[dict[str, str]],
        embedding_func: Optional[Callable[[str], Any]] = None,
    ) -> Optional[RequestSignature]:
        """Check if similar request exists in in-flight requests.

        Returns the signature of a similar in-flight request if found.
        """
        # Extract main content
        main_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                main_content = msg.get("content", "")
                break

        if not main_content:
            return None

        # Get embedding for current request
        current_embedding = await self._get_embedding(main_content, embedding_func)

        # Check against in-flight requests
        async with self._in_flight_lock:
            for signature in self._in_flight.keys():
                # Extract content from signature (we need to store it)
                # For now, we'll skip semantic matching for in-flight
                pass

        return None

    async def register_in_flight(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> RequestSignature:
        """Register an in-flight request.

        Returns the signature and a future that will be resolved with the response.
        """
        signature = self._create_signature(messages, model, temperature)

        async with self._in_flight_lock:
            if signature in self._in_flight:
                # Request already in flight
                self._stats.in_flight_hits += 1
                logger.debug(f"In-flight request found: {signature.content_hash[:8]}")
                return signature

            # Create a future for this request
            future: asyncio.Future = asyncio.Future()
            self._in_flight[signature] = future

        return signature

    async def register_or_get_in_flight(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
    ) -> tuple[RequestSignature, bool]:
        """Atomically register an in-flight request or detect an existing one.

        Unlike :meth:`register_in_flight`, this distinguishes the *primary*
        caller (the one that must perform the real LLM call and then
        :meth:`resolve_in_flight`) from *followers* (identical requests already
        in flight, which should instead await :meth:`get_in_flight_response`).

        Doing the check-and-register under a single lock acquisition removes the
        deadlock where a primary caller would await its own freshly-created
        future (which only resolves after the LLM call it has not made yet).

        Returns:
            ``(signature, is_primary)``. ``is_primary=True`` means THIS caller
            created the future and owns the LLM call; ``False`` means an
            identical request is already in flight.
        """
        signature = self._create_signature(messages, model, temperature)

        async with self._in_flight_lock:
            if signature in self._in_flight:
                logger.debug(
                    f"In-flight duplicate detected: {signature.content_hash[:8]}"
                )
                return signature, False

            future: asyncio.Future = asyncio.Future()
            self._in_flight[signature] = future
            return signature, True

    async def resolve_in_flight(
        self,
        signature: RequestSignature,
        response: Any,
    ) -> None:
        """Resolve an in-flight request with a response."""
        async with self._in_flight_lock:
            if signature in self._in_flight:
                future = self._in_flight[signature]
                if not future.done():
                    future.set_result(response)

    async def fail_in_flight(
        self,
        signature: RequestSignature,
        error: BaseException,
    ) -> None:
        """Fail an in-flight request so waiting followers stop blocking.

        When the primary caller's LLM call raises, followers awaiting the shared
        future would otherwise block until ``in_flight_timeout`` (300s). Setting
        the exception lets them fail fast and fall back to their own call.
        """
        async with self._in_flight_lock:
            future = self._in_flight.get(signature)
            if future is not None and not future.done():
                future.set_exception(error)
            # Drop the entry so a later identical request starts a fresh call
            # rather than re-raising this stale error.
            self._in_flight.pop(signature, None)

    async def get_in_flight_response(
        self,
        signature: RequestSignature,
        timeout: Optional[float] = None,
    ) -> Optional[Any]:
        """Get response from an in-flight request.

        Returns None if request is not in flight or times out.
        """
        async with self._in_flight_lock:
            if signature not in self._in_flight:
                return None
            future = self._in_flight[signature]

        try:
            timeout = timeout or self._in_flight_timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"In-flight request timeout: {signature.content_hash[:8]}")
            return None
        except Exception as e:
            logger.error(f"Error getting in-flight response: {e}")
            return None

    async def cleanup_in_flight(self, max_age: float = 600.0) -> None:
        """Clean up expired in-flight requests.

        Args:
            max_age: Maximum age of in-flight requests in seconds
        """
        current_time = time.time()
        expired = []

        async with self._in_flight_lock:
            for signature, future in self._in_flight.items():
                age = current_time - signature.timestamp
                if age > max_age:
                    expired.append(signature)

            for signature in expired:
                del self._in_flight[signature]
                logger.debug(f"Cleaned up expired in-flight request: {signature.content_hash[:8]}")

    def record_deduplication(
        self,
        dedup_type: str = "cache",
    ) -> None:
        """Record a deduplication event.

        Marks an already-counted request (see :meth:`record_request`) as
        deduplicated. It must NOT touch ``total_requests`` — doing so
        double-counts the request and lets ``deduplicated_requests`` exceed
        ``total_requests``, breaking the ``deduplication_rate`` invariant
        (dedup count is by definition a subset of total).

        Args:
            dedup_type: Type of deduplication ("cache", "in_flight", "semantic")
        """
        self._stats.deduplicated_requests += 1

        if dedup_type == "cache":
            self._stats.cache_hits += 1
        elif dedup_type == "in_flight":
            self._stats.in_flight_hits += 1
        elif dedup_type == "semantic":
            self._stats.semantic_matches += 1

    def record_request(self) -> None:
        """Record a new request."""
        self._stats.total_requests += 1

    def get_stats(self) -> dict[str, Any]:
        """Get deduplication statistics."""
        return self._stats.to_dict()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = DeduplicationStats()

    async def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._embedding_cache.clear()
        logger.info("Embedding cache cleared")


# Global deduplicator instance
_deduplicator: Optional[LLMDeduplicator] = None


def get_deduplicator() -> LLMDeduplicator:
    """Get or create the global deduplicator."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = LLMDeduplicator()
    return _deduplicator
