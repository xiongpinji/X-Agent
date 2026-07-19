"""Plugin System Integration - Unified API for all plugin operations"""

from __future__ import annotations

import logging
from typing import Any

from plugin_schema import (
    PluginSchema,
    PluginStatus,
    PluginInstallRequest,
    PluginUninstallRequest,
)
from plugin_loader import (
    plugin_loader,
    permission_manager,
    compatibility_checker,
)
from plugin_marketplace import marketplace, installation_manager
from plugin_lifecycle import lifecycle_manager, audit_system

logger = logging.getLogger(__name__)


class PluginSystemManager:
    """Unified interface for all plugin system operations"""

    def __init__(self):
        self.marketplace = marketplace
        self.loader = plugin_loader
        self.permissions = permission_manager
        self.compatibility = compatibility_checker
        self.lifecycle = lifecycle_manager
        self.audit = audit_system
        self.installation = installation_manager

    # Discovery Operations

    def discover_plugins(
        self, capability: str | None = None, risk_level: str | None = None
    ) -> list[PluginSchema]:
        """Discover available plugins"""
        return self.marketplace.discover_plugins(capability, risk_level)

    def search_plugins(self, query: str) -> list[PluginSchema]:
        """Search plugins by name or description"""
        return self.marketplace.search_plugins(query)

    def get_plugin_info(self, plugin_id: str) -> PluginSchema | None:
        """Get detailed plugin information"""
        return self.marketplace.get_plugin(plugin_id)

    def list_installed_plugins(self) -> list[PluginSchema]:
        """List all installed plugins"""
        return self.marketplace.list_plugins(installed_only=True)

    def list_all_plugins(self) -> list[PluginSchema]:
        """List all available plugins"""
        return self.marketplace.list_plugins()

    # Installation Operations

    def install_plugin(
        self,
        plugin_id: str,
        config: dict[str, Any] | None = None,
        auto_enable: bool = False,
    ) -> tuple[bool, str | None]:
        """Install a plugin"""
        plugin = self.marketplace.get_plugin(plugin_id)
        if not plugin:
            return False, "Plugin not found"

        # Check compatibility
        installed = {p.plugin_id: p for p in self.list_installed_plugins()}
        compat_check = self.compatibility.check_compatibility(plugin, installed)
        if not compat_check.compatible:
            return False, f"Compatibility issues: {', '.join(compat_check.issues)}"

        # Install
        request = PluginInstallRequest(
            plugin_id=plugin_id, config=config, auto_enable=auto_enable
        )
        success, error = self.installation.install_plugin(request)

        if success:
            self.lifecycle.initialize_lifecycle(plugin_id, plugin)
            self.lifecycle.record_install(plugin_id)
            self.audit.record_install(plugin_id, details={"config": config})

        return success, error

    def uninstall_plugin(self, plugin_id: str, force: bool = False) -> tuple[bool, str | None]:
        """Uninstall a plugin"""
        plugin = self.marketplace.get_plugin(plugin_id)
        if not plugin:
            return False, "Plugin not found"

        # Uninstall
        request = PluginUninstallRequest(plugin_id=plugin_id, force=force)
        success, error = self.installation.uninstall_plugin(request)

        if success:
            self.loader.unload_plugin(plugin_id)
            self.lifecycle.record_uninstall(plugin_id)
            self.audit.record_uninstall(plugin_id)

        return success, error

    def enable_plugin(self, plugin_id: str) -> tuple[bool, str | None]:
        """Enable an installed plugin"""
        success, error = self.installation.enable_plugin(plugin_id)

        if success:
            self.lifecycle.record_enable(plugin_id)
            self.audit.record_enable(plugin_id)
            # Load plugin
            plugin = self.marketplace.get_plugin(plugin_id)
            if plugin:
                self.loader.load_plugin(plugin)

        return success, error

    def disable_plugin(self, plugin_id: str) -> tuple[bool, str | None]:
        """Disable an installed plugin"""
        success, error = self.installation.disable_plugin(plugin_id)

        if success:
            self.lifecycle.record_disable(plugin_id)
            self.audit.record_disable(plugin_id)
            # Unload plugin
            self.loader.unload_plugin(plugin_id)

        return success, error

    def upgrade_plugin(self, plugin_id: str, new_version: str) -> tuple[bool, str | None]:
        """Upgrade plugin to new version"""
        plugin = self.marketplace.get_plugin(plugin_id)
        if not plugin:
            return False, "Plugin not found"

        old_version = plugin.version
        success, error = self.installation.upgrade_plugin(plugin_id, new_version)

        if success:
            self.lifecycle.record_upgrade(plugin_id, new_version)
            self.audit.record_action(
                plugin_id,
                "upgrade",
                details={"from_version": old_version, "to_version": new_version},
            )
            # Reload plugin
            self.loader.reload_plugin(plugin)

        return success, error

    # Permission Operations

    def grant_permission(self, plugin_id: str, permission: str) -> None:
        """Grant permission to plugin"""
        self.permissions.grant_permission(plugin_id, permission)
        self.audit.record_permission_change(
            plugin_id, list(self.permissions.get_permissions(plugin_id))
        )

    def revoke_permission(self, plugin_id: str, permission: str) -> None:
        """Revoke permission from plugin"""
        self.permissions.revoke_permission(plugin_id, permission)
        self.audit.record_permission_change(
            plugin_id, list(self.permissions.get_permissions(plugin_id))
        )

    def get_plugin_permissions(self, plugin_id: str) -> set[str]:
        """Get all permissions for plugin"""
        return self.permissions.get_permissions(plugin_id)

    def set_plugin_permissions(self, plugin_id: str, permissions: list[str]) -> None:
        """Set all permissions for plugin"""
        self.permissions.set_permissions(plugin_id, permissions)
        self.audit.record_permission_change(plugin_id, permissions)

    # Execution Operations

    def execute_plugin_action(
        self, plugin_id: str, action: str, **kwargs
    ) -> dict[str, Any]:
        """Execute plugin action"""
        plugin = self.marketplace.get_plugin(plugin_id)
        if not plugin:
            return {"success": False, "error": "Plugin not found"}

        if not plugin.enabled:
            return {"success": False, "error": "Plugin not enabled"}

        # Check permission
        required_permission = f"{action}:execute"
        if not self.permissions.has_permission(plugin_id, required_permission):
            self.audit.record_execution(
                plugin_id, action, success=False, error="Permission denied"
            )
            return {"success": False, "error": "Permission denied"}

        # Load and execute
        loaded_plugin = self.loader.get_plugin(plugin_id)
        if not loaded_plugin:
            return {"success": False, "error": "Plugin not loaded"}

        try:
            result = loaded_plugin.execute(action, **kwargs)
            success = result.get("success", True)
            self.audit.record_execution(
                plugin_id, action, success=success, details=result
            )
            return result
        except Exception as e:
            error_msg = str(e)
            self.audit.record_execution(
                plugin_id, action, success=False, error=error_msg
            )
            return {"success": False, "error": error_msg}

    # Audit Operations

    def get_plugin_audit_trail(self, plugin_id: str) -> list[dict[str, Any]]:
        """Get complete audit trail for plugin"""
        records = self.audit.get_plugin_audit_trail(plugin_id)
        return [
            {
                "audit_id": r.audit_id,
                "action": r.action,
                "actor_id": r.actor_id,
                "outcome": r.outcome,
                "created_at": r.created_at.isoformat(),
                "details": r.details,
            }
            for r in records
        ]

    def get_audit_records(
        self, plugin_id: str | None = None, action: str | None = None
    ) -> list[dict[str, Any]]:
        """Get audit records with filtering"""
        records = self.audit.get_audit_records(plugin_id, action)
        return [
            {
                "audit_id": r.audit_id,
                "plugin_id": r.plugin_id,
                "action": r.action,
                "actor_id": r.actor_id,
                "outcome": r.outcome,
                "created_at": r.created_at.isoformat(),
                "details": r.details,
            }
            for r in records
        ]

    def export_audit_report(self, plugin_id: str | None = None) -> dict[str, Any]:
        """Export audit report"""
        return self.audit.export_audit_report(plugin_id)

    # Lifecycle Operations

    def get_plugin_lifecycle(self, plugin_id: str) -> dict[str, Any] | None:
        """Get plugin lifecycle state"""
        return self.lifecycle.get_lifecycle_state(plugin_id)

    def get_plugin_action_history(self, plugin_id: str) -> list[dict[str, Any]]:
        """Get plugin action history"""
        return self.lifecycle.get_action_history(plugin_id)

    # Status Operations

    def get_system_status(self) -> dict[str, Any]:
        """Get overall plugin system status"""
        all_plugins = self.list_all_plugins()
        installed = self.list_installed_plugins()

        active_count = sum(1 for p in installed if p.enabled)
        disabled_count = sum(1 for p in installed if not p.enabled)

        return {
            "total_available": len(all_plugins),
            "total_installed": len(installed),
            "active_plugins": active_count,
            "disabled_plugins": disabled_count,
            "plugins": [
                {
                    "plugin_id": p.plugin_id,
                    "name": p.name,
                    "version": p.version,
                    "status": p.status,
                    "enabled": p.enabled,
                }
                for p in installed
            ],
        }

    def verify_system_integrity(self) -> tuple[bool, list[str]]:
        """Verify plugin system integrity"""
        issues = []

        # Check audit integrity
        audit_valid, audit_issues = self.audit.verify_audit_integrity()
        if not audit_valid:
            issues.extend(audit_issues)

        # Check for orphaned plugins
        installed = self.list_installed_plugins()
        for plugin in installed:
            if plugin.install_path and not plugin.install_path.exists():
                issues.append(f"Orphaned plugin: {plugin.name} (path not found)")

        return len(issues) == 0, issues


# Global instance
plugin_system = PluginSystemManager()
