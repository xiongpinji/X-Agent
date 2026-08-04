"""
工具目录 (ToolCatalog) - 支持动态注册、版本管理、权限检查、审计与持久化。

历史命名说明：本模块的目录类原名 ``ToolRegistry``，与 ``core/tools.py`` 中
负责运行时执行（policy/approval/hooks/execute）的 ``ToolRegistry`` 同名，长期
造成混淆。现规范名为 ``ToolCatalog``（工具 schema 目录/生命周期），并保留
``ToolRegistry`` 作为向后兼容别名，避免破坏既有 import。

P1-10 架构裁决（单一事实来源）：

* **运行时执行注册表唯一**：``backend.app.core.tools.ToolRegistry`` 是 Agent
  主循环唯一的工具执行表（policy/approval/hooks/execute 咽喉点）。
* **Schema 目录唯一**：本模块的 ``ToolCatalog`` 是唯一的工具元数据目录
  （版本/状态/生命周期），通过 :meth:`ToolCatalog.bind_runtime_registry`
  与运行时注册表形成显式组合关系，而非平行第三套注册表。
* **风险模型统一**：目录侧 ``ToolRiskLevel`` 与运行时侧
  ``contracts.RiskLevel`` 的换算只允许经
  :func:`catalog_risk_to_runtime` / :func:`runtime_risk_to_catalog`，
  禁止各调用方自行实现第二份映射。
* **审计单轨**：工具*执行*审计的唯一轨道是运行时注册表写入的
  ``ToolExecutionStore``；``ToolCatalog.record_call`` 仅供
  ``core/tool_executor.py`` 的旧管理面调用，不再承接 MCP/主循环执行审计。
* **实例唯一（2026-08-04 收尾）**：``ToolCatalog`` 的唯一生产实例由
  ``backend.app.dependencies.get_tool_catalog()`` 持有（lru_cache 单例），
  main.py startup（MCP 发现双写）、container、ToolExecutor/ToolManager
  旧管理面全部共享；仅显式传 ``storage_path`` 的场景（测试/离线工具）
  允许构造隔离实例。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from backend.app.core.contracts import RiskLevel
from backend.app.core.tool_schema import (
    ToolAuditEntry,
    ToolCategory,
    ToolLifecycleEvent,
    ToolRiskLevel,
    ToolSchema,
    ToolStatus,
)

# 风险等级严重度顺序（单一事实来源，供映射与"取较高者"比较使用）。
_RISK_SEVERITY: tuple[str, ...] = ("low", "medium", "high", "critical")


def catalog_risk_to_runtime(risk: ToolRiskLevel | str) -> RiskLevel:
    """目录侧 ToolRiskLevel → 运行时 contracts.RiskLevel（唯一换算入口）。"""
    value = risk.value if isinstance(risk, ToolRiskLevel) else str(risk)
    try:
        return RiskLevel(value)
    except ValueError:
        # 未知等级一律按 HIGH 处理（保守，不允许静默降级为低风险）。
        return RiskLevel.HIGH


def runtime_risk_to_catalog(risk: RiskLevel | str) -> ToolRiskLevel:
    """运行时 contracts.RiskLevel → 目录侧 ToolRiskLevel（唯一换算入口）。"""
    value = risk.value if isinstance(risk, RiskLevel) else str(risk)
    try:
        return ToolRiskLevel(value)
    except ValueError:
        return ToolRiskLevel.HIGH


def max_catalog_risk(*risks: ToolRiskLevel) -> ToolRiskLevel:
    """返回若干目录风险等级中最高者（用于多来源风险信号取保守值）。"""
    if not risks:
        return ToolRiskLevel.LOW
    return max(risks, key=lambda r: _RISK_SEVERITY.index(r.value))


class ToolCatalog:
    """工具目录 - 管理所有工具的 schema 生命周期（注册/版本/审计/持久化）。"""

    def __init__(self, storage_path: str | Path | None = None):
        self._tools: dict[str, ToolSchema] = {}
        self._versions: dict[str, list[ToolSchema]] = {}  # tool_name -> [versions]
        self._audit_log: list[ToolAuditEntry] = []
        self._lifecycle_events: list[ToolLifecycleEvent] = []
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path else None
        # 显式组合关系：目录可选地绑定唯一的运行时执行注册表
        # （core.tools.ToolRegistry），供 MCP 发现等写入方把工具桥接进主循环。
        self._runtime_registry: Any | None = None
        if self._storage_path:
            self._load_from_disk()

    def bind_runtime_registry(self, runtime_registry: Any) -> None:
        """绑定唯一的运行时执行注册表（显式组合，而非平行注册表）。

        绑定后，MCP 发现等写入方在注册目录条目的同时，会把可执行 handler
        桥接进该运行时注册表，使 Agent 主循环可以真正调用到这些工具。
        """
        self._runtime_registry = runtime_registry

    @property
    def runtime_registry(self) -> Any | None:
        """已绑定的运行时执行注册表（未绑定返回 None）。"""
        return self._runtime_registry

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
        """记录工具调用（旧管理面审计入口）。

        注意（P1-10 审计单轨裁决）：Agent 主循环与 MCP 桥接工具的*执行*审计
        统一由运行时 ``ToolRegistry.execute`` 写入 ``ToolExecutionStore``，
        不经本方法。本方法仅供 ``core/tool_executor.py`` 的旧管理面使用。
        """
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


# ---------------------------------------------------------------------------
# Backward-compatible alias.
#
# ``ToolCatalog`` is the canonical name for this schema/lifecycle catalog.
# ``ToolRegistry`` is retained so existing imports
# (``from backend.app.core.tool_registry import ToolRegistry``) keep working
# unchanged. New code should import ``ToolCatalog`` to avoid confusion with
# ``backend.app.core.tools.ToolRegistry`` (the runtime execution registry).
# ---------------------------------------------------------------------------
ToolRegistry = ToolCatalog
