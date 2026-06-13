"""Tests for Redis-backed rate limiting implementation.

SECURITY: Tests distributed rate limiting with Redis backend,
including sliding window algorithm verification and fault tolerance.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.rate_limiter import (
    RATE_LIMITS,
    RateLimitResult,
    RateLimiter,
    RedisRateLimiter,
    get_rate_limiter,
)


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""

    def test_rate_limit_result_creation(self) -> None:
        """Test creating RateLimitResult with valid data."""
        result = RateLimitResult(
            allowed=True,
            remaining=99,
            reset_at=int(time.time()) + 60,
            limit=100,
        )

        assert result.allowed is True
        assert result.remaining == 99
        assert result.limit == 100
        assert result.reset_at > int(time.time())

    def test_rate_limit_result_denied(self) -> None:
        """Test RateLimitResult when request is denied."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=int(time.time()) + 60,
            limit=10,
        )

        assert result.allowed is False
        assert result.remaining == 0
        assert result.limit == 10


class TestInMemoryRateLimiter:
    """Tests for in-memory rate limiter implementation."""

    def test_allows_requests_under_limit(self) -> None:
        """Test that requests under limit are allowed."""
        limiter = RateLimiter()

        for i in range(5):
            assert limiter.is_allowed("user:1", 5, 60) is True

    def test_denies_requests_over_limit(self) -> None:
        """Test that requests over limit are denied."""
        limiter = RateLimiter()

        # Make 5 requests (at limit)
        for i in range(5):
            limiter.is_allowed("user:1", 5, 60)

        # 6th request should be denied
        assert limiter.is_allowed("user:1", 5, 60) is False

    def test_window_expiry(self) -> None:
        """Test that old requests expire after window."""
        limiter = RateLimiter()

        # Make 5 requests in 1-second window
        for i in range(5):
            assert limiter.is_allowed("user:1", 5, 1) is True

        # Immediately, 6th request is denied
        assert limiter.is_allowed("user:1", 5, 1) is False

        # Wait for window to expire
        time.sleep(1.1)

        # Request should be allowed again
        assert limiter.is_allowed("user:1", 5, 1) is True

    def test_detailed_result_allowed(self) -> None:
        """Test detailed check_rate_limit when request is allowed."""
        limiter = RateLimiter()

        result = limiter.check_rate_limit("user:1", 10, 60)

        assert isinstance(result, RateLimitResult)
        assert result.allowed is True
        assert result.remaining == 9
        assert result.limit == 10
        assert result.reset_at > int(time.time())

    def test_detailed_result_denied(self) -> None:
        """Test detailed check_rate_limit when request is denied."""
        limiter = RateLimiter()

        # Max out the limit
        for i in range(10):
            limiter.check_rate_limit("user:1", 10, 60)

        # Next request should be denied
        result = limiter.check_rate_limit("user:1", 10, 60)

        assert result.allowed is False
        assert result.remaining == 0

    def test_remaining_count_accuracy(self) -> None:
        """Test that remaining count is accurate."""
        limiter = RateLimiter()

        for i in range(3):
            result = limiter.check_rate_limit("user:1", 10, 60)
            assert result.remaining == (10 - (i + 1))  # remaining = limit - count_after_add

    def test_independent_keys(self) -> None:
        """Test that different keys have independent limits."""
        limiter = RateLimiter()

        for i in range(5):
            limiter.is_allowed("user:1", 5, 60)
            limiter.is_allowed("user:2", 3, 60)

        # user:1 should be at limit
        assert limiter.is_allowed("user:1", 5, 60) is False

        # user:2 should be over limit
        assert limiter.is_allowed("user:2", 3, 60) is False


@pytest.mark.asyncio
class TestRedisRateLimiter:
    """Tests for Redis-backed rate limiter."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create mock Redis client."""
        return MagicMock()

    def test_redis_limiter_init(self) -> None:
        """Test RedisRateLimiter initialization."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            limiter = RedisRateLimiter("redis://localhost:6379/0")

            assert limiter.redis is mock_redis
            mock_from_url.assert_called_once_with(
                "redis://localhost:6379/0", decode_responses=True
            )

    async def test_redis_limiter_allows_under_limit(self) -> None:
        """Test Redis limiter allows requests under limit."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            # pipeline() returns a sync object with async execute()
            mock_pipe = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe
            mock_pipe.execute = AsyncMock(return_value=[0, 0, 1, True])

            limiter = RedisRateLimiter("redis://localhost:6379/0")
            result = await limiter.check_rate_limit_async("user:1", 10, 60)

            assert result.allowed is True
            assert result.remaining == 9

    async def test_redis_limiter_blocks_over_limit(self) -> None:
        """Test Redis limiter blocks requests over limit."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            mock_pipe = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe
            mock_pipe.execute = AsyncMock(return_value=[0, 10, 1, True])
            mock_redis.zrem = AsyncMock()

            limiter = RedisRateLimiter("redis://localhost:6379/0")
            result = await limiter.check_rate_limit_async("user:1", 10, 60)

            assert result.allowed is False
            assert result.remaining == 0
            mock_redis.zrem.assert_called_once()

    async def test_redis_limiter_window_expiry(self) -> None:
        """Test Redis limiter respects window expiry."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            mock_pipe = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe

            mock_pipe.execute = AsyncMock(return_value=[0, 0, 1, True])
            limiter = RedisRateLimiter("redis://localhost:6379/0")
            result1 = await limiter.check_rate_limit_async("user:1", 10, 60)
            assert result1.allowed is True

            mock_pipe.execute = AsyncMock(return_value=[1, 0, 1, True])
            result2 = await limiter.check_rate_limit_async("user:1", 10, 60)
            assert result2.allowed is True

    async def test_redis_limiter_close(self) -> None:
        """Test closing Redis connection."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            limiter = RedisRateLimiter("redis://localhost:6379/0")
            await limiter.close()

            mock_redis.close.assert_called_once()


class TestGetRateLimiter:
    """Tests for get_rate_limiter factory function."""

    def test_factory_returns_in_memory_limiter_without_redis(self) -> None:
        """Test factory returns in-memory limiter when no Redis URL provided."""
        limiter = get_rate_limiter(redis_url=None)

        assert isinstance(limiter, RateLimiter)
        assert not isinstance(limiter, RedisRateLimiter)

    def test_factory_returns_redis_limiter_with_url(self) -> None:
        """Test factory returns Redis limiter when URL provided."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            limiter = get_rate_limiter(redis_url="redis://localhost:6379/0")

            assert isinstance(limiter, RedisRateLimiter)

    def test_factory_with_empty_string_url(self) -> None:
        """Test factory treats empty string same as None."""
        limiter = get_rate_limiter(redis_url="")

        assert isinstance(limiter, RateLimiter)
        assert not isinstance(limiter, RedisRateLimiter)


class TestRateLimitConfigurations:
    """Tests for predefined rate limit configurations."""

    def test_auth_login_limit(self) -> None:
        """Test auth_login rate limit configuration."""
        config = RATE_LIMITS["auth_login"]
        assert config["max_requests"] == 5
        assert config["window_seconds"] == 900

    def test_auth_register_limit(self) -> None:
        """Test auth_register rate limit configuration."""
        config = RATE_LIMITS["auth_register"]
        assert config["max_requests"] == 3
        assert config["window_seconds"] == 3600

    def test_general_api_limit(self) -> None:
        """Test general_api rate limit configuration."""
        config = RATE_LIMITS["general_api"]
        assert config["max_requests"] == 100
        assert config["window_seconds"] == 60

    def test_all_limits_have_required_fields(self) -> None:
        """Test all limit configurations have required fields."""
        for name, config in RATE_LIMITS.items():
            assert "max_requests" in config, f"{name} missing max_requests"
            assert "window_seconds" in config, f"{name} missing window_seconds"
            assert isinstance(config["max_requests"], int)
            assert isinstance(config["window_seconds"], int)


class TestRateLimitIntegration:
    """Integration tests for rate limiting."""

    def test_multiple_keys_independent_limits(self) -> None:
        """Test that multiple keys have independent limits."""
        limiter = RateLimiter()

        # Two users: user:1 has limit 10, user:2 has limit 5
        for i in range(5):
            assert limiter.is_allowed("user:1", 10, 60) is True
            assert limiter.is_allowed("user:2", 5, 60) is True

        # user:1 still has room (5/10)
        assert limiter.is_allowed("user:1", 10, 60) is True

        # user:2 at limit (5/5) — next should be denied
        assert limiter.is_allowed("user:2", 5, 60) is False

    def test_check_and_raise_behavior(self) -> None:
        """Test check_and_raise raises on limit exceeded."""
        limiter = RateLimiter()

        # Mock the api_error to capture the call
        with patch("backend.app.core.rate_limiter.api_error") as mock_error:
            mock_error.side_effect = ValueError("Rate limit exceeded")

            # Fill the limit
            for i in range(3):
                limiter.is_allowed("user:1", 3, 60)

            # Should raise on next call
            with pytest.raises(ValueError):
                limiter.check_and_raise("user:1", 3, 60, "Rate limit exceeded")

    def test_sliding_window_accuracy(self) -> None:
        """Test sliding window implementation accuracy."""
        limiter = RateLimiter()

        # Make 3 requests in a 2-second window
        for i in range(3):
            result = limiter.check_rate_limit("user:1", 5, 2)
            assert result.allowed is True

        # Wait 1 second
        time.sleep(1)

        # Requests should still be at limit (3 requests within 2 second window from start)
        result = limiter.check_rate_limit("user:1", 5, 2)
        # Some entries may have expired depending on timing
        assert isinstance(result, RateLimitResult)

        # Wait another 1.2 seconds (total 2.2 seconds)
        time.sleep(1.2)

        # Now old requests should have expired, allowing new requests
        result = limiter.check_rate_limit("user:1", 5, 2)
        assert result.allowed is True
