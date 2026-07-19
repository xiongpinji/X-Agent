"""MCP adapter for integrating MCP tools with X-Agent system.

P1-10：本适配器**不再持有裸 dict 工具表**（原 ``self.tool_registry:
Dict[str, Callable]`` 是系统里第四套平行注册表，造成权限/审计双轨）。
现改为显式组合唯一的运行时 ``ToolRegistry``（``core/tools.py``）：

* 工具以 ``ToolDefinition`` 注册进运行时注册表（风险等级取统一风险模型）；
* 执行一律经 ``ToolRegistry.execute`` 咽喉点 —— 策略、hooks、执行审计
  （``ToolExecutionStore``）与 Agent 主循环同轨；
* 各 legacy 工具（file/search/browser）自带的 ``PermissionChecker`` 作为
  操作级二次防线保留：默认策略引擎 ``enable_high_risk_tools=True``（本适配器
  是运维/管理 API 执行面，操作级放行/拒绝由工具的 PermissionChecker 裁决，
  其拒绝映射为 ``PERMISSION_DENIED``）；注入 ``approval_store`` /
  ``execution_store`` / ``hook_manager`` 后，审批与执行审计立即并入单轨。
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any, Dict, Optional, List, Callable, Tuple
from datetime import datetime
from uuid import uuid4

from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.tools.file_tool import FileOperationTool, PermissionChecker as FilePermissionChecker
from backend.app.core.mcp.tools.search_tool import SearchOperationTool, SearchPermissionChecker
from backend.app.core.mcp.tools.browser_tool import BrowserTool, BrowserPermissionChecker
from backend.app.core.tool_schema import ToolCallInput, ToolCallOutput
from backend.app.core.tools import ToolRegistry

logger = logging.getLogger(__name__)

# 工具内部 PermissionError → ToolCallOutput.error_code 的传递通道
# （registry.execute 会把异常收敛为 record.error 字符串，错误码经此
# contextvar 跨调用边界带回；协程安全，并发执行互不漏串）。
_adapter_error_code: "contextvars.ContextVar[Optional[str]]" = contextvars.ContextVar(
    "xagent_mcp_adapter_error_code", default=None
)


class MCPToolAdapter:
    """Adapter for integrating MCP tools with X-Agent tool system.

    持有唯一的运行时 ``ToolRegistry``（显式组合），legacy 工具注册其中。
    """

    # name -> (description, category, risk_level)
    _LEGACY_TOOL_META: Dict[str, Tuple[str, str, RiskLevel]] = {
        "file_read": ("Read file content", "file", RiskLevel.LOW),
        "file_write": ("Write content to file", "file", RiskLevel.HIGH),
        "file_list": ("List files in directory", "file", RiskLevel.LOW),
        "file_delete": ("Delete file", "file", RiskLevel.CRITICAL),
        "file_exists": ("Check if file exists", "file", RiskLevel.LOW),
        "search_web": ("Search the web", "search", RiskLevel.LOW),
        "search_news": ("Search news", "search", RiskLevel.LOW),
        "browser_navigate": ("Navigate to URL", "browser", RiskLevel.MEDIUM),
        "browser_click": ("Click element", "browser", RiskLevel.MEDIUM),
        "browser_type": ("Type text", "browser", RiskLevel.MEDIUM),
        "browser_screenshot": ("Take screenshot", "browser", RiskLevel.LOW),
        "browser_scroll": ("Scroll page", "browser", RiskLevel.LOW),
        "browser_wait": ("Wait for duration", "browser", RiskLevel.LOW),
        "browser_get_content": ("Get page content", "browser", RiskLevel.LOW),
    }

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        file_tool: Optional[FileOperationTool] = None,
        search_tool: Optional[SearchOperationTool] = None,
        browser_tool: Optional[BrowserTool] = None,
        *,
        runtime_registry: Optional[ToolRegistry] = None,
        approval_store: Any = None,
        execution_store: Any = None,
        hook_manager: Any = None,
    ):
        """Initialize MCP tool adapter.

        Args:
            mcp_client: MCP client instance
            file_tool: File operation tool instance
            search_tool: Search operation tool instance
            browser_tool: Browser control tool instance
            runtime_registry: 复用外部运行时 ToolRegistry（缺省时自建）
            approval_store: 审批存储（注入后高/危风险执行产生审批记录）
            execution_store: 执行审计存储（注入后每次执行写入审计单轨）
            hook_manager: 钩子管理器（注入后 pre/post_tool_use 钩子生效）
        """
        self.mcp_client = mcp_client
        self.file_tool = file_tool
        self.search_tool = search_tool
        self.browser_tool = browser_tool
        self._runtime_registry = runtime_registry or self._build_registry(
            approval_store=approval_store,
            execution_store=execution_store,
            hook_manager=hook_manager,
        )
        self._register_tools()

    @staticmethod
    def _build_registry(
        approval_store: Any = None,
        execution_store: Any = None,
        hook_manager: Any = None,
    ) -> ToolRegistry:
        """构建适配器自用的运行时注册表。

        策略引擎 ``enable_high_risk_tools=True``：本适配器是运维/管理 API
        执行面，操作级权限由各工具的 PermissionChecker 裁决（拒绝时抛
        PermissionError → PERMISSION_DENIED）；审批/审计/钩子在注入相应
        组件后于同一咽喉点生效。
        """
        from backend.app.core.policy import ToolPolicyEngine

        policy = ToolPolicyEngine(enable_high_risk_tools=True)
        return ToolRegistry(
            policy,
            approval_store=approval_store,
            execution_store=execution_store,
            hook_manager=hook_manager,
        )

    @property
    def runtime_registry(self) -> ToolRegistry:
        """适配器持有的唯一运行时注册表（显式组合关系）。"""
        return self._runtime_registry

    def _register_tools(self) -> None:
        """把所有可用 legacy 工具注册进运行时注册表（替代原裸 dict）。"""
        handlers: Dict[str, Callable] = {}
        if self.file_tool:
            handlers.update(
                {
                    "file_read": self.file_tool.read_file,
                    "file_write": self.file_tool.write_file,
                    "file_list": self.file_tool.list_files,
                    "file_delete": self.file_tool.delete_file,
                    "file_exists": self.file_tool.file_exists,
                }
            )
        if self.search_tool:
            handlers.update(
                {
                    "search_web": self.search_tool.search_web,
                    "search_news": self.search_tool.search_news,
                }
            )
        if self.browser_tool:
            handlers.update(
                {
                    "browser_navigate": self.browser_tool.navigate,
                    "browser_click": self.browser_tool.click,
                    "browser_type": self.browser_tool.type_text,
                    "browser_screenshot": self.browser_tool.screenshot,
                    "browser_scroll": self.browser_tool.scroll,
                    "browser_wait": self.browser_tool.wait,
                    "browser_get_content": self.browser_tool.get_page_content,
                }
            )

        for name, func in handlers.items():
            description, _category, risk_level = self._LEGACY_TOOL_META[name]
            self._runtime_registry.register(
                name,
                description,
                self._wrap_legacy_handler(func),
                risk_level=risk_level,
                required_scope=f"tool:{name}",
                # **kwargs 签名无法推导参数 schema；显式放行任意对象参数，
                # 参数级校验由工具自身完成。
                parameters_schema={"type": "object"},
            )

    @staticmethod
    def _wrap_legacy_handler(func: Callable) -> Callable:
        """把 legacy 工具函数包装为注册表 handler。

        PermissionError（工具自身 PermissionChecker 拒绝）经 contextvar
        带出 PERMISSION_DENIED 错误码后原样上抛，由 registry 收敛为
        失败记录。
        """

        async def _shim(**kwargs: Any) -> Any:
            try:
                return await func(**kwargs)
            except PermissionError:
                _adapter_error_code.set("PERMISSION_DENIED")
                raise

        _shim.__name__ = getattr(func, "__name__", "legacy_tool")
        return _shim

    async def execute_tool(self, tool_input: ToolCallInput) -> ToolCallOutput:
        """Execute a tool call（经运行时注册表咽喉点）.

        Args:
            tool_input: Tool call input

        Returns:
            Tool call output
        """
        tool_name = tool_input.tool_name
        arguments = tool_input.arguments or {}

        if self._runtime_registry.get(tool_name) is None:
            return ToolCallOutput(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error=f"Tool {tool_name} not found in MCP adapter",
                error_code="TOOL_NOT_FOUND",
            )

        context = RunContext(
            trace_id=tool_input.trace_id or str(uuid4()),
            tenant_id=tool_input.tenant_id,
            user_id=tool_input.user_id,
        )

        token = _adapter_error_code.set(None)
        try:
            record = await self._runtime_registry.execute(
                context, tool_name, arguments
            )
            handler_error_code = _adapter_error_code.get()
        finally:
            _adapter_error_code.reset(token)

        if record.success:
            return ToolCallOutput(
                tool_id=tool_name,
                tool_name=tool_name,
                success=True,
                result=record.output,
                latency_ms=int(record.latency_ms),
            )

        if handler_error_code:
            error_code = handler_error_code
        elif not record.policy.allowed:
            # 策略/审批拒绝统一映射为 PERMISSION_DENIED
            error_code = "PERMISSION_DENIED"
        else:
            error_code = "EXECUTION_ERROR"

        return ToolCallOutput(
            tool_id=tool_name,
            tool_name=tool_name,
            success=False,
            error=record.error,
            error_code=error_code,
            latency_ms=int(record.latency_ms),
        )

    async def execute_tools_batch(
        self, tool_inputs: List[ToolCallInput]
    ) -> List[ToolCallOutput]:
        """Execute multiple tool calls concurrently.

        Args:
            tool_inputs: List of tool call inputs

        Returns:
            List of tool call outputs
        """
        import asyncio

        tasks = [self.execute_tool(tool_input) for tool_input in tool_inputs]
        return await asyncio.gather(*tasks)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools（以运行时注册表为唯一事实来源）.

        Returns:
            List of tool definitions
        """
        tools = []
        for definition in self._runtime_registry.manifest():
            _description, category, _risk = self._LEGACY_TOOL_META.get(
                definition["name"], ("", "utility", RiskLevel.LOW)
            )
            tools.append(
                {
                    "name": definition["name"],
                    "description": definition["description"],
                    "category": category,
                    "risk_level": definition["risk_level"],
                }
            )
        return tools

    def get_audit_logs(self, tool_category: Optional[str] = None) -> Dict[str, Any]:
        """Get audit logs from all tools.

        Args:
            tool_category: Optional category filter (file, search, browser)

        Returns:
            Audit logs by tool
        """
        logs = {}

        if tool_category in (None, "file") and self.file_tool:
            logs["file"] = self.file_tool.get_audit_logs()

        if tool_category in (None, "search") and self.search_tool:
            logs["search"] = self.search_tool.get_audit_logs()

        if tool_category in (None, "browser") and self.browser_tool:
            logs["browser"] = self.browser_tool.get_audit_logs()

        return logs

    def set_tool_permissions(
        self, tool_category: str, permissions: Dict[str, bool]
    ) -> None:
        """Set permissions for a tool category.

        Args:
            tool_category: Tool category (file, search, browser)
            permissions: Dict of operation -> allowed
        """
        if tool_category == "file" and self.file_tool:
            self.file_tool.set_permissions(permissions)
        elif tool_category == "search" and self.search_tool:
            self.search_tool.set_permissions(permissions)
        elif tool_category == "browser" and self.browser_tool:
            self.browser_tool.set_permissions(permissions)

    def get_tool_permissions(self, tool_category: str) -> Dict[str, bool]:
        """Get permissions for a tool category.

        Args:
            tool_category: Tool category (file, search, browser)

        Returns:
            Dict of operation -> allowed
        """
        if tool_category == "file" and self.file_tool:
            return self.file_tool.permission_checker.allowed_operations.copy()
        elif tool_category == "search" and self.search_tool:
            return self.search_tool.get_permissions()
        elif tool_category == "browser" and self.browser_tool:
            return self.browser_tool.get_permissions()
        return {}

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all MCP tools.

        Returns:
            Health status
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "mcp_client": "unknown",
            "file_tool": "unknown",
            "search_tool": "unknown",
            "browser_tool": "unknown",
        }

        if self.mcp_client:
            try:
                is_healthy = await self.mcp_client.health_check()
                status["mcp_client"] = "healthy" if is_healthy else "unhealthy"
            except Exception as e:
                status["mcp_client"] = f"error: {str(e)}"

        if self.file_tool:
            status["file_tool"] = "ready"

        if self.search_tool:
            status["search_tool"] = "ready"

        if self.browser_tool:
            status["browser_tool"] = "ready"

        return status

    async def close(self) -> None:
        """Close all resources."""
        if self.mcp_client:
            await self.mcp_client.close()
        if self.browser_tool:
            await self.browser_tool.close()
        logger.info("MCP adapter closed")
