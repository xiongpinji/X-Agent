"""MCP API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.mcp import MCPServer, MCPRequest, MCPResponse
from backend.app.core.mcp.tools import FileOperationTool, SearchOperationTool, DatabaseOperationTool
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Initialize MCP server
mcp_server = MCPServer(host="localhost", port=8001)

# Register tools
file_tool = FileOperationTool(base_path="./data")
search_tool = SearchOperationTool()

# Register file operations
mcp_server.register_tool(
    "file_read",
    file_tool.read_file,
    description="Read file content",
    input_schema={"path": "string", "encoding": "string"},
)

mcp_server.register_tool(
    "file_write",
    file_tool.write_file,
    description="Write content to file",
    input_schema={"path": "string", "content": "string", "encoding": "string"},
)

mcp_server.register_tool(
    "file_list",
    file_tool.list_files,
    description="List files in directory",
    input_schema={"path": "string"},
)

mcp_server.register_tool(
    "file_delete",
    file_tool.delete_file,
    description="Delete file",
    input_schema={"path": "string"},
)

# Register search operations
mcp_server.register_tool(
    "search_web",
    search_tool.search_web,
    description="Search the web",
    input_schema={"query": "string", "num_results": "integer"},
)

mcp_server.register_tool(
    "extract_content",
    search_tool.extract_content,
    description="Extract content from URL",
    input_schema={"url": "string"},
)


@router.post("/request")
async def handle_mcp_request(
    request: MCPRequest,
    principal: PrincipalDependency,
) -> dict:
    """Handle MCP request.

    Args:
        request: MCP request
        principal: Current principal

    Returns:
        MCP response
    """
    enforce_scope(principal, "mcp:execute")

    try:
        response = await mcp_server.handle_request(request)
        return response.model_dump(mode="json")
    except Exception as e:
        error_response = MCPResponse(
            type="error",
            id=request.id,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )
        return error_response.model_dump(mode="json")


@router.get("/tools")
async def list_tools(
    principal: PrincipalDependency,
) -> dict:
    """List available MCP tools.

    Args:
        principal: Current principal

    Returns:
        List of tools
    """
    enforce_scope(principal, "mcp:read")

    tools = mcp_server.list_tools()
    return {
        "tools": [t.model_dump(mode="json") for t in tools],
        "count": len(tools),
    }


@router.get("/tools/{tool_name}")
async def get_tool_definition(
    tool_name: str,
    principal: PrincipalDependency,
) -> dict:
    """Get tool definition.

    Args:
        tool_name: Tool name
        principal: Current principal

    Returns:
        Tool definition
    """
    enforce_scope(principal, "mcp:read")

    tool = mcp_server.get_tool_definition(tool_name)
    if not tool:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, f"Tool not found: {tool_name}")

    return tool.model_dump(mode="json")


@router.post("/tools/{tool_name}/call")
async def call_tool(
    tool_name: str,
    args: dict,
    principal: PrincipalDependency,
) -> dict:
    """Call a tool directly.

    Args:
        tool_name: Tool name
        args: Tool arguments
        principal: Current principal

    Returns:
        Tool result
    """
    enforce_scope(principal, "mcp:execute")

    tool = mcp_server.get_tool_definition(tool_name)
    if not tool:
        raise api_error(404, ErrorCode.RUN_NOT_FOUND, f"Tool not found: {tool_name}")

    try:
        request = MCPRequest(
            type="request",
            method="tools/call",
            params={"tool": tool_name, "args": args},
        )
        response = await mcp_server.handle_request(request)

        if response.error:
            raise api_error(400, ErrorCode.INVALID_REQUEST, response.error.get("message", "Tool call failed"))

        return response.result or {}
    except Exception as e:
        raise api_error(400, ErrorCode.INVALID_REQUEST, f"Tool call failed: {str(e)}")


@router.get("/status")
async def get_mcp_status(
    principal: PrincipalDependency,
) -> dict:
    """Get MCP server status.

    Args:
        principal: Current principal

    Returns:
        Server status
    """
    enforce_scope(principal, "mcp:read")

    tools = mcp_server.list_tools()
    return {
        "status": "running",
        "host": mcp_server.host,
        "port": mcp_server.port,
        "tools_count": len(tools),
        "tools": [t.name for t in tools],
    }
