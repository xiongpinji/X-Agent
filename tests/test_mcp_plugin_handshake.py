"""P1-12 后续：插件子进程真实 stdio MCP 握手测试。

覆盖（backend.app.core.mcp_plugin_adapter.MCPPluginStdioSession /
MCPPluginAdapter / backend.plugins.runtime.PluginRuntime）：

- 握手消息序列：initialize 请求（protocolVersion/capabilities/clientInfo）
  → notifications/initialized 通知 → tools/list → tools/call——用原始
  JSON-RPC 假 server（tests/mcp_fixtures/stdio_recording_server.py）记录
  真实线上消息逐条断言；
- 握手超时 fail-closed（错误可诊断 + 子进程清理）；
- 握手成功后插件进程退出 → 会话判死，后续调用 fail-closed；
- 真实 MCP server（官方 SDK FastMCP，经临时插件目录）下 PluginRuntime
  全生命周期：start（握手+工具发现）→ call_plugin_tool（tools/call）→
  桥接进 ToolRegistry（Agent 主循环可调用）→ stop（工具与进程清理）；
- 真实 plugins/ 目录三个示例插件（filesystem/github/database，已迁移为
  真实 stdio MCP server）：缺配置 fail-closed（错误含插件 stderr 诊断）、
  配置注入后握手→工具发现→工具调用→stop 全链路（filesystem 用临时目录
  验证真实读写与路径越界拒绝；database 用 sqlite 真实查询往返）；
- 适配器契约：命令推导、docker 拒绝、未启动调用报错、env 超时解析。
"""

from __future__ import annotations

# --- 并行期防御（同 test_plugin_runtime_p1_12.py）---------------------------
import sys as _sys
import types as _types

try:  # pragma: no cover - 取决于并行工作区状态
    import backend.app.main  # noqa: F401
except Exception:  # pragma: no cover
    if "backend.app.main" not in _sys.modules:
        _stub = _types.ModuleType("backend.app.main")
        _stub._rate_limiter = _types.SimpleNamespace(_windows={})
        _sys.modules["backend.app.main"] = _stub
# ------------------------------------------------------------------------

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from backend.app.core.mcp_plugin_adapter import (
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_START_TIMEOUT,
    ENV_REQUEST_TIMEOUT,
    ENV_START_TIMEOUT,
    MCPPluginAdapter,
    MCPPluginHandshakeError,
    MCPPluginStdioSession,
    MCPPluginToolError,
    MCPPluginTransportError,
    MCPPluginStatus,
)
from backend.plugins.runtime import PluginRuntime

FIXTURES_DIR = Path(__file__).resolve().parent / "mcp_fixtures"
RECORDING_SERVER = FIXTURES_DIR / "stdio_recording_server.py"
SILENT_SERVER = FIXTURES_DIR / "stdio_silent_server.py"
CRASH_SERVER = FIXTURES_DIR / "stdio_crash_server.py"
HANG_SERVER = FIXTURES_DIR / "stdio_hang_server.py"


def make_session(script: Path, *extra_args: str, **kwargs) -> MCPPluginStdioSession:
    """以当前解释器拉起假 server 的 stdio 会话。"""
    kwargs.setdefault("start_timeout", 10.0)
    kwargs.setdefault("request_timeout", 5.0)
    return MCPPluginStdioSession(
        command=sys.executable, args=[str(script), *extra_args], **kwargs
    )


# ---------------------------------------------------------------------------
# 握手消息序列（原始 JSON-RPC 线上消息级断言）
# ---------------------------------------------------------------------------


@pytest.mark.mcp
@pytest.mark.timeout(60)
class TestHandshakeMessageSequence:
    def test_full_handshake_message_sequence(self, tmp_path: Path):
        record_path = tmp_path / "record.json"
        session = make_session(RECORDING_SERVER, str(record_path)).start()
        try:
            assert session.is_alive
            # 握手阶段已完成 tools/list（发现 echo）
            assert [t["name"] for t in session.tools_discovered] == ["echo"]
            assert session.server_info["server_name"] == "recording-fake-plugin"
            # tools/call 真实调用
            result = session.call_tool("echo", {"text": "hello"})
            assert isinstance(result, str)
            assert result.startswith("echo:echo:")
            assert "hello" in result
        finally:
            session.stop()
        assert not session.is_alive

        messages = json.loads(record_path.read_text(encoding="utf-8"))
        methods = [m.get("method") for m in messages]

        # --- 1. initialize 请求（含 protocolVersion/capabilities/clientInfo） ---
        assert methods[0] == "initialize"
        init_params = messages[0]["params"]
        assert isinstance(init_params["protocolVersion"], str)
        assert init_params["protocolVersion"]
        assert isinstance(init_params["capabilities"], dict)
        assert init_params["clientInfo"]["name"] == "x-agent-plugin-runtime"
        assert "version" in init_params["clientInfo"]

        # --- 2. initialized 通知（无 id） ---
        assert methods[1] == "notifications/initialized"
        assert "id" not in messages[1]

        # --- 3. tools/list 请求 ---
        assert "tools/list" in methods

        # --- 4. tools/call 请求（参数完整） ---
        call_msgs = [m for m in messages if m.get("method") == "tools/call"]
        assert len(call_msgs) == 1
        assert call_msgs[0]["params"]["name"] == "echo"
        assert call_msgs[0]["params"]["arguments"] == {"text": "hello"}

        # 序列顺序：initialize < initialized < tools/list < tools/call
        idx = {m: methods.index(m) for m in ("initialize", "tools/list")}
        assert idx["initialize"] < methods.index("notifications/initialized")
        assert methods.index("notifications/initialized") < idx["tools/list"]
        assert idx["tools/list"] < methods.index("tools/call")

    def test_list_tools_refresh_and_tool_level_error(self):
        session = make_session(RECORDING_SERVER).start()
        try:
            tools = session.list_tools()
            assert [t["name"] for t in tools] == ["echo"]
            schema = tools[0]["input_schema"]
            assert schema["required"] == ["text"]

            # 远端工具级失败（isError=True）：报错但会话保持可用
            with pytest.raises(MCPPluginToolError, match="unknown tool"):
                session.call_tool("no-such-tool", {})
            assert session.is_alive
            assert session.call_tool("echo", {"text": "still-alive"}) .startswith(
                "echo:echo:"
            )
        finally:
            session.stop()


# ---------------------------------------------------------------------------
# 超时 fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.mcp
@pytest.mark.timeout(30)
class TestHandshakeTimeout:
    def test_start_timeout_fails_closed_with_diagnostics(self):
        session = MCPPluginStdioSession(
            command=sys.executable,
            args=[str(SILENT_SERVER)],
            start_timeout=1.5,
        )
        with pytest.raises(MCPPluginHandshakeError) as exc_info:
            session.start()
        message = str(exc_info.value)
        # 可诊断：超时秒数 + 命令行 + cwd
        assert "1.5" in message
        assert "stdio_silent_server.py" in message
        # fail-closed：会话不可用、后台线程退出
        assert not session.is_alive
        assert session._thread is not None and not session._thread.is_alive()

    def test_request_timeout_marks_session_dead(self):
        """握手成功但 tools/call 永不回包 → 请求超时判死 + 后续立即失败。"""
        session = make_session(HANG_SERVER, request_timeout=1.5).start()
        try:
            assert [t["name"] for t in session.tools_discovered] == ["hang"]

            with pytest.raises(MCPPluginTransportError) as exc_info:
                session.call_tool("hang", {})
            assert "超时" in str(exc_info.value)

            with pytest.raises(MCPPluginTransportError, match="不可用"):
                session.call_tool("hang", {})
            assert not session.is_alive
        finally:
            session.stop()


# ---------------------------------------------------------------------------
# 进程退出 → 会话判死
# ---------------------------------------------------------------------------


@pytest.mark.mcp
@pytest.mark.timeout(60)
class TestProcessExit:
    def test_process_exit_after_handshake_fails_closed(self):
        session = make_session(CRASH_SERVER, request_timeout=2.0).start()
        try:
            # crash server 在应答 tools/list 后退出，但握手已完成
            assert [t["name"] for t in session.tools_discovered] == ["boom"]

            with pytest.raises(MCPPluginTransportError) as exc_info:
                session.call_tool("boom", {})
            assert "失败" in str(exc_info.value) or "超时" in str(exc_info.value)

            # 判死后：立即失败（可诊断），不再等待
            with pytest.raises(MCPPluginTransportError, match="不可用"):
                session.call_tool("boom", {})
            assert not session.is_alive
        finally:
            session.stop()

    def test_submit_before_start_rejected(self):
        session = make_session(RECORDING_SERVER)
        with pytest.raises(MCPPluginTransportError, match="未在运行"):
            session.call_tool("echo", {})


# ---------------------------------------------------------------------------
# 真实 MCP server（FastMCP）下的 PluginRuntime 全生命周期
# ---------------------------------------------------------------------------

# 临时插件目录内容：server.py（真实 stdio MCP server）+ manifest.json
PLUGIN_SERVER_PY = '''"""真实 stdio MCP server（官方 SDK FastMCP）——测试夹具插件。"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-plugin")


@mcp.tool(description="Echo text back to the caller")
def echo(text: str) -> str:
    return f"echo:{text}"


@mcp.tool(description="Always fails")
def fail(message: str) -> str:
    raise RuntimeError(f"intentional failure: {message}")


if __name__ == "__main__":
    mcp.run()  # stdio 传输
'''

PLUGIN_MANIFEST = {
    "schema_version": "1.0",
    "name": "demo-plugin",
    "version": "1.0.0",
    "type": "mcp-plugin",
    "xagent_compatibility": {"min_version": "0.1.0", "max_version": "1.0.0"},
    "metadata": {"author": "pytest"},
    "chinese": {"name": "测试插件"},
    "capabilities": {"tools": True, "resources": False, "prompts": False},
    "permissions": {"network": {}, "filesystem": {}, "environment": {}},
    "entry_point": {"type": "python", "module": "server", "class": "Server"},
    "dependencies": {"python": ">=3.11"},
    "tools": [
        {
            "name": "echo",
            "description": "Echo text",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "fail",
            "description": "Always fails",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    ],
}


@pytest.fixture()
def demo_plugin_dir(tmp_path: Path) -> Path:
    plugin_dir = tmp_path / "plugins" / "demo-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "server.py").write_text(PLUGIN_SERVER_PY, encoding="utf-8")
    (plugin_dir / "manifest.json").write_text(
        json.dumps(PLUGIN_MANIFEST, ensure_ascii=False), encoding="utf-8"
    )
    return plugin_dir.parent


@pytest.mark.mcp
@pytest.mark.timeout(90)
class TestPluginRuntimeMcpLifecycle:
    def test_start_handshake_discover_call_stop(self, demo_plugin_dir: Path):
        runtime = PluginRuntime(demo_plugin_dir)
        assert runtime.load("demo-plugin").status == "loaded"

        # --- start：spawn → initialize → initialized → tools/list ---
        result = runtime.start("demo-plugin", timeout=20)
        assert result["ok"] is True, result.get("error")
        plugin = runtime.get_loaded("demo-plugin")
        assert plugin.status == MCPPluginStatus.RUNNING
        assert plugin.server_info["server_name"] == "demo-plugin"
        assert sorted(result["tools"]) == ["echo", "fail"]

        # --- 幂等：已在运行时重复 start 直接成功（不重复拉起进程） ---
        assert runtime.start("demo-plugin", timeout=20)["ok"] is True
        assert plugin.session is not None and plugin.session.is_alive

        # --- tools/call：成功路径（structuredContent 优先，与 MCPClient 契约一致） ---
        output = runtime.call_plugin_tool("demo-plugin", "echo", {"text": "hello"})
        assert "echo:hello" in str(output)

        # --- tools/call：远端工具级失败（插件保持 RUNNING） ---
        with pytest.raises(ValueError, match="MCP tool 'fail' failed"):
            runtime.call_plugin_tool("demo-plugin", "fail", {"message": "boom"})
        assert plugin.status == MCPPluginStatus.RUNNING

        # --- manifest 信任边界：未声明工具 / 必填参数缺失 ---
        with pytest.raises(ValueError, match="Tool not found"):
            runtime.call_plugin_tool("demo-plugin", "undeclared", {})
        with pytest.raises(ValueError, match="Required field missing"):
            runtime.call_plugin_tool("demo-plugin", "echo", {})

        # --- 实时 tools/list ---
        tools = runtime.list_remote_tools("demo-plugin")
        assert {t["name"] for t in tools} == {"echo", "fail"}

        # --- stop：进程清理、状态显式 ---
        stop_result = runtime.stop("demo-plugin")
        assert stop_result["ok"] is True
        assert plugin.status == MCPPluginStatus.STOPPED
        assert plugin.session is None

        # 停止后调用 fail-closed
        with pytest.raises(RuntimeError, match="not running"):
            runtime.call_plugin_tool("demo-plugin", "echo", {"text": "x"})

        assert runtime.unload("demo-plugin") is True

    async def test_bridge_into_tool_registry_and_execute(self, demo_plugin_dir: Path):
        from backend.app.core.contracts import RunContext
        from backend.app.core.plugin_agent_adapter import (
            PLUGIN_MCP_TOOL_PREFIX,
            plugin_mcp_tool_name,
        )
        from backend.app.core.tools import ToolRegistry

        registry = ToolRegistry()
        runtime = PluginRuntime(demo_plugin_dir)
        runtime.load("demo-plugin")

        # 未启动（无会话）时桥接为空（显式，不静默注册）
        assert runtime.bridge_tools("demo-plugin", registry) == []

        start_result = runtime.start(
            "demo-plugin", timeout=20, tool_registry=registry
        )
        assert start_result["ok"] is True, start_result.get("error")
        expected_echo = plugin_mcp_tool_name("demo-plugin", "echo")
        expected_fail = plugin_mcp_tool_name("demo-plugin", "fail")
        assert set(start_result["registered_tools"]) == {expected_echo, expected_fail}

        # LLM 可见（主循环执行表）
        assert registry.get(expected_echo) is not None
        assert expected_echo.startswith(PLUGIN_MCP_TOOL_PREFIX)
        llm_names = [d["function"]["name"] for d in registry.definitions_for_llm()]
        assert expected_echo in llm_names

        # 主循环咽喉点真实调用远端工具
        record = await registry.execute(
            RunContext(), expected_echo, {"text": "via-registry"}
        )
        assert record.success, f"echo 调用失败: {record.error}"
        assert "echo:via-registry" in str(record.output)

        # stop 后桥接工具移除，主循环调不到
        runtime.stop("demo-plugin")
        assert registry.get(expected_echo) is None


# ---------------------------------------------------------------------------
# 适配器契约（无子进程）
# ---------------------------------------------------------------------------


@pytest.mark.mcp
class TestAdapterContract:
    @staticmethod
    def _loaded_plugin(tmp_path: Path, entry: dict, tools: list | None = None):
        plugin_dir = tmp_path / "plugins" / "contract-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        manifest = dict(PLUGIN_MANIFEST)
        manifest["name"] = "contract-plugin"
        manifest["entry_point"] = entry
        manifest["tools"] = tools or []
        (plugin_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        adapter = MCPPluginAdapter(tmp_path / "plugins")
        return adapter.load_plugin(plugin_dir)

    def test_build_server_command_python(self, tmp_path: Path):
        plugin = self._loaded_plugin(
            tmp_path, {"type": "python", "module": "server", "class": "Server"}
        )
        command, args, cwd = MCPPluginAdapter._build_server_command(plugin)
        assert command == sys.executable
        assert args == ["-m", "server"]
        assert cwd == str(plugin.plugin_path)

    def test_build_server_command_node(self, tmp_path: Path):
        plugin = self._loaded_plugin(
            tmp_path, {"type": "node", "module": "index.js", "class": "Server"}
        )
        command, args, cwd = MCPPluginAdapter._build_server_command(plugin)
        assert command == "node"
        assert args == [str(plugin.plugin_path / "index.js")]

    def test_docker_entry_fails_closed(self, tmp_path: Path):
        plugin = self._loaded_plugin(
            tmp_path, {"type": "docker", "module": "image", "class": "Server"}
        )
        adapter = MCPPluginAdapter(tmp_path / "plugins")
        assert adapter.start_server(plugin) is False
        assert plugin.status == MCPPluginStatus.ERROR
        assert "docker" in (plugin.error_message or "")

    def test_call_tool_before_start_rejected(self, tmp_path: Path):
        plugin = self._loaded_plugin(
            tmp_path,
            {"type": "python", "module": "server", "class": "Server"},
            tools=[{"name": "echo", "input_schema": {"required": ["text"]}}],
        )
        adapter = MCPPluginAdapter(tmp_path / "plugins")
        with pytest.raises(RuntimeError, match="not running"):
            adapter.call_tool(plugin, "echo", {"text": "x"})

    def test_stop_without_session_is_noop(self, tmp_path: Path):
        plugin = self._loaded_plugin(
            tmp_path, {"type": "python", "module": "server", "class": "Server"}
        )
        adapter = MCPPluginAdapter(tmp_path / "plugins")
        assert adapter.stop_server(plugin) is True
        # 从未启动：状态保持 loaded，不残留会话/进程
        assert plugin.status == MCPPluginStatus.LOADED
        assert plugin.session is None and plugin.process is None

    def test_env_timeout_parsing(self, monkeypatch):
        monkeypatch.delenv(ENV_START_TIMEOUT, raising=False)
        monkeypatch.delenv(ENV_REQUEST_TIMEOUT, raising=False)
        adapter = MCPPluginAdapter()
        assert adapter.start_timeout == DEFAULT_START_TIMEOUT
        assert adapter.request_timeout == DEFAULT_REQUEST_TIMEOUT

        monkeypatch.setenv(ENV_START_TIMEOUT, "2.5")
        monkeypatch.setenv(ENV_REQUEST_TIMEOUT, "7")
        adapter = MCPPluginAdapter()
        assert adapter.start_timeout == 2.5
        assert adapter.request_timeout == 7.0

        monkeypatch.setenv(ENV_START_TIMEOUT, "not-a-number")
        adapter = MCPPluginAdapter()
        assert adapter.start_timeout == DEFAULT_START_TIMEOUT

    def test_env_timeout_invalid_rejected(self, monkeypatch):
        monkeypatch.setenv(ENV_START_TIMEOUT, "0")
        monkeypatch.setenv(ENV_REQUEST_TIMEOUT, "-3")
        session = MCPPluginStdioSession(command="x")
        assert session._start_timeout == DEFAULT_START_TIMEOUT
        assert session._request_timeout == DEFAULT_REQUEST_TIMEOUT


# ---------------------------------------------------------------------------
# 真实 plugins/ 目录插件（已迁移为真实 stdio MCP server）：
# 缺配置 fail-closed（可诊断）+ 配置后全生命周期（握手→发现→调用→stop）
# ---------------------------------------------------------------------------


def _as_dict(output: Any) -> dict:
    """工具返回值归一化：JSON 文本 → dict（dict 返回原样）。"""
    if isinstance(output, str):
        return json.loads(output)
    return output


@pytest.mark.mcp
@pytest.mark.timeout(60)
class TestRealPluginsMissingConfig:
    """缺配置（无凭证）启动必须 fail-closed：不 spawn 成功、错误可诊断。"""

    @pytest.mark.parametrize(
        "plugin_name, expected_reason",
        [
            ("filesystem-mcp", "allowed_paths"),
            ("github-mcp", "github_token"),
            ("database-mcp", "required configuration missing"),
        ],
    )
    def test_missing_config_fails_closed_with_reason(
        self, plugin_name: str, expected_reason: str
    ):
        from backend.plugins.runtime import get_default_plugins_dir

        runtime = PluginRuntime(get_default_plugins_dir())
        assert runtime.load(plugin_name).status == "loaded"

        result = runtime.start(plugin_name, timeout=20)
        assert result["ok"] is False
        plugin = runtime.get_loaded(plugin_name)
        assert plugin.status == MCPPluginStatus.ERROR
        assert plugin.session is None

        error = result.get("error") or ""
        # 握手失败（fail-closed）且错误携带插件自身的缺配置诊断（stderr 尾部）
        assert "握手" in error
        assert expected_reason in error
        runtime.unload(plugin_name)


@pytest.mark.mcp
@pytest.mark.timeout(120)
class TestRealPluginsLifecycle:
    """三个真实插件的完整子进程生命周期（spawn → 握手 → 工具发现 → 调用 → stop）。"""

    def test_filesystem_full_lifecycle_with_sandbox(self, tmp_path: Path):
        from backend.plugins.runtime import get_default_plugins_dir

        runtime = PluginRuntime(get_default_plugins_dir())
        assert runtime.load("filesystem-mcp").status == "loaded"

        # --- start（真实握手 + 工具发现），allowed_paths 指向临时目录 ---
        result = runtime.start(
            "filesystem-mcp",
            timeout=30,
            config={"allowed_paths": [str(tmp_path)], "max_file_size_mb": 5},
        )
        assert result["ok"] is True, result.get("error")
        plugin = runtime.get_loaded("filesystem-mcp")
        assert plugin.status == MCPPluginStatus.RUNNING
        assert plugin.server_info["server_name"] == "filesystem-mcp"
        assert plugin.server_info["protocol_version"]
        assert set(result["tools"]) == {
            "read_file", "write_file", "list_files",
            "search_files", "delete_file", "get_file_info",
        }

        # --- 真实读写往返 ---
        target = tmp_path / "notes" / "hello.txt"
        written = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "write_file",
            {"path": str(target), "content": "hello x-agent"},
        ))
        assert written["status"] == "success", written

        read = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "read_file", {"path": str(target)},
        ))
        assert read["status"] == "success"
        assert read["data"]["content"] == "hello x-agent"

        listed = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "list_files", {"path": str(tmp_path), "recursive": True},
        ))
        assert listed["status"] == "success"
        assert any(item["name"] == "hello.txt" for item in listed["data"])

        found = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "search_files",
            {"path": str(tmp_path), "pattern": "*.txt"},
        ))
        assert found["count"] == 1

        info = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "get_file_info", {"path": str(target)},
        ))
        assert info["data"]["size"] == len("hello x-agent")

        # --- 信任边界：越界路径拒绝（allowed_paths 之外） ---
        escape = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "read_file",
            {"path": str(tmp_path.parent / "escape-attempt.txt")},
        ))
        assert escape["status"] == "error"
        assert "not allowed" in escape["message"]

        # --- manifest 信任边界：未声明工具 / 必填参数缺失 ---
        with pytest.raises(ValueError, match="Tool not found"):
            runtime.call_plugin_tool("filesystem-mcp", "undeclared_tool", {})
        with pytest.raises(ValueError, match="Required field missing"):
            runtime.call_plugin_tool("filesystem-mcp", "write_file", {"path": str(target)})

        # --- 删除（写操作）+ stop ---
        deleted = _as_dict(runtime.call_plugin_tool(
            "filesystem-mcp", "delete_file", {"path": str(target)},
        ))
        assert deleted["status"] == "success"
        assert not target.exists()

        stop_result = runtime.stop("filesystem-mcp")
        assert stop_result["ok"] is True
        assert plugin.status == MCPPluginStatus.STOPPED
        assert plugin.session is None
        runtime.unload("filesystem-mcp")

    def test_github_missing_config_then_configured_start(self):
        """无凭证 fail-closed 后，提供 token 可重新启动成功（占位工具可用）。"""
        from backend.plugins.runtime import get_default_plugins_dir

        runtime = PluginRuntime(get_default_plugins_dir())
        assert runtime.load("github-mcp").status == "loaded"

        # --- 无 token：fail-closed（可诊断） ---
        skipped = runtime.start("github-mcp", timeout=20)
        assert skipped["ok"] is False
        assert "github_token" in (skipped.get("error") or "")

        # --- 提供 token：真实握手 + 工具发现 + 占位工具调用（无网络请求） ---
        result = runtime.start(
            "github-mcp", timeout=30, config={"github_token": "ghp_test_placeholder"},
        )
        assert result["ok"] is True, result.get("error")
        plugin = runtime.get_loaded("github-mcp")
        assert plugin.status == MCPPluginStatus.RUNNING
        assert plugin.server_info["server_name"] == "github-mcp"
        assert set(result["tools"]) == {
            "list_repositories", "get_repository", "create_issue",
            "list_issues", "create_pull_request",
        }

        placeholder = _as_dict(runtime.call_plugin_tool(
            "github-mcp", "get_repository", {"owner": "octocat", "repo": "Hello-World"},
        ))
        assert placeholder["status"] == "placeholder"
        assert placeholder["arguments"] == {"owner": "octocat", "repo": "Hello-World"}

        assert runtime.stop("github-mcp")["ok"] is True
        runtime.unload("github-mcp")

    def test_database_missing_config_then_sqlite_roundtrip(self, tmp_path: Path):
        """无数据库配置 fail-closed；sqlite 配置后真实 SQL 往返。"""
        from backend.plugins.runtime import get_default_plugins_dir

        runtime = PluginRuntime(get_default_plugins_dir())
        assert runtime.load("database-mcp").status == "loaded"

        # --- 无配置：fail-closed（默认 postgresql 缺连接五元组） ---
        skipped = runtime.start("database-mcp", timeout=20)
        assert skipped["ok"] is False
        assert "required configuration" in (skipped.get("error") or "")

        # --- sqlite 本地库：真实握手 + 真实查询往返 ---
        db_file = tmp_path / "lifecycle.db"
        result = runtime.start(
            "database-mcp", timeout=30,
            config={"db_type": "sqlite", "db_name": str(db_file)},
        )
        assert result["ok"] is True, result.get("error")
        plugin = runtime.get_loaded("database-mcp")
        assert plugin.status == MCPPluginStatus.RUNNING
        assert plugin.server_info["server_name"] == "database-mcp"
        assert set(result["tools"]) == {
            "execute_query", "list_tables", "get_table_schema",
            "export_query_result", "analyze_table",
        }

        def query(sql: str) -> dict:
            return _as_dict(runtime.call_plugin_tool(
                "database-mcp", "execute_query", {"query": sql},
            ))

        assert query("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")["status"] == "success"
        assert query("INSERT INTO notes (body) VALUES ('hello')")["status"] == "success"

        selected = query("SELECT id, body FROM notes")
        assert selected["status"] == "success"
        assert selected["data"] == [{"id": 1, "body": "hello"}]

        tables = _as_dict(runtime.call_plugin_tool("database-mcp", "list_tables", {}))
        assert tables["data"] == ["notes"]

        schema = _as_dict(runtime.call_plugin_tool(
            "database-mcp", "get_table_schema", {"table_name": "notes"},
        ))
        assert [c["name"] for c in schema["data"]] == ["id", "body"]

        stats = _as_dict(runtime.call_plugin_tool(
            "database-mcp", "analyze_table", {"table_name": "notes"},
        ))
        assert stats["data"]["row_count"] == 1

        assert runtime.stop("database-mcp")["ok"] is True
        runtime.unload("database-mcp")

    def test_invalid_start_config_rejected_without_spawn(self):
        """config 未知键/类型不符：显式拒绝且不 spawn（不静默降级）。"""
        from backend.plugins.runtime import get_default_plugins_dir

        runtime = PluginRuntime(get_default_plugins_dir())
        assert runtime.load("filesystem-mcp").status == "loaded"

        result = runtime.start(
            "filesystem-mcp", timeout=20, config={"unknown_key": "x"},
        )
        assert result["ok"] is False
        assert "configuration invalid" in (result.get("error") or "")
        assert "unknown_key" in (result.get("error") or "")
        plugin = runtime.get_loaded("filesystem-mcp")
        # 未 spawn：状态保持 loaded，无会话残留
        assert plugin.status == MCPPluginStatus.LOADED
        assert plugin.session is None
        runtime.unload("filesystem-mcp")
