"""Rate limiting implementation for API endpoints.

SECURITY: Implements distributed rate limiting to prevent brute force attacks
and DoS attacks.
"""

import time
from dataclasses import dataclass
from typing import Optional

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode


@dataclass
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed
        remaining: Number of requests remaining in the window
        reset_at: Unix timestamp when the window resets
        limit: Total limit for the window
    """
    allowed: bool
    remaining: int
    reset_at: int
    limit: int


class RateLimiter:
    """In-memory rate limiter with optional Redis backend."""

    def __init__(self, redis_client=None):
        """Initialize rate limiter.

        Args:
            redis_client: Optional Redis client for distributed rate limiting
        """
        self.redis_client = redis_client
        self._local_buckets: dict[str, list[float]] = {}

    def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (e.g., user_id, IP address)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()

        if self.redis_client:
            return self._check_redis(key, max_requests, window_seconds, now)
        else:
            return self._check_local(key, max_requests, window_seconds, now)

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit and return detailed result.

        Args:
            key: Rate limit key
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            RateLimitResult with detailed rate limit information
        """
        now = time.time()

        if self.redis_client:
            return self._check_redis_detailed(key, limit, window_seconds, now)
        else:
            return self._check_local_detailed(key, limit, window_seconds, now)

    def _check_redis(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float,
    ) -> bool:
        """Check rate limit using Redis.

        Args:
            key: Rate limit key
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            now: Current timestamp

        Returns:
            True if allowed, False if rate limited
        """
        try:
            redis_key = f"ratelimit:{key}"
            current = self.redis_client.incr(redis_key)

            if current == 1:
                # First request in window, set expiration
                self.redis_client.expire(redis_key, window_seconds)

            return current <= max_requests

        except Exception:
            # Fall back to local limiting on Redis error
            return self._check_local(key, max_requests, window_seconds, now)

    def _check_local(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        now: float,
    ) -> bool:
        """Check rate limit using local in-memory storage.

        Args:
            key: Rate limit key
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            now: Current timestamp

        Returns:
            True if allowed, False if rate limited
        """
        if key not in self._local_buckets:
            self._local_buckets[key] = []

        # Remove old requests outside the window
        bucket = self._local_buckets[key]
        bucket[:] = [ts for ts in bucket if now - ts < window_seconds]

        if len(bucket) < max_requests:
            bucket.append(now)
            return True

        return False

    def _check_redis_detailed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        now: float,
    ) -> RateLimitResult:
        """Check rate limit using Redis with detailed result.

        Uses a sliding window counter implemented with Redis sorted sets.
        Algorithm:
        1. Remove entries older than window
        2. Count remaining entries
        3. If under limit, add new entry with current timestamp
        4. Return result with remaining/reset info

        Args:
            key: Rate limit key
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds
            now: Current timestamp

        Returns:
            RateLimitResult with detailed rate limit information
        """
        try:
            redis_key = f"ratelimit:zset:{key}"
            window_start = now - window_seconds

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window_seconds)
            results = pipe.execute()

            current_count = results[1]
            allowed = current_count < limit
            remaining = max(0, limit - current_count - 1) if allowed else 0
            reset_at = int(now + window_seconds)

            if not allowed:
                # Remove the entry we just added since rate limit exceeded
                self.redis_client.zrem(redis_key, str(now))

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                limit=limit,
            )

        except Exception:
            # Fall back to local limiting on Redis error
            return self._check_local_detailed(key, limit, window_seconds, now)

    def _check_local_detailed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        now: float,
    ) -> RateLimitResult:
        """Check rate limit using local in-memory storage with detailed result.

        Args:
            key: Rate limit key
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds
            now: Current timestamp

        Returns:
            RateLimitResult with detailed rate limit information
        """
        if key not in self._local_buckets:
            self._local_buckets[key] = []

        # Remove old requests outside the window
        bucket = self._local_buckets[key]
        bucket[:] = [ts for ts in bucket if now - ts < window_seconds]

        allowed = len(bucket) < limit
        if allowed:
            bucket.append(now)

        remaining = max(0, limit - len(bucket))
        reset_at = int(now + window_seconds)

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            limit=limit,
        )

    def check_and_raise(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        error_message: str = "Rate limit exceeded",
    ) -> None:
        """Check rate limit and raise error if exceeded.

        Args:
            key: Rate limit key
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            error_message: Error message to return

        Raises:
            api_error: If rate limit exceeded
        """
        if not self.is_allowed(key, max_requests, window_seconds):
            raise api_error(
                429,
                ErrorCode.VALIDATION_ERROR,
                error_message,
                details={
                    "max_requests": max_requests,
                    "window_seconds": window_seconds,
                },
            )


class RedisRateLimiter(RateLimiter):
    """Redis-backed rate limiter for distributed deployments.

    Uses Redis sorted sets for sliding window counter implementation,
    enabling distributed rate limiting across multiple instances.
    """

    def __init__(self, redis_url: str):
        """Initialize Redis rate limiter.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
        """
        import redis.asyncio as aioredis
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        super().__init__(redis_client=None)  # Will use self.redis directly

    async def check_rate_limit_async(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check rate limit asynchronously using Redis.

        Uses sliding window counter with sorted sets.

        Args:
            key: Rate limit key
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            RateLimitResult with detailed rate limit information
        """
        now = time.time()
        redis_key = f"ratelimit:zset:{key}"
        window_start = now - window_seconds

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {str(now): now})
        pipe.expire(redis_key, window_seconds)
        results = await pipe.execute()

        current_count = results[1]
        allowed = current_count < limit
        remaining = max(0, limit - current_count - 1) if allowed else 0
        reset_at = int(now + window_seconds)

        if not allowed:
            # Remove the entry we just added since rate limit exceeded
            await self.redis.zrem(redis_key, str(now))

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            limit=limit,
        )

    async def close(self) -> None:
        """Close Redis connection.

        Should be called during application shutdown.
        """
        if self.redis:
            await self.redis.close()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(redis_url: str | None = None) -> RateLimiter:
    """Get or create global rate limiter instance.

    Provides factory selection between Redis-backed and in-memory limiters.
    In-memory limiter is used by default, but Redis is preferred for
    distributed deployments.

    Args:
        redis_url: Optional Redis URL. If provided, returns RedisRateLimiter;
                   otherwise returns in-memory RateLimiter.

    Returns:
        Appropriate RateLimiter instance (Redis-backed or in-memory)
    """
    if redis_url:
        return RedisRateLimiter(redis_url)
    return RateLimiter()


# Predefined rate limit configurations
RATE_LIMITS = {
    "auth_login": {"max_requests": 5, "window_seconds": 900},  # 5 per 15 min
    "auth_register": {"max_requests": 3, "window_seconds": 3600},  # 3 per hour
    "api_key_create": {"max_requests": 10, "window_seconds": 3600},  # 10 per hour
    "general_api": {"max_requests": 100, "window_seconds": 60},  # 100 per minute
    "search": {"max_requests": 30, "window_seconds": 60},  # 30 per minute
}
