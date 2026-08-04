"""P1-08 残留收尾：租户/用户配额穿透主循环 + 断链修复 + 429 映射的回归测试。

覆盖：
1. AgentLoop fast-path 与主规划循环调用 ``llm.chat`` 时穿透
   ``context.tenant_id`` / ``context.user_id``（此前不传，配额只落 default 桶）。
2. ``llm/quota.py::get_quota_manager`` 状态访问器（修复 api/agents.py 与
   api/tenant_isolation.py 引用了不存在函数的断链）。
3. QuotaExceededError → HTTP 429 的全局异常映射（此前会从端点冒出 500）。
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm import LLMRouter
from backend.app.core.llm.quota import QuotaExceededError, get_quota_manager
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


class _RecordingQuotaManager:
    """Minimal stand-in for TokenQuotaManager: records every interaction."""

    def __init__(self) -> None:
        self.checks: list[tuple[str | None, str | None]] = []
        self.records: list[tuple[str | None, str | None, int, float]] = []

    async def check_quota(self, tenant_id: str | None, user_id: str | None) -> None:
        self.checks.append((tenant_id, user_id))

    async def record_usage(
        self,
        tenant_id: str | None,
        user_id: str | None,
        tokens: int,
        cost_usd: float = 0.0,
    ) -> None:
        self.records.append((tenant_id, user_id, tokens, cost_usd))


def _build_agent(quota: _RecordingQuotaManager) -> AgentLoop:
    return AgentLoop(
        llm_router=LLMRouter(quota_manager=quota),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )


async def test_fast_path_penetrates_tenant_context() -> None:
    quota = _RecordingQuotaManager()
    agent = _build_agent(quota)
    context = RunContext(tenant_id="t-acme", user_id="u-7")

    result = await agent.run(context, "介绍一下 X-Agent")

    assert result.status == RunStatus.COMPLETED
    assert result.execution_summary.get("fast_path") is True
    # 配额拦截与记账都必须携带真实租户/用户，而不是 default 桶
    assert ("t-acme", "u-7") in quota.checks
    assert all(t == "t-acme" and u == "u-7" for t, u in quota.checks)
    assert any(t == "t-acme" and u == "u-7" for t, u, *_ in quota.records)


async def test_main_loop_penetrates_tenant_context() -> None:
    quota = _RecordingQuotaManager()
    agent = _build_agent(quota)
    context = RunContext(tenant_id="t-acme", user_id="u-7")

    # 含复杂关键词（"创建"）→ 不走 fast-path，进入完整规划循环
    result = await agent.run(context, "创建一个 Python 函数计算斐波那契数列")

    assert result.status in (RunStatus.COMPLETED, RunStatus.FAILED)
    # 规划循环的 llm.chat 必须穿透租户上下文
    assert ("t-acme", "u-7") in quota.checks


class TestGetQuotaManager:
    def test_returns_none_when_router_has_no_quota(self, monkeypatch) -> None:
        import backend.app.dependencies as deps

        monkeypatch.setattr(deps, "get_llm_router", lambda: LLMRouter())
        assert get_quota_manager() is None

    def test_returns_attached_manager(self, monkeypatch) -> None:
        import backend.app.dependencies as deps

        sentinel = _RecordingQuotaManager()
        monkeypatch.setattr(
            deps, "get_llm_router", lambda: LLMRouter(quota_manager=sentinel)
        )
        assert get_quota_manager() is sentinel

    def test_returns_none_when_router_unbuildable(self, monkeypatch) -> None:
        import backend.app.dependencies as deps

        def _boom():
            raise RuntimeError("no credentials")

        monkeypatch.setattr(deps, "get_llm_router", _boom)
        assert get_quota_manager() is None


def test_quota_exceeded_maps_to_429() -> None:
    from backend.app.api.errors import quota_exceeded_handler

    app = FastAPI()
    app.add_exception_handler(QuotaExceededError, quota_exceeded_handler)

    @app.get("/boom")
    async def boom() -> None:
        raise QuotaExceededError(
            scope="tenant",
            identifier="t-acme",
            used_tokens=1_000_000,
            limit_tokens=1_000_000,
            period="day",
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/boom")

    assert resp.status_code == 429
    body = resp.json()
    assert body["code"] == "rate_limit_exceeded"
    assert "t-acme" in body["message"]
    assert body["details"]["scope"] == "tenant"
    assert body["details"]["identifier"] == "t-acme"
