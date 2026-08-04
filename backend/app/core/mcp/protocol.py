"""MCP Protocol implementation.

.. deprecated:: P1-01
   本模块中的 ``MCPRequest`` / ``MCPResponse`` / ``MCPMessage`` / ``MCPServer``
   是 X-Agent 早期自造的私有 JSON 协议（HTTP POST ``/mcp/request``），**不是**
   官方 Model Context Protocol。它们仅为既有测试保留；旧端点文件
   ``backend/app/api/mcp.py``（系统 B，从未挂载）已于 2026-08-04 归档至
   ``archive/dead_code_2026-08/``。

   真实的 MCP 协议（JSON-RPC 2.0，``initialize`` / ``tools/list`` /
   ``tools/call``，stdio 与 Streamable HTTP 传输）由
   ``backend.app.core.mcp.client.MCPClient`` 基于官方 ``mcp`` Python SDK 实现。
   新代码请使用 ``MCPClient``，不要再使用本模块的服务端/消息类型。

``MCPTool`` 仍作为发现层的工具描述数据类沿用（与官方 ``mcp.types.Tool``
字段对齐：``input_schema`` ↔ ``inputSchema``、``annotations`` ↔ ``annotations``）。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MCPRequest(BaseModel):
    """MCP request message."""

    type: str
    id: str = Field(default_factory=lambda: str(uuid4()))
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MCPResponse(BaseModel):
    """MCP response message."""

    type: str
    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MCPMessage(BaseModel):
    """MCP message base class."""

    type: str
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MCPTool(BaseModel):
    """MCP tool definition.

    ``annotations`` 对应官方 MCP ``ToolAnnotations``（readOnlyHint /
    destructiveHint / idempotentHint / openWorldHint 等），发现层据此做
    风险等级推断。
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    annotations: dict[str, Any] = Field(default_factory=dict)


class MCPServer:
    """MCP server implementation."""

    def __init__(self, host: str = "localhost", port: int = 8001):
        """Initialize MCP server.

        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.tools: dict[str, Callable] = {}
        self.tool_definitions: dict[str, MCPTool] = {}

    def register_tool(
        self,
        name: str,
        tool: Callable,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Register a tool with the MCP server.

        Args:
            name: Tool name
            tool: Callable tool function
            description: Tool description
            input_schema: Input schema for the tool
            output_schema: Output schema for the tool
            tags: Tool tags for categorization
        """
        self.tools[name] = tool
        self.tool_definitions[name] = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema,
            tags=tags or [],
        )

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an MCP request.

        Args:
            request: MCP request message

        Returns:
            MCP response message
        """
        try:
            if request.method == "tools/list":
                return await self._handle_list_tools(request)
            elif request.method == "tools/call":
                return await self._handle_tool_call(request)
            else:
                return MCPResponse(
                    type="error",
                    id=request.id,
                    error={"code": "METHOD_NOT_FOUND", "message": f"Unknown method: {request.method}"},
                )
        except Exception as e:
            return MCPResponse(
                type="error",
                id=request.id,
                error={"code": "INTERNAL_ERROR", "message": str(e)},
            )

    async def _handle_list_tools(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request."""
        tools = [tool.model_dump() for tool in self.tool_definitions.values()]
        return MCPResponse(
            type="result",
            id=request.id,
            result={"tools": tools},
        )

    async def _handle_tool_call(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request."""
        tool_name = request.params.get("tool")
        tool_args = request.params.get("args", {})

        if tool_name not in self.tools:
            return MCPResponse(
                type="error",
                id=request.id,
                error={"code": "TOOL_NOT_FOUND", "message": f"Tool not found: {tool_name}"},
            )

        try:
            tool = self.tools[tool_name]
            result = await tool(**tool_args) if callable(tool) else tool

            return MCPResponse(
                type="result",
                id=request.id,
                result={"output": result},
            )
        except Exception as e:
            return MCPResponse(
                type="error",
                id=request.id,
                error={"code": "TOOL_ERROR", "message": str(e)},
            )

    def get_tool_definition(self, name: str) -> MCPTool | None:
        """Get tool definition by name."""
        return self.tool_definitions.get(name)

    def list_tools(self) -> list[MCPTool]:
        """List all registered tools."""
        return list(self.tool_definitions.values())
