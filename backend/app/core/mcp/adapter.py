"""MCP adapter for integrating MCP tools with X-Agent system."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime

from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.tools.file_tool import FileOperationTool, PermissionChecker as FilePermissionChecker
from backend.app.core.mcp.tools.search_tool import SearchOperationTool, SearchPermissionChecker
from backend.app.core.mcp.tools.browser_tool import BrowserTool, BrowserPermissionChecker
from backend.app.core.tool_schema import ToolCallInput, ToolCallOutput, ToolSchema, ToolRiskLevel

logger = logging.getLogger(__name__)


class MCPToolAdapter:
    """Adapter for integrating MCP tools with X-Agent tool system."""

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        file_tool: Optional[FileOperationTool] = None,
        search_tool: Optional[SearchOperationTool] = None,
        browser_tool: Optional[BrowserTool] = None,
    ):
        """Initialize MCP tool adapter.

        Args:
            mcp_client: MCP client instance
            file_tool: File operation tool instance
            search_tool: Search operation tool instance
            browser_tool: Browser control tool instance
        """
        self.mcp_client = mcp_client
        self.file_tool = file_tool
        self.search_tool = search_tool
        self.browser_tool = browser_tool
        self.tool_registry: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all available MCP tools."""
        if self.file_tool:
            self.tool_registry["file_read"] = self.file_tool.read_file
            self.tool_registry["file_write"] = self.file_tool.write_file
            self.tool_registry["file_list"] = self.file_tool.list_files
            self.tool_registry["file_delete"] = self.file_tool.delete_file
            self.tool_registry["file_exists"] = self.file_tool.file_exists

        if self.search_tool:
            self.tool_registry["search_web"] = self.search_tool.search_web
            self.tool_registry["search_news"] = self.search_tool.search_news

        if self.browser_tool:
            self.tool_registry["browser_navigate"] = self.browser_tool.navigate
            self.tool_registry["browser_click"] = self.browser_tool.click
            self.tool_registry["browser_type"] = self.browser_tool.type_text
            self.tool_registry["browser_screenshot"] = self.browser_tool.screenshot
            self.tool_registry["browser_scroll"] = self.browser_tool.scroll
            self.tool_registry["browser_wait"] = self.browser_tool.wait
            self.tool_registry["browser_get_content"] = self.browser_tool.get_page_content

    async def execute_tool(self, tool_input: ToolCallInput) -> ToolCallOutput:
        """Execute a tool call.

        Args:
            tool_input: Tool call input

        Returns:
            Tool call output
        """
        tool_name = tool_input.tool_name
        arguments = tool_input.arguments or {}

        try:
            if tool_name not in self.tool_registry:
                return ToolCallOutput(
                    tool_id="",
                    tool_name=tool_name,
                    success=False,
                    error=f"Tool {tool_name} not found in MCP adapter",
                    error_code="TOOL_NOT_FOUND",
                )

            tool_func = self.tool_registry[tool_name]
            result = await tool_func(**arguments)

            return ToolCallOutput(
                tool_id=tool_name,
                tool_name=tool_name,
                success=True,
                result=result,
            )
        except PermissionError as e:
            logger.warning(f"Permission denied for tool {tool_name}: {e}")
            return ToolCallOutput(
                tool_id=tool_name,
                tool_name=tool_name,
                success=False,
                error=str(e),
                error_code="PERMISSION_DENIED",
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolCallOutput(
                tool_id=tool_name,
                tool_name=tool_name,
                success=False,
                error=str(e),
                error_code="EXECUTION_ERROR",
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
        """Get list of available tools.

        Returns:
            List of tool definitions
        """
        tools = []

        if self.file_tool:
            tools.extend([
                {
                    "name": "file_read",
                    "description": "Read file content",
                    "category": "file",
                    "risk_level": "low",
                },
                {
                    "name": "file_write",
                    "description": "Write content to file",
                    "category": "file",
                    "risk_level": "high",
                },
                {
                    "name": "file_list",
                    "description": "List files in directory",
                    "category": "file",
                    "risk_level": "low",
                },
                {
                    "name": "file_delete",
                    "description": "Delete file",
                    "category": "file",
                    "risk_level": "critical",
                },
                {
                    "name": "file_exists",
                    "description": "Check if file exists",
                    "category": "file",
                    "risk_level": "low",
                },
            ])

        if self.search_tool:
            tools.extend([
                {
                    "name": "search_web",
                    "description": "Search the web",
                    "category": "search",
                    "risk_level": "low",
                },
                {
                    "name": "search_news",
                    "description": "Search news",
                    "category": "search",
                    "risk_level": "low",
                },
            ])

        if self.browser_tool:
            tools.extend([
                {
                    "name": "browser_navigate",
                    "description": "Navigate to URL",
                    "category": "browser",
                    "risk_level": "medium",
                },
                {
                    "name": "browser_click",
                    "description": "Click element",
                    "category": "browser",
                    "risk_level": "medium",
                },
                {
                    "name": "browser_type",
                    "description": "Type text",
                    "category": "browser",
                    "risk_level": "medium",
                },
                {
                    "name": "browser_screenshot",
                    "description": "Take screenshot",
                    "category": "browser",
                    "risk_level": "low",
                },
                {
                    "name": "browser_scroll",
                    "description": "Scroll page",
                    "category": "browser",
                    "risk_level": "low",
                },
                {
                    "name": "browser_wait",
                    "description": "Wait for duration",
                    "category": "browser",
                    "risk_level": "low",
                },
                {
                    "name": "browser_get_content",
                    "description": "Get page content",
                    "category": "browser",
                    "risk_level": "low",
                },
            ])

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
