"""Compatibility layer for smooth Agent V1 to V2 migration.

This module provides a unified interface that routes requests to either
Agent V1 or V2 based on feature flags, ensuring backward compatibility
during gradual rollout.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from backend.app.core.feature_flags import FeatureFlag, get_feature_flag_manager

if TYPE_CHECKING:
    from backend.app.core.agent_v2.agent_executor import AgentExecutor
    from backend.app.core.contracts import AgentRunResponse, RunContext

logger = logging.getLogger(__name__)


class AgentCompatibilityLayer:
    """Routes agent execution between V1 and V2 based on feature flags.

    Provides a unified interface for agent execution that transparently
    routes to either the legacy Agent V1 or new Agent V2 implementation
    based on feature flag configuration.
    """

    def __init__(
        self,
        agent_v1: Any = None,
        agent_v2: Optional[AgentExecutor] = None,
    ) -> None:
        """Initialize compatibility layer.

        Args:
            agent_v1: Legacy Agent V1 instance.
            agent_v2: New Agent V2 executor instance.
        """
        self.agent_v1 = agent_v1
        self.agent_v2 = agent_v2
        self.feature_flag_manager = get_feature_flag_manager()
        self._execution_stats = {
            "v1_executions": 0,
            "v2_executions": 0,
            "v1_errors": 0,
            "v2_errors": 0,
        }

    def should_use_v2(
        self,
        context: RunContext,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Determine if Agent V2 should be used for this execution.

        Args:
            context: Execution context.
            tenant_id: Tenant ID for tenant-specific routing.
            user_id: User ID for user-specific routing.

        Returns:
            True if Agent V2 should be used, False for Agent V1.
        """
        return self.feature_flag_manager.is_enabled(
            FeatureFlag.USE_AGENT_V2,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def execute(
        self,
        context: RunContext,
        task: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentRunResponse:
        """Execute agent task using appropriate version.

        Routes to Agent V1 or V2 based on feature flags and execution context.

        Args:
            context: Execution context with trace/auth info.
            task: Task description.
            tenant_id: Tenant ID for routing decisions.
            user_id: User ID for routing decisions.
            **kwargs: Additional arguments passed to agent executor.

        Returns:
            Agent execution response.

        Raises:
            RuntimeError: If appropriate agent version is not available.
        """
        use_v2 = self.should_use_v2(context, tenant_id, user_id)

        if use_v2:
            if self.agent_v2 is None:
                logger.error("Agent V2 requested but not available, falling back to V1")
                use_v2 = False
            else:
                try:
                    logger.info(
                        f"Executing with Agent V2 (tenant={tenant_id}, user={user_id})"
                    )
                    self._execution_stats["v2_executions"] += 1
                    return await self.agent_v2.execute(context, task, **kwargs)
                except Exception as e:
                    logger.error(f"Agent V2 execution failed: {e}", exc_info=True)
                    self._execution_stats["v2_errors"] += 1
                    # Fall back to V1 on error
                    logger.info("Falling back to Agent V1 due to V2 error")

        if self.agent_v1 is None:
            raise RuntimeError("No agent version available for execution")

        try:
            logger.info(
                f"Executing with Agent V1 (tenant={tenant_id}, user={user_id})"
            )
            self._execution_stats["v1_executions"] += 1
            return await self.agent_v1.execute(context, task, **kwargs)
        except Exception as e:
            logger.error(f"Agent V1 execution failed: {e}", exc_info=True)
            self._execution_stats["v1_errors"] += 1
            raise

    def get_execution_stats(self) -> dict[str, int]:
        """Get execution statistics.

        Returns:
            Dictionary with execution counts and error counts.
        """
        return self._execution_stats.copy()

    def reset_execution_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_stats = {
            "v1_executions": 0,
            "v2_executions": 0,
            "v1_errors": 0,
            "v2_errors": 0,
        }

    def get_routing_info(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get routing information for debugging.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.

        Returns:
            Dictionary with routing information.
        """
        flag_config = self.feature_flag_manager.get_flag_config(FeatureFlag.USE_AGENT_V2)
        return {
            "use_v2": self.should_use_v2(None, tenant_id, user_id),
            "flag_enabled": flag_config.enabled if flag_config else False,
            "rollout_percentage": flag_config.rollout_percentage if flag_config else 0,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "v1_available": self.agent_v1 is not None,
            "v2_available": self.agent_v2 is not None,
        }


# Global compatibility layer instance
_compatibility_layer: Optional[AgentCompatibilityLayer] = None


def get_compatibility_layer() -> AgentCompatibilityLayer:
    """Get or create global compatibility layer.

    Returns:
        Global compatibility layer instance.
    """
    global _compatibility_layer
    if _compatibility_layer is None:
        _compatibility_layer = AgentCompatibilityLayer()
    return _compatibility_layer


def set_compatibility_layer(layer: AgentCompatibilityLayer) -> None:
    """Set global compatibility layer instance.

    Args:
        layer: Compatibility layer instance to use globally.
    """
    global _compatibility_layer
    _compatibility_layer = layer
