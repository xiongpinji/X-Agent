"""
工具初始化和集成 - 将所有工具注册到系统
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.core.tool_definitions import STANDARD_TOOLS
from backend.app.core.tool_executor import ToolExecutionEngine
from backend.app.core.tool_registry import ToolCatalog
from backend.app.core.tool_schema import ToolCallInput, ToolCallOutput


class ToolManager:
    """工具管理器 - 初始化和管理所有工具

    P1-10：默认共享 dependencies 持有的 ToolCatalog 单例；仅当显式传入
    storage_path 时构造隔离实例（测试/离线工具场景）。
    """

    def __init__(self, storage_path: str | Path | None = None):
        if storage_path is None:
            from backend.app.dependencies import get_tool_catalog

            self.registry = get_tool_catalog()
        else:
            self.registry = ToolCatalog(storage_path)
        self.engine = ToolExecutionEngine(self.registry)
        self._initialized = False

    def initialize(self) -> None:
        """初始化所有标准工具"""
        if self._initialized:
            return

        # 注册所有标准工具
        for tool_schema in STANDARD_TOOLS:
            try:
                self.registry.register(tool_schema)
            except ValueError:
                # 工具已存在，跳过
                pass

        # 注册处理器
        self._register_handlers()
        self._initialized = True

    def _register_handlers(self) -> None:
        """注册工具处理器"""
        # Browser 工具处理器
        self.engine.wrapper.register_handler("browser_navigate", self._handle_browser_navigate)
        self.engine.wrapper.register_handler("browser_click", self._handle_browser_click)
        self.engine.wrapper.register_handler("browser_fill", self._handle_browser_fill)
        self.engine.wrapper.register_handler("browser_screenshot", self._handle_browser_screenshot)
        self.engine.wrapper.register_handler("browser_extract_text", self._handle_browser_extract_text)

        # Desktop 工具处理器
        self.engine.wrapper.register_handler("desktop_click", self._handle_desktop_click)
        self.engine.wrapper.register_handler("desktop_type", self._handle_desktop_type)
        self.engine.wrapper.register_handler("desktop_screenshot", self._handle_desktop_screenshot)

        # Memory 工具处理器
        self.engine.wrapper.register_handler("memory_store", self._handle_memory_store)
        self.engine.wrapper.register_handler("memory_retrieve", self._handle_memory_retrieve)
        self.engine.wrapper.register_handler("memory_update", self._handle_memory_update)

        # Workflow 工具处理器
        self.engine.wrapper.register_handler("workflow_execute", self._handle_workflow_execute)
        self.engine.wrapper.register_handler("workflow_status", self._handle_workflow_status)

        # Plugin 工具处理器
        self.engine.wrapper.register_handler("plugin_install", self._handle_plugin_install)
        self.engine.wrapper.register_handler("plugin_uninstall", self._handle_plugin_uninstall)
        self.engine.wrapper.register_handler("plugin_execute", self._handle_plugin_execute)

    # ========================================================================
    # Browser 工具处理器
    # ========================================================================

    async def _handle_browser_navigate(self, url: str, timeout: int = 30) -> dict[str, Any]:
        """处理浏览器导航"""
        return {
            "url": url,
            "title": "Page Title",
            "status": 200,
        }

    async def _handle_browser_click(self, selector: str) -> dict[str, Any]:
        """处理浏览器点击"""
        return {
            "success": True,
            "message": f"Clicked {selector}",
        }

    async def _handle_browser_fill(self, selector: str, value: str) -> dict[str, Any]:
        """处理浏览器填充"""
        return {
            "success": True,
            "message": f"Filled {selector} with {value}",
        }

    async def _handle_browser_screenshot(self, path: str | None = None) -> dict[str, Any]:
        """处理浏览器截图"""
        return {
            "path": path or "/tmp/screenshot.png",
            "size": 1024000,
        }

    async def _handle_browser_extract_text(self, selector: str | None = None) -> dict[str, Any]:
        """处理浏览器文本提取"""
        return {
            "text": "Extracted text content",
        }

    # ========================================================================
    # Desktop 工具处理器
    # ========================================================================

    async def _handle_desktop_click(self, x: int, y: int) -> dict[str, Any]:
        """处理桌面点击"""
        return {
            "success": True,
        }

    async def _handle_desktop_type(self, text: str) -> dict[str, Any]:
        """处理桌面输入"""
        return {
            "success": True,
        }

    async def _handle_desktop_screenshot(self, path: str | None = None) -> dict[str, Any]:
        """处理桌面截图"""
        return {
            "path": path or "/tmp/desktop_screenshot.png",
        }

    # ========================================================================
    # Memory 工具处理器
    # ========================================================================

    async def _handle_memory_store(
        self,
        content: str,
        layer: int = 5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """处理内存存储"""
        from datetime import UTC, datetime
        from uuid import uuid4

        return {
            "memory_id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
        }

    async def _handle_memory_retrieve(
        self,
        query: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """处理内存检索"""
        return {
            "items": [],
            "total": 0,
        }

    async def _handle_memory_update(
        self,
        memory_id: str,
        content: str,
    ) -> dict[str, Any]:
        """处理内存更新"""
        return {
            "success": True,
        }

    # ========================================================================
    # Workflow 工具处理器
    # ========================================================================

    async def _handle_workflow_execute(
        self,
        workflow_id: str,
        input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理工作流执行"""
        from uuid import uuid4

        return {
            "run_id": str(uuid4()),
            "status": "running",
        }

    async def _handle_workflow_status(self, run_id: str) -> dict[str, Any]:
        """处理工作流状态"""
        return {
            "status": "completed",
            "progress": 100,
        }

    # ========================================================================
    # Plugin 工具处理器
    # ========================================================================

    async def _handle_plugin_install(
        self,
        plugin_name: str,
        version: str = "latest",
    ) -> dict[str, Any]:
        """处理插件安装"""
        from uuid import uuid4

        return {
            "plugin_id": str(uuid4()),
            "status": "installed",
        }

    async def _handle_plugin_uninstall(self, plugin_id: str) -> dict[str, Any]:
        """处理插件卸载"""
        return {
            "success": True,
        }

    async def _handle_plugin_execute(
        self,
        plugin_id: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """处理插件执行"""
        return {
            "success": True,
            "output": {},
        }

    # ========================================================================
    # 公共接口
    # ========================================================================

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        trace_id: str | None = None,
        run_id: str | None = None,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> ToolCallOutput:
        """执行工具"""
        tool_input = ToolCallInput(
            tool_id="",
            tool_name=tool_name,
            arguments=arguments,
            trace_id=trace_id,
            run_id=run_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return await self.engine.execute_tool(tool_input)

    def get_tool_manifest(self) -> list[dict[str, Any]]:
        """获取工具清单"""
        return self.engine.get_all_tools()

    def get_tool_info(self, tool_name: str) -> dict[str, Any] | None:
        """获取工具信息"""
        return self.engine.get_tool_info(tool_name)

    def get_audit_log(self, tool_name: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """获取审计日志"""
        return self.engine.get_audit_log(tool_name, limit)

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return self.engine.get_statistics()

    def enable_tool(self, tool_name: str) -> bool:
        """启用工具"""
        return self.engine.enable_tool(tool_name)

    def disable_tool(self, tool_name: str) -> bool:
        """禁用工具"""
        return self.engine.disable_tool(tool_name)

    def deprecate_tool(self, tool_name: str, reason: str = "") -> bool:
        """弃用工具"""
        return self.engine.deprecate_tool(tool_name, reason)
