"""Feature flags for gradual rollout and A/B testing.

This module provides feature flag management for controlling new features
and gradual rollout of Agent V2 architecture.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FeatureFlag(str, Enum):
    """Available feature flags."""

    USE_AGENT_V2 = "use_agent_v2"
    ENABLE_MEMORY_GRAPH = "enable_memory_graph"
    ENABLE_ADVANCED_PLANNING = "enable_advanced_planning"
    ENABLE_AUTO_RECOVERY = "enable_auto_recovery"


@dataclass
class FeatureFlagConfig:
    """Configuration for a feature flag."""

    name: FeatureFlag
    enabled: bool = False
    rollout_percentage: int = 0  # 0-100, percentage of users
    allowed_tenants: list[str] | None = None  # None means all tenants
    allowed_users: list[str] | None = None  # None means all users
    description: str = ""


class FeatureFlagManager:
    """Manages feature flags with support for gradual rollout."""

    def __init__(self) -> None:
        """Initialize feature flag manager."""
        self._flags: dict[FeatureFlag, FeatureFlagConfig] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default feature flag configurations."""
        self._flags[FeatureFlag.USE_AGENT_V2] = FeatureFlagConfig(
            name=FeatureFlag.USE_AGENT_V2,
            enabled=False,
            rollout_percentage=0,
            description="Enable Agent V2 architecture",
        )
        self._flags[FeatureFlag.ENABLE_MEMORY_GRAPH] = FeatureFlagConfig(
            name=FeatureFlag.ENABLE_MEMORY_GRAPH,
            enabled=True,
            rollout_percentage=100,
            description="Enable memory graph functionality",
        )
        self._flags[FeatureFlag.ENABLE_ADVANCED_PLANNING] = FeatureFlagConfig(
            name=FeatureFlag.ENABLE_ADVANCED_PLANNING,
            enabled=False,
            rollout_percentage=0,
            description="Enable advanced planning phase",
        )
        self._flags[FeatureFlag.ENABLE_AUTO_RECOVERY] = FeatureFlagConfig(
            name=FeatureFlag.ENABLE_AUTO_RECOVERY,
            enabled=False,
            rollout_percentage=0,
            description="Enable automatic recovery mechanisms",
        )

    def is_enabled(
        self,
        flag: FeatureFlag,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Check if a feature flag is enabled for a user/tenant.

        Args:
            flag: Feature flag to check.
            tenant_id: Tenant ID for tenant-specific flags.
            user_id: User ID for user-specific flags.

        Returns:
            True if feature is enabled for the user/tenant.
        """
        if flag not in self._flags:
            logger.warning(f"Unknown feature flag: {flag}")
            return False

        config = self._flags[flag]

        # Check if globally disabled
        if not config.enabled:
            return False

        # Check tenant allowlist
        if config.allowed_tenants is not None:
            if tenant_id is None or tenant_id not in config.allowed_tenants:
                return False

        # Check user allowlist
        if config.allowed_users is not None:
            if user_id is None or user_id not in config.allowed_users:
                return False

        # Check rollout percentage
        if config.rollout_percentage < 100:
            return self._should_rollout(
                user_id or tenant_id or "default",
                config.rollout_percentage,
            )

        return True

    def _should_rollout(self, identifier: str, percentage: int) -> bool:
        """Determine if identifier should be included in rollout.

        Uses consistent hashing to ensure same identifier always gets
        same result.

        Args:
            identifier: User or tenant identifier.
            percentage: Rollout percentage (0-100).

        Returns:
            True if identifier should be included in rollout.
        """
        if percentage <= 0:
            return False
        if percentage >= 100:
            return True

        # Use consistent hashing for deterministic rollout
        hash_value = int(
            hashlib.md5(identifier.encode(), usedforsecurity=False).hexdigest(),
            16,
        )
        return (hash_value % 100) < percentage

    def set_flag(
        self,
        flag: FeatureFlag,
        enabled: bool,
        rollout_percentage: int = 0,
        allowed_tenants: list[str] | None = None,
        allowed_users: list[str] | None = None,
    ) -> None:
        """Update feature flag configuration.

        Args:
            flag: Feature flag to update.
            enabled: Whether flag is enabled.
            rollout_percentage: Rollout percentage (0-100).
            allowed_tenants: List of allowed tenant IDs.
            allowed_users: List of allowed user IDs.
        """
        if flag not in self._flags:
            logger.warning(f"Unknown feature flag: {flag}")
            return

        self._flags[flag] = FeatureFlagConfig(
            name=flag,
            enabled=enabled,
            rollout_percentage=rollout_percentage,
            allowed_tenants=allowed_tenants,
            allowed_users=allowed_users,
            description=self._flags[flag].description,
        )
        logger.info(
            f"Updated feature flag {flag}: enabled={enabled}, "
            f"rollout={rollout_percentage}%"
        )

    def get_flag_config(self, flag: FeatureFlag) -> Optional[FeatureFlagConfig]:
        """Get feature flag configuration.

        Args:
            flag: Feature flag to retrieve.

        Returns:
            Feature flag configuration or None if not found.
        """
        return self._flags.get(flag)

    def list_flags(self) -> dict[FeatureFlag, FeatureFlagConfig]:
        """List all feature flags.

        Returns:
            Dictionary of all feature flags and their configurations.
        """
        return self._flags.copy()


# Global feature flag manager instance
_feature_flag_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get or create global feature flag manager.

    Returns:
        Global feature flag manager instance.
    """
    global _feature_flag_manager
    if _feature_flag_manager is None:
        _feature_flag_manager = FeatureFlagManager()
    return _feature_flag_manager
