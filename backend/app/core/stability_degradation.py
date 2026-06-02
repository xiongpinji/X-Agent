"""
Degradation Strategy Implementation for X-Agent

Implements multi-layer degradation strategies to maintain core functionality during failures:
- Feature degradation: Disable non-critical features
- Cache degradation: Use cached data when services unavailable
- Read-only mode: Accept only read operations
- Graceful fallback: Use alternative implementations

Features:
- Feature flags and toggles
- Automatic degradation triggers
- Recovery monitoring
- Detailed logging and metrics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from threading import RLock
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DegradationLevel(str, Enum):
    """Degradation levels"""
    NORMAL = "normal"
    DEGRADED = "degraded"
    SEVERELY_DEGRADED = "severely_degraded"
    MAINTENANCE = "maintenance"


class FeatureStatus(str, Enum):
    """Feature status"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    DEGRADED = "degraded"
    FALLBACK = "fallback"


class DegradationMetrics(BaseModel):
    """Metrics for degradation monitoring"""
    current_level: DegradationLevel = DegradationLevel.NORMAL
    enabled_features: int = 0
    disabled_features: int = 0
    degraded_features: int = 0
    fallback_features: int = 0
    cache_hit_rate: float = 0.0
    read_only_mode: bool = False
    last_degradation_time: datetime | None = None
    last_recovery_time: datetime | None = None
    degradation_duration: int = 0


@dataclass
class FeatureConfig:
    """Configuration for a feature"""
    name: str
    critical: bool = False
    has_fallback: bool = False
    fallback_impl: Optional[Callable] = None
    cache_enabled: bool = False
    cache_ttl: int = 300


class DegradationStrategy:
    """
    Manages degradation strategies for fault tolerance.

    Automatically degrades functionality when services fail while maintaining
    core operations.
    """

    def __init__(self):
        self._lock = RLock()
        self._features: dict[str, FeatureConfig] = {}
        self._feature_status: dict[str, FeatureStatus] = {}
        self._degradation_level = DegradationLevel.NORMAL
        self._read_only_mode = False
        self._cache: dict[str, tuple[Any, float]] = {}
        self._metrics = DegradationMetrics()
        self._last_degradation_time: float | None = None

    def register_feature(self, config: FeatureConfig) -> None:
        """Register a feature"""
        with self._lock:
            self._features[config.name] = config
            self._feature_status[config.name] = FeatureStatus.ENABLED
            logger.info(f"Registered feature: {config.name}")

    def disable_feature(self, name: str, reason: str = "") -> None:
        """Disable a feature"""
        with self._lock:
            if name not in self._features:
                logger.warning(f"Feature not found: {name}")
                return

            config = self._features[name]
            if config.critical:
                logger.warning(f"Cannot disable critical feature: {name}")
                return

            self._feature_status[name] = FeatureStatus.DISABLED
            logger.warning(f"Feature disabled: {name}, reason: {reason}")
            self._update_metrics()

    def enable_feature(self, name: str) -> None:
        """Enable a feature"""
        with self._lock:
            if name not in self._features:
                logger.warning(f"Feature not found: {name}")
                return

            self._feature_status[name] = FeatureStatus.ENABLED
            logger.info(f"Feature enabled: {name}")
            self._update_metrics()

    def degrade_feature(self, name: str, reason: str = "") -> None:
        """Degrade a feature to fallback mode"""
        with self._lock:
            if name not in self._features:
                logger.warning(f"Feature not found: {name}")
                return

            config = self._features[name]
            if not config.has_fallback:
                logger.warning(f"Feature has no fallback: {name}")
                self.disable_feature(name, reason)
                return

            self._feature_status[name] = FeatureStatus.DEGRADED
            logger.warning(f"Feature degraded: {name}, reason: {reason}")
            self._update_metrics()

    def use_fallback(self, name: str, reason: str = "") -> None:
        """Switch feature to fallback implementation"""
        with self._lock:
            if name not in self._features:
                logger.warning(f"Feature not found: {name}")
                return

            config = self._features[name]
            if not config.has_fallback:
                logger.warning(f"Feature has no fallback: {name}")
                return

            self._feature_status[name] = FeatureStatus.FALLBACK
            logger.warning(f"Feature using fallback: {name}, reason: {reason}")
            self._update_metrics()

    def is_feature_enabled(self, name: str) -> bool:
        """Check if feature is enabled"""
        with self._lock:
            status = self._feature_status.get(name, FeatureStatus.ENABLED)
            return status in (FeatureStatus.ENABLED, FeatureStatus.DEGRADED)

    def get_feature_status(self, name: str) -> FeatureStatus:
        """Get feature status"""
        with self._lock:
            return self._feature_status.get(name, FeatureStatus.ENABLED)

    def set_degradation_level(self, level: DegradationLevel) -> None:
        """Set system degradation level"""
        with self._lock:
            if level == self._degradation_level:
                return

            old_level = self._degradation_level
            self._degradation_level = level
            self._last_degradation_time = datetime.now(UTC).timestamp()
            logger.warning(
                f"Degradation level changed: {old_level.value} -> {level.value}"
            )

            if level == DegradationLevel.SEVERELY_DEGRADED:
                self._enable_read_only_mode()
            elif level == DegradationLevel.NORMAL:
                self._disable_read_only_mode()

            self._update_metrics()

    def get_degradation_level(self) -> DegradationLevel:
        """Get current degradation level"""
        with self._lock:
            return self._degradation_level

    def enable_read_only_mode(self) -> None:
        """Enable read-only mode"""
        with self._lock:
            self._enable_read_only_mode()

    def _enable_read_only_mode(self) -> None:
        """Internal method to enable read-only mode"""
        self._read_only_mode = True
        logger.warning("Read-only mode enabled")
        self._update_metrics()

    def disable_read_only_mode(self) -> None:
        """Disable read-only mode"""
        with self._lock:
            self._disable_read_only_mode()

    def _disable_read_only_mode(self) -> None:
        """Internal method to disable read-only mode"""
        self._read_only_mode = False
        logger.info("Read-only mode disabled")
        self._update_metrics()

    def is_read_only_mode(self) -> bool:
        """Check if in read-only mode"""
        with self._lock:
            return self._read_only_mode

    def cache_result(self, key: str, value: Any, ttl: int = 300) -> None:
        """Cache a result"""
        with self._lock:
            import time
            self._cache[key] = (value, time.time() + ttl)
            logger.debug(f"Cached result: {key}")

    def get_cached_result(self, key: str) -> Any | None:
        """Get cached result if available and not expired"""
        with self._lock:
            if key not in self._cache:
                return None

            value, expiry = self._cache[key]
            import time
            if time.time() > expiry:
                del self._cache[key]
                return None

            logger.debug(f"Cache hit: {key}")
            return value

    def clear_cache(self) -> None:
        """Clear all cached results"""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def _update_metrics(self) -> None:
        """Update metrics"""
        enabled = sum(
            1 for s in self._feature_status.values()
            if s == FeatureStatus.ENABLED
        )
        disabled = sum(
            1 for s in self._feature_status.values()
            if s == FeatureStatus.DISABLED
        )
        degraded = sum(
            1 for s in self._feature_status.values()
            if s == FeatureStatus.DEGRADED
        )
        fallback = sum(
            1 for s in self._feature_status.values()
            if s == FeatureStatus.FALLBACK
        )

        self._metrics.current_level = self._degradation_level
        self._metrics.enabled_features = enabled
        self._metrics.disabled_features = disabled
        self._metrics.degraded_features = degraded
        self._metrics.fallback_features = fallback
        self._metrics.read_only_mode = self._read_only_mode

    def get_metrics(self) -> DegradationMetrics:
        """Get current metrics"""
        with self._lock:
            return self._metrics.model_copy()

    def get_all_feature_status(self) -> dict[str, FeatureStatus]:
        """Get status of all features"""
        with self._lock:
            return self._feature_status.copy()

    def recover(self) -> None:
        """Attempt recovery from degradation"""
        with self._lock:
            logger.info("Attempting recovery from degradation")
            self._degradation_level = DegradationLevel.NORMAL
            self._disable_read_only_mode()
            for name in self._feature_status:
                self._feature_status[name] = FeatureStatus.ENABLED
            self._metrics.last_recovery_time = datetime.now(UTC)
            self._update_metrics()


# Global degradation strategy instance
_degradation_strategy = DegradationStrategy()


def get_degradation_strategy() -> DegradationStrategy:
    """Get global degradation strategy"""
    return _degradation_strategy
