"""P1-11 技能运行时验证测试（Wave A）

覆盖：
- SkillLoader 默认指向真实 skills/ 目录并加载两个可执行技能
- code-review-skill / data-analysis-skill 功能级执行（含显式失败路径）
- skill_agent_adapter：工具列表、ToolRegistry 注册、经 registry.execute 调用
- skills_api.py：tenant_id 解析、路由顺序、可挂载性
"""

from __future__ import annotations

# --- Wave A 并行期防御（2026-07-20）-------------------------------------
# tests/conftest.py 的 autouse fixture 需要 backend.app.main._rate_limiter；
# 其他子代理正在并行改造 main 的导入链（dispatch/collaboration），
# main 暂时不可导入。此处仅在其导入失败时安装最小 stub（_windows 字典），
# main 恢复健康后本 shim 自动失效。本 shim 不影响被测对象（均不依赖 main）。
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

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.skills import SkillLoader, SkillContext, get_default_skills_dirs
from backend.app.core.skill_agent_adapter import (
    SKILL_TOOL_PREFIX,
    list_skill_tools,
    register_skills_into_tool_registry,
    skill_tool_name,
)


# ---------- 加载器 ----------


class TestSkillLoaderRuntime:
    def test_default_dirs_point_to_real_skills_dir(self):
        dirs = get_default_skills_dirs()
        names = [d.name for d in dirs]
        assert "skills" in names
        skills_dir = next(d for d in dirs if d.name == "skills")
        assert (skills_dir / "code-review-skill" / "main.py").is_file()
        assert (skills_dir / "data-analysis-skill" / "main.py").is_file()

    async def test_load_all_real_skills(self):
        loader = SkillLoader()
        skills = await loader.load_all_skills()
        loaded = set(loader.list_loaded_skills())
        assert "code-review-skill" in loaded
        assert "data-analysis-skill" in loaded
        assert len(skills) >= 2
        # 加载报告显式记录，全部成功
        report = loader.load_report
        assert report["code-review-skill"]["status"] == "loaded"
        assert report["data-analysis-skill"]["status"] == "loaded"

    async def test_load_missing_skill_is_explicit_failure(self):
        loader = SkillLoader()
        skill = await loader.load_skill("no-such-skill")
        assert skill is None
        assert loader.load_report["no-such-skill"]["status"] == "failed"
        assert loader.load_report["no-such-skill"]["error"]


# ---------- 技能功能级执行 ----------


class TestCodeReviewSkill:
    async def _execute(self, **kwargs):
        loader = SkillLoader()
        skill = await loader.load_skill("code-review-skill")
        assert skill is not None
        ctx = SkillContext(skill_name="code-review-skill", execution_id="t1")
        return await skill.execute(ctx, **kwargs)

    async def test_detects_real_issues(self):
        code = (
            "def add(a, b=[]):\n"
            "    try:\n"
            "        return a + b\n"
            "    except:\n"
            "        eval('1+1')\n"
        )
        result = await self._execute(code=code)
        assert result.success, result.error
        rules = {i["rule"] for i in result.data["issues"]}
        assert "mutable-default-argument" in rules
        assert "bare-except" in rules
        assert "no-eval-exec" in rules
        assert result.data["summary"]["errors"] >= 2
        assert "report_markdown" in result.data

    async def test_non_python_input_fails_explicitly(self):
        result = await self._execute(code="def add(a, b) { return a + b; }")
        assert not result.success
        assert "Python" in result.error  # 显式降级说明，不假装审查成功

    async def test_missing_code_param_fails_explicitly(self):
        result = await self._execute()
        assert not result.success
        assert "code" in result.error


class TestDataAnalysisSkill:
    async def _execute(self, **kwargs):
        loader = SkillLoader()
        skill = await loader.load_skill("data-analysis-skill")
        assert skill is not None
        ctx = SkillContext(skill_name="data-analysis-skill", execution_id="t2")
        return await skill.execute(ctx, **kwargs)

    async def test_csv_profile_stats(self):
        csv_text = "city,sales\n北京,120\n上海,200\n北京,150\n广州,80\n"
        result = await self._execute(csv_text=csv_text)
        assert result.success, result.error
        assert result.data["row_count"] == 4
        assert result.data["column_count"] == 2
        cols = {c["column"]: c for c in result.data["columns"]}
        assert cols["sales"]["type"] == "numeric"
        assert cols["sales"]["stats"]["min"] == 80.0
        assert cols["sales"]["stats"]["max"] == 200.0
        assert cols["sales"]["stats"]["mean"] == pytest.approx(137.5)
        assert cols["city"]["type"] == "text"
        top = cols["city"]["stats"]["top_values"][0]
        assert top["value"] == "北京" and top["count"] == 2

    async def test_missing_input_fails_explicitly(self):
        result = await self._execute()
        assert not result.success
        assert "csv_text" in result.error or "file_path" in result.error

    async def test_missing_file_fails_explicitly(self):
        result = await self._execute(file_path="D:/no/such/file.csv")
        assert not result.success
        assert "不存在" in result.error


# ---------- AgentLoop 消费适配器 ----------


class TestSkillAgentAdapter:
    async def test_list_skill_tools(self):
        tools = await list_skill_tools()
        by_name = {t["name"]: t for t in tools}
        assert skill_tool_name("code-review-skill") in by_name
        assert skill_tool_name("data-analysis-skill") in by_name
        cr = by_name[skill_tool_name("code-review-skill")]
        assert cr["name"].startswith(SKILL_TOOL_PREFIX)
        assert "code" in cr["parameters_schema"].get("required", [])
        assert cr["description"]

    async def test_register_and_execute_via_tool_registry(self):
        from backend.app.core.contracts import RunContext
        from backend.app.core.tools import ToolRegistry

        registry = ToolRegistry()
        registered = await register_skills_into_tool_registry(registry)
        assert skill_tool_name("code-review-skill") in registered
        assert skill_tool_name("data-analysis-skill") in registered

        # LLM 可见的工具定义
        llm_defs = {d["function"]["name"] for d in registry.definitions_for_llm()}
        assert skill_tool_name("code-review-skill") in llm_defs

        # 经 ToolRegistry.execute 真实调用（与 AgentLoop 消费路径一致）
        record = await registry.execute(
            RunContext(),
            skill_tool_name("code-review-skill"),
            {"code": "def f(x=[]):\n    return eval('1')\n"},
        )
        assert record.success, record.error
        assert record.result["success"] is True
        rules = {i["rule"] for i in record.result["data"]["issues"]}
        assert "mutable-default-argument" in rules

    async def test_handler_unknown_skill_fails_explicitly(self):
        from backend.app.core.skill_agent_adapter import build_skill_tool_handler

        handler = build_skill_tool_handler("no-such-skill")
        result = await handler()
        assert result["success"] is False
        assert "no-such-skill" in result["error"]


# ---------- skills_api.py 安全与可挂载性 ----------


class TestSkillsApiTenantFix:
    def test_authenticated_principal_overrides_tenant(self):
        from backend.app.api.skills_api import _resolve_tenant_user
        from backend.app.core.security import Principal

        principal = Principal(tenant_id="tenant-a", user_id="user-a", authenticated=True)
        # 请求未显式指定 tenant → 以 Principal 为准
        tenant, user = _resolve_tenant_user("", "", principal)
        assert tenant == "tenant-a" and user == "user-a"
        # 请求显式指定且一致 → 放行
        tenant, user = _resolve_tenant_user("tenant-a", "whoever", principal)
        assert tenant == "tenant-a" and user == "user-a"

    def test_tenant_mismatch_raises_403(self):
        from backend.app.api.errors import XAgentAPIError
        from backend.app.api.skills_api import _resolve_tenant_user
        from backend.app.core.security import Principal

        principal = Principal(tenant_id="tenant-a", user_id="user-a", authenticated=True)
        with pytest.raises(XAgentAPIError) as exc_info:
            _resolve_tenant_user("tenant-b", "", principal)
        assert exc_info.value.status_code == 403

    def test_anonymous_dev_passthrough(self):
        from backend.app.api.skills_api import _resolve_tenant_user
        from backend.app.core.security import Principal

        principal = Principal(authenticated=False)  # 仅本地开发可达
        tenant, user = _resolve_tenant_user("t-dev", "u-dev", principal)
        assert tenant == "t-dev" and user == "u-dev"


def _make_test_app(router) -> FastAPI:
    """构建带 XAgent 异常处理器的测试 app（与 main.py 的注册方式一致）"""
    from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler

    app = FastAPI()
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.include_router(router)
    return app


class TestSkillsApiMountable:
    @staticmethod
    def _client() -> TestClient:
        from backend.app.api.skills_api import router

        return TestClient(_make_test_app(router), headers={"x-api-key": "bootstrap"})

    def test_health_not_shadowed_by_skill_id_route(self):
        """路由顺序修复：GET /api/skills/health 不再被 /{skill_id} 抢占"""
        response = self._client().get("/api/skills/health")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "health" in body  # 命中的是健康端点，不是 get_skill_info("health")

    def test_static_routes_reachable(self):
        client = self._client()
        assert client.get("/api/skills/discover").status_code == 200
        assert client.get("/api/skills/search", params={"query": "x"}).status_code == 200
        assert client.get("/api/skills/stats/marketplace").status_code == 200
        assert client.get("/api/skills/stats/top").status_code == 200
        assert client.get("/api/skills").status_code == 200

    def test_execute_rejects_tenant_mismatch(self):
        response = self._client().post(
            "/api/skills/execute",
            json={"skill_name": "x", "input_data": {}, "tenant_id": "other-tenant"},
        )
        assert response.status_code == 403

    def test_unauthenticated_request_rejected(self):
        from backend.app.api.skills_api import router

        # 无凭证：开发模式匿名主体无 scope，enforce_scope 必须拒绝
        response = TestClient(_make_test_app(router)).get("/api/skills/discover")
        assert response.status_code == 401
