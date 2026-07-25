"""Rate limiting implementation for API endpoints.

SECURITY: Implements distributed rate limiting to prevent brute force attacks
and DoS attacks.
"""

import time

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode


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


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter(redis_client=None) -> RateLimiter:
    """Get or create global rate limiter instance.

    Args:
        redis_client: Optional Redis client

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(redis_client)
    return _rate_limiter


# Predefined rate limit configurations
RATE_LIMITS = {
    "auth_login": {"max_requests": 5, "window_seconds": 900},  # 5 per 15 min
    "auth_register": {"max_requests": 3, "window_seconds": 3600},  # 3 per hour
    "api_key_create": {"max_requests": 10, "window_seconds": 3600},  # 10 per hour
    "general_api": {"max_requests": 100, "window_seconds": 60},  # 100 per minute
    "search": {"max_requests": 30, "window_seconds": 60},  # 30 per minute
}
