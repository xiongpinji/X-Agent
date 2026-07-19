#!/usr/bin/env python3
"""最小 stdio MCP server（官方 mcp SDK，FastMCP）——端到端连通测试夹具。

以子进程方式被 tests/test_mcp_stdio_e2e.py 拉起，经 stdin/stdout 讲标准
MCP 协议（JSON-RPC 2.0）。提供三个工具覆盖：只读（LOW）、数值计算（LOW）、
名称含破坏性关键词（HIGH，用于验证风险映射与审批策略拦截）。
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("xagent-e2e-stdio")


@mcp.tool(description="Echo text back to the caller")
def echo(text: str) -> str:
    return f"echo:{text}"


@mcp.tool(description="Add two integers")
def add(a: int, b: int) -> int:
    return a + b


@mcp.tool(description="Delete a file at the given path (destructive test tool)")
def delete_file(path: str) -> str:
    # 测试夹具：不执行真实删除，仅回显。
    return f"deleted:{path}"


if __name__ == "__main__":
    mcp.run()  # 默认 stdio 传输
