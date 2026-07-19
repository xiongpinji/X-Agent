"""MCP Plugin Adapter - Load, validate, and manage MCP plugins for X-Agent"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class MCPPluginStatus(StrEnum):
    """MCP Plugin Status"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNLOADING = "unloading"


class MCPCapability(BaseModel):
    """MCP Capability"""
    tools: bool = False
    resources: bool = False
    prompts: bool = False


class MCPPermission(BaseModel):
    """MCP Permission"""
    network: dict[str, Any] = Field(default_factory=dict)
    filesystem: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)


class MCPEntryPoint(BaseModel):
    """MCP Entry Point"""
    type: str  # python, node, docker
    module: str
    class_name: str = Field(alias="class")

    class Config:
        populate_by_name = True


class MCPManifest(BaseModel):
    """MCP Plugin Manifest"""
    schema_version: str
    name: str
    version: str
    type: str = "mcp-plugin"
    xagent_compatibility: dict[str, str]
    metadata: dict[str, Any]
    chinese: dict[str, Any]
    capabilities: MCPCapability
    permissions: MCPPermission
    entry_point: MCPEntryPoint
    dependencies: dict[str, Any]
    configuration: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    security: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)

    @validator("schema_version")
    def validate_schema_version(cls, v):
        if v != "1.0":
            raise ValueError("schema_version must be '1.0'")
        return v

    @validator("type")
    def validate_type(cls, v):
        if v != "mcp-plugin":
            raise ValueError("type must be 'mcp-plugin'")
        return v

    @validator("name")
    def validate_name(cls, v):
        import re
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("name must contain only lowercase letters, numbers, and hyphens")
        return v


@dataclass
class MCPPlugin:
    """MCP Plugin Instance"""
    plugin_id: str = Field(default_factory=lambda: str(uuid4()))
    manifest: MCPManifest = None
    plugin_path: Path = None
    status: MCPPluginStatus = MCPPluginStatus.UNLOADED
    process: Optional[subprocess.Popen] = None
    config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name if self.manifest else None,
            "version": self.manifest.version if self.manifest else None,
            "status": self.status.value,
            "plugin_path": str(self.plugin_path) if self.plugin_path else None,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
        }


class MCPPluginAdapter:
    """Adapter for loading and managing MCP plugins"""

    def __init__(self, plugins_dir: str | Path | None = None):
        self.plugins_dir = Path(plugins_dir) if plugins_dir else Path("./plugins")
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, MCPPlugin] = {}
        self._lock = RLock()
        self._manifest_cache: dict[str, MCPManifest] = {}

    def load_manifest(self, plugin_path: str | Path) -> MCPManifest:
        """Load and parse plugin manifest"""
        plugin_path = Path(plugin_path)
        manifest_file = plugin_path / "manifest.json"

        if not manifest_file.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_file}")

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            manifest = MCPManifest(**manifest_data)
            self._manifest_cache[manifest.name] = manifest
            logger.info(f"Loaded manifest for plugin: {manifest.name} v{manifest.version}")
            return manifest

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in manifest: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse manifest: {e}")

    def validate_manifest(self, manifest: MCPManifest) -> tuple[bool, list[str]]:
        """Validate plugin manifest"""
        errors = []

        # Check schema version
        if manifest.schema_version != "1.0":
            errors.append(f"Invalid schema_version: {manifest.schema_version}")

        # Check type
        if manifest.type != "mcp-plugin":
            errors.append(f"Invalid type: {manifest.type}")

        # Check name format
        import re
        if not re.match(r"^[a-z0-9-]+$", manifest.name):
            errors.append(f"Invalid name format: {manifest.name}")

        # Check version format
        if not self._is_valid_semver(manifest.version):
            errors.append(f"Invalid version format: {manifest.version}")

        # Check compatibility
        if not self._is_valid_version_range(manifest.xagent_compatibility):
            errors.append("Invalid xagent_compatibility version range")

        # Check metadata
        if not manifest.metadata.get("author"):
            errors.append("metadata.author is required")

        # Check entry point
        if manifest.entry_point.type not in ["python", "node", "docker"]:
            errors.append(f"Invalid entry_point.type: {manifest.entry_point.type}")

        return len(errors) == 0, errors

    def check_compatibility(self, manifest: MCPManifest, xagent_version: str = "0.1.0") -> tuple[bool, list[str]]:
        """Check plugin compatibility with X-Agent version"""
        warnings = []

        min_version = manifest.xagent_compatibility.get("min_version", "0.1.0")
        max_version = manifest.xagent_compatibility.get("max_version", "1.0.0")

        if not self._version_in_range(xagent_version, min_version, max_version):
            return False, [f"X-Agent version {xagent_version} not in range [{min_version}, {max_version}]"]

        # Check Python version if applicable
        if manifest.entry_point.type == "python":
            python_req = manifest.dependencies.get("python", ">=3.8")
            if not self._check_python_version(python_req):
                warnings.append(f"Current Python version may not meet requirement: {python_req}")

        return True, warnings

    def load_plugin(self, plugin_path: str | Path) -> MCPPlugin:
        """Load a plugin from path"""
        plugin_path = Path(plugin_path)

        if not plugin_path.is_dir():
            raise ValueError(f"Plugin path is not a directory: {plugin_path}")

        try:
            # Load manifest
            manifest = self.load_manifest(plugin_path)

            # Validate manifest
            is_valid, errors = self.validate_manifest(manifest)
            if not is_valid:
                raise ValueError(f"Manifest validation failed: {', '.join(errors)}")

            # Create plugin instance
            plugin = MCPPlugin(
                manifest=manifest,
                plugin_path=plugin_path,
                status=MCPPluginStatus.LOADED,
            )

            with self._lock:
                self._plugins[plugin.plugin_id] = plugin

            logger.info(f"Plugin loaded: {manifest.name} ({plugin.plugin_id})")
            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_path}: {e}")
            raise

    def start_server(self, plugin: MCPPlugin) -> bool:
        """Start MCP server for plugin"""
        if plugin.status == MCPPluginStatus.RUNNING:
            logger.warning(f"Plugin {plugin.manifest.name} is already running")
            return True

        try:
            plugin.status = MCPPluginStatus.LOADING
            plugin.updated_at = datetime.now(UTC)

            entry_point = plugin.manifest.entry_point

            if entry_point.type == "python":
                # Start Python MCP server
                cmd = [
                    sys.executable,
                    "-m",
                    entry_point.module,
                ]
                plugin.process = subprocess.Popen(
                    cmd,
                    cwd=str(plugin.plugin_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                plugin.status = MCPPluginStatus.RUNNING
                logger.info(f"Started Python MCP server for {plugin.manifest.name}")

            elif entry_point.type == "node":
                # Start Node.js MCP server
                cmd = ["node", str(plugin.plugin_path / entry_point.module)]
                plugin.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                plugin.status = MCPPluginStatus.RUNNING
                logger.info(f"Started Node.js MCP server for {plugin.manifest.name}")

            elif entry_point.type == "docker":
                # Start Docker container
                logger.info(f"Docker support not yet implemented for {plugin.manifest.name}")
                return False

            return True

        except Exception as e:
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to start server for {plugin.manifest.name}: {e}")
            return False

    def stop_server(self, plugin: MCPPlugin) -> bool:
        """Stop MCP server for plugin"""
        if plugin.status != MCPPluginStatus.RUNNING:
            logger.warning(f"Plugin {plugin.manifest.name} is not running")
            return True

        try:
            plugin.status = MCPPluginStatus.UNLOADING
            plugin.updated_at = datetime.now(UTC)

            if plugin.process:
                plugin.process.terminate()
                try:
                    plugin.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    plugin.process.kill()
                    plugin.process.wait()

            plugin.status = MCPPluginStatus.STOPPED
            logger.info(f"Stopped MCP server for {plugin.manifest.name}")
            return True

        except Exception as e:
            plugin.status = MCPPluginStatus.ERROR
            plugin.error_message = str(e)
            logger.error(f"Failed to stop server for {plugin.manifest.name}: {e}")
            return False

    def call_tool(self, plugin: MCPPlugin, tool_name: str, args: dict[str, Any]) -> Any:
        """Call a tool provided by the plugin.

        ⚠️ 未实现：插件进程的 MCP 协议握手（initialize/tools-call）尚未接线，
        ``start_server`` 仅拉起进程。本方法**显式报错**而不是返回伪造的成功
        结果（P1-01 反"假成功"裁决）。真实 MCP server 请使用
        ``backend.app.core.mcp.client.MCPClient``（stdio / Streamable HTTP）。
        """
        if plugin.status != MCPPluginStatus.RUNNING:
            raise RuntimeError(f"Plugin {plugin.manifest.name} is not running")

        # Find tool definition
        tool_def = None
        for tool in plugin.manifest.tools:
            if tool.get("name") == tool_name:
                tool_def = tool
                break

        if not tool_def:
            raise ValueError(f"Tool not found: {tool_name}")

        # Validate input schema
        self._validate_tool_input(tool_def, args)

        raise NotImplementedError(
            f"Plugin tool invocation over MCP protocol is not implemented "
            f"(plugin={plugin.manifest.name}, tool={tool_name}). "
            f"Use backend.app.core.mcp.client.MCPClient for real MCP servers "
            f"(stdio / Streamable HTTP); plugin-process MCP handshake is a "
            f"tracked TODO owned by the plugin runtime (P1-12)."
        )

    def get_resources(self, plugin: MCPPlugin) -> list[dict[str, Any]]:
        """Get resources provided by plugin"""
        if not plugin.manifest.capabilities.resources:
            return []

        return plugin.manifest.resources

    def get_tools(self, plugin: MCPPlugin) -> list[dict[str, Any]]:
        """Get tools provided by plugin"""
        if not plugin.manifest.capabilities.tools:
            return []

        return plugin.manifest.tools

    def update_config(self, plugin: MCPPlugin, config: dict[str, Any]) -> bool:
        """Update plugin configuration"""
        try:
            # Validate configuration
            self._validate_config(plugin.manifest, config)

            plugin.config.update(config)
            plugin.updated_at = datetime.now(UTC)
            logger.info(f"Updated config for plugin {plugin.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update config for {plugin.manifest.name}: {e}")
            return False

    def get_plugin(self, plugin_id: str) -> Optional[MCPPlugin]:
        """Get plugin by ID"""
        with self._lock:
            return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[MCPPlugin]:
        """List all loaded plugins"""
        with self._lock:
            return list(self._plugins.values())

    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin"""
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return False

        try:
            # Stop server if running
            if plugin.status == MCPPluginStatus.RUNNING:
                self.stop_server(plugin)

            with self._lock:
                del self._plugins[plugin_id]

            logger.info(f"Unloaded plugin {plugin.manifest.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}")
            return False

    # Helper methods

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if version is valid semantic version"""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?(\+[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))

    @staticmethod
    def _is_valid_version_range(version_range: dict[str, str]) -> bool:
        """Check if version range is valid"""
        min_v = version_range.get("min_version")
        max_v = version_range.get("max_version")

        if not min_v or not max_v:
            return False

        if not MCPPluginAdapter._is_valid_semver(min_v):
            return False

        if not MCPPluginAdapter._is_valid_semver(max_v):
            return False

        return MCPPluginAdapter._compare_versions(min_v, max_v) <= 0

    @staticmethod
    def _version_in_range(version: str, min_v: str, max_v: str) -> bool:
        """Check if version is in range"""
        return (MCPPluginAdapter._compare_versions(version, min_v) >= 0 and
                MCPPluginAdapter._compare_versions(version, max_v) <= 0)

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """Compare two semantic versions. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2"""
        def parse_version(v):
            parts = v.split("-")[0].split("+")[0].split(".")
            return tuple(int(p) for p in parts)

        p1 = parse_version(v1)
        p2 = parse_version(v2)

        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        else:
            return 0

    @staticmethod
    def _check_python_version(requirement: str) -> bool:
        """Check if current Python version meets requirement"""
        import re
        current = sys.version_info

        # Parse requirement like ">=3.11" or "3.8"
        match = re.match(r"([><=!]+)?(\d+\.\d+)", requirement)
        if not match:
            return True

        op = match.group(1) or ">="
        required = tuple(int(x) for x in match.group(2).split("."))

        if op == ">=":
            return (current.major, current.minor) >= required
        elif op == ">":
            return (current.major, current.minor) > required
        elif op == "<=":
            return (current.major, current.minor) <= required
        elif op == "<":
            return (current.major, current.minor) < required
        elif op == "==":
            return (current.major, current.minor) == required
        elif op == "!=":
            return (current.major, current.minor) != required

        return True

    @staticmethod
    def _validate_tool_input(tool_def: dict[str, Any], args: dict[str, Any]) -> None:
        """Validate tool input against schema"""
        schema = tool_def.get("input_schema", {})
        required = schema.get("required", [])

        for field in required:
            if field not in args:
                raise ValueError(f"Required field missing: {field}")

    @staticmethod
    def _validate_config(manifest: MCPManifest, config: dict[str, Any]) -> None:
        """Validate configuration against manifest"""
        config_schema = manifest.configuration

        for key, value in config.items():
            if key not in config_schema:
                raise ValueError(f"Unknown configuration key: {key}")

            field_schema = config_schema[key]
            expected_type = field_schema.get("type")

            # Type validation
            if expected_type == "string" and not isinstance(value, str):
                raise ValueError(f"Configuration {key} must be string")
            elif expected_type == "integer" and not isinstance(value, int):
                raise ValueError(f"Configuration {key} must be integer")
            elif expected_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"Configuration {key} must be boolean")

        # Check required fields
        for key, field_schema in config_schema.items():
            if field_schema.get("required") and key not in config:
                raise ValueError(f"Required configuration missing: {key}")
