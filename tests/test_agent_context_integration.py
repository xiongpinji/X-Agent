# -*- coding: utf-8 -*-
"""P1-14：core/context 接入 Agent 主循环的回归测试。

覆盖：
- AgentLoop 会话打开/保存/跨运行恢复（recap 注入规划提示词）
- LLM 消息 token 级压缩（超阈值触发、system 与尾部消息保护）
- ContextManager 压缩阈值门槛与近期消息保护
- 会话租户隔离（initialize_session 显式报错、list_sessions 过滤）
- _compress_context token 预算感知裁剪（替代旧白名单）
- sessions API 租户收敛（principal 强制、请求体 tenant_id 已移除）
"""

from __future__ import annotations

import pytest

from backend.app.core.agent.loop import AgentLoop
from backend.app.core.context.agent_integration import (
    AgentLoopContextBridge,
    fit_messages_to_token_budget,
)
from backend.app.core.context.context_manager import ContextManager
from backend.app.core.context.session_recovery import SessionRecovery, SessionState
from backend.app.core.context_compactor import ContextCompactor
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm.backends import BaseLLMBackend, LLMResponse, LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


class CapturingMockBackend(BaseLLMBackend):
    """记录每次 chat 收到的消息列表的 mock 后端。"""

    name = "capturing-mock"

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages, tools):
        self.calls.append([dict(m) for m in messages])
        return LLMResponse(content="X-Agent Phase 0 mock response: captured", model="capturing-mock")


def _make_agent(
    storage: str,
    *,
    token_budget: int = 24_000,
    backend: BaseLLMBackend | None = None,
) -> tuple[AgentLoop, AgentLoopContextBridge]:
    bridge = AgentLoopContextBridge.create_default(storage_path=storage, token_budget=token_budget)
    agent = AgentLoop(
        llm_router=LLMRouter(backend=backend) if backend else LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
        context_bridge=bridge,
        context_token_budget=token_budget,
    )
    return agent, bridge


async def test_agent_run_persists_and_restores_session(tmp_path) -> None:
    """同一会话 ID 的第二次运行应从存储恢复历史并注入 recap。"""
    storage = str(tmp_path / "sessions")
    backend1 = CapturingMockBackend()
    agent1, _ = _make_agent(storage, backend=backend1)

    ctx1 = RunContext(session_id="pytest-session", tenant_id="tenant-x")
    r1 = await agent1.run(ctx1, "记住：项目代号是 Phoenix", {"root": str(tmp_path)})

    assert r1.status == RunStatus.COMPLETED
    cm1 = r1.execution_summary["context_management"]
    assert cm1["enabled"] is True
    assert cm1["session_restored"] is False
    assert cm1["session_saved"] is True
    assert (tmp_path / "sessions" / "pytest-session" / "state.json").exists()

    # 模拟进程重启：全新 AgentLoop + bridge
    backend2 = CapturingMockBackend()
    agent2, _ = _make_agent(storage, backend=backend2)
    ctx2 = RunContext(session_id="pytest-session", tenant_id="tenant-x")
    r2 = await agent2.run(ctx2, "项目代号是什么？", {"root": str(tmp_path)})

    assert r2.status == RunStatus.COMPLETED
    cm2 = r2.execution_summary["context_management"]
    assert cm2["session_restored"] is True
    assert cm2["restored_messages"] > 0

    # recap 注入规划提示词
    assert any(
        "Recovered session context" in str(m.get("content", "")) and "Phoenix" in str(m.get("content", ""))
        for call in backend2.calls
        for m in call
    )


async def test_agent_run_compresses_llm_messages_over_budget(tmp_path) -> None:
    """小 token 预算下，发给 LLM 的消息应被压缩并记录事件。"""
    backend = CapturingMockBackend()
    agent, _ = _make_agent(str(tmp_path / "sessions"), token_budget=120, backend=backend)

    big_context = {
        "root": str(tmp_path),
        "goal": "分析这个超长的上下文字段 " + "数据" * 500,
        "notes": "很长的备注 " + "内容" * 800,
    }
    result = await agent.run(RunContext(session_id="pytest-compress"), "分析任务", big_context)

    assert result.status == RunStatus.COMPLETED
    events = result.execution_summary["context_management"]["llm_compression_events"]
    assert len(events) >= 1
    assert events[0]["compressed_tokens"] < events[0]["original_tokens"]
    # system 提示词受保护
    assert backend.calls[0][0]["role"] == "system"


async def test_agent_run_without_session_id_disables_persistence(tmp_path) -> None:
    """无 session_id 时不启用会话持久化，运行不受影响。"""
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    result = await agent.run(RunContext(), "介绍一下 X-Agent", {"root": str(tmp_path)})
    assert result.status == RunStatus.COMPLETED
    assert result.execution_summary["context_management"]["enabled"] is False


async def test_context_manager_compresses_only_over_threshold(tmp_path) -> None:
    """阈值门槛：未超不压；超阈值保留最近消息并返回 CompactionResult。"""
    recovery = SessionRecovery(storage_path=str(tmp_path))
    compactor = ContextCompactor(token_limit=200, compression_threshold=0.5, min_messages_to_keep=3)
    manager = ContextManager(session_recovery=recovery, context_compactor=compactor, auto_compress_enabled=True)
    await manager.initialize_session("pytest-cm", tenant_id="t")

    await manager.add_message("user", "短消息")
    metrics = await manager.get_metrics()
    assert metrics.compression_count == 0

    for i in range(12):
        await manager.add_message("user" if i % 2 == 0 else "assistant", "消息 " + "x" * 300)

    metrics = await manager.get_metrics()
    assert metrics.compression_count >= 1

    session = manager.current_session
    assert session is not None
    # 最近 3 条原样保留
    assert all(m.content.endswith("x" * 300) for m in session.messages[-3:])
    assert len(session.messages) < 13
    # total_tokens 按压缩后重算
    assert session.total_tokens == sum(m.token_count for m in session.messages)
    assert len(session.compression_history) >= 1
    await manager.cleanup()


async def test_context_manager_tenant_mismatch_raises(tmp_path) -> None:
    """跨租户恢复同一会话 ID 必须显式报错。"""
    storage = str(tmp_path)
    m1 = ContextManager(
        session_recovery=SessionRecovery(storage_path=storage),
        context_compactor=ContextCompactor(),
    )
    await m1.initialize_session("pytest-tenant", tenant_id="tenant-1")
    await m1.add_message("user", "tenant-1 的数据")
    await m1.save_session()
    await m1.cleanup()

    m2 = ContextManager(
        session_recovery=SessionRecovery(storage_path=storage),
        context_compactor=ContextCompactor(),
    )
    with pytest.raises(ValueError, match="Tenant mismatch"):
        await m2.initialize_session("pytest-tenant", tenant_id="tenant-2")
    await m2.cleanup()


async def test_session_recovery_tenant_filtered_listing(tmp_path) -> None:
    """list_sessions 按租户过滤。"""
    recovery = SessionRecovery(storage_path=str(tmp_path))
    for sid, tenant in [("s-1", "tenant-a"), ("s-2", "tenant-a"), ("s-3", "tenant-b")]:
        await recovery.save_snapshot(SessionState(session_id=sid, agent_id="agent-1", tenant_id=tenant))

    assert len(await recovery.list_sessions()) == 3
    tenant_a = await recovery.list_sessions(tenant_id="tenant-a")
    assert {s.session_id for s in tenant_a} == {"s-1", "s-2"}
    assert all(s.tenant_id == "tenant-a" for s in tenant_a)


def test_compress_context_preserves_operational_keys(tmp_path) -> None:
    """_compress_context：操作性键原样保留（含旧白名单遗漏的 needle/tree_limit）。"""
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    ctx = {
        "root": "/repo", "path": "a.py", "old_text": "foo", "new_text": "bar",
        "needle": "foo", "tree_limit": 99,
        "patches": [{"path": "a.py", "old_text": "x", "new_text": "y"}],
    }
    compact = agent._compress_context(ctx)
    for key, value in ctx.items():
        assert compact.get(key) == value
    assert compact["target_path"] == "a.py"
    assert compact["patch_count"] == 1


def test_compress_context_budget_trims_non_operational(tmp_path) -> None:
    """_compress_context：非操作性大值截断、超预算显式丢弃、均有记录。"""
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    compact = agent._compress_context({"big": "z" * 5000, "small": "ok"})
    assert len(compact["big"]) < 1200
    assert "truncated" in compact["big"]
    assert "big" in compact["_context_compaction"]["truncated_keys"]
    assert compact["small"] == "ok"

    many = {f"key{i}": "v" * 900 for i in range(30)}
    compact2 = agent._compress_context(many)
    dropped = compact2["_context_compaction"]["dropped_keys"]
    assert len(dropped) > 0
    assert all(k not in compact2 for k in dropped)


def test_compress_context_handles_invalid_input(tmp_path) -> None:
    """_compress_context：非 dict 与循环引用显式安全降级。"""
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    assert agent._compress_context("invalid") == {}

    circular: dict = {"key": "value"}
    circular["self"] = circular
    compact = agent._compress_context(circular)
    assert isinstance(compact.get("self"), str)


def test_fit_messages_to_token_budget_protects_system_and_tail() -> None:
    """LLM 消息压缩：未超阈值原样返回；超阈值保护 system 与尾部消息。"""
    compactor = ContextCompactor(token_limit=100, compression_threshold=0.5)

    small = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    fitted, meta = fit_messages_to_token_budget(compactor, small)
    assert meta is None and fitted == small

    big = (
        [{"role": "system", "content": "system prompt 必须保留"}]
        + [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"历史消息{i} " + "长" * 200}
            for i in range(8)
        ]
        + [{"role": "user", "content": "倒数第二条"}, {"role": "user", "content": "最后的问题"}]
    )
    fitted2, meta2 = fit_messages_to_token_budget(compactor, big)
    assert meta2 is not None and meta2["triggered"] is True
    assert fitted2[0]["role"] == "system" and "必须保留" in fitted2[0]["content"]
    assert fitted2[-1]["content"] == "最后的问题"
    assert fitted2[-2]["content"] == "倒数第二条"
    assert meta2["compressed_tokens"] < meta2["original_tokens"]


def test_sessions_api_has_no_client_tenant_field() -> None:
    """sessions API：InitializeSessionRequest 不再接受客户端 tenant_id。"""
    from backend.app.api.sessions import InitializeSessionRequest

    assert "tenant_id" not in InitializeSessionRequest.model_fields


async def test_sessions_api_tenant_converged_to_principal(tmp_path) -> None:
    """sessions API：initialize 强制使用 principal.tenant_id；跨租户操作 404。"""
    from backend.app.api import sessions as sessions_api
    from backend.app.core.security import Principal

    manager = ContextManager(
        session_recovery=SessionRecovery(storage_path=str(tmp_path)),
        context_compactor=ContextCompactor(),
    )
    sessions_api.set_context_manager(manager)

    principal_a = Principal(tenant_id="tenant-a", user_id="u-a", role="admin", scopes=["agent:run", "agent:read"], authenticated=True)
    principal_b = Principal(tenant_id="tenant-b", user_id="u-b", role="admin", scopes=["agent:run", "agent:read"], authenticated=True)

    # tenant-a 初始化会话（请求体无法指定租户）
    result = await sessions_api.initialize_session(
        sessions_api.InitializeSessionRequest(session_id="api-session"),
        principal_a,
    )
    assert result["tenant_id"] == "tenant-a"
    await manager.save_session()

    # tenant-b 恢复同一会话 → 404（不泄露存在性）
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await sessions_api.restore_session("api-session", principal_b)
    assert exc_info.value.status_code == 404

    # tenant-a 正常恢复
    restored = await sessions_api.restore_session("api-session", principal_a)
    assert restored["tenant_id"] == "tenant-a"

    # tenant-b 的列表看不到 tenant-a 的会话（直接调用需显式传 Query 默认值）
    listed_b = await sessions_api.list_sessions(principal_b, agent_id=None, limit=100)
    assert all(s["session_id"] != "api-session" for s in listed_b.sessions)
    listed_a = await sessions_api.list_sessions(principal_a, agent_id=None, limit=100)
    assert any(s["session_id"] == "api-session" for s in listed_a.sessions)

    sessions_api.set_context_manager(None)  # type: ignore[arg-type]
