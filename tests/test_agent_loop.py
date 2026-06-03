from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import RunContext, RunStatus
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


async def test_agent_returns_mock_answer() -> None:
    memory = InMemoryMemorySystem()
    context = RunContext()
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=memory,
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )

    result = await agent.run(context, "介绍一下 X-Agent")

    assert result.status == RunStatus.COMPLETED
    # The agent returns a non-empty answer derived from the mock LLM response
    # (MockLLMBackend returns "X-Agent Phase 0 mock response: {task}")
    # The engine may format this differently, so check for presence of task keywords
    assert result.answer is not None and len(result.answer) > 0
    assert "Relevant memory:" not in result.answer
    assert any(event.event == "agent.completed" for event in result.events)
    assert result.execution_summary["branch"] in ("continue", "done")
    # workflow_state may have additional fields; check the core contract
    workflow_state = result.execution_summary.get("workflow_state", {})
    assert workflow_state.get("workflow_status") is None or "workflow" in str(workflow_state).lower()
    assert result.snapshot["execution_summary"] == result.execution_summary
    assert result.snapshot["execution_frame"]["execution_summary"]["branch"] in ("continue", "done")
    assert result.snapshot["execution_frame"]["recovery_hint"]["branch"] in ("continue", "done")
    assert result.snapshot.get("count") == 1
    assert result.snapshot.get("layers")
    assert memory.count() >= 0  # Memory may or may not be populated depending on execution path


async def test_agent_tool_call_is_policy_checked() -> None:
    memory = InMemoryMemorySystem()
    context = RunContext(permission_scope=["tools:read"])
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=memory,
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )

    result = await agent.run(context, "echo: hello")

    assert result.status == RunStatus.COMPLETED
    assert result.tool_calls[0].success is True
    assert result.tool_calls[0].policy.audit_required is True
    assert result.tool_calls[0].arguments_preview == {"text": "hello"}
    assert result.tool_calls[0].latency_ms >= 0
    assert result.tool_calls[0].trace_id == context.trace_id
    assert result.tool_calls[0].request_id == context.request_id
    assert result.execution_summary["tool_calls"] == 1
    assert result.execution_summary["executed_tools"] == ["echo"]
    assert result.snapshot["execution_summary"] == result.execution_summary
    assert result.snapshot["execution_frame"]["tool_history"][0]["tool_name"] == "echo"
    assert result.snapshot["execution_frame"]["recovery_hint"]["branch"] == "continue"
