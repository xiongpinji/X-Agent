"""MCP API endpoints with enhanced features.

P1-01: 官方 MCP SDK 集成 — 工具发现与管理 API。
"""

import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.core.mcp import MCPRequest, MCPResponse, MCPServer
from backend.app.core.mcp.adapter import MCPToolAdapter
from backend.app.core.mcp.client import MCPClient
from backend.app.core.mcp.config import MCPConfig
from backend.app.core.mcp.manager import get_mcp_manager
from backend.app.core.mcp.tools.browser_tool import (
    BrowserAuditLog,
    BrowserPermissionChecker,
    BrowserTool,
)
from backend.app.core.mcp.tools.file_tool import AuditLog as FileAuditLog
from backend.app.core.mcp.tools.file_tool import FileOperationTool
from backend.app.core.mcp.tools.file_tool import PermissionChecker as FilePermissionChecker
from backend.app.core.mcp.tools.search_tool import (
    SearchAuditLog,
    SearchOperationTool,
    SearchPermissionChecker,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# Global instances
_mcp_adapter: MCPToolAdapter | None = None
_mcp_config: MCPConfig | None = None
_mcp_server: MCPServer | None = None


class ToolExecutionRequest(BaseModel):
    """Tool execution request."""

    tool_name: str
    arguments: dict[str, Any] | None = None


class ToolExecutionResponse(BaseModel):
    """Tool execution response."""

    tool_name: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    timestamp: str


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    components: dict[str, str]


class AuditLogResponse(BaseModel):
    """Audit log response."""

    tool_category: str
    entries: list[dict[str, Any]]
    count: int
    timestamp: str


class PermissionUpdateRequest(BaseModel):
    """Permission update request."""

    tool_category: str
    permissions: dict[str, bool]


def initialize_mcp_system(
    mcp_server_url: str = "http://localhost:8001",
    file_base_path: str = "./data",
) -> None:
    """Initialize MCP system with all components.

    Args:
        mcp_server_url: MCP server URL
        file_base_path: Base path for file operations
    """
    global _mcp_adapter, _mcp_config, _mcp_server

    try:
        # Initialize configuration
        _mcp_config = MCPConfig()
        _mcp_config.set_mcp_client_config(server_url=mcp_server_url)
        _mcp_config.set_file_tool_config(base_path=file_base_path)
        _mcp_config.set_search_tool_config()
        _mcp_config.set_browser_tool_config()

        # Initialize tools with audit and permission support
        file_audit = FileAuditLog()
        file_perms = FilePermissionChecker()
        file_tool = FileOperationTool(
            base_path=file_base_path,
            permission_checker=file_perms,
            audit_log=file_audit,
        )

        search_audit = SearchAuditLog()
        search_perms = SearchPermissionChecker()
        search_tool = SearchOperationTool(
            permission_checker=search_perms,
            audit_log=search_audit,
        )

        browser_audit = BrowserAuditLog()
        browser_perms = BrowserPermissionChecker()
        browser_tool = BrowserTool(
            permission_checker=browser_perms,
            audit_log=browser_audit,
        )

        # Initialize MCP client
        mcp_client = MCPClient(
            server_url=mcp_server_url,
            max_retries=3,
            enable_cache=True,
        )

        # Initialize adapter
        _mcp_adapter = MCPToolAdapter(
            mcp_client=mcp_client,
            file_tool=file_tool,
            search_tool=search_tool,
            browser_tool=browser_tool,
        )

        # Initialize legacy MCP server for backward compatibility
        _mcp_server = MCPServer(host="localhost", port=8001)
        _mcp_server.register_tool(
            "file_read",
            file_tool.read_file,
            description="Read file content",
            input_schema={"path": "string", "encoding": "string"},
        )
        _mcp_server.register_tool(
            "file_write",
            file_tool.write_file,
            description="Write content to file",
            input_schema={"path": "string", "content": "string", "encoding": "string"},
        )
        _mcp_server.register_tool(
            "file_list",
            file_tool.list_files,
            description="List files in directory",
            input_schema={"path": "string"},
        )
        _mcp_server.register_tool(
            "file_delete",
            file_tool.delete_file,
            description="Delete file",
            input_schema={"path": "string"},
        )
        _mcp_server.register_tool(
            "search_web",
            search_tool.search_web,
            description="Search the web",
            input_schema={"query": "string", "num_results": "integer"},
        )

        logger.info("MCP system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MCP system: {e}")
        raise


def get_mcp_adapter() -> MCPToolAdapter:
    """Get MCP adapter instance."""
    if _mcp_adapter is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP adapter not initialized",
        )
    return _mcp_adapter


def get_mcp_server() -> MCPServer:
    """Get MCP server instance."""
    if _mcp_server is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP server not initialized",
        )
    return _mcp_server


@router.post("/request")
async def handle_mcp_request(
    request: MCPRequest,
    principal: PrincipalDependency,
    server: MCPServer = Depends(get_mcp_server),
) -> dict:
    """Handle MCP request (legacy endpoint).

    Args:
        request: MCP request
        principal: Current principal
        server: MCP server instance

    Returns:
        MCP response
    """
    enforce_scope(principal, "mcp:execute")

    try:
        response = await server.handle_request(request)
        return response.model_dump(mode="json")
    except Exception as e:
        error_response = MCPResponse(
            type="error",
            id=request.id,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )
        return error_response.model_dump(mode="json")


@router.post("/tools/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    principal: PrincipalDependency,
    adapter: MCPToolAdapter = Depends(get_mcp_adapter),
) -> ToolExecutionResponse:
    """Execute a tool with enhanced features.

    Args:
        request: Tool execution request
        principal: Current principal
        adapter: MCP adapter instance

    Returns:
        Tool execution response
    """
    enforce_scope(principal, "mcp:execute")

    try:
        from backend.app.core.tool_schema import ToolCallInput

        tool_input = ToolCallInput(
            tool_name=request.tool_name,
            arguments=request.arguments or {},
        )
        output = await adapter.execute_tool(tool_input)

        return ToolExecutionResponse(
            tool_name=request.tool_name,
            success=output.success,
            result=output.result,
            error=output.error,
            error_code=output.error_code,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Error executing tool {request.tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/tools")
async def list_tools(
    principal: PrincipalDependency,
    server: MCPServer = Depends(get_mcp_server),
) -> dict:
    """List available MCP tools.

    Args:
        principal: Current principal
        server: MCP server instance

    Returns:
        List of tools
    """
    enforce_scope(principal, "mcp:read")

    tools = server.list_tools()
    return {
        "tools": [t.model_dump(mode="json") for t in tools],
        "count": len(tools),
    }


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    principal: PrincipalDependency,
    adapter: MCPToolAdapter = Depends(get_mcp_adapter),
) -> HealthCheckResponse:
    """Check MCP health status.

    Args:
        principal: Current principal
        adapter: MCP adapter instance

    Returns:
        Health check response
    """
    enforce_scope(principal, "mcp:read")

    try:
        status_dict = await adapter.health_check()
        components = {k: v for k, v in status_dict.items() if k != "timestamp"}

        overall_status = "healthy"
        if any("error" in str(v) for v in components.values()):
            overall_status = "degraded"

        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            components=components,
        )
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/audit-logs", response_model=AuditLogResponse)
async def get_audit_logs(
    tool_category: str | None = None,
    *,
    principal: PrincipalDependency,
    adapter: MCPToolAdapter = Depends(get_mcp_adapter),
) -> AuditLogResponse:
    """Get audit logs.

    Args:
        tool_category: Optional tool category filter
        principal: Current principal
        adapter: MCP adapter instance

    Returns:
        Audit log response
    """
    enforce_scope(principal, "mcp:read")

    try:
        logs = adapter.get_audit_logs(tool_category)
        entries = []
        if tool_category:
            entries = logs.get(tool_category, [])
        else:
            for category_logs in logs.values():
                entries.extend(category_logs)

        return AuditLogResponse(
            tool_category=tool_category or "all",
            entries=entries,
            count=len(entries),
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/permissions/{tool_category}")
async def get_permissions(
    tool_category: str,
    principal: PrincipalDependency,
    adapter: MCPToolAdapter = Depends(get_mcp_adapter),
) -> dict[str, bool]:
    """Get permissions for a tool category.

    Args:
        tool_category: Tool category (file, search, browser)
        principal: Current principal
        adapter: MCP adapter instance

    Returns:
        Permissions dictionary
    """
    enforce_scope(principal, "mcp:read")

    try:
        return adapter.get_tool_permissions(tool_category)
    except Exception as e:
        logger.error(f"Error getting permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/permissions/{tool_category}")
async def update_permissions(
    tool_category: str,
    request: PermissionUpdateRequest,
    principal: PrincipalDependency,
    adapter: MCPToolAdapter = Depends(get_mcp_adapter),
) -> dict[str, Any]:
    """Update permissions for a tool category.

    Args:
        tool_category: Tool category (file, search, browser)
        request: Permission update request
        principal: Current principal
        adapter: MCP adapter instance

    Returns:
        Update result
    """
    enforce_scope(principal, "mcp:admin")

    try:
        adapter.set_tool_permissions(tool_category, request.permissions)
        return {
            "success": True,
            "tool_category": tool_category,
            "permissions": request.permissions,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error updating permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/status")
async def get_mcp_status(
    principal: PrincipalDependency,
    server: MCPServer = Depends(get_mcp_server),
) -> dict:
    """Get MCP server status.

    Args:
        principal: Current principal
        server: MCP server instance

    Returns:
        Server status
    """
    enforce_scope(principal, "mcp:read")

    tools = server.list_tools()
    return {
        "status": "running",
        "host": server.host,
        "port": server.port,
        "tools_count": len(tools),
        "tools": [t.name for t in tools],
        "timestamp": datetime.now().isoformat(),
    }


# ─── P1-01: MCP Manager 集成端点（官方 SDK 工具发现与管理）───────────────────


class ToolInvokeRequest(BaseModel):
    """Tool invocation request body."""

    arguments: dict[str, Any] = {}


@router.get("/servers")
async def list_mcp_servers(
    principal: PrincipalDependency,
) -> dict:
    """List configured MCP servers and their connection status.

    P1-01: 返回所有已配置的 MCP 服务器及其连接状态。

    Args:
        principal: Current principal

    Returns:
        Server list with status info
    """
    enforce_scope(principal, "mcp:read")

    manager = get_mcp_manager()
    if manager is None:
        return {
            "servers": [],
            "count": 0,
            "mcp_enabled": False,
            "message": "MCP manager not initialized (XAGENT_MCP_ENABLED=false or no config)",
            "timestamp": datetime.now().isoformat(),
        }

    stats = manager.get_stats()
    servers_info = []
    for server_name, server_stats in stats.get("servers", {}).get("servers", {}).items():
        servers_info.append({
            "name": server_name,
            "connected": server_stats.get("connected", False),
            "transport": server_stats.get("transport", "unknown"),
            "server_info": server_stats.get("server_info", {}),
        })

    return {
        "servers": servers_info,
        "count": len(servers_info),
        "mcp_enabled": True,
        "initialized": manager.initialized,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/discovered-tools")
async def list_discovered_mcp_tools(
    principal: PrincipalDependency,
) -> dict:
    """List all discovered MCP tools from connected servers.

    P1-01: 返回通过官方 MCP SDK 发现的所有工具。

    Args:
        principal: Current principal

    Returns:
        Discovered tools grouped by server
    """
    enforce_scope(principal, "mcp:read")

    manager = get_mcp_manager()
    if manager is None:
        return {
            "tools": [],
            "count": 0,
            "servers": {},
            "message": "MCP manager not initialized",
            "timestamp": datetime.now().isoformat(),
        }

    # 从 discovery 层获取已发现的工具
    discovery = manager.discovery
    tools_by_server: dict[str, list[dict[str, Any]]] = {}
    all_tools: list[dict[str, Any]] = []

    for tool_key, mcp_tool in discovery.discovered_tools.items():
        server_name, tool_name = tool_key.split(":", 1)
        tool_info = {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            "input_schema": mcp_tool.input_schema,
            "server": server_name,
            "registered_name": f"mcp_{server_name}_{mcp_tool.name}",
        }
        tools_by_server.setdefault(server_name, []).append(tool_info)
        all_tools.append(tool_info)

    return {
        "tools": all_tools,
        "count": len(all_tools),
        "servers": tools_by_server,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/tools/{server_name}/{tool_name}/invoke")
async def invoke_mcp_tool(
    server_name: str,
    tool_name: str,
    request: ToolInvokeRequest,
    principal: PrincipalDependency,
) -> dict:
    """Invoke a specific MCP tool on a specific server.

    P1-01: 通过官方 MCP SDK 调用指定服务器上的工具。

    Args:
        server_name: MCP server name
        tool_name: Tool name on the server
        request: Invocation request with arguments
        principal: Current principal

    Returns:
        Tool execution result
    """
    enforce_scope(principal, "mcp:execute")

    manager = get_mcp_manager()
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP manager not initialized (XAGENT_MCP_ENABLED=false or no config)",
        )

    # 检查服务器是否已连接
    client = manager.discovery.servers.get(server_name)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_name}' not found or not connected",
        )

    try:
        result = await client.call_tool(tool_name, request.arguments)
        return {
            "success": True,
            "server": server_name,
            "tool": tool_name,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
    except ValueError as e:
        # 工具级失败（远端返回 isError=True）
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"MCP tool execution failed: {e}",
        )
    except Exception as e:
        logger.error(f"Error invoking MCP tool {server_name}/{tool_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP tool invocation error: {e}",
        )
