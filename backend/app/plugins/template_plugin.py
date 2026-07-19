"""Plugin Development Template - Use as base for new plugins"""

from __future__ import annotations

from typing import Any
import logging

logger = logging.getLogger(__name__)


class TemplatePlugin:
    """
    Template plugin demonstrating the standard plugin interface.

    To create a new plugin:
    1. Copy this file and rename it
    2. Update PLUGIN_* class variables
    3. Implement your plugin logic
    4. Register with marketplace
    """

    # Required metadata
    PLUGIN_NAME = "template"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_AUTHOR = "Your Name"
    PLUGIN_DESCRIPTION = "Plugin description"

    # Plugin capabilities this plugin provides
    PLUGIN_CAPABILITIES = ["capability1", "capability2"]

    # Permissions required by this plugin
    PLUGIN_PERMISSIONS = ["resource:action"]

    # Risk level: low, medium, high, critical
    PLUGIN_RISK_LEVEL = "medium"

    # Dependencies on other plugins (plugin IDs)
    PLUGIN_DEPENDENCIES = []

    def __init__(self):
        """Initialize plugin"""
        self.logger = logger
        self.logger.info(f"Initializing {self.PLUGIN_NAME} v{self.PLUGIN_VERSION}")

    def initialize(self, config: dict[str, Any] | None = None) -> bool:
        """
        Initialize plugin with configuration.

        Args:
            config: Plugin configuration dictionary

        Returns:
            True if initialization successful
        """
        try:
            self.config = config or {}
            self.logger.info(f"Plugin initialized with config: {self.config}")
            return True
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate plugin configuration.

        Args:
            config: Configuration to validate

        Returns:
            Tuple of (valid, error_message)
        """
        # Implement your validation logic
        return True, None

    def execute(self, action: str, **kwargs) -> dict[str, Any]:
        """
        Execute plugin action.

        Args:
            action: Action name to execute
            **kwargs: Action parameters

        Returns:
            Result dictionary with 'success' and 'data' or 'error'
        """
        try:
            if action == "action1":
                return self._action1(**kwargs)
            elif action == "action2":
                return self._action2(**kwargs)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return {"success": False, "error": str(e)}

    def _action1(self, **kwargs) -> dict[str, Any]:
        """Implement action1"""
        return {"success": True, "data": "action1 result"}

    def _action2(self, **kwargs) -> dict[str, Any]:
        """Implement action2"""
        return {"success": True, "data": "action2 result"}

    def get_capabilities(self) -> list[str]:
        """Get list of capabilities provided by this plugin"""
        return self.PLUGIN_CAPABILITIES

    def get_permissions(self) -> list[str]:
        """Get list of permissions required by this plugin"""
        return self.PLUGIN_PERMISSIONS

    def get_metadata(self) -> dict[str, Any]:
        """Get plugin metadata"""
        return {
            "name": self.PLUGIN_NAME,
            "version": self.PLUGIN_VERSION,
            "author": self.PLUGIN_AUTHOR,
            "description": self.PLUGIN_DESCRIPTION,
            "capabilities": self.PLUGIN_CAPABILITIES,
            "permissions": self.PLUGIN_PERMISSIONS,
            "risk_level": self.PLUGIN_RISK_LEVEL,
            "dependencies": self.PLUGIN_DEPENDENCIES,
        }

    def shutdown(self) -> bool:
        """
        Shutdown plugin gracefully.

        Returns:
            True if shutdown successful
        """
        try:
            self.logger.info(f"Shutting down {self.PLUGIN_NAME}")
            return True
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            return False


# Plugin entry point - must be named 'plugin'
plugin = TemplatePlugin()
