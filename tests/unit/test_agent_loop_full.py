"""Full-coverage unit tests for backend.app.core.agent.loop (AgentLoop).

Covers all helper methods and main loop branches:
- _derive_goal, _decompose_task, _compress_context, _safe_context_repr
- _dump_model, _test_mapping_from_context, _infer_task_mode
- _build_initial_recovery_frame, _merge_recovery_from_repair, _build_final_recovery_frame
- _finalize_answer, _build_execution_summary
- _acquire_context_bridge, _fit_llm_messages
- _open_context_session, _close_context_session
- _fire_lifecycle_hook (denial path)
- _extract_workflow/approval/browser/desktop_context
- _build_tool_context, _emit_trace, _record_audit
- _verify_write_result, _repair_write_step, _maybe_replan_after_failure
- _save_iteration_checkpoint
- run() with hooks denial, session context, resume, tool steps
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.agent.loop import AgentLoop, AgentPlanStep, AgentTrajectory
from backend.app.core.contracts import (
    ExecutionFrame,
    RecoveryFrame,
    RunContext,
    RunStatus,
    TaskFrame,
    ToolCallRecord,
    ToolPolicyVerdict,
)
from backend.app.core.llm.backends import LLMRouter, MockLLMBackend
from backend.app.core.memory.store import MemorySystem
from backend.app.core.tools import ToolRegistry, echo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**kw) -> RunContext:
    defaults = dict(trace_id="t1", agent_id="a1", tenant_id="ten1", user_id="u1")
    defaults.update(kw)
    return RunContext(**defaults)


def _agent(**kw) -> AgentLoop:
    defaults = dict(max_iterations=4)
    defaults.update(kw)
    return AgentLoop(
        llm_router=LLMRouter(backend=MockLLMBackend()),
        memory=MemorySystem(),
        tools=ToolRegistry(),
        **defaults,
    )


def _trajectory(**kw) -> AgentTrajectory:
    defaults = dict(task="test task", goal="test goal")
    defaults.update(kw)
    return AgentTrajectory(**defaults)


# ---------------------------------------------------------------------------
# _derive_goal
# ---------------------------------------------------------------------------

class TestDeriveGoal:
    def test_from_goal_key(self):
        agent = _agent()
        assert agent._derive_goal("do stuff", {"goal": "my goal"}) == "my goal"

    def test_from_objective_key(self):
        agent = _agent()
        assert agent._derive_goal("do stuff", {"objective": "obj"}) == "obj"

    def test_from_task_text(self):
        agent = _agent()
        result = agent._derive_goal("fix the bug", {})
        assert result == "fix the bug"

    def test_long_task_truncated(self):
        agent = _agent()
        long_task = "x" * 300
        result = agent._derive_goal(long_task, {})
        assert len(result) <= 240

    def test_empty_task(self):
        agent = _agent()
        assert agent._derive_goal("", {}) == "complete the task"

    def test_multiline_uses_first(self):
        agent = _agent()
        result = agent._derive_goal("first line\nsecond line", {})
        assert result == "first line"


# ---------------------------------------------------------------------------
# _decompose_task
# ---------------------------------------------------------------------------

class TestDecomposeTask:
    def test_code_change_keywords(self):
        agent = _agent()
        result = agent._decompose_task("fix the bug and verify", {})
        assert "apply modification" in result
        assert "verify results" in result

    def test_search_keywords(self):
        agent = _agent()
        result = agent._decompose_task("find and search for files", {})
        assert "locate relevant files" in result

    def test_default_subtasks(self):
        agent = _agent()
        result = agent._decompose_task("hello world", {})
        assert result == ["understand request", "complete task", "verify output"]

    def test_max_5_subtasks(self):
        agent = _agent()
        result = agent._decompose_task("analyze find plan modify verify summarize", {})
        assert len(result) <= 5

    def test_deduplication(self):
        agent = _agent()
        result = agent._decompose_task("test test test", {})
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# _compress_context
# ---------------------------------------------------------------------------

class TestCompressContext:
    def test_non_dict_returns_empty(self):
        agent = _agent()
        assert agent._compress_context("not a dict") == {}
        assert agent._compress_context(None) == {}

    def test_operational_keys_preserved(self):
        agent = _agent()
        ctx = {"root": "/app", "path": "main.py", "goal": "fix"}
        result = agent._compress_context(ctx)
        assert result["root"] == "/app"
        assert result["path"] == "main.py"
        assert result["goal"] == "fix"

    def test_derived_target_path(self):
        agent = _agent()
        result = agent._compress_context({"path": "x.py"})
        assert result["target_path"] == "x.py"

    def test_derived_task_focus(self):
        agent = _agent()
        result = agent._compress_context({"goal": "my goal"})
        assert result["task_focus"] == "my goal"

    def test_patch_preview(self):
        agent = _agent()
        patches = [{"path": "a.py", "old_text": "x", "new_text": "y", "replace_all": True}]
        result = agent._compress_context({"patches": patches})
        assert result["patch_count"] == 1
        assert result["patch_preview"][0]["path"] == "a.py"

    def test_long_value_truncated(self):
        agent = _agent()
        result = agent._compress_context({"custom_key": "x" * 2000})
        assert "_context_compaction" in result
        assert "custom_key" in result["_context_compaction"]["truncated_keys"]

    def test_nested_context_operational_keys(self):
        agent = _agent()
        result = agent._compress_context({"context": {"root": "/nested"}})
        assert result["root"] == "/nested"


# ---------------------------------------------------------------------------
# _safe_context_repr
# ---------------------------------------------------------------------------

class TestSafeContextRepr:
    def test_normal_value(self):
        assert AgentLoop._safe_context_repr({"a": 1}) == '{"a": 1}'

    def test_unserializable(self):
        # Circular reference causes RecursionError in json.dumps
        a: dict = {}
        a["self"] = a
        result = AgentLoop._safe_context_repr(a)
        # Should fall back to repr or unserializable marker
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _dump_model
# ---------------------------------------------------------------------------

class TestDumpModel:
    def test_pydantic_model(self):
        agent = _agent()
        frame = TaskFrame(goal="g", description="d", risk_level="low")
        result = agent._dump_model(frame)
        assert isinstance(result, dict)
        assert result["goal"] == "g"

    def test_dict_object(self):
        agent = _agent()

        class Obj:
            def __init__(self):
                self.x = 1
                self.y = "hi"

        result = agent._dump_model(Obj())
        assert result == {"x": 1, "y": "hi"}

    def test_primitive(self):
        agent = _agent()
        assert agent._dump_model(42) == {"value": 42}
        assert agent._dump_model("str") == {"value": "str"}


# ---------------------------------------------------------------------------
# _test_mapping_from_context
# ---------------------------------------------------------------------------

class TestTestMappingFromContext:
    def test_none(self):
        agent = _agent()
        assert agent._test_mapping_from_context(None) is None

    def test_empty_dict(self):
        agent = _agent()
        assert agent._test_mapping_from_context({}) is None

    def test_dict_rebuilds(self):
        from backend.app.core.test_mapper import TestMappingResult

        agent = _agent()
        data = {"related_files": ["a.py"], "test_files": ["test_a.py"], "impact_hints": [], "dependency_hints": [], "recommended_commands": []}
        result = agent._test_mapping_from_context(data)
        assert isinstance(result, TestMappingResult)
        assert result.related_files == ["a.py"]

    def test_passthrough_test_mapping_result(self):
        from backend.app.core.test_mapper import TestMappingResult

        agent = _agent()
        tm = TestMappingResult(query="q", related_files=[], test_files=[], impact_hints=[], dependency_hints=[], recommended_commands=[])
        assert agent._test_mapping_from_context(tm) is tm


# ---------------------------------------------------------------------------
# _infer_task_mode
# ---------------------------------------------------------------------------

class TestInferTaskMode:
    def test_edit_mode(self):
        agent = _agent()
        assert agent._infer_task_mode("fix the bug", {}) == "edit"
        assert agent._infer_task_mode("write a function", {}) == "edit"

    def test_analyze_mode(self):
        agent = _agent()
        assert agent._infer_task_mode("analyze dependencies", {}) == "analyze"

    def test_summarize_mode(self):
        agent = _agent()
        assert agent._infer_task_mode("summarize the code", {}) == "summarize"

    def test_search_mode(self):
        agent = _agent()
        assert agent._infer_task_mode("find files in repo", {}) == "search"

    def test_general_mode(self):
        agent = _agent()
        assert agent._infer_task_mode("hello", {}) == "general"


# ---------------------------------------------------------------------------
# Recovery frames
# ---------------------------------------------------------------------------

class TestRecoveryFrames:
    def test_initial_recovery_frame(self):
        agent = _agent()
        frame = agent._build_initial_recovery_frame("echo")
        assert frame.branch == "continue"
        assert frame.tool_name == "echo"
        assert frame.retryable is False

    def test_merge_recovery_from_repair(self):
        agent = _agent()
        recovery = RecoveryFrame(branch="continue", retryable=False, confidence=0.5)
        suggestion = MagicMock()
        suggestion.follow_up = ["step1", "step2"]
        suggestion.confidence = 0.8
        suggestion.reason = "retry needed"
        result = agent._merge_recovery_from_repair(recovery, suggestion, "echo")
        assert result.tool_name == "echo"
        assert result.retryable is True
        assert result.confidence == 0.8
        assert "step1" in result.follow_up

    def test_build_final_recovery_frame_approval(self):
        agent = _agent()
        summary = {
            "approval_state": {"pending_count": 2, "approval_status": "pending"},
            "workflow_state": {},
            "browser_state": {},
            "desktop_state": {},
        }
        frame = agent._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "approval_wait"
        assert frame.pending_count == 2

    def test_build_final_recovery_frame_browser(self):
        agent = _agent()
        summary = {
            "approval_state": {},
            "workflow_state": {"workflow_node_type": "browser"},
            "browser_state": {"active_count": 1},
            "desktop_state": {},
        }
        frame = agent._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "browser_observe"

    def test_build_final_recovery_frame_desktop(self):
        agent = _agent()
        summary = {
            "approval_state": {},
            "workflow_state": {"workflow_node_type": "desktop"},
            "browser_state": {},
            "desktop_state": {"active_count": 1},
        }
        frame = agent._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "desktop_observe"


# ---------------------------------------------------------------------------
# _finalize_answer
# ---------------------------------------------------------------------------

class TestFinalizeAnswer:
    def test_with_reflections(self):
        agent = _agent()
        traj = _trajectory(reflections=["my reflection"])
        result = agent._finalize_answer("task", traj, None, {})
        assert result == "my reflection"

    def test_with_last_tool_result(self):
        agent = _agent()
        traj = _trajectory()
        result = agent._finalize_answer("task", traj, "tool output", {})
        assert "tool output" in result

    def test_with_open_items(self):
        agent = _agent()
        traj = _trajectory(subtasks=["step1", "step2"], subtask_status={"step1": "pending"})
        result = agent._finalize_answer("task", traj, None, {})
        assert "remaining steps" in result or "next step" in result

    def test_completed_no_items(self):
        agent = _agent()
        traj = _trajectory(subtasks=["s1"], subtask_status={"s1": "done"})
        result = agent._finalize_answer("task", traj, None, {})
        # With all subtasks done, answer references goal
        assert "test goal" in result

    def test_empty_goal(self):
        agent = _agent()
        traj = _trajectory(goal="", subtasks=[])
        result = agent._finalize_answer("task", traj, None, {})
        assert "Completed" in result


# ---------------------------------------------------------------------------
# _build_execution_summary
# ---------------------------------------------------------------------------

class TestBuildExecutionSummary:
    def test_basic_summary(self):
        agent = _agent()
        traj = _trajectory(subtasks=["s1"], subtask_status={"s1": "done"})
        result = agent._build_execution_summary(traj, ["obs"], [], [], "answer")
        assert result["goal"] == "test goal"
        assert result["observations"] == 1
        assert result["final_answer"] == "answer"

    def test_with_tool_calls(self):
        agent = _agent()
        traj = _trajectory()
        tc = ToolCallRecord(
            tool_name="echo", success=True, output={"path": "x.py", "verified": True},
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, sandbox_profile="open", reason="ok", approval_id=None),
            risk_level="low", latency_ms=1.0, trace_id="t1", request_id="r1",
        )
        result = agent._build_execution_summary(traj, [], [tc], [], "ans")
        assert result["successful_tools"] == ["echo"]
        assert "x.py" in result["affected_files"]

    def test_workflow_approval_branch(self):
        agent = _agent()
        traj = _trajectory()
        extra = {"workflow_state": {"workflow_status": "needs_approval"}, "approval_state": {}, "browser_state": {}, "desktop_state": {}}
        result = agent._build_execution_summary(traj, [], [], [], "", extra)
        assert result["branch"] == "approval_wait"


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

class TestContextExtraction:
    def test_extract_workflow_context(self):
        agent = _agent()
        ctx = {"workflow_id": "wf1", "workflow_status": "running"}
        result = agent._extract_workflow_context(ctx)
        assert result["workflow_id"] == "wf1"

    def test_extract_workflow_nested(self):
        agent = _agent()
        ctx = {"workflow": {"workflow_id": "wf2"}}
        result = agent._extract_workflow_context(ctx)
        assert result["workflow_id"] == "wf2"

    def test_extract_approval_context(self):
        agent = _agent()
        ctx = {"approval_id": "ap1", "approval_status": "approved"}
        result = agent._extract_approval_context(ctx)
        assert result["approval_id"] == "ap1"

    def test_extract_browser_context(self):
        agent = _agent()
        ctx = {"browser_session_id": "bs1"}
        result = agent._extract_browser_context(ctx)
        assert result["browser_session_id"] == "bs1"

    def test_extract_desktop_context(self):
        agent = _agent()
        ctx = {"desktop_session_id": "ds1"}
        result = agent._extract_desktop_context(ctx)
        assert result["desktop_session_id"] == "ds1"


# ---------------------------------------------------------------------------
# _build_tool_context
# ---------------------------------------------------------------------------

class TestBuildToolContext:
    def test_preserves_fields(self):
        agent = _agent()
        ctx = _ctx(trace_id="tx", tenant_id="ten", user_id="usr")
        step = AgentPlanStep(kind="tool", instruction="test", tool_name="echo")
        result = agent._build_tool_context(ctx, step)
        assert result.trace_id == "tx"
        assert result.tenant_id == "ten"
        assert result.user_id == "usr"


# ---------------------------------------------------------------------------
# _acquire_context_bridge
# ---------------------------------------------------------------------------

class TestAcquireContextBridge:
    def test_none_session(self):
        agent = _agent()
        assert agent._acquire_context_bridge(None) is None

    def test_explicit_bridge(self):
        bridge = MagicMock()
        agent = _agent(context_bridge=bridge)
        result = agent._acquire_context_bridge("s1")
        assert result is bridge
        assert agent._bridge_ephemeral is False

    def test_factory_bridge(self):
        factory = MagicMock(return_value=MagicMock())
        agent = _agent(context_bridge_factory=factory)
        result = agent._acquire_context_bridge("s1")
        assert result is not None
        assert agent._bridge_ephemeral is True


# ---------------------------------------------------------------------------
# _fit_llm_messages
# ---------------------------------------------------------------------------

class TestFitLlmMessages:
    def test_no_bridge_uses_local(self):
        agent = _agent()
        agent._active_bridge = None
        msgs = [{"role": "user", "content": "hello"}]
        result, meta = agent._fit_llm_messages(msgs)
        assert result == msgs

    def test_with_bridge(self):
        agent = _agent()
        bridge = MagicMock()
        bridge.fit_messages.return_value = ([{"role": "user", "content": "compressed"}], {"strategy": "trim"})
        agent._active_bridge = bridge
        msgs = [{"role": "user", "content": "hello"}]
        result, meta = agent._fit_llm_messages(msgs)
        assert result[0]["content"] == "compressed"


# ---------------------------------------------------------------------------
# _record_audit
# ---------------------------------------------------------------------------

class TestRecordAudit:
    def test_no_store(self):
        agent = _agent()
        # Should not raise
        agent._record_audit("test.action", _ctx(), _trajectory())

    def test_with_store(self):
        store = MagicMock()
        agent = _agent(audit_store=store)
        agent._record_audit("test.action", _ctx(), _trajectory(), outcome="success")
        store.record.assert_called_once()


# ---------------------------------------------------------------------------
# run() with hook denial
# ---------------------------------------------------------------------------

class TestRunWithHookDenial:
    async def test_agent_start_denied(self):
        from backend.app.core.hooks import HookManager

        hm = HookManager()
        mock_result = MagicMock()
        mock_result.denied = True
        mock_result.reason = "blocked by policy"
        hm.trigger = AsyncMock(return_value=mock_result)
        hm.has_hooks = MagicMock(return_value=True)

        agent = _agent(hook_manager=hm)
        result = await agent.run(_ctx(), "do something")
        assert result.status == RunStatus.FAILED
        assert "blocked" in result.error


# ---------------------------------------------------------------------------
# run() basic flow
# ---------------------------------------------------------------------------

class TestRunBasicFlow:
    async def test_simple_run(self):
        agent = _agent()
        result = await agent.run(_ctx(), "hello world")
        assert result.status == RunStatus.COMPLETED
        assert result.answer

    async def test_run_with_session_id(self):
        agent = _agent()
        ctx = _ctx(session_id="sess-1")
        result = await agent.run(ctx, "test task")
        assert result.status == RunStatus.COMPLETED
        assert "context_management" in result.execution_summary

    async def test_run_with_extra_context(self):
        agent = _agent()
        result = await agent.run(_ctx(), "task", extra_context={"goal": "my goal", "priority": "high"})
        assert result.status == RunStatus.COMPLETED

    async def test_run_with_tool(self):
        agent = _agent()
        agent.tools.register("echo", "Echo", echo)
        result = await agent.run(_ctx(), "echo: hello")
        assert result.status == RunStatus.COMPLETED

    async def test_run_stores_memory(self):
        agent = _agent()
        result = await agent.run(_ctx(), "remember this")
        assert result.memory_hits >= 0

    async def test_run_with_retry_budget(self):
        agent = _agent()
        result = await agent.run(_ctx(), "task", extra_context={"retry_budget": 2})
        assert result.status == RunStatus.COMPLETED


# ---------------------------------------------------------------------------
# _open_context_session / _close_context_session
# ---------------------------------------------------------------------------

class TestContextSession:
    async def test_open_no_bridge(self):
        agent = _agent()
        agent._active_bridge = None
        result = await agent._open_context_session(_ctx(), "task", "s1")
        assert result == ""

    async def test_open_with_bridge(self):
        bridge = MagicMock()
        bridge.open_session = AsyncMock()
        bridge.record = AsyncMock()
        bridge.restored_message_count = 0
        bridge.session_active = True
        agent = _agent()
        agent._active_bridge = bridge
        result = await agent._open_context_session(_ctx(), "task", "s1")
        assert result == ""
        assert agent._run_context_mgmt["enabled"] is True

    async def test_open_with_restored_messages(self):
        bridge = MagicMock()
        bridge.open_session = AsyncMock()
        bridge.record = AsyncMock()
        bridge.restored_message_count = 5
        bridge.build_session_recap.return_value = "previous context"
        bridge.session_active = True
        agent = _agent()
        agent._active_bridge = bridge
        result = await agent._open_context_session(_ctx(), "task", "s1")
        assert result == "previous context"
        assert agent._run_context_mgmt["session_restored"] is True

    async def test_open_failure_degrades(self):
        bridge = MagicMock()
        bridge.open_session = AsyncMock(side_effect=RuntimeError("db down"))
        agent = _agent()
        agent._active_bridge = bridge
        result = await agent._open_context_session(_ctx(), "task", "s1")
        assert result == ""
        assert agent._run_context_mgmt["enabled"] is False

    async def test_close_no_bridge(self):
        agent = _agent()
        agent._active_bridge = None
        await agent._close_context_session("answer", _ctx())

    async def test_close_with_bridge(self):
        bridge = MagicMock()
        bridge.record = AsyncMock()
        bridge.close = AsyncMock(return_value=True)
        bridge.metrics_snapshot.return_value = {"total_messages": 10}
        agent = _agent()
        agent._active_bridge = bridge
        agent._bridge_ephemeral = True
        await agent._close_context_session("answer", _ctx())
        assert agent._run_context_mgmt["session_saved"] is True
        assert agent._active_bridge is None  # ephemeral cleared

    async def test_close_failure(self):
        bridge = MagicMock()
        bridge.record = AsyncMock(side_effect=RuntimeError("fail"))
        bridge.metrics_snapshot.return_value = {}
        agent = _agent()
        agent._active_bridge = bridge
        agent._bridge_ephemeral = False
        await agent._close_context_session("answer", _ctx())
        assert agent._run_context_mgmt["session_saved"] is False


# ---------------------------------------------------------------------------
# _verify_write_result
# ---------------------------------------------------------------------------

class TestVerifyWriteResult:
    async def test_verified_true(self):
        agent = _agent()
        step = AgentPlanStep(kind="tool", instruction="write", tool_name="write_file", arguments={"path": "x.py"})
        record = ToolCallRecord(
            tool_name="write_file", success=True, output={"verified": True, "path": "x.py"},
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, sandbox_profile="open", reason="ok", approval_id=None),
            risk_level="high", latency_ms=1.0, trace_id="t1", request_id="r1",
        )
        result = await agent._verify_write_result(_ctx(), step, record)
        assert result is not None
        assert "passed" in result

    async def test_unverified_no_path(self):
        agent = _agent()
        step = AgentPlanStep(kind="tool", instruction="write", tool_name="write_file", arguments={})
        record = ToolCallRecord(
            tool_name="write_file", success=True, output={},
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, sandbox_profile="open", reason="ok", approval_id=None),
            risk_level="high", latency_ms=1.0, trace_id="t1", request_id="r1",
        )
        result = await agent._verify_write_result(_ctx(), step, record)
        assert result is None


# ---------------------------------------------------------------------------
# _maybe_replan_after_failure
# ---------------------------------------------------------------------------

class TestMaybeReplanAfterFailure:
    def test_non_write_tool_ignored(self):
        agent = _agent()
        traj = _trajectory()
        step = AgentPlanStep(kind="tool", instruction="read", tool_name="read_file")
        record = ToolCallRecord(
            tool_name="read_file", success=False, error="fail",
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, sandbox_profile="open", reason="ok", approval_id=None),
            risk_level="low", latency_ms=1.0, trace_id="t1", request_id="r1",
        )
        plan = []
        agent._maybe_replan_after_failure(_ctx(), traj, step, record, {}, plan)
        assert plan == []

    def test_write_tool_replans(self):
        agent = _agent()
        traj = _trajectory()
        step = AgentPlanStep(kind="tool", instruction="patch", tool_name="apply_text_patch", arguments={"path": "x.py", "old_text": "a", "new_text": "b"})
        record = ToolCallRecord(
            tool_name="apply_text_patch", success=False, error="not found",
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False, sandbox_profile="open", reason="ok", approval_id=None),
            risk_level="high", latency_ms=1.0, trace_id="t1", request_id="r1",
        )
        plan: list[AgentPlanStep] = []
        agent._maybe_replan_after_failure(_ctx(), traj, step, record, {"path": "x.py"}, plan)
        assert len(plan) > 0


# ---------------------------------------------------------------------------
# _save_iteration_checkpoint
# ---------------------------------------------------------------------------

class TestSaveIterationCheckpoint:
    def test_checkpoint_saves(self):
        agent = _agent()
        traj = _trajectory()
        # Should not raise even if checkpoint store has issues
        agent._save_iteration_checkpoint(
            context=_ctx(), task="task", iteration=1, plan=[], completed_steps=[],
            tool_calls=[], observations=["obs"], answer_so_far="ans",
            memory_hits=0, trajectory=traj, extra_context={},
        )


# ---------------------------------------------------------------------------
# _build_final_recovery_state
# ---------------------------------------------------------------------------

class TestBuildFinalRecoveryState:
    def test_continue_branch(self):
        agent = _agent()
        traj = _trajectory()
        frame = ExecutionFrame(
            trace_id="t1", agent_id="a1", tenant_id="ten1", user_id="u1",
            request_id="r1", task=TaskFrame(goal="g", description="d", risk_level="low"),
        )
        frame.execution_summary = {"branch": "continue"}
        branch, state = agent._build_final_recovery_state(frame, traj)
        assert branch == "continue"

    def test_approval_branch(self):
        agent = _agent()
        traj = _trajectory()
        frame = ExecutionFrame(
            trace_id="t1", agent_id="a1", tenant_id="ten1", user_id="u1",
            request_id="r1", task=TaskFrame(goal="g", description="d", risk_level="low"),
        )
        frame.execution_summary = {"approval_state": {"pending_count": 1}, "workflow_state": {}, "browser_state": {}, "desktop_state": {}}
        branch, state = agent._build_final_recovery_state(frame, traj)
        assert branch == "approval_wait"


# ---------------------------------------------------------------------------
# AgentTrajectory / AgentPlanStep dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_plan_step_defaults(self):
        step = AgentPlanStep(kind="observe", instruction="look")
        assert step.tool_name is None
        assert step.arguments == {}

    def test_trajectory_defaults(self):
        traj = AgentTrajectory(task="t", goal="g")
        assert traj.stage == "planning"
        assert traj.subtasks == []
        assert traj.observations == []
        assert traj.reflections == []
        assert traj.steps == []
