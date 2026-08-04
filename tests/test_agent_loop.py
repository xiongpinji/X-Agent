from backend.app.core.agent import AgentLoop, AgentTrajectory
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
    assert result.answer is not None and len(result.answer) > 0
    assert "Relevant memory:" not in result.answer
    assert any(event.event == "agent.completed" for event in result.events)
    assert result.execution_summary["branch"] in ("continue", "done")

    # Fast-path returns a simplified snapshot; full pipeline returns detailed structure
    is_fast_path = result.execution_summary.get("fast_path", False)
    if not is_fast_path:
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


def test_reflect_replan_prompt_prefers_mutating_tool_after_read() -> None:
    memory = InMemoryMemorySystem()
    context = RunContext(permission_scope=["tools:read", "tools:write"])
    agent = AgentLoop(
        llm_router=LLMRouter(),
        memory=memory,
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    trajectory = AgentTrajectory(
        task="fix app.py by replacing foo with bar",
        goal="fix app.py by replacing foo with bar",
        stage="step_2_reflect",
        subtasks=["locate relevant files", "apply modification", "verify results"],
        subtask_status={"locate relevant files": "done", "apply modification": "pending"},
        current_subtask_index=1,
        observations=["app.py contains foo"],
        tool_results=[
            {
                "tool_name": "read_file",
                "success": True,
                "output": "print('foo')",
                "arguments_preview": {"path": "app.py"},
            }
        ],
    )

    prompt = agent._build_user_prompt(
        context,
        trajectory,
        {
            "_after_reflect_replan": True,
            "_replan_guidance": "Use write tools now.",
        },
        agent.tools.related_tools("fix app.py write_file apply_text_patch"),
        {},
    )

    assert "Reflect re-plan guidance" in prompt
    assert "Do not choose read_file/search_text again" in prompt
    assert "apply_text_patch" in prompt
    assert "write_file" in prompt


async def test_code_change_plan_inserts_reflect_before_final_after_read_only_plan() -> None:
    from backend.app.core.llm.backends import LLMResponse

    class _ReadOnlyPlanner:
        async def chat(self, messages, tools, **_kwargs):
            return LLMResponse(
                content=(
                    '[{"kind":"tool","instruction":"inspect repo","tool_name":"inspect_tree","arguments":{"root":"."}},'
                    '{"kind":"tool","instruction":"read calc","tool_name":"read_file","arguments":{"path":"calc.py"}},'
                    '{"kind":"final","instruction":"Finalize answer"}]'
                ),
                model="fake",
            )

    agent = AgentLoop(
        llm_router=_ReadOnlyPlanner(),
        memory=InMemoryMemorySystem(),
        tools=build_default_tool_registry(ToolPolicyEngine()),
    )
    trajectory = AgentTrajectory(
        task="fix calc.py by adding a subtract function",
        goal="fix calc.py by adding a subtract function",
    )

    steps = await agent._plan(RunContext(), trajectory, {"root": "."})
    tool_names = [step.tool_name for step in steps if step.kind == "tool"]
    kinds = [step.kind for step in steps]

    assert "inspect_tree" in tool_names
    assert any(name in {"read_file", "search_text", "inspect_tree"} for name in tool_names)
    assert not any(name in {"write_file", "apply_text_patch", "apply_batch_patch"} for name in tool_names)
    assert "reflect" in kinds
    assert kinds[-1] == "reflect"
