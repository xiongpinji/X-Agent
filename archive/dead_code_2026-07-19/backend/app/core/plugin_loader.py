"""Plugin Loader with Sandboxing and Permission Control"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable
from threading import RLock
import logging

from plugin_schema import PluginSchema, PluginStatus, PluginCompatibilityCheck

logger = logging.getLogger(__name__)


class PluginSandbox:
    """Sandbox environment for plugin execution"""

    def __init__(self, plugin_id: str, allowed_modules: list[str] | None = None):
        self.plugin_id = plugin_id
        self.allowed_modules = allowed_modules or [
            "json",
            "datetime",
            "uuid",
            "logging",
            "re",
            "collections",
        ]
        self._restricted_builtins = {
            "open": None,
            "exec": None,
            "eval": None,
            "__import__": None,
            "compile": None,
            "globals": None,
            "locals": None,
            "vars": None,
            "dir": None,
        }

    def create_restricted_globals(self) -> dict[str, Any]:
        """Create restricted global namespace for plugin execution"""
        safe_builtins = {
            k: v for k, v in __builtins__.items() if k not in self._restricted_builtins
        }
        return {
            "__builtins__": safe_builtins,
            "__name__": f"plugin_{self.plugin_id}",
            "__doc__": None,
        }

    def validate_import(self, module_name: str) -> bool:
        """Validate if module can be imported"""
        base_module = module_name.split(".")[0]
        return base_module in self.allowed_modules


class PluginLoader:
    """Dynamic plugin loader with version management"""

    def __init__(self, plugin_dir: str | Path | None = None):
        self.plugin_dir = Path(plugin_dir) if plugin_dir else Path("./plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_plugins: dict[str, Any] = {}
        self._lock = RLock()
        self._version_cache: dict[str, dict[str, Any]] = {}

    def load_plugin(
        self, plugin_schema: PluginSchema, sandbox: bool = True
    ) -> tuple[bool, str | None]:
        """Load plugin from install path"""
        try:
            if not plugin_schema.install_path:
                return False, "No install path specified"

            install_path = Path(plugin_schema.install_path)
            if not install_path.exists():
                return False, f"Plugin path not found: {install_path}"

            # Check if it's a Python module
            if install_path.is_dir():
                init_file = install_path / "__init__.py"
                if not init_file.exists():
                    return False, "Invalid plugin package: missing __init__.py"
                module_path = init_file
            else:
                module_path = install_path

            # Load module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_schema.plugin_id}", module_path
            )
            if not spec or not spec.loader:
                return False, "Failed to create module spec"

            module = importlib.util.module_from_spec(spec)

            if sandbox:
                sandbox_env = PluginSandbox(plugin_schema.plugin_id)
                module.__dict__.update(sandbox_env.create_restricted_globals())

            sys.modules[f"plugin_{plugin_schema.plugin_id}"] = module
            spec.loader.exec_module(module)

            with self._lock:
                self._loaded_plugins[plugin_schema.plugin_id] = module
                self._version_cache[plugin_schema.plugin_id] = {
                    "version": plugin_schema.version,
                    "loaded_at": str(__import__("datetime").datetime.now()),
                }

            logger.info(f"Plugin loaded: {plugin_schema.name} v{plugin_schema.version}")
            return True, None

        except Exception as e:
            error_msg = f"Failed to load plugin: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload plugin from memory"""
        try:
            with self._lock:
                if plugin_id in self._loaded_plugins:
                    del self._loaded_plugins[plugin_id]
                module_name = f"plugin_{plugin_id}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                if plugin_id in self._version_cache:
                    del self._version_cache[plugin_id]
            logger.info(f"Plugin unloaded: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {str(e)}")
            return False

    def get_plugin(self, plugin_id: str) -> Any | None:
        """Get loaded plugin module"""
        return self._loaded_plugins.get(plugin_id)

    def list_loaded_plugins(self) -> list[str]:
        """List all loaded plugin IDs"""
        return list(self._loaded_plugins.keys())

    def reload_plugin(self, plugin_schema: PluginSchema) -> tuple[bool, str | None]:
        """Reload plugin"""
        self.unload_plugin(plugin_schema.plugin_id)
        return self.load_plugin(plugin_schema)


class PluginPermissionManager:
    """Manage plugin permissions and access control"""

    def __init__(self):
        self._permissions: dict[str, set[str]] = {}
        self._lock = RLock()

    def grant_permission(self, plugin_id: str, permission: str) -> None:
        """Grant permission to plugin"""
        with self._lock:
            if plugin_id not in self._permissions:
                self._permissions[plugin_id] = set()
            self._permissions[plugin_id].add(permission)

    def revoke_permission(self, plugin_id: str, permission: str) -> None:
        """Revoke permission from plugin"""
        with self._lock:
            if plugin_id in self._permissions:
                self._permissions[plugin_id].discard(permission)

    def has_permission(self, plugin_id: str, permission: str) -> bool:
        """Check if plugin has permission"""
        return permission in self._permissions.get(plugin_id, set())

    def get_permissions(self, plugin_id: str) -> set[str]:
        """Get all permissions for plugin"""
        return self._permissions.get(plugin_id, set()).copy()

    def set_permissions(self, plugin_id: str, permissions: list[str]) -> None:
        """Set all permissions for plugin"""
        with self._lock:
            self._permissions[plugin_id] = set(permissions)


class PluginCompatibilityChecker:
    """Check plugin compatibility with system"""

    def __init__(self, system_version: str = "1.0.0"):
        self.system_version = system_version

    def check_compatibility(
        self, plugin_schema: PluginSchema, installed_plugins: dict[str, PluginSchema]
    ) -> PluginCompatibilityCheck:
        """Check if plugin is compatible with current system"""
        issues = []
        warnings = []

        # Check dependencies
        for dep in plugin_schema.dependencies:
            if dep not in installed_plugins:
                issues.append(f"Missing dependency: {dep}")
            else:
                installed = installed_plugins[dep]
                if installed.status != PluginStatus.ACTIVE:
                    warnings.append(f"Dependency not active: {dep}")

        # Check version compatibility
        if not self._is_version_compatible(plugin_schema.version):
            issues.append(
                f"Plugin version {plugin_schema.version} not compatible with system {self.system_version}"
            )

        compatible = len(issues) == 0
        return PluginCompatibilityCheck(
            compatible=compatible, issues=issues, warnings=warnings
        )

    def _is_version_compatible(self, plugin_version: str) -> bool:
        """Simple version compatibility check"""
        try:
            pv = tuple(map(int, plugin_version.split(".")))
            sv = tuple(map(int, self.system_version.split(".")))
            return pv[0] == sv[0]  # Major version must match
        except (ValueError, IndexError):
            return True  # Assume compatible if can't parse


# Global instances
plugin_loader = PluginLoader()
permission_manager = PluginPermissionManager()
compatibility_checker = PluginCompatibilityChecker()
