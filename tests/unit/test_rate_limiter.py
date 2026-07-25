"""Unit tests for backend.app.core.rate_limiter — sliding-window rate limiting."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.rate_limiter import RATE_LIMITS, RateLimiter, get_rate_limiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def limiter():
    """Fresh in-memory rate limiter (no Redis)."""
    return RateLimiter(redis_client=None)


@pytest.fixture()
def redis_limiter():
    """Rate limiter backed by a mock Redis client."""
    mock_redis = MagicMock()
    mock_redis.incr.return_value = 1
    return RateLimiter(redis_client=mock_redis), mock_redis


# ---------------------------------------------------------------------------
# Sliding window — local bucket
# ---------------------------------------------------------------------------


class TestSlidingWindowLocal:
    """Verify in-memory sliding window logic."""

    def test_allows_requests_under_limit(self, limiter: RateLimiter):
        """Requests under the limit should all be allowed."""
        for _ in range(5):
            assert limiter.is_allowed("user:1", max_requests=5, window_seconds=60) is True

    def test_blocks_when_limit_exceeded(self, limiter: RateLimiter):
        """The (limit+1)-th request within the window should be denied."""
        for _ in range(5):
            limiter.is_allowed("user:2", max_requests=5, window_seconds=60)
        assert limiter.is_allowed("user:2", max_requests=5, window_seconds=60) is False

    def test_window_expiry_allows_new_requests(self, limiter: RateLimiter):
        """After the window expires, requests should be allowed again."""
        for _ in range(3):
            limiter.is_allowed("user:3", max_requests=3, window_seconds=1)

        assert limiter.is_allowed("user:3", max_requests=3, window_seconds=1) is False

        # Simulate time passing beyond window
        limiter._local_buckets["user:3"] = [time.time() - 2]
        assert limiter.is_allowed("user:3", max_requests=3, window_seconds=1) is True

    def test_different_keys_are_independent(self, limiter: RateLimiter):
        """Different keys should have independent buckets."""
        for _ in range(5):
            limiter.is_allowed("ip:10.0.0.1", max_requests=5, window_seconds=60)
        # ip:10.0.0.1 is now exhausted
        assert limiter.is_allowed("ip:10.0.0.1", max_requests=5, window_seconds=60) is False
        # ip:10.0.0.2 should still be fine
        assert limiter.is_allowed("ip:10.0.0.2", max_requests=5, window_seconds=60) is True


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class TestRedisBackend:
    """Verify Redis-backed rate limiting."""

    def test_redis_incr_and_expire(self, redis_limiter):
        limiter, mock_redis = redis_limiter
        mock_redis.incr.return_value = 1
        assert limiter.is_allowed("k", max_requests=10, window_seconds=60) is True
        mock_redis.incr.assert_called_once_with("ratelimit:k")
        mock_redis.expire.assert_called_once_with("ratelimit:k", 60)

    def test_redis_over_limit(self, redis_limiter):
        limiter, mock_redis = redis_limiter
        mock_redis.incr.return_value = 11
        assert limiter.is_allowed("k", max_requests=10, window_seconds=60) is False

    def test_redis_error_falls_back_to_local(self, redis_limiter):
        limiter, mock_redis = redis_limiter
        mock_redis.incr.side_effect = ConnectionError("Redis down")
        # Should fall back to local and allow
        assert limiter.is_allowed("fallback_key", max_requests=5, window_seconds=60) is True


# ---------------------------------------------------------------------------
# check_and_raise — 429 behaviour
# ---------------------------------------------------------------------------


class TestCheckAndRaise:
    """Verify that check_and_raise raises a 429 error when limit exceeded."""

    def test_no_error_under_limit(self, limiter: RateLimiter):
        """Should not raise when under limit."""
        limiter.check_and_raise("ok_key", max_requests=10, window_seconds=60)

    def test_raises_429_when_exceeded(self, limiter: RateLimiter):
        """Should raise XAgentAPIError with status 429 when limit exceeded."""
        for _ in range(5):
            limiter.is_allowed("strict_key", max_requests=5, window_seconds=60)

        from backend.app.api.errors import XAgentAPIError

        with pytest.raises(XAgentAPIError) as exc_info:
            limiter.check_and_raise("strict_key", max_requests=5, window_seconds=60)
        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# Auth routes have stricter limits
# ---------------------------------------------------------------------------


class TestAuthRouteLimits:
    """Verify predefined auth rate limits are stricter than general API."""

    def test_auth_login_stricter_than_general(self):
        assert RATE_LIMITS["auth_login"]["max_requests"] < RATE_LIMITS["general_api"]["max_requests"]

    def test_auth_register_stricter_than_general(self):
        assert RATE_LIMITS["auth_register"]["max_requests"] < RATE_LIMITS["general_api"]["max_requests"]

    def test_auth_login_limit_is_5_per_15min(self):
        cfg = RATE_LIMITS["auth_login"]
        assert cfg["max_requests"] == 5
        assert cfg["window_seconds"] == 900

    def test_auth_register_limit_is_3_per_hour(self):
        cfg = RATE_LIMITS["auth_register"]
        assert cfg["max_requests"] == 3
        assert cfg["window_seconds"] == 3600


# ---------------------------------------------------------------------------
# Singleton getter
# ---------------------------------------------------------------------------


class TestGetRateLimiter:
    def test_returns_singleton(self):
        import backend.app.core.rate_limiter as rl_module

        rl_module._rate_limiter = None  # reset
        a = get_rate_limiter()
        b = get_rate_limiter()
        assert a is b
        rl_module._rate_limiter = None  # cleanup
