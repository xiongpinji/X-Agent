"""
工具注册表 - 支持动态注册、版本管理、权限检查
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from backend.app.core.tool_schema import (
    ToolSchema,
    ToolCategory,
    ToolRiskLevel,
    ToolStatus,
    ToolAuditEntry,
    ToolLifecycleEvent,
)


class ToolRegistry:
    """工具注册表 - 管理所有工具的生命周期"""

    def __init__(self, storage_path: str | Path | None = None):
        self._tools: dict[str, ToolSchema] = {}
        self._versions: dict[str, list[ToolSchema]] = {}  # tool_name -> [versions]
        self._audit_log: list[ToolAuditEntry] = []
        self._lifecycle_events: list[ToolLifecycleEvent] = []
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def register(self, schema: ToolSchema) -> ToolSchema:
        """注册新工具或更新现有工具"""
        with self._lock:
            # 检查是否已存在
            existing = self._tools.get(schema.name)
            if existing and existing.version == schema.version:
                raise ValueError(f"Tool {schema.name}@{schema.version} already registered")

            # 保存到版本历史
            if schema.name not in self._versions:
                self._versions[schema.name] = []
            self._versions[schema.name].append(schema)

            # 更新当前版本
            self._tools[schema.name] = schema

            # 记录生命周期事件
            event = ToolLifecycleEvent(
                tool_id=schema.id,
                tool_name=schema.name,
                event_type="installed",
                version=schema.version,
            )
            self._lifecycle_events.append(event)

            self._persist()
            return schema

    def unregister(self, tool_name: str) -> bool:
        """注销工具"""
        with self._lock:
            if tool_name not in self._tools:
                return False

            tool = self._tools.pop(tool_name)

            # 记录生命周期事件
            event = ToolLifecycleEvent(
                tool_id=tool.id,
                tool_name=tool_name,
                event_type="uninstalled",
                version=tool.version,
            )
            self._lifecycle_events.append(event)

            self._persist()
            return True

    def get(self, tool_name: str) -> ToolSchema | None:
        """获取工具"""
        return self._tools.get(tool_name)

    def get_version(self, tool_name: str, version: str) -> ToolSchema | None:
        """获取特定版本的工具"""
        versions = self._versions.get(tool_name, [])
        for v in versions:
            if v.version == version:
                return v
        return None

    def list_all(self) -> list[ToolSchema]:
        """列出所有工具"""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> list[ToolSchema]:
        """按分类列出工具"""
        return [t for t in self._tools.values() if t.category == category]

    def list_by_status(self, status: ToolStatus) -> list[ToolSchema]:
        """按状态列出工具"""
        return [t for t in self._tools.values() if t.status == status]

    def list_versions(self, tool_name: str) -> list[ToolSchema]:
        """列出工具的所有版本"""
        return self._versions.get(tool_name, [])

    def enable(self, tool_name: str) -> bool:
        """启用工具"""
        with self._lock:
            tool = self._tools.get(tool_name)
            if not tool:
                return False

            tool.status = ToolStatus.ACTIVE
            tool.updated_at = datetime.now(UTC)

            event = ToolLifecycleEvent(
                tool_id=tool.id,
                tool_name=tool_name,
                event_type="enabled",
                version=tool.version,
            )
            self._lifecycle_events.append(event)

            self._persist()
            return True

    def disable(self, tool_name: str) -> bool:
        """禁用工具"""
        with self._lock:
            tool = self._tools.get(tool_name)
            if not tool:
                return False

            tool.status = ToolStatus.DISABLED
            tool.updated_at = datetime.now(UTC)

            event = ToolLifecycleEvent(
                tool_id=tool.id,
                tool_name=tool_name,
                event_type="disabled",
                version=tool.version,
            )
            self._lifecycle_events.append(event)

            self._persist()
            return True

    def deprecate(self, tool_name: str, reason: str = "") -> bool:
        """弃用工具"""
        with self._lock:
            tool = self._tools.get(tool_name)
            if not tool:
                return False

            tool.status = ToolStatus.DEPRECATED
            tool.deprecated_at = datetime.now(UTC)
            tool.deprecated_reason = reason
            tool.updated_at = datetime.now(UTC)

            event = ToolLifecycleEvent(
                tool_id=tool.id,
                tool_name=tool_name,
                event_type="deprecated",
                version=tool.version,
                details={"reason": reason},
            )
            self._lifecycle_events.append(event)

            self._persist()
            return True

    def upgrade(self, tool_name: str, new_schema: ToolSchema) -> bool:
        """升级工具版本"""
        with self._lock:
            old_tool = self._tools.get(tool_name)
            if not old_tool:
                return False

            # 保存新版本
            if tool_name not in self._versions:
                self._versions[tool_name] = []
            self._versions[tool_name].append(new_schema)

            # 更新当前版本
            self._tools[tool_name] = new_schema

            event = ToolLifecycleEvent(
                tool_id=new_schema.id,
                tool_name=tool_name,
                event_type="upgraded",
                version=new_schema.version,
                details={"from_version": old_tool.version},
            )
            self._lifecycle_events.append(event)

            self._persist()
            return True

    def check_permission(self, tool_name: str, required_scope: str) -> bool:
        """检查权限"""
        tool = self._tools.get(tool_name)
        if not tool:
            return False

        return required_scope in tool.permissions

    def record_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: int = 0,
        input_preview: dict[str, Any] | None = None,
        output_preview: dict[str, Any] | None = None,
        error: str | None = None,
        trace_id: str | None = None,
        run_id: str | None = None,
        actor_id: str = "system",
        tenant_id: str = "default",
    ) -> ToolAuditEntry:
        """记录工具调用"""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        entry = ToolAuditEntry(
            tool_id=tool.id,
            tool_name=tool_name,
            action="call",
            actor_id=actor_id,
            tenant_id=tenant_id,
            input_preview=input_preview,
            output_preview=output_preview,
            success=success,
            error=error,
            latency_ms=latency_ms,
            trace_id=trace_id,
            run_id=run_id,
        )

        with self._lock:
            self._audit_log.append(entry)
            self._persist()

        return entry

    def get_audit_log(
        self,
        tool_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolAuditEntry]:
        """获取审计日志"""
        logs = self._audit_log
        if tool_name:
            logs = [l for l in logs if l.tool_name == tool_name]

        logs.sort(key=lambda x: x.created_at, reverse=True)
        return logs[offset : offset + limit]

    def get_lifecycle_events(
        self,
        tool_name: str | None = None,
        limit: int = 100,
    ) -> list[ToolLifecycleEvent]:
        """获取生命周期事件"""
        events = self._lifecycle_events
        if tool_name:
            events = [e for e in events if e.tool_name == tool_name]

        events.sort(key=lambda x: x.created_at, reverse=True)
        return events[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": len(self._tools),
            "active_tools": len([t for t in self._tools.values() if t.status == ToolStatus.ACTIVE]),
            "disabled_tools": len([t for t in self._tools.values() if t.status == ToolStatus.DISABLED]),
            "deprecated_tools": len([t for t in self._tools.values() if t.status == ToolStatus.DEPRECATED]),
            "by_category": {
                cat.value: len([t for t in self._tools.values() if t.category == cat])
                for cat in ToolCategory
            },
            "by_risk_level": {
                risk.value: len([t for t in self._tools.values() if t.risk_level == risk])
                for risk in ToolRiskLevel
            },
            "total_calls": len(self._audit_log),
            "successful_calls": len([a for a in self._audit_log if a.success]),
            "failed_calls": len([a for a in self._audit_log if not a.success]),
        }

    def _persist(self) -> None:
        """持久化到磁盘"""
        if not self._storage_path:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存工具
        tools_file = self._storage_path / "tools.jsonl"
        with tools_file.open("w", encoding="utf-8") as f:
            for tool in self._tools.values():
                f.write(tool.model_dump_json() + "\n")

        # 保存审计日志
        audit_file = self._storage_path / "audit.jsonl"
        with audit_file.open("w", encoding="utf-8") as f:
            for entry in self._audit_log:
                f.write(entry.model_dump_json() + "\n")

        # 保存生命周期事件
        events_file = self._storage_path / "lifecycle.jsonl"
        with events_file.open("w", encoding="utf-8") as f:
            for event in self._lifecycle_events:
                f.write(event.model_dump_json() + "\n")

    def _load_from_disk(self) -> None:
        """从磁盘加载"""
        if not self._storage_path:
            return

        # 加载工具
        tools_file = self._storage_path / "tools.jsonl"
        if tools_file.exists():
            with tools_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        tool = ToolSchema.model_validate_json(line)
                        self._tools[tool.name] = tool
                        if tool.name not in self._versions:
                            self._versions[tool.name] = []
                        self._versions[tool.name].append(tool)

        # 加载审计日志
        audit_file = self._storage_path / "audit.jsonl"
        if audit_file.exists():
            with audit_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = ToolAuditEntry.model_validate_json(line)
                        self._audit_log.append(entry)

        # 加载生命周期事件
        events_file = self._storage_path / "lifecycle.jsonl"
        if events_file.exists():
            with events_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        event = ToolLifecycleEvent.model_validate_json(line)
                        self._lifecycle_events.append(event)
