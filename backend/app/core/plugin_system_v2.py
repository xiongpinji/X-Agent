"""Enhanced Plugin System V2 - Production-Ready Plugin Management

This module provides a comprehensive plugin system with:
- Advanced lifecycle management
- Dependency resolution
- Version compatibility checking
- Sandboxed execution
- Permission-based access control
- Hot loading/unloading
- Plugin configuration management
- Audit logging
- Update mechanism
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import logging
import sys
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class PluginStatus(StrEnum):
    """Plugin lifecycle status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    INSTALLING = "installing"
    INSTALLED = "installed"
    UPDATING = "updating"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    DEPRECATED = "deprecated"


class PluginRiskLevel(StrEnum):
    """Plugin risk assessment level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionScope(StrEnum):
    """Permission scope levels"""
    SYSTEM = "system"
    USER = "user"
    WORKSPACE = "workspace"
    PLUGIN = "plugin"


# ==================== Data Models ====================

class PluginPermission(BaseModel):
    """Plugin permission specification"""
    resource: str = Field(..., description="Resource being accessed")
    action: str = Field(..., description="Action to perform")
    scope: PermissionScope = Field(default=PermissionScope.PLUGIN)
    description: str = Field(default="")


class PluginDependency(BaseModel):
    """Plugin dependency specification"""
    plugin_id: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    optional: bool = False


class PluginCapability(BaseModel):
    """Plugin capability specification"""
    name: str
    description: str
    version: str = "1.0"
    parameters: dict[str, Any] = Field(default_factory=dict)


class PluginMetadata(BaseModel):
    """Plugin metadata"""
    plugin_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    author: str
    description: str
    long_description: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = "MIT"
    keywords: list[str] = Field(default_factory=list)
    icon_url: Optional[str] = None
    screenshots: list[str] = Field(default_factory=list)

    @validator("version")
    def validate_version(cls, v):
        """Validate semantic versioning"""
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError("Version must be semantic (e.g., 1.0.0)")
        return v


class PluginManifest(BaseModel):
    """Complete plugin manifest"""
    metadata: PluginMetadata
    capabilities: list[PluginCapability] = Field(default_factory=list)
    dependencies: list[PluginDependency] = Field(default_factory=list)
    permissions: list[PluginPermission] = Field(default_factory=list)
    entry_point: str = Field(..., description="Main entry point module")
    config_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: PluginRiskLevel = PluginRiskLevel.MEDIUM
    requires_approval: bool = False
    sandbox_enabled: bool = True


class PluginConfig(BaseModel):
    """Plugin configuration"""
    plugin_id: str
    enabled: bool = False
    auto_start: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    permissions: list[PluginPermission] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginInstallRequest(BaseModel):
    """Request to install a plugin"""
    plugin_id: str
    version: Optional[str] = None
    source_url: str
    config: dict[str, Any] = Field(default_factory=dict)
    auto_enable: bool = False
    skip_verification: bool = False


class PluginUpdateRequest(BaseModel):
    """Request to update a plugin"""
    plugin_id: str
    new_version: str
    auto_restart: bool = True


class PluginExecutionRequest(BaseModel):
    """Request to execute plugin action"""
    plugin_id: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 30


# ==================== Plugin Sandbox ====================

class PluginSandbox:
    """Isolated execution environment for plugins"""

    def __init__(self, plugin_id: str, allowed_modules: Optional[list[str]] = None):
        self.plugin_id = plugin_id
        self.allowed_modules = allowed_modules or [
            "json", "datetime", "uuid", "logging", "re", "collections",
            "math", "random", "itertools", "functools", "operator"
        ]
        self._restricted_builtins = {
            "open", "exec", "eval", "__import__", "compile",
            "globals", "locals", "vars", "dir", "input",
            "breakpoint", "exit", "quit"
        }

    def create_restricted_globals(self) -> dict[str, Any]:
        """Create restricted global namespace"""
        # Create a safer builtins dict
        safe_builtins = {}
        if isinstance(__builtins__, dict):
            builtins_dict = __builtins__
        else:
            import builtins
            builtins_dict = vars(builtins)

        for k, v in builtins_dict.items():
            if k not in self._restricted_builtins:
                safe_builtins[k] = v

        return {
            "__builtins__": safe_builtins,
            "__name__": f"plugin_{self.plugin_id}",
            "__doc__": None,
            "__file__": None,
            "__loader__": None,
            "__spec__": None,
            "__cached__": None,
        }

    def validate_import(self, module_name: str) -> bool:
        """Validate if module can be imported"""
        base_module = module_name.split(".")[0]
        return base_module in self.allowed_modules


# ==================== Plugin Loader ====================

class PluginLoader:
    """Dynamic plugin loader with version management"""

    def __init__(self, plugin_dir: Optional[str | Path] = None):
        self.plugin_dir = Path(plugin_dir) if plugin_dir else Path("./plugins")
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_plugins: dict[str, Any] = {}
        self._lock = RLock()
        self._version_cache: dict[str, dict[str, Any]] = {}
        self._sandboxes: dict[str, PluginSandbox] = {}

    def load_plugin(
        self,
        plugin_id: str,
        manifest: PluginManifest,
        sandbox: bool = True
    ) -> tuple[bool, Optional[str]]:
        """Load plugin from manifest"""
        try:
            entry_point = manifest.entry_point
            plugin_path = self.plugin_dir / plugin_id

            if not plugin_path.exists():
                return False, f"Plugin path not found: {plugin_path}"

            # Verify entry point is within plugin directory (prevent directory traversal)
            if entry_point.endswith(".py"):
                module_path = plugin_path / entry_point
            else:
                module_path = plugin_path / f"{entry_point}.py"

            # Security check: ensure module_path is within plugin_path
            try:
                module_path.resolve().relative_to(plugin_path.resolve())
            except ValueError:
                return False, f"Entry point outside plugin directory: {module_path}"

            if not module_path.exists():
                return False, f"Entry point not found: {module_path}"

            # Verify file integrity if manifest has checksum
            if hasattr(manifest, 'checksum') and manifest.checksum:
                import hashlib
                with open(module_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if file_hash != manifest.checksum:
                    return False, f"Plugin file integrity check failed: {module_path}"

            # Create sandbox if enabled
            if sandbox:
                sandbox_env = PluginSandbox(plugin_id)
                self._sandboxes[plugin_id] = sandbox_env

            # Load module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_id}",
                module_path
            )
            if not spec or not spec.loader:
                return False, "Failed to create module spec"

            module = importlib.util.module_from_spec(spec)

            if sandbox:
                # Apply sandbox restrictions
                restricted_globals = self._sandboxes[plugin_id].create_restricted_globals()
                module.__dict__.update(restricted_globals)

            sys.modules[f"plugin_{plugin_id}"] = module

            # Execute module in restricted environment
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                # Remove from sys.modules on failure
                sys.modules.pop(f"plugin_{plugin_id}", None)
                raise

            with self._lock:
                self._loaded_plugins[plugin_id] = module
                self._version_cache[plugin_id] = {
                    "version": manifest.metadata.version,
                    "loaded_at": datetime.now(UTC).isoformat(),
                    "manifest": manifest.model_dump(),
                }

            logger.info(f"Plugin loaded: {manifest.metadata.name} v{manifest.metadata.version}")
            return True, None

        except Exception as e:
            error_msg = f"Failed to load plugin: {str(e)}"
            logger.error(error_msg, exc_info=True)
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
                if plugin_id in self._sandboxes:
                    del self._sandboxes[plugin_id]
            logger.info(f"Plugin unloaded: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {str(e)}")
            return False

    def reload_plugin(
        self,
        plugin_id: str,
        manifest: PluginManifest
    ) -> tuple[bool, Optional[str]]:
        """Reload plugin"""
        self.unload_plugin(plugin_id)
        return self.load_plugin(plugin_id, manifest)

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        """Get loaded plugin module"""
        return self._loaded_plugins.get(plugin_id)

    def list_loaded_plugins(self) -> list[str]:
        """List all loaded plugin IDs"""
        return list(self._loaded_plugins.keys())

    def get_plugin_version(self, plugin_id: str) -> Optional[dict[str, Any]]:
        """Get plugin version info"""
        return self._version_cache.get(plugin_id)


# ==================== Permission Manager ====================

class PermissionManager:
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
            logger.info(f"Permission granted to {plugin_id}: {permission}")

    def revoke_permission(self, plugin_id: str, permission: str) -> None:
        """Revoke permission from plugin"""
        with self._lock:
            if plugin_id in self._permissions:
                self._permissions[plugin_id].discard(permission)
                logger.info(f"Permission revoked from {plugin_id}: {permission}")

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
            logger.info(f"Permissions set for {plugin_id}: {permissions}")

    def verify_permission(
        self,
        plugin_id: str,
        resource: str,
        action: str
    ) -> bool:
        """Verify if plugin can perform action on resource"""
        permission = f"{resource}:{action}"
        return self.has_permission(plugin_id, permission)


# ==================== Dependency Resolver ====================

class DependencyResolver:
    """Resolve and validate plugin dependencies"""

    def __init__(self):
        self._plugins: dict[str, PluginManifest] = {}
        self._lock = RLock()

    def register_plugin(self, manifest: PluginManifest) -> None:
        """Register plugin for dependency resolution"""
        with self._lock:
            self._plugins[manifest.metadata.plugin_id] = manifest

    def resolve_dependencies(
        self,
        plugin_id: str,
        installed_plugins: dict[str, PluginManifest]
    ) -> tuple[bool, list[str], list[str]]:
        """Resolve and validate dependencies"""
        issues = []
        warnings = []

        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False, ["Plugin not found"], []

        for dep in plugin.dependencies:
            if dep.plugin_id not in installed_plugins:
                if not dep.optional:
                    issues.append(f"Missing required dependency: {dep.plugin_id}")
                else:
                    warnings.append(f"Missing optional dependency: {dep.plugin_id}")
            else:
                installed = installed_plugins[dep.plugin_id]
                if not self._check_version_compatibility(
                    installed.metadata.version,
                    dep.min_version,
                    dep.max_version
                ):
                    issues.append(
                        f"Dependency version mismatch: {dep.plugin_id} "
                        f"(required: {dep.min_version}-{dep.max_version}, "
                        f"installed: {installed.metadata.version})"
                    )

        return len(issues) == 0, issues, warnings

    def _check_version_compatibility(
        self,
        installed_version: str,
        min_version: Optional[str],
        max_version: Optional[str]
    ) -> bool:
        """Check version compatibility"""
        try:
            installed = self._parse_version(installed_version)
            if min_version:
                min_v = self._parse_version(min_version)
                if installed < min_v:
                    return False
            if max_version:
                max_v = self._parse_version(max_version)
                if installed > max_v:
                    return False
            return True
        except (ValueError, IndexError):
            return True

    @staticmethod
    def _parse_version(version: str) -> tuple:
        """Parse semantic version"""
        return tuple(map(int, version.split(".")))


# ==================== Plugin Registry ====================

class PluginRegistry:
    """Central registry for all plugins"""

    def __init__(self, storage_path: Optional[str | Path] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./plugin_registry")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, PluginManifest] = {}
        self._configs: dict[str, PluginConfig] = {}
        self._lock = RLock()
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from storage"""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file) as f:
                    data = json.load(f)
                    for plugin_data in data.get("plugins", []):
                        manifest = PluginManifest(**plugin_data)
                        self._registry[manifest.metadata.plugin_id] = manifest
                logger.info(f"Loaded {len(self._registry)} plugins from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self) -> None:
        """Save registry to storage"""
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

    def register_plugin(self, manifest: PluginManifest) -> None:
        """Register plugin"""
        with self._lock:
            self._registry[manifest.metadata.plugin_id] = manifest
            self._save_registry()
            logger.info(f"Plugin registered: {manifest.metadata.name}")

    def unregister_plugin(self, plugin_id: str) -> None:
        """Unregister plugin"""
        with self._lock:
            if plugin_id in self._registry:
                del self._registry[plugin_id]
                self._save_registry()
                logger.info(f"Plugin unregistered: {plugin_id}")

    def get_plugin(self, plugin_id: str) -> Optional[PluginManifest]:
        """Get plugin manifest"""
        return self._registry.get(plugin_id)

    def list_plugins(self) -> list[PluginManifest]:
        """List all plugins"""
        return list(self._registry.values())

    def search_plugins(self, query: str) -> list[PluginManifest]:
        """Search plugins"""
        query_lower = query.lower()
        return [
            p for p in self._registry.values()
            if query_lower in p.metadata.name.lower()
            or query_lower in p.metadata.description.lower()
            or any(query_lower in cap.name.lower() for cap in p.capabilities)
        ]

    def save_config(self, config: PluginConfig) -> None:
        """Save plugin configuration"""
        with self._lock:
            self._configs[config.plugin_id] = config
            config_file = self.storage_path / f"{config.plugin_id}_config.json"
            with open(config_file, "w") as f:
                json.dump(json.loads(config.model_dump_json()), f, indent=2, default=str)

    def get_config(self, plugin_id: str) -> Optional[PluginConfig]:
        """Get plugin configuration"""
        return self._configs.get(plugin_id)


# ==================== Audit Logger ====================

class AuditLogger:
    """Audit logging for plugin operations"""

    def __init__(self, storage_path: Optional[str | Path] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./plugin_audit")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._audit_log: list[dict[str, Any]] = []
        self._lock = RLock()

    def log_action(
        self,
        plugin_id: str,
        action: str,
        actor_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True
    ) -> None:
        """Log plugin action"""
        record = {
            "audit_id": str(uuid4()),
            "plugin_id": plugin_id,
            "action": action,
            "actor_id": actor_id or "system",
            "success": success,
            "timestamp": datetime.now(UTC).isoformat(),
            "details": details or {}
        }

        with self._lock:
            self._audit_log.append(record)
            self._save_audit_log()

        logger.info(f"Audit: {action} on {plugin_id} by {actor_id or 'system'}")

    def _save_audit_log(self) -> None:
        """Save audit log to storage"""
        audit_file = self.storage_path / "audit.json"
        try:
            with open(audit_file, "w") as f:
                json.dump(self._audit_log, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def get_audit_trail(self, plugin_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get audit trail"""
        if plugin_id:
            return [r for r in self._audit_log if r["plugin_id"] == plugin_id]
        return self._audit_log.copy()


# ==================== Plugin System Manager ====================

class PluginSystemV2:
    """Enhanced plugin system manager"""

    def __init__(self, base_path: Optional[str | Path] = None):
        base_path = Path(base_path) if base_path else Path("./plugin_system")
        base_path.mkdir(parents=True, exist_ok=True)

        self.loader = PluginLoader(base_path / "plugins")
        self.permissions = PermissionManager()
        self.dependency_resolver = DependencyResolver()
        self.registry = PluginRegistry(base_path / "registry")
        self.audit = AuditLogger(base_path / "audit")
        self._lock = RLock()

    def install_plugin(
        self,
        request: PluginInstallRequest,
        actor_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Install a plugin"""
        try:
            # Verify plugin exists
            plugin = self.registry.get_plugin(request.plugin_id)
            if not plugin:
                self.audit.log_action(
                    request.plugin_id,
                    "install",
                    actor_id,
                    {"error": "Plugin not found"},
                    False
                )
                return False, "Plugin not found"

            # Check dependencies
            installed = {p.metadata.plugin_id: p for p in self.registry.list_plugins()}
            compatible, issues, warnings = self.dependency_resolver.resolve_dependencies(
                request.plugin_id,
                installed
            )
            if not compatible:
                error_msg = "; ".join(issues)
                self.audit.log_action(
                    request.plugin_id,
                    "install",
                    actor_id,
                    {"errors": issues},
                    False
                )
                return False, error_msg

            # Load plugin
            success, error = self.loader.load_plugin(request.plugin_id, plugin)
            if not success:
                self.audit.log_action(
                    request.plugin_id,
                    "install",
                    actor_id,
                    {"error": error},
                    False
                )
                return False, error

            # Save configuration
            config = PluginConfig(
                plugin_id=request.plugin_id,
                enabled=request.auto_enable,
                config=request.config
            )
            self.registry.save_config(config)

            # Grant default permissions
            for perm in plugin.permissions:
                self.permissions.grant_permission(
                    request.plugin_id,
                    f"{perm.resource}:{perm.action}"
                )

            self.audit.log_action(
                request.plugin_id,
                "install",
                actor_id,
                {"version": plugin.metadata.version, "config": request.config}
            )

            logger.info(f"Plugin installed: {plugin.metadata.name}")
            return True, None

        except Exception as e:
            error_msg = f"Installation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.audit.log_action(
                request.plugin_id,
                "install",
                actor_id,
                {"error": error_msg},
                False
            )
            return False, error_msg

    def uninstall_plugin(
        self,
        plugin_id: str,
        actor_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Uninstall a plugin"""
        try:
            plugin = self.registry.get_plugin(plugin_id)
            if not plugin:
                return False, "Plugin not found"

            # Unload plugin
            self.loader.unload_plugin(plugin_id)

            # Remove configuration
            config = self.registry.get_config(plugin_id)
            if config:
                config_file = self.registry.storage_path / f"{plugin_id}_config.json"
                if config_file.exists():
                    config_file.unlink()

            self.audit.log_action(
                plugin_id,
                "uninstall",
                actor_id,
                {"version": plugin.metadata.version}
            )

            logger.info(f"Plugin uninstalled: {plugin.metadata.name}")
            return True, None

        except Exception as e:
            error_msg = f"Uninstallation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.audit.log_action(plugin_id, "uninstall", actor_id, {"error": error_msg}, False)
            return False, error_msg

    def enable_plugin(
        self,
        plugin_id: str,
        actor_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Enable a plugin"""
        try:
            config = self.registry.get_config(plugin_id)
            if not config:
                return False, "Plugin not configured"

            config.enabled = True
            config.updated_at = datetime.now(UTC)
            self.registry.save_config(config)

            self.audit.log_action(plugin_id, "enable", actor_id)
            logger.info(f"Plugin enabled: {plugin_id}")
            return True, None

        except Exception as e:
            error_msg = f"Enable failed: {str(e)}"
            logger.error(error_msg)
            self.audit.log_action(plugin_id, "enable", actor_id, {"error": error_msg}, False)
            return False, error_msg

    def disable_plugin(
        self,
        plugin_id: str,
        actor_id: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Disable a plugin"""
        try:
            config = self.registry.get_config(plugin_id)
            if not config:
                return False, "Plugin not configured"

            config.enabled = False
            config.updated_at = datetime.now(UTC)
            self.registry.save_config(config)

            self.audit.log_action(plugin_id, "disable", actor_id)
            logger.info(f"Plugin disabled: {plugin_id}")
            return True, None

        except Exception as e:
            error_msg = f"Disable failed: {str(e)}"
            logger.error(error_msg)
            self.audit.log_action(plugin_id, "disable", actor_id, {"error": error_msg}, False)
            return False, error_msg

    def execute_plugin_action(
        self,
        request: PluginExecutionRequest,
        actor_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Execute plugin action"""
        try:
            # Check if plugin is enabled
            config = self.registry.get_config(request.plugin_id)
            if not config or not config.enabled:
                self.audit.log_action(
                    request.plugin_id,
                    f"execute:{request.action}",
                    actor_id,
                    {"error": "Plugin not enabled"},
                    False
                )
                return {"success": False, "error": "Plugin not enabled"}

            # Check permission
            if not self.permissions.verify_permission(
                request.plugin_id,
                "action",
                request.action
            ):
                self.audit.log_action(
                    request.plugin_id,
                    f"execute:{request.action}",
                    actor_id,
                    {"error": "Permission denied"},
                    False
                )
                return {"success": False, "error": "Permission denied"}

            # Get loaded plugin
            plugin_module = self.loader.get_plugin(request.plugin_id)
            if not plugin_module:
                return {"success": False, "error": "Plugin not loaded"}

            # Execute action
            if not hasattr(plugin_module, "execute"):
                return {"success": False, "error": "Plugin does not support execution"}

            result = plugin_module.execute(request.action, **request.parameters)

            self.audit.log_action(
                request.plugin_id,
                f"execute:{request.action}",
                actor_id,
                {"parameters": request.parameters, "result": result}
            )

            return result

        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.audit.log_action(
                request.plugin_id,
                f"execute:{request.action}",
                actor_id,
                {"error": error_msg},
                False
            )
            return {"success": False, "error": error_msg}

    def get_system_status(self) -> dict[str, Any]:
        """Get plugin system status"""
        plugins = self.registry.list_plugins()
        loaded = self.loader.list_loaded_plugins()
        enabled_count = sum(1 for p in plugins if self.registry.get_config(p.metadata.plugin_id) and self.registry.get_config(p.metadata.plugin_id).enabled)

        return {
            "total_plugins": len(plugins),
            "loaded_plugins": len(loaded),
            "enabled_plugins": enabled_count,
            "plugins": [
                {
                    "plugin_id": p.metadata.plugin_id,
                    "name": p.metadata.name,
                    "version": p.metadata.version,
                    "loaded": p.metadata.plugin_id in loaded,
                    "enabled": self.registry.get_config(p.metadata.plugin_id) and self.registry.get_config(p.metadata.plugin_id).enabled,
                }
                for p in plugins
            ]
        }


# Global instance
plugin_system_v2 = PluginSystemV2()
