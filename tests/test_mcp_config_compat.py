"""MCP 配置兼容层测试（2026-08-04）：.mcp.json 解析、${VAR} 展开、白名单接线。"""

import json

from backend.app.core.mcp.manager import MCPManager


class TestMcpJsonCompat:
    """.mcp.json（Claude Code/Codex 兼容格式）解析。"""

    def _manager(self, tmp_path, content: str, name: str = ".mcp.json") -> MCPManager:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return MCPManager(tool_registry=None, config_path=str(path))

    def test_stdio_server_map_converted(self, tmp_path):
        m = self._manager(tmp_path, json.dumps({
            "mcpServers": {
                "filesystem": {"command": "npx", "args": ["-y", "@mcp/fs", "/tmp"], "env": {"KEY": "v1"}},
            }
        }))
        assert m._load_config() is True
        servers = m.config["mcp_servers"]
        assert len(servers) == 1
        s = servers[0]
        assert s["name"] == "filesystem"
        assert s["command"] == "npx"
        assert s["args"] == ["-y", "@mcp/fs", "/tmp"]
        assert s["env"] == {"KEY": "v1"}
        assert s["transport"] == "stdio"

    def test_http_server_map_converted(self, tmp_path):
        m = self._manager(tmp_path, json.dumps({
            "mcpServers": {"remote": {"url": "http://localhost:9000/mcp", "type": "sse"}}
        }))
        assert m._load_config() is True
        s = m.config["mcp_servers"][0]
        assert s["url"] == "http://localhost:9000/mcp"
        assert s["transport"] == "http"  # legacy 'sse' 映射为 streamable HTTP

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret-123")
        m = self._manager(tmp_path, json.dumps({
            "mcpServers": {"s": {"command": "run", "env": {"TOKEN": "${MY_TOKEN}"}, "args": ["--key=${MY_TOKEN}"]}}
        }))
        assert m._load_config() is True
        s = m.config["mcp_servers"][0]
        assert s["env"]["TOKEN"] == "secret-123"
        assert s["args"] == ["--key=secret-123"]

    def test_unset_env_var_kept_literal(self, tmp_path):
        m = self._manager(tmp_path, json.dumps({
            "mcpServers": {"s": {"command": "run", "env": {"T": "${DEFINITELY_NOT_SET_XYZ}"}}}
        }))
        assert m._load_config() is True
        assert m.config["mcp_servers"][0]["env"]["T"] == "${DEFINITELY_NOT_SET_XYZ}"

    def test_internal_format_json_passthrough(self, tmp_path):
        m = self._manager(tmp_path, json.dumps({"mcp_servers": [{"name": "x", "command": "c"}]}))
        assert m._load_config() is True
        assert m.config["mcp_servers"][0]["name"] == "x"

    def test_missing_config_returns_false(self, tmp_path):
        m = MCPManager(tool_registry=None, config_path=str(tmp_path / "nonexistent.yaml"))
        assert m._load_config() is False


class TestServerWhitelist:
    """P2-04 白名单接线。"""

    def test_whitelist_passed_to_discovery(self):
        m = MCPManager(tool_registry=None, server_whitelist=["allowed-a"])
        assert m.discovery._server_whitelist == {"allowed-a"}

    def test_no_whitelist_allows_all(self):
        m = MCPManager(tool_registry=None)
        assert m.discovery._server_whitelist is None
