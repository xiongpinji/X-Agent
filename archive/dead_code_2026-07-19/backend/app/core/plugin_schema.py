"""Plugin Schema and Data Models for X-Agent Plugin System"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class PluginRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PluginStatus(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    INSTALLING = "installing"
    UNINSTALLING = "uninstalling"


class PluginSchema(BaseModel):
    """Standard plugin schema for X-Agent marketplace"""

    plugin_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    author: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    risk_level: PluginRiskLevel = PluginRiskLevel.MEDIUM
    install_url: str
    documentation_url: str
    status: PluginStatus = PluginStatus.INACTIVE
    installed: bool = False
    enabled: bool = False
    install_path: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @validator("version")
    def validate_version(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("Version must be a non-empty string")
        return v

    @validator("capabilities", "dependencies", "permissions", pre=True, always=True)
    def ensure_list(cls, v):
        return v or []


class PluginDependency(BaseModel):
    """Plugin dependency specification"""

    plugin_id: str
    min_version: str | None = None
    max_version: str | None = None
    optional: bool = False


class PluginPermission(BaseModel):
    """Plugin permission specification"""

    resource: str
    action: str
    scope: str = "default"


class PluginCapability(BaseModel):
    """Plugin capability specification"""

    name: str
    description: str
    version: str = "1.0"
    parameters: dict[str, Any] = Field(default_factory=dict)


class PluginInstallRequest(BaseModel):
    """Request to install a plugin"""

    plugin_id: str
    version: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    auto_enable: bool = False


class PluginUninstallRequest(BaseModel):
    """Request to uninstall a plugin"""

    plugin_id: str
    force: bool = False


class PluginExecutionRecord(BaseModel):
    """Record of plugin execution"""

    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    action: str
    success: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginCompatibilityCheck(BaseModel):
    """Result of plugin compatibility check"""

    compatible: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_version: str | None = None


class PluginAuditRecord(BaseModel):
    """Audit record for plugin operations"""

    audit_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    action: str
    actor_id: str = "system"
    outcome: str = "success"
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
