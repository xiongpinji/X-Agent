"""MCP protocol tests."""

import pytest
from backend.app.core.mcp import MCPServer, MCPRequest, MCPResponse


@pytest.mark.asyncio
async def test_mcp_server_initialization():
    """Test MCP server initialization."""
    server = MCPServer(host="localhost", port=8001)
    assert server.host == "localhost"
    assert server.port == 8001
    assert len(server.tools) == 0


@pytest.mark.asyncio
async def test_register_tool():
    """Test tool registration."""
    server = MCPServer()

    async def dummy_tool(arg1: str) -> str:
        return f"Result: {arg1}"

    server.register_tool(
        "test_tool",
        dummy_tool,
        description="Test tool",
        input_schema={"arg1": "string"},
    )

    assert "test_tool" in server.tools
    assert server.tool_definitions["test_tool"].name == "test_tool"


@pytest.mark.asyncio
async def test_list_tools():
    """Test listing tools."""
    server = MCPServer()

    async def tool1() -> str:
        return "tool1"

    async def tool2() -> str:
        return "tool2"

    server.register_tool("tool1", tool1, description="Tool 1")
    server.register_tool("tool2", tool2, description="Tool 2")

    tools = server.list_tools()
    assert len(tools) == 2
    assert tools[0].name in ["tool1", "tool2"]


@pytest.mark.asyncio
async def test_handle_list_tools_request():
    """Test handling list tools request."""
    server = MCPServer()

    async def dummy_tool() -> str:
        return "result"

    server.register_tool("test", dummy_tool, description="Test")

    request = MCPRequest(
        type="request",
        method="tools/list",
    )

    response = await server.handle_request(request)
    assert response.type == "result"
    assert response.result is not None
    assert "tools" in response.result


@pytest.mark.asyncio
async def test_handle_tool_call():
    """Test handling tool call."""
    server = MCPServer()

    async def add(a: int, b: int) -> int:
        return a + b

    server.register_tool("add", add, description="Add two numbers")

    request = MCPRequest(
        type="request",
        method="tools/call",
        params={"tool": "add", "args": {"a": 5, "b": 3}},
    )

    response = await server.handle_request(request)
    assert response.type == "result"
    assert response.result["output"] == 8


@pytest.mark.asyncio
async def test_handle_unknown_method():
    """Test handling unknown method."""
    server = MCPServer()

    request = MCPRequest(
        type="request",
        method="unknown/method",
    )

    response = await server.handle_request(request)
    assert response.type == "error"
    assert response.error is not None


@pytest.mark.asyncio
async def test_handle_tool_not_found():
    """Test handling tool not found."""
    server = MCPServer()

    request = MCPRequest(
        type="request",
        method="tools/call",
        params={"tool": "nonexistent", "args": {}},
    )

    response = await server.handle_request(request)
    assert response.type == "error"
    assert "TOOL_NOT_FOUND" in response.error["code"]


@pytest.mark.asyncio
async def test_tool_error_handling():
    """Test tool error handling."""
    server = MCPServer()

    async def failing_tool() -> None:
        raise ValueError("Test error")

    server.register_tool("failing", failing_tool)

    request = MCPRequest(
        type="request",
        method="tools/call",
        params={"tool": "failing", "args": {}},
    )

    response = await server.handle_request(request)
    assert response.type == "error"
    assert "TOOL_ERROR" in response.error["code"]
