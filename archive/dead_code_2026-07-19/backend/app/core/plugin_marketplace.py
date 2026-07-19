"""Plugin Marketplace - Discovery, Search, Install, Update"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from plugin_schema import (
    PluginSchema,
    PluginStatus,
    PluginInstallRequest,
    PluginUninstallRequest,
)

logger = logging.getLogger(__name__)


class PluginMarketplace:
    """Central plugin marketplace for discovery and management"""

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./marketplace")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, PluginSchema] = {}
        self._lock = RLock()
        self._load_registry()

    def _load_registry(self) -> None:
        """Load plugin registry from storage"""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            import json

            try:
                with open(registry_file) as f:
                    data = json.load(f)
                    for plugin_data in data.get("plugins", []):
                        plugin = PluginSchema(**plugin_data)
                        self._registry[plugin.plugin_id] = plugin
                logger.info(f"Loaded {len(self._registry)} plugins from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self) -> None:
        """Save plugin registry to storage"""
        import json

        registry_file = self.storage_path / "registry.json"
        try:
            with open(registry_file, "w") as f:
                data = {
                    "plugins": [
                        json.loads(p.model_dump_json())
                        for p in self._registry.values()
                    ]
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_plugin(self, plugin: PluginSchema) -> PluginSchema:
        """Register a new plugin in marketplace"""
        with self._lock:
            self._registry[plugin.plugin_id] = plugin
            self._save_registry()
        logger.info(f"Plugin registered: {plugin.name} v{plugin.version}")
        return plugin

    def discover_plugins(
        self, capability: str | None = None, risk_level: str | None = None
    ) -> list[PluginSchema]:
        """Discover plugins by capability or risk level"""
        results = list(self._registry.values())

        if capability:
            results = [p for p in results if capability in p.capabilities]

        if risk_level:
            results = [p for p in results if p.risk_level == risk_level]

        results.sort(key=lambda p: p.updated_at, reverse=True)
        return results

    def search_plugins(self, query: str) -> list[PluginSchema]:
        """Search plugins by name or description"""
        query_lower = query.lower()
        results = [
            p
            for p in self._registry.values()
            if query_lower in p.name.lower()
            or query_lower in p.description.lower()
            or any(query_lower in cap.lower() for cap in p.capabilities)
        ]
        results.sort(key=lambda p: p.updated_at, reverse=True)
        return results

    def get_plugin(self, plugin_id: str) -> PluginSchema | None:
        """Get plugin by ID"""
        return self._registry.get(plugin_id)

    def list_plugins(self, installed_only: bool = False) -> list[PluginSchema]:
        """List all plugins or only installed ones"""
        plugins = list(self._registry.values())
        if installed_only:
            plugins = [p for p in plugins if p.installed]
        plugins.sort(key=lambda p: p.updated_at, reverse=True)
        return plugins

    def update_plugin_status(
        self, plugin_id: str, status: PluginStatus
    ) -> PluginSchema | None:
        """Update plugin status"""
        with self._lock:
            plugin = self._registry.get(plugin_id)
            if plugin:
                plugin.status = status
                plugin.updated_at = datetime.now(UTC)
                self._save_registry()
        return plugin

    def update_plugin_config(
        self, plugin_id: str, config: dict[str, Any]
    ) -> PluginSchema | None:
        """Update plugin configuration"""
        with self._lock:
            plugin = self._registry.get(plugin_id)
            if plugin:
                plugin.config.update(config)
                plugin.updated_at = datetime.now(UTC)
                self._save_registry()
        return plugin

    def get_plugin_versions(self, plugin_id: str) -> list[str]:
        """Get available versions for a plugin"""
        plugin = self._registry.get(plugin_id)
        if not plugin:
            return []
        # In real implementation, would fetch from version store
        return [plugin.version]

    def check_updates(self) -> list[tuple[PluginSchema, str]]:
        """Check for available updates for installed plugins"""
        updates = []
        for plugin in self._registry.values():
            if plugin.installed:
                # In real implementation, would check remote registry
                pass
        return updates


class PluginInstallationManager:
    """Manage plugin installation lifecycle"""

    def __init__(self, marketplace: PluginMarketplace):
        self.marketplace = marketplace
        self._lock = RLock()
        self._installation_queue: dict[str, dict[str, Any]] = {}

    def install_plugin(
        self, request: PluginInstallRequest
    ) -> tuple[bool, str | None]:
        """Install a plugin"""
        try:
            plugin = self.marketplace.get_plugin(request.plugin_id)
            if not plugin:
                return False, "Plugin not found"

            if plugin.installed:
                return False, "Plugin already installed"

            # Update status
            self.marketplace.update_plugin_status(
                request.plugin_id, PluginStatus.INSTALLING
            )

            # Apply configuration
            if request.config:
                self.marketplace.update_plugin_config(request.plugin_id, request.config)

            # Mark as installed
            with self._lock:
                plugin.installed = True
                if request.auto_enable:
                    plugin.enabled = True
                    plugin.status = PluginStatus.ACTIVE
                else:
                    plugin.status = PluginStatus.INACTIVE
                plugin.updated_at = datetime.now(UTC)

            self.marketplace._save_registry()
            logger.info(f"Plugin installed: {plugin.name}")
            return True, None

        except Exception as e:
            error_msg = f"Installation failed: {str(e)}"
            logger.error(error_msg)
            self.marketplace.update_plugin_status(
                request.plugin_id, PluginStatus.ERROR
            )
            return False, error_msg

    def uninstall_plugin(
        self, request: PluginUninstallRequest
    ) -> tuple[bool, str | None]:
        """Uninstall a plugin"""
        try:
            plugin = self.marketplace.get_plugin(request.plugin_id)
            if not plugin:
                return False, "Plugin not found"

            if not plugin.installed:
                return False, "Plugin not installed"

            # Update status
            self.marketplace.update_plugin_status(
                request.plugin_id, PluginStatus.UNINSTALLING
            )

            # Mark as uninstalled
            with self._lock:
                plugin.installed = False
                plugin.enabled = False
                plugin.status = PluginStatus.INACTIVE
                plugin.install_path = None
                plugin.updated_at = datetime.now(UTC)

            self.marketplace._save_registry()
            logger.info(f"Plugin uninstalled: {plugin.name}")
            return True, None

        except Exception as e:
            error_msg = f"Uninstallation failed: {str(e)}"
            logger.error(error_msg)
            self.marketplace.update_plugin_status(
                request.plugin_id, PluginStatus.ERROR
            )
            return False, error_msg

    def enable_plugin(self, plugin_id: str) -> tuple[bool, str | None]:
        """Enable an installed plugin"""
        try:
            plugin = self.marketplace.get_plugin(plugin_id)
            if not plugin:
                return False, "Plugin not found"

            if not plugin.installed:
                return False, "Plugin not installed"

            plugin.enabled = True
            plugin.status = PluginStatus.ACTIVE
            plugin.updated_at = datetime.now(UTC)
            self.marketplace._save_registry()
            logger.info(f"Plugin enabled: {plugin.name}")
            return True, None

        except Exception as e:
            return False, f"Enable failed: {str(e)}"

    def disable_plugin(self, plugin_id: str) -> tuple[bool, str | None]:
        """Disable an installed plugin"""
        try:
            plugin = self.marketplace.get_plugin(plugin_id)
            if not plugin:
                return False, "Plugin not found"

            plugin.enabled = False
            plugin.status = PluginStatus.DISABLED
            plugin.updated_at = datetime.now(UTC)
            self.marketplace._save_registry()
            logger.info(f"Plugin disabled: {plugin.name}")
            return True, None

        except Exception as e:
            return False, f"Disable failed: {str(e)}"

    def upgrade_plugin(
        self, plugin_id: str, new_version: str
    ) -> tuple[bool, str | None]:
        """Upgrade plugin to new version"""
        try:
            plugin = self.marketplace.get_plugin(plugin_id)
            if not plugin:
                return False, "Plugin not found"

            old_version = plugin.version
            plugin.version = new_version
            plugin.updated_at = datetime.now(UTC)
            self.marketplace._save_registry()
            logger.info(f"Plugin upgraded: {plugin.name} {old_version} -> {new_version}")
            return True, None

        except Exception as e:
            return False, f"Upgrade failed: {str(e)}"


# Global instances
marketplace = PluginMarketplace()
installation_manager = PluginInstallationManager(marketplace)
