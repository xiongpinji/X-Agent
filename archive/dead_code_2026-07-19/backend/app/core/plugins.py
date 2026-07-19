from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field


class PluginStatus(str):
    INACTIVE = "inactive"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class PluginRecord(BaseModel):
    plugin_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str = "v1"
    description: str = ""
    status: str = PluginStatus.INACTIVE
    capabilities: list[str] = Field(default_factory=list)
    manifest: dict[str, object] = Field(default_factory=dict)
    sandbox: str = "isolated"
    risk_level: str = "medium"
    allowed_actions: list[str] = Field(default_factory=lambda: ["read", "execute"])
    requires_approval: bool = False
    installed: bool = False
    install_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginExecutionRecord(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str
    action: str
    success: bool = True
    output: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PluginStore:
    _records: dict[str, PluginRecord] = field(default_factory=dict)
    _executions: list[PluginExecutionRecord] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock)

    def register(self, name: str, version: str = "v1", description: str = "", capabilities: list[str] | None = None, manifest: dict[str, object] | None = None, sandbox: str = "isolated", risk_level: str = "medium", allowed_actions: list[str] | None = None, requires_approval: bool = False, installed: bool = False, install_path: str | None = None) -> PluginRecord:
        record = PluginRecord(
            name=name,
            version=version,
            description=description,
            capabilities=capabilities or [],
            manifest=manifest or {},
            sandbox=sandbox,
            risk_level=risk_level,
            allowed_actions=allowed_actions or ["read", "execute"],
            requires_approval=requires_approval,
            installed=installed,
            install_path=install_path,
        )
        with self._lock:
            self._records[record.plugin_id] = record
        return record

    def list(self) -> list[PluginRecord]:
        items = list(self._records.values())
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def get(self, plugin_id: str) -> PluginRecord | None:
        return self._records.get(plugin_id)

    def update(self, plugin_id: str, **changes) -> PluginRecord | None:
        with self._lock:
            record = self._records.get(plugin_id)
            if record is None:
                return None
            updated = record.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
            self._records[plugin_id] = updated
            return updated

    def can_execute(self, plugin_id: str, action: str) -> bool:
        record = self._records.get(plugin_id)
        if record is None:
            return False
        if record.status != PluginStatus.ACTIVE or not record.installed:
            return False
        return action in set(record.allowed_actions) or "*" in set(record.allowed_actions)

    def needs_approval(self, plugin_id: str) -> bool:
        record = self._records.get(plugin_id)
        if record is None:
            return True
        return bool(record.requires_approval) or record.risk_level in {"high", "critical"}

    def enable(self, plugin_id: str) -> PluginRecord | None:
        return self.update(plugin_id, status=PluginStatus.ACTIVE, installed=True)

    def disable(self, plugin_id: str) -> PluginRecord | None:
        return self.update(plugin_id, status=PluginStatus.DISABLED)

    def install(self, plugin_id: str, install_path: str | None = None) -> PluginRecord | None:
        return self.update(plugin_id, installed=True, install_path=install_path, status=PluginStatus.ACTIVE)

    def uninstall(self, plugin_id: str) -> PluginRecord | None:
        return self.update(plugin_id, installed=False, install_path=None, status=PluginStatus.INACTIVE)

    def delete(self, plugin_id: str) -> bool:
        with self._lock:
            return self._records.pop(plugin_id, None) is not None

    def record_execution(self, plugin_id: str, action: str, *, success: bool = True, output: dict[str, object] | None = None, error: str | None = None) -> PluginExecutionRecord:
        record = PluginExecutionRecord(
            plugin_id=plugin_id,
            action=action,
            success=success,
            output=output or {},
            error=error,
        )
        with self._lock:
            self._executions.append(record)
        return record

    def list_executions(self, plugin_id: str | None = None) -> list[PluginExecutionRecord]:
        executions = self._executions
        if plugin_id is not None:
            executions = [item for item in executions if item.plugin_id == plugin_id]
        return list(reversed(executions))


plugin_store = PluginStore()
