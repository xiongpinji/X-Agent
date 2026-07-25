"""
工具包装器和执行引擎 - 统一的调用接口、权限检查、审计记录
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any, TypeVar

from backend.app.core.tool_registry import ToolCatalog
from backend.app.core.tool_schema import (
    ToolCallInput,
    ToolCallOutput,
    ToolRiskLevel,
    ToolSchema,
)

T = TypeVar("T")


class ToolExecutionError(Exception):
    """工具执行错误"""

    def __init__(self, tool_name: str, error_code: str, message: str):
        self.tool_name = tool_name
        self.error_code = error_code
        self.message = message
        super().__init__(f"Tool {tool_name} failed: {message}")


class ToolPermissionError(Exception):
    """工具权限错误"""

    def __init__(self, tool_name: str, required_scope: str):
        self.tool_name = tool_name
        self.required_scope = required_scope
        super().__init__(f"Tool {tool_name} requires scope: {required_scope}")


class ToolApprovalRequired(Exception):
    """工具需要审批"""

    def __init__(self, tool_name: str, risk_level: ToolRiskLevel):
        self.tool_name = tool_name
        self.risk_level = risk_level
        super().__init__(f"Tool {tool_name} (risk: {risk_level}) requires approval")


class ToolWrapper:
    """工具包装器 - 提供统一的调用接口"""

    def __init__(
        self,
        registry: ToolCatalog,
        approval_checker: Callable[[str, ToolRiskLevel], bool] | None = None,
        permission_checker: Callable[[str, str], bool] | None = None,
    ):
        self.registry = registry
        self.approval_checker = approval_checker or (lambda t, r: False)
        self.permission_checker = permission_checker or (lambda t, s: True)
        self._handlers: dict[str, Callable] = {}

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """注册工具处理器"""
        self._handlers[tool_name] = handler

    async def execute(
        self,
        tool_input: ToolCallInput,
        handler: Callable | None = None,
    ) -> ToolCallOutput:
        """执行工具调用"""
        tool_name = tool_input.tool_name
        tool = self.registry.get(tool_name)

        if not tool:
            return ToolCallOutput(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error=f"Tool {tool_name} not found",
                error_code="TOOL_NOT_FOUND",
            )

        # 权限检查
        if tool.permissions:
            for scope in tool.permissions:
                if not self.permission_checker(tool_name, scope):
                    raise ToolPermissionError(tool_name, scope)

        # 审批检查
        if tool.requires_approval and not self.approval_checker(tool_name, tool.risk_level):
            raise ToolApprovalRequired(tool_name, tool.risk_level)

        # 参数验证
        validation_error = self._validate_parameters(tool, tool_input.arguments)
        if validation_error:
            return ToolCallOutput(
                tool_id=tool.id,
                tool_name=tool_name,
                success=False,
                error=validation_error,
                error_code="INVALID_PARAMETERS",
            )

        # 执行工具
        start_time = time.time()
        try:
            # 获取处理器
            actual_handler = handler or self._handlers.get(tool_name)
            if not actual_handler:
                raise ToolExecutionError(
                    tool_name,
                    "NO_HANDLER",
                    f"No handler registered for tool {tool_name}",
                )

            # 调用处理器
            if asyncio.iscoroutinefunction(actual_handler):
                result = await actual_handler(**tool_input.arguments)
            else:
                result = actual_handler(**tool_input.arguments)

            latency_ms = int((time.time() - start_time) * 1000)

            # 记录审计
            self.registry.record_call(
                tool_name=tool_name,
                success=True,
                latency_ms=latency_ms,
                input_preview=tool_input.arguments,
                output_preview=result if isinstance(result, dict) else {"type": type(result).__name__},
                trace_id=tool_input.trace_id,
                run_id=tool_input.run_id,
                actor_id=tool_input.user_id,
                tenant_id=tool_input.tenant_id,
            )

            return ToolCallOutput(
                tool_id=tool.id,
                tool_name=tool_name,
                success=True,
                result=result if isinstance(result, dict) else {"output": result},
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            # 记录审计
            self.registry.record_call(
                tool_name=tool_name,
                success=False,
                latency_ms=latency_ms,
                error=str(e),
                trace_id=tool_input.trace_id,
                run_id=tool_input.run_id,
                actor_id=tool_input.user_id,
                tenant_id=tool_input.tenant_id,
            )

            return ToolCallOutput(
                tool_id=tool.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                error_code="EXECUTION_ERROR",
                latency_ms=latency_ms,
            )

    def _validate_parameters(self, tool: ToolSchema, arguments: dict[str, Any]) -> str | None:
        """验证参数"""
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                return f"Missing required parameter: {param.name}"

            if param.name in arguments:
                value = arguments[param.name]

                # 类型检查
                if param.type == "string" and not isinstance(value, str):
                    return f"Parameter {param.name} must be string"
                elif param.type == "number" and not isinstance(value, (int, float)):
                    return f"Parameter {param.name} must be number"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return f"Parameter {param.name} must be boolean"

                # 长度检查
                if isinstance(value, str):
                    if param.min_length and len(value) < param.min_length:
                        return f"Parameter {param.name} too short (min: {param.min_length})"
                    if param.max_length and len(value) > param.max_length:
                        return f"Parameter {param.name} too long (max: {param.max_length})"

                # 枚举检查
                if param.enum and value not in param.enum:
                    return f"Parameter {param.name} must be one of: {param.enum}"

        return None


class ToolExecutionEngine:
    """工具执行引擎 - 管理工具的生命周期和执行"""

    def __init__(self, registry: ToolCatalog):
        self.registry = registry
        self.wrapper = ToolWrapper(registry)

    def install_tool(self, schema: ToolSchema, handler: Callable) -> ToolSchema:
        """安装工具"""
        registered = self.registry.register(schema)
        self.wrapper.register_handler(schema.name, handler)
        return registered

    def uninstall_tool(self, tool_name: str) -> bool:
        """卸载工具"""
        return self.registry.unregister(tool_name)

    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        return self.registry.enable(tool_name)

    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        return self.registry.disable(tool_name)

    def deprecate_tool(self, tool_name: str, reason: str = "") -> bool:
        """弃用工具"""
        return self.registry.deprecate(tool_name, reason)

    def upgrade_tool(self, tool_name: str, new_schema: ToolSchema, new_handler: Callable) -> bool:
        """升级工具"""
        success = self.registry.upgrade(tool_name, new_schema)
        if success:
            self.wrapper.register_handler(tool_name, new_handler)
        return success

    async def execute_tool(
        self,
        tool_input: ToolCallInput,
        handler: Callable | None = None,
    ) -> ToolCallOutput:
        """执行工具"""
        return await self.wrapper.execute(tool_input, handler)

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """获取工具信息"""
        tool = self.registry.get(tool_name)
        if not tool:
            return None

        return {
            "id": tool.id,
            "name": tool.name,
            "version": tool.version,
            "description": tool.description,
            "category": tool.category.value,
            "risk_level": tool.risk_level.value,
            "status": tool.status.value,
            "parameters": [p.model_dump() for p in tool.parameters],
            "returns": tool.returns.model_dump(),
            "permissions": tool.permissions,
            "requires_approval": tool.requires_approval,
            "examples": [e.model_dump() for e in tool.examples],
        }

    def get_all_tools(self) -> list[dict[str, Any]]:
        """获取所有工具"""
        return [self.get_tool_info(t.name) for t in self.registry.list_all()]

    def get_audit_log(self, tool_name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """获取审计日志"""
        entries = self.registry.get_audit_log(tool_name, limit)
        return [e.model_dump() for e in entries]

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return self.registry.get_statistics()


class ToolExecutor(ToolExecutionEngine):
    """便捷的工具执行器。

    相比 ToolExecutionEngine，构造时可不传 registry（自动新建一个），
    并接受可选的 timeout_seconds 参数。
    """

    def __init__(
        self,
        registry: ToolCatalog | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(registry if registry is not None else ToolCatalog())
        self.timeout_seconds = timeout_seconds
