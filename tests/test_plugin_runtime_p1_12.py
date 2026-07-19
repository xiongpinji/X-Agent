"""P1-12 插件运行时验证测试（Wave A）

覆盖：
- PluginRuntime.scan 对 plugins/ 目录的真实分类（3 MCP / 3 legacy / 辅助目录）
- MCP 插件加载（含适配器 FieldInfo 缺陷规避、JSON 可序列化）
- inspect_entrypoint 进程内真实验证（filesystem-mcp）
- legacy 插件显式拒绝（不静默、不假装可用）
- router 可挂载性（未挂载到主 app）
"""

from __future__ import annotations

# --- Wave A 并行期防御（2026-07-20）-------------------------------------
# 同 test_skill_runtime_p1_11.py：main 导入链被并行改造时的最小 stub，
# main 恢复健康后自动失效。
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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.plugins.runtime import PluginRuntime, get_default_plugins_dir


@pytest.fixture()
def runtime() -> PluginRuntime:
    return PluginRuntime(get_default_plugins_dir())


class TestPluginScan:
    def test_default_dir_is_project_plugins(self):
        assert get_default_plugins_dir().name == "plugins"
        assert (get_default_plugins_dir() / "filesystem-mcp" / "manifest.json").is_file()

    def test_scan_classifies_all_dirs(self, runtime: PluginRuntime):
        infos = {i.name: i for i in runtime.scan(refresh=True)}

        # 3 个真实 MCP 插件可加载
        for name in ("filesystem-mcp", "database-mcp", "github-mcp"):
            assert infos[name].status == "loadable", infos[name].errors
            assert infos[name].format == "mcp"
            assert infos[name].tools  # manifest 声明了工具

        # 3 个旧格式插件显式标记 legacy_unsupported（不静默、不假装可用）
        for name in ("github-plugin", "automation-plugin", "data-processor-plugin"):
            assert infos[name].status == "legacy_unsupported"
            assert infos[name].format == "legacy"
            assert "Phase 3" in (infos[name].detail or "")

        # 辅助目录显式归类
        assert infos["examples"].status == "no_manifest"
        assert infos["templates"].status == "no_manifest"

    def test_scan_results_json_serializable(self, runtime: PluginRuntime):
        for info in runtime.scan(refresh=True):
            json.dumps(info.to_dict())  # 不抛异常即可


class TestPluginLoad:
    def test_load_filesystem_mcp(self, runtime: PluginRuntime):
        info = runtime.load("filesystem-mcp")
        assert info.status == "loaded", info.errors
        plugin = runtime.get_loaded("filesystem-mcp")
        assert plugin is not None
        # 适配器 FieldInfo 缺陷已被规避
        assert isinstance(plugin.plugin_id, str)
        json.dumps(plugin.to_dict())  # 可 JSON 序列化

    def test_load_all_reports_each_plugin(self, runtime: PluginRuntime):
        results = {r.name: r for r in runtime.load_all()}
        assert results["filesystem-mcp"].status == "loaded"
        assert results["database-mcp"].status == "loaded"
        assert results["github-mcp"].status == "loaded"
        assert results["github-plugin"].status == "legacy_unsupported"
        assert set(runtime.list_loaded()) == {"filesystem-mcp", "database-mcp", "github-mcp"}

    def test_legacy_plugin_cannot_load(self, runtime: PluginRuntime):
        info = runtime.load("github-plugin")
        assert info.status == "legacy_unsupported"
        assert runtime.get_loaded("github-plugin") is None

    def test_unload(self, runtime: PluginRuntime):
        runtime.load("filesystem-mcp")
        assert runtime.unload("filesystem-mcp") is True
        assert runtime.get_loaded("filesystem-mcp") is None
        assert runtime.unload("filesystem-mcp") is False


class TestPluginInspect:
    def test_inspect_filesystem_mcp_entrypoint(self, runtime: PluginRuntime):
        result = runtime.inspect_entrypoint(
            "filesystem-mcp", config={"allowed_paths": ["D:/AI编程库/项目库/进行中的项目/X-Agent"]}
        )
        assert result["ok"], result.get("error") or result.get("missing_tools")
        assert result["entry_class"] == "FileSystemPlugin"
        assert "read_file" in result["declared_tools"]
        assert result["missing_tools"] == []

    def test_inspect_reports_missing_config_honestly(self, runtime: PluginRuntime):
        # filesystem-mcp 的 allowed_paths 为必填；缺省时必须显式报错而非假装成功
        result = runtime.inspect_entrypoint("filesystem-mcp", config={})
        assert result["ok"] is False
        assert result["error"]

    def test_inspect_unknown_plugin(self, runtime: PluginRuntime):
        result = runtime.inspect_entrypoint("no-such-plugin")
        assert result["ok"] is False


class TestPluginRouterMountable:
    @staticmethod
    def _client() -> TestClient:
        from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
        from backend.plugins.router import router

        app = FastAPI()
        app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
        app.include_router(router)
        return TestClient(app, headers={"x-api-key": "bootstrap"})

    def test_list_plugins(self):
        response = self._client().get("/api/v1/plugins")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        statuses = {p["name"]: p["status"] for p in body["plugins"]}
        assert statuses["filesystem-mcp"] in ("loadable", "loaded")
        assert statuses["github-plugin"] == "legacy_unsupported"

    def test_load_and_inspect_via_router(self):
        client = self._client()
        response = client.post("/api/v1/plugins/filesystem-mcp/load")
        assert response.status_code == 200, response.text
        assert response.json()["plugin"]["status"] == "loaded"

        response = client.post(
            "/api/v1/plugins/filesystem-mcp/inspect",
            json={"config": {"allowed_paths": ["D:/AI编程库/项目库/进行中的项目/X-Agent"]}},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_load_legacy_plugin_returns_400_with_reason(self):
        response = self._client().post("/api/v1/plugins/github-plugin/load")
        assert response.status_code == 400
        assert "legacy_unsupported" in response.text

    def test_unauthenticated_rejected(self):
        from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
        from backend.plugins.router import router

        app = FastAPI()
        app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
        app.include_router(router)
        response = TestClient(app).get("/api/v1/plugins")
        assert response.status_code == 401
