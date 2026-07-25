"""
Graceful degradation strategies for maintaining service availability.

Implements:
- Service degradation
- Cache-based fallback
- Default value fallback
- Feature flags
- Degradation policies
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DegradationLevel(StrEnum):
    """Degradation levels."""

    FULL_SERVICE = "full_service"
    REDUCED_FEATURES = "reduced_features"
    BASIC_FEATURES = "basic_features"
    MINIMAL_SERVICE = "minimal_service"
    UNAVAILABLE = "unavailable"


@dataclass
class DegradationConfig:
    """Degradation configuration."""

    enabled: bool = True
    level: DegradationLevel = DegradationLevel.FULL_SERVICE
    cache_ttl: int = 300
    default_values: dict[str, Any] = field(default_factory=dict)
    feature_flags: dict[str, bool] = field(default_factory=dict)


class ServiceDegradation:
    """Service degradation manager."""

    def __init__(self, config: DegradationConfig | None = None) -> None:
        self.config = config or DegradationConfig()
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get_degraded_response(
        self,
        key: str,
        default_value: Any = None,
    ) -> Any:
        """Get degraded response from cache or default."""
        async with self._lock:
            # Try cache first
            if key in self._cache:
                value, timestamp = self._cache[key]
                if asyncio.get_event_loop().time() - timestamp < self.config.cache_ttl:
                    logger.info(f"Using cached value for {key}")
                    return value

            # Try default values
            if key in self.config.default_values:
                logger.info(f"Using default value for {key}")
                return self.config.default_values[key]

            # Use provided default
            if default_value is not None:
                logger.info(f"Using provided default for {key}")
                return default_value

            return None

    async def cache_value(self, key: str, value: Any) -> None:
        """Cache a value for degradation."""
        async with self._lock:
            self._cache[key] = (value, asyncio.get_event_loop().time())

    async def set_degradation_level(self, level: DegradationLevel) -> None:
        """Set degradation level."""
        async with self._lock:
            self.config.level = level
            logger.warning(f"Degradation level set to: {level.value}")

    def get_degradation_level(self) -> DegradationLevel:
        """Get current degradation level."""
        return self.config.level

    async def clear_cache(self) -> None:
        """Clear degradation cache."""
        async with self._lock:
            self._cache.clear()


class CacheFallback:
    """Cache-based fallback strategy."""

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[..., Any],
        *args: Any,
        use_stale: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Get value from cache or fetch fresh."""
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                elapsed = asyncio.get_event_loop().time() - timestamp

                if elapsed < self.ttl:
                    logger.debug(f"Cache hit for {key}")
                    return value

                if use_stale:
                    logger.warning(f"Using stale cache for {key} (age: {elapsed:.1f}s)")
                    return value

        # Fetch fresh value
        try:
            if asyncio.iscoroutinefunction(fetch_func):
                value = await fetch_func(*args, **kwargs)
            else:
                value = fetch_func(*args, **kwargs)

            async with self._lock:
                self._cache[key] = (value, asyncio.get_event_loop().time())

            return value

        except Exception as e:
            logger.error(f"Fetch failed for {key}: {e}")

            # Try to return stale cache
            async with self._lock:
                if key in self._cache:
                    value, _ = self._cache[key]
                    logger.warning(f"Returning stale cache for {key} after fetch failure")
                    return value

            raise

    async def clear_cache(self) -> None:
        """Clear cache."""
        async with self._lock:
            self._cache.clear()


class DefaultValueFallback:
    """Default value fallback strategy."""

    def __init__(self, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}

    async def get_with_default(
        self,
        key: str,
        fetch_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Get value with default fallback."""
        try:
            if asyncio.iscoroutinefunction(fetch_func):
                return await fetch_func(*args, **kwargs)
            else:
                return fetch_func(*args, **kwargs)

        except Exception as e:
            logger.error(f"Fetch failed for {key}: {e}")

            if key in self.defaults:
                logger.warning(f"Using default value for {key}")
                return self.defaults[key]

            raise

    def set_default(self, key: str, value: Any) -> None:
        """Set default value."""
        self.defaults[key] = value

    def get_default(self, key: str) -> Any | None:
        """Get default value."""
        return self.defaults.get(key)


class FeatureFlag:
    """Feature flag for controlled degradation."""

    def __init__(self, name: str, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled

    async def is_enabled(self) -> bool:
        """Check if feature is enabled."""
        return self.enabled

    async def enable(self) -> None:
        """Enable feature."""
        self.enabled = True
        logger.info(f"Feature '{self.name}' enabled")

    async def disable(self) -> None:
        """Disable feature."""
        self.enabled = False
        logger.warning(f"Feature '{self.name}' disabled")

    async def execute_if_enabled(
        self,
        func: Callable[..., Any],
        *args: Any,
        fallback: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute function if feature is enabled."""
        if not self.enabled:
            logger.debug(f"Feature '{self.name}' is disabled, using fallback")
            if fallback:
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                else:
                    return fallback(*args, **kwargs)
            return None

        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


class FeatureFlagRegistry:
    """Registry for managing feature flags."""

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()

    async def register(self, name: str, enabled: bool = True) -> FeatureFlag:
        """Register a feature flag."""
        async with self._lock:
            if name not in self._flags:
                self._flags[name] = FeatureFlag(name, enabled)
            return self._flags[name]

    async def get(self, name: str) -> FeatureFlag | None:
        """Get a feature flag."""
        async with self._lock:
            return self._flags.get(name)

    async def enable(self, name: str) -> None:
        """Enable a feature."""
        flag = await self.get(name)
        if flag:
            await flag.enable()

    async def disable(self, name: str) -> None:
        """Disable a feature."""
        flag = await self.get(name)
        if flag:
            await flag.disable()

    async def get_all_flags(self) -> dict[str, bool]:
        """Get all feature flags."""
        async with self._lock:
            return {name: flag.enabled for name, flag in self._flags.items()}


class DegradationPolicy:
    """Policy for graceful degradation."""

    def __init__(self) -> None:
        self.service_degradation = ServiceDegradation()
        self.cache_fallback = CacheFallback()
        self.default_fallback = DefaultValueFallback()
        self.feature_flags = FeatureFlagRegistry()

    async def apply_degradation(
        self,
        key: str,
        fetch_func: Callable[..., Any],
        *args: Any,
        use_cache: bool = True,
        use_default: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Apply degradation policy."""
        # Try cache first
        if use_cache:
            try:
                return await self.cache_fallback.get_or_fetch(
                    key, fetch_func, *args, **kwargs
                )
            except Exception as e:
                logger.warning(f"Cache fallback failed: {e}")

        # Try default value
        if use_default:
            try:
                return await self.default_fallback.get_with_default(
                    key, fetch_func, *args, **kwargs
                )
            except Exception as e:
                logger.warning(f"Default fallback failed: {e}")

        # Last resort
        raise RuntimeError(f"All degradation strategies failed for {key}")


# Global degradation policy
_degradation_policy: DegradationPolicy | None = None


def get_degradation_policy() -> DegradationPolicy:
    """Get or create the global degradation policy."""
    global _degradation_policy
    if _degradation_policy is None:
        _degradation_policy = DegradationPolicy()
    return _degradation_policy
