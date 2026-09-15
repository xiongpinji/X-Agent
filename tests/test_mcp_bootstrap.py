"""P1-3「MCP / 插件转正」的证明性测试。

缺陷背景（三处叠加，缺一即"MCP 生态"是空壳）：
1. ``settings.mcp_enabled`` 默认 False —— 仓库自带的 ``config/mcp_servers.yaml``
   与本地 stdio MCP server（``plugins/filesystem-mcp`` 等）在默认部署里从不加载。
2. 仓库根本没有 ``config/mcp_servers.yaml``（settings.mcp_config_path 的默认指向），
   只有 ``mcp_servers.example.yaml``。
3. ``config/mcp_servers.yaml`` 若要指向本地 server，必须写死解释器与仓库绝对路径
   （各机器不同），因为 ``MCPManager._load_config`` 原生 ``mcp_servers`` 列表
   **不做** 占位符展开——写死的配置无法进版本库复用。

验收标准（本文件断言）：
1. 出厂配置可加载，且 ``${XAGENT_PYTHON}`` / ``${XAGENT_PROJECT_ROOT}`` 被解析为
   本机真实路径（配置与机器无关）。
2. 出厂配置只默认启用**确实能连上**的本地 stdio server，其余保持 disabled——
   避免默认部署去连接不存在的 localhost 端点。
3. 真实 stdio MCP 握手成功，发现的工具落到运行时 ToolRegistry（``mcp_<server>_<tool>``）。
4. ``settings.mcp_enabled`` 的模型默认值为 True。
"""

from __future__ import annotations

import sys
from pathlib import Path

from backend.app.core.mcp.manager import MCPManager
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tool_registry import ToolCatalog
from backend.app.core.tools import build_default_tool_registry
from backend.app.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_CONFIG = REPO_ROOT / "config" / "mcp_servers.yaml"


def _load_shipped_config() -> MCPManager:
    manager = MCPManager(ToolCatalog(), str(SHIPPED_CONFIG))
    assert manager._load_config() is True, "shipped config/mcp_servers.yaml must be loadable"
    return manager


def test_mcp_enabled_model_default_is_true() -> None:
    """出厂默认开启 MCP（否则配置文件形同虚设）。"""
    assert Settings.model_fields["mcp_enabled"].default is True


def test_shipped_config_exists_at_the_default_path() -> None:
    """settings.mcp_config_path 的默认值必须真实存在。"""
    default_rel = Settings.model_fields["mcp_config_path"].default
    assert (REPO_ROOT / default_rel).is_file(), (
        f"settings.mcp_config_path defaults to {default_rel!r} but that file does not exist"
    )


def test_shipped_config_placeholders_are_fully_resolved() -> None:
    """内建伪变量被解析为真实路径；配置因此与机器无关。"""
    manager = _load_shipped_config()
    servers = {s["name"]: s for s in manager.config["mcp_servers"]}

    filesystem = servers["filesystem"]
    assert filesystem["command"] == sys.executable, (
        "${XAGENT_PYTHON} must resolve to the running interpreter"
    )
    assert Path(filesystem["cwd"]).resolve() == (REPO_ROOT / "plugins" / "filesystem-mcp").resolve(), (
        "${XAGENT_PROJECT_ROOT} must resolve to the repository root"
    )
    assert "${" not in filesystem["env"]["XAGENT_PLUGIN_CONFIG"], (
        "the allowed_paths default must be expanded, not left as a literal placeholder"
    )

    # 不应残留任何未解析的内建伪变量（未知变量保持原样，故只断言这两个）。
    for name in ("XAGENT_PYTHON", "XAGENT_PROJECT_ROOT"):
        assert f"${{{name}}}" not in str(manager.config), f"{name} placeholder left unresolved"


def test_shipped_config_only_enables_reachable_servers() -> None:
    """默认只启用本地可用的 stdio server；需要外部端点/凭据的一律 disabled。"""
    manager = _load_shipped_config()
    servers = {s["name"]: s for s in manager.config["mcp_servers"]}

    enabled = {n for n, s in servers.items() if s.get("enabled", True)}
    assert enabled == {"filesystem"}, (
        "only the bundled, always-reachable filesystem server may be enabled by default; "
        f"got {sorted(enabled)}"
    )
    # 被禁用的 server 也不能带 http 假端点（examples 里的 localhost:8001/8002 已清掉）
    for name in ("database", "web-search"):
        assert servers[name]["enabled"] is False


def test_expand_env_vars_supports_default_syntax() -> None:
    """${VAR} / ${VAR:-default} / 未知变量保持原样。"""
    import os

    os.environ["XAGENT_P13_TEST_VAR"] = "set-value"
    try:
        assert MCPManager._expand_env_vars("${XAGENT_P13_TEST_VAR}") == "set-value"
        assert MCPManager._expand_env_vars("${XAGENT_P13_MISSING:-fallback}") == "fallback"
        assert MCPManager._expand_env_vars("${XAGENT_P13_MISSING}") == "${XAGENT_P13_MISSING}"
        # 递归结构
        assert MCPManager._expand_env_vars({"a": ["${XAGENT_P13_MISSING:-x}"]}) == {"a": ["x"]}
    finally:
        os.environ.pop("XAGENT_P13_TEST_VAR", None)


async def test_filesystem_stdio_server_registers_tools_into_runtime_registry() -> None:
    """真实 stdio 握手：发现 6 个工具并注册进运行时 ToolRegistry。"""
    catalog = ToolCatalog()
    runtime_registry = build_default_tool_registry(ToolPolicyEngine())
    manager = MCPManager(catalog, str(SHIPPED_CONFIG), runtime_registry=runtime_registry)

    try:
        assert await manager.initialize() is True, "filesystem MCP server must connect"
        registered = [
            entry["name"]
            for entry in runtime_registry.manifest()
            if str(entry.get("name", "")).startswith("mcp_filesystem_")
        ]
        expected = {
            "mcp_filesystem_read_file",
            "mcp_filesystem_write_file",
            "mcp_filesystem_list_files",
            "mcp_filesystem_search_files",
            "mcp_filesystem_delete_file",
            "mcp_filesystem_get_file_info",
        }
        assert set(registered) == expected, f"got {sorted(registered)}"

        stats = manager.get_stats()
        assert stats["tools_registered"] == 6
        assert stats["servers"]["servers"]["filesystem"]["connected"] is True
    finally:
        await manager.shutdown()
