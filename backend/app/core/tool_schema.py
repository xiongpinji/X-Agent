"""
工具 Schema 定义 - 统一的工具协议标准
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ToolCategory(StrEnum):
    """工具分类"""
    BROWSER = "browser"
    DESKTOP = "desktop"
    MEMORY = "memory"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"
    SYSTEM = "system"
    # 生产代码 mcp/discovery.py 的 _infer_category 引用以下成员;
    # 缺失会在 MCP 工具发现时抛 AttributeError。补齐以对齐生产用法。
    FILE_SYSTEM = "file_system"
    DATABASE = "database"
    WEB = "web"
    SEARCH = "search"
    CODE_EXECUTION = "code_execution"
    UTILITY = "utility"


class ToolRiskLevel(StrEnum):
    """工具风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolStatus(StrEnum):
    """工具状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ERROR = "error"


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[str] | None = None
    pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None


class ToolReturn(BaseModel):
    """工具返回值定义"""
    type: str  # string, number, boolean, object, array
    description: str = ""
    result_schema: dict[str, Any] = Field(default_factory=dict)


class ToolExample(BaseModel):
    """工具使用示例"""
    name: str
    description: str
    input: dict[str, Any]
    output: dict[str, Any]


class ToolSchema(BaseModel):
    """统一的工具 Schema"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str = "1.0.0"
    description: str
    category: ToolCategory

    # 功能定义
    parameters: list[ToolParameter] = Field(default_factory=list)
    returns: ToolReturn = Field(default_factory=lambda: ToolReturn(type="object"))

    # 安全与权限
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    permissions: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    sandbox_level: str = "isolated"  # isolated, restricted, unrestricted

    # 生命周期
    status: ToolStatus = ToolStatus.ACTIVE
    deprecated_at: datetime | None = None
    deprecated_reason: str | None = None

    # 文档与示例
    examples: list[ToolExample] = Field(default_factory=list)
    documentation_url: str | None = None

    # 元数据
    author: str = "system"
    tags: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Config:
        use_enum_values = False


class ToolCallInput(BaseModel):
    """工具调用输入"""
    tool_id: str
    tool_name: str
    arguments: dict[str, Any]
    trace_id: str | None = None
    run_id: str | None = None
    tenant_id: str = "default"
    user_id: str = "anonymous"


class ToolCallOutput(BaseModel):
    """工具调用输出"""
    tool_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    error_code: str | None = None
    latency_ms: int = 0


class ToolAuditEntry(BaseModel):
    """工具审计条目"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_id: str
    tool_name: str
    action: str  # call, install, uninstall, enable, disable, upgrade
    actor_id: str = "system"
    tenant_id: str = "default"

    # 调用详情
    input_preview: dict[str, Any] | None = None
    output_preview: dict[str, Any] | None = None
    success: bool = True
    error: str | None = None

    # 性能指标
    latency_ms: int = 0
    memory_used_mb: float = 0.0

    # 追踪
    trace_id: str | None = None
    run_id: str | None = None

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolLifecycleEvent(BaseModel):
    """工具生命周期事件"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_id: str
    tool_name: str
    event_type: str  # installed, uninstalled, enabled, disabled, upgraded, deprecated
    version: str | None = None
    actor_id: str = "system"
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
