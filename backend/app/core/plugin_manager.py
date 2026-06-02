"""
Plugin marketplace system for X-Agent.
Manages plugin discovery, installation, versioning, and dependency resolution.
"""

from __future__ import annotations

import asyncio
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Callable
from abc import ABC, abstractmethod
import semver


class PluginStatus(str, Enum):
    """Plugin status."""
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATING = "updating"
    DISABLED = "disabled"
    BROKEN = "broken"


class PluginCategory(str, Enum):
    """Plugin categories."""
    TOOLS = "tools"
    INTEGRATIONS = "integrations"
    MODELS = "models"
    STORAGE = "storage"
    OBSERVABILITY = "observability"
    UTILITIES = "utilities"


@dataclass
class PluginDependency:
    """Plugin dependency specification."""
    name: str
    version: str  # Semantic version constraint
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PluginMetadata:
    """Plugin metadata."""
    name: str
    version: str
    author: str
    description: str
    category: PluginCategory
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = "MIT"
    keywords: list[str] = field(default_factory=list)
    dependencies: list[PluginDependency] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    min_xagent_version: str = "0.1.0"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['category'] = self.category.value
        data['dependencies'] = [d.to_dict() for d in self.dependencies]
        return data


@dataclass
class PluginInfo:
    """Plugin information."""
    metadata: PluginMetadata
    status: PluginStatus
    installed_version: Optional[str] = None
    installed_at: Optional[str] = None
    enabled: bool = True
    checksum: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "status": self.status.value,
            "installed_version": self.installed_version,
            "installed_at": self.installed_at,
            "enabled": self.enabled,
            "checksum": self.checksum,
        }


class VersionConstraint:
    """Semantic version constraint resolver."""

    @staticmethod
    def matches(version: str, constraint: str) -> bool:
        """Check if version matches constraint."""
        try:
            v = semver.VersionInfo.parse(version)

            # Handle different constraint formats
            if constraint.startswith("^"):
                # Caret: compatible with version
                min_v = semver.VersionInfo.parse(constraint[1:])
                return v >= min_v and v.major == min_v.major

            elif constraint.startswith("~"):
                # Tilde: approximately equivalent
                min_v = semver.VersionInfo.parse(constraint[1:])
                return v >= min_v and v.major == min_v.major and v.minor == min_v.minor

            elif constraint.startswith(">="):
                min_v = semver.VersionInfo.parse(constraint[2:])
                return v >= min_v

            elif constraint.startswith("<="):
                max_v = semver.VersionInfo.parse(constraint[2:])
                return v <= max_v

            elif constraint.startswith("=="):
                target_v = semver.VersionInfo.parse(constraint[2:])
                return v == target_v

            else:
                # Exact match
                target_v = semver.VersionInfo.parse(constraint)
                return v == target_v

        except Exception:
            return False


class DependencyResolver:
    """Resolves plugin dependencies."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    async def resolve(self, plugin: PluginMetadata) -> tuple[bool, list[str], list[str]]:
        """
        Resolve plugin dependencies.
        Returns: (success, resolved_plugins, errors)
        """
        resolved = []
        errors = []
        visited = set()

        async def resolve_recursive(dep: PluginDependency) -> bool:
            if dep.name in visited:
                return True

            visited.add(dep.name)

            # Find plugin in registry
            available = await self.registry.search(name=dep.name)
            if not available:
                if not dep.optional:
                    errors.append(f"Dependency not found: {dep.name}")
                return dep.optional

            # Check version compatibility
            plugin_info = available[0]
            if not VersionConstraint.matches(plugin_info.metadata.version, dep.version):
                if not dep.optional:
                    errors.append(
                        f"Version mismatch for {dep.name}: "
                        f"required {dep.version}, found {plugin_info.metadata.version}"
                    )
                return dep.optional

            resolved.append(dep.name)

            # Recursively resolve dependencies
            for sub_dep in plugin_info.metadata.dependencies:
                if not await resolve_recursive(sub_dep):
                    return False

            return True

        # Resolve all dependencies
        for dep in plugin.dependencies:
            if not await resolve_recursive(dep):
                if not dep.optional:
                    return False, resolved, errors

        return True, resolved, errors


class PluginRegistry:
    """Central plugin registry."""

    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or Path("~/.xagent/plugins/registry.json").expanduser()
        self.plugins: dict[str, PluginInfo] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from disk."""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text())
                # Deserialize plugins
                for name, plugin_data in data.items():
                    metadata_dict = plugin_data["metadata"]
                    metadata_dict["category"] = PluginCategory(metadata_dict["category"])
                    metadata_dict["dependencies"] = [
                        PluginDependency(**d) for d in metadata_dict.get("dependencies", [])
                    ]
                    metadata = PluginMetadata(**metadata_dict)
                    self.plugins[name] = PluginInfo(
                        metadata=metadata,
                        status=PluginStatus(plugin_data["status"]),
                        installed_version=plugin_data.get("installed_version"),
                        installed_at=plugin_data.get("installed_at"),
                        enabled=plugin_data.get("enabled", True),
                        checksum=plugin_data.get("checksum"),
                    )
            except Exception:
                pass

    def _save_registry(self) -> None:
        """Save registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {name: plugin.to_dict() for name, plugin in self.plugins.items()}
        self.registry_path.write_text(json.dumps(data, indent=2))

    async def register(self, metadata: PluginMetadata) -> bool:
        """Register a plugin."""
        if metadata.name in self.plugins:
            return False

        self.plugins[metadata.name] = PluginInfo(
            metadata=metadata,
            status=PluginStatus.AVAILABLE,
        )
        self._save_registry()
        return True

    async def search(
        self,
        name: Optional[str] = None,
        category: Optional[PluginCategory] = None,
        keyword: Optional[str] = None,
    ) -> list[PluginInfo]:
        """Search plugins."""
        results = []

        for plugin in self.plugins.values():
            if name and plugin.metadata.name != name:
                continue

            if category and plugin.metadata.category != category:
                continue

            if keyword:
                search_text = (
                    f"{plugin.metadata.name} {plugin.metadata.description} "
                    f"{' '.join(plugin.metadata.keywords)}"
                ).lower()
                if keyword.lower() not in search_text:
                    continue

            results.append(plugin)

        return results

    async def get(self, name: str) -> Optional[PluginInfo]:
        """Get plugin by name."""
        return self.plugins.get(name)

    async def update_status(self, name: str, status: PluginStatus) -> bool:
        """Update plugin status."""
        if name not in self.plugins:
            return False

        self.plugins[name].status = status
        self._save_registry()
        return True

    async def list_installed(self) -> list[PluginInfo]:
        """List installed plugins."""
        return [p for p in self.plugins.values() if p.status == PluginStatus.INSTALLED]

    async def list_available(self) -> list[PluginInfo]:
        """List available plugins."""
        return [p for p in self.plugins.values() if p.status == PluginStatus.AVAILABLE]


class PluginLoader(ABC):
    """Abstract plugin loader."""

    @abstractmethod
    async def load(self, plugin_path: Path) -> Any:
        """Load plugin from path."""
        pass

    @abstractmethod
    async def unload(self, plugin_name: str) -> bool:
        """Unload plugin."""
        pass


class PythonPluginLoader(PluginLoader):
    """Loads Python plugins."""

    def __init__(self):
        self.loaded_plugins: dict[str, Any] = {}

    async def load(self, plugin_path: Path) -> Any:
        """Load Python plugin."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("plugin", plugin_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            return None
        except Exception:
            return None

    async def unload(self, plugin_name: str) -> bool:
        """Unload plugin."""
        if plugin_name in self.loaded_plugins:
            del self.loaded_plugins[plugin_name]
            return True
        return False


class PluginManager:
    """Manages plugin lifecycle."""

    def __init__(self, plugins_dir: Optional[Path] = None):
        self.plugins_dir = plugins_dir or Path("~/.xagent/plugins").expanduser()
        self.registry = PluginRegistry()
        self.dependency_resolver = DependencyResolver(self.registry)
        self.loader = PythonPluginLoader()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    async def install(self, plugin_name: str, version: Optional[str] = None) -> tuple[bool, str]:
        """Install a plugin."""
        # Search for plugin
        results = await self.registry.search(name=plugin_name)
        if not results:
            return False, f"Plugin not found: {plugin_name}"

        plugin_info = results[0]

        # Resolve dependencies
        success, resolved, errors = await self.dependency_resolver.resolve(plugin_info.metadata)
        if not success:
            return False, f"Dependency resolution failed: {', '.join(errors)}"

        # Update status
        await self.registry.update_status(plugin_name, PluginStatus.INSTALLED)
        plugin_info.installed_version = plugin_info.metadata.version
        plugin_info.installed_at = datetime.utcnow().isoformat()

        return True, f"Plugin installed: {plugin_name}"

    async def uninstall(self, plugin_name: str) -> tuple[bool, str]:
        """Uninstall a plugin."""
        plugin_info = await self.registry.get(plugin_name)
        if not plugin_info:
            return False, f"Plugin not found: {plugin_name}"

        await self.registry.update_status(plugin_name, PluginStatus.AVAILABLE)
        await self.loader.unload(plugin_name)

        return True, f"Plugin uninstalled: {plugin_name}"

    async def enable(self, plugin_name: str) -> tuple[bool, str]:
        """Enable a plugin."""
        plugin_info = await self.registry.get(plugin_name)
        if not plugin_info:
            return False, f"Plugin not found: {plugin_name}"

        plugin_info.enabled = True
        self.registry._save_registry()
        return True, f"Plugin enabled: {plugin_name}"

    async def disable(self, plugin_name: str) -> tuple[bool, str]:
        """Disable a plugin."""
        plugin_info = await self.registry.get(plugin_name)
        if not plugin_info:
            return False, f"Plugin not found: {plugin_name}"

        plugin_info.enabled = False
        self.registry._save_registry()
        return True, f"Plugin disabled: {plugin_name}"

    async def list_plugins(self) -> list[PluginInfo]:
        """List all plugins."""
        return list(self.registry.plugins.values())

    async def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information."""
        return await self.registry.get(plugin_name)
