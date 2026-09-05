"""GitHub MCP Plugin - 真实 stdio MCP server（官方 ``mcp`` SDK FastMCP）

迁移说明（原为普通 Python 类占位，握手必然失败）：

- 本模块是插件子进程入口（``python -m main``，stdio MCP server）；保留
  ``GitHubPlugin`` 入口类供 PluginRuntime.inspect_entrypoint() 进程内验证。
- 配置注入契约：从 ``XAGENT_PLUGIN_CONFIG`` 环境变量读取 JSON 对象配置。
- fail-closed 契约：``github_token`` 缺失时进程在握手前退出（码 2 + stderr
  诊断），绝不以无凭证姿态伪造可用。
- 工具形态：**占位实现 + 配置校验**。凭证（github_token）校验通过、握手与
  工具发现真实可用，但 REST API 调用尚未接线——工具如实返回
  ``status="placeholder"``（不伪造数据、不静默成功、不发起网络请求）。
  接线真实 API 时替换各工具实现即可，manifest 契约不变。

进程内使用（不经 MCP）::

    from main import GitHubPlugin
    plugin = GitHubPlugin({"github_token": "ghp_..."})
    await plugin.get_repository("octocat", "Hello-World")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, NoReturn

logger = logging.getLogger(__name__)

# 与 backend.app.core.mcp_plugin_adapter.PLUGIN_CONFIG_ENV_VAR 保持一致
CONFIG_ENV_VAR = "XAGENT_PLUGIN_CONFIG"
PLUGIN_NAME = "github-mcp"

PLACEHOLDER_MESSAGE = (
    "GitHub REST API integration is not wired yet; this is an honest "
    "placeholder response. Configuration (github_token) was validated "
    "successfully and the MCP handshake/tools are fully functional."
)


class GitHubPlugin:
    """GitHub MCP Plugin Server（占位工具 + 配置校验）"""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize GitHub plugin"""
        self.config = config or {}
        self.token = self.config.get("github_token")
        self.timeout = self.config.get("timeout", 30)

        if not self.token or not isinstance(self.token, str):
            raise ValueError(
                "github_token is required (non-empty string); without it the "
                "plugin refuses to start (fail-closed)"
            )

        logger.info("GitHubPlugin initialized (placeholder tools, config validated)")

    def _require_token(self) -> None:
        """防御性二次校验（正常情况下 init 已保证）。"""
        if not self.token:
            raise ValueError("github_token is required")

    def _placeholder(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """占位响应：如实声明未接线，回显参数便于核对，不伪造数据。"""
        self._require_token()
        return {
            "status": "placeholder",
            "tool": tool,
            "arguments": arguments,
            "message": PLACEHOLDER_MESSAGE,
        }

    async def list_repositories(self, username: str, limit: int = 10) -> dict[str, Any]:
        """List user repositories (placeholder: config validated, API not wired)"""
        return self._placeholder("list_repositories", {"username": username, "limit": limit})

    async def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository information (placeholder: config validated, API not wired)"""
        return self._placeholder("get_repository", {"owner": owner, "repo": repo})

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str = ""
    ) -> dict[str, Any]:
        """Create an issue (placeholder: config validated, API not wired)"""
        return self._placeholder(
            "create_issue",
            {"owner": owner, "repo": repo, "title": title, "body": body},
        )

    async def list_issues(
        self, owner: str, repo: str, state: str = "open", limit: int = 10
    ) -> dict[str, Any]:
        """List repository issues (placeholder: config validated, API not wired)"""
        return self._placeholder(
            "list_issues",
            {"owner": owner, "repo": repo, "state": state, "limit": limit},
        )

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> dict[str, Any]:
        """Create a pull request (placeholder: config validated, API not wired)"""
        return self._placeholder(
            "create_pull_request",
            {"owner": owner, "repo": repo, "title": title, "head": head, "base": base, "body": body},
        )


# ----------------------------------------------------------------------
# stdio MCP server 入口（python -m main）
# ----------------------------------------------------------------------

def _fail_closed(message: str) -> NoReturn:
    """输出可诊断错误并退出（不进入 MCP 循环，握手 fail-closed）。"""
    import time

    sys.stderr.write(f"[{PLUGIN_NAME}] fail-closed: {message}\n")
    sys.stderr.write(
        f"[{PLUGIN_NAME}] configure this plugin via the {CONFIG_ENV_VAR} "
        "environment variable (JSON object; provided by the X-Agent plugin "
        "runtime, e.g. PluginRuntime.start(name, config={...})).\n"
    )
    sys.stderr.flush()
    time.sleep(0.25)
    raise SystemExit(2)


def load_config_from_env() -> dict[str, Any]:
    """从约定环境变量读取 JSON 配置（缺失返回空 dict，由插件自行校验）。"""
    raw = (os.environ.get(CONFIG_ENV_VAR) or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        _fail_closed(f"{CONFIG_ENV_VAR} is not valid JSON: {e}")
    if not isinstance(parsed, dict):
        _fail_closed(
            f"{CONFIG_ENV_VAR} must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def build_server(config: dict[str, Any]) -> Any:
    """构建 FastMCP stdio server（工具 = GitHubPlugin 类方法，占位实现）。"""
    from mcp.server.fastmcp import FastMCP

    plugin = GitHubPlugin(config)

    mcp = FastMCP(PLUGIN_NAME)

    mcp.tool()(plugin.list_repositories)
    mcp.tool()(plugin.get_repository)
    mcp.tool()(plugin.create_issue)
    mcp.tool()(plugin.list_issues)
    mcp.tool()(plugin.create_pull_request)

    return mcp


def main() -> None:
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    config = load_config_from_env()

    if not config.get("github_token"):
        _fail_closed(
            "required configuration 'github_token' is missing or empty "
            "(type: string, GitHub Personal Access Token)"
        )

    try:
        server = build_server(config)
    except ValueError as e:
        _fail_closed(str(e))

    server.run()  # stdio 传输


if __name__ == "__main__":
    main()
