"""Deep coverage tests for backend/app/core/agent/loop.py — all helper methods."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from backend.app.core.agent.loop import AgentLoop, AgentPlanStep, AgentTrajectory
from backend.app.core.contracts import RecoveryFrame, RunContext, RunStatus, TaskFrame


def _make_loop(**overrides):
    """Create an AgentLoop with all dependencies mocked."""
    defaults = dict(
        llm_router=MagicMock(),
        memory=MagicMock(),
        tools=MagicMock(),
        max_iterations=4,
        tracer=MagicMock(),
        run_store=None,
        browser_store=None,
        desktop_store=None,
        audit_store=None,
        orchestrator=MagicMock(),
        verification_engine=MagicMock(),
        repair_loop=MagicMock(),
        hook_manager=MagicMock(),
        approval_store=None,
        context_bridge=None,
        context_bridge_factory=None,
        context_token_budget=24000,
    )
    defaults.update(overrides)
    return AgentLoop(**defaults)


def _ctx(**kw):
    defaults = dict(tenant_id="t1", user_id="u1", agent_id="a1", trace_id="tr1")
    defaults.update(kw)
    return RunContext(**defaults)


def _traj(task="fix bug", goal="fix bug", **kw):
    return AgentTrajectory(task=task, goal=goal, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
# _derive_goal
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeriveGoal:
    def test_goal_from_extra_context(self):
        loop = _make_loop()
        assert loop._derive_goal("task", {"goal": "my goal"}) == "my goal"

    def test_objective_from_extra_context(self):
        loop = _make_loop()
        assert loop._derive_goal("task", {"objective": "obj"}) == "obj"

    def test_goal_takes_priority_over_objective(self):
        loop = _make_loop()
        assert loop._derive_goal("task", {"goal": "g", "objective": "o"}) == "g"

    def test_task_first_line(self):
        loop = _make_loop()
        assert loop._derive_goal("first line\nsecond", {}) == "first line"

    def test_truncation_240(self):
        loop = _make_loop()
        long_task = "x" * 300
        result = loop._derive_goal(long_task, {})
        assert len(result) == 240

    def test_keyword_match_returns_text(self):
        loop = _make_loop()
        assert loop._derive_goal("fix the bug", {}) == "fix the bug"

    def test_empty_task_returns_default(self):
        loop = _make_loop()
        assert loop._derive_goal("", {}) == "complete the task"

    def test_whitespace_only_task(self):
        loop = _make_loop()
        assert loop._derive_goal("   ", {}) == "complete the task"


# ═══════════════════════════════════════════════════════════════════════════════
# _decompose_task
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecomposeTask:
    def test_analyze_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("analyze the code", {})
        assert "understand request" in result

    def test_find_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("find the file", {})
        assert "locate relevant files" in result

    def test_plan_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("plan the design", {})
        assert "draft implementation plan" in result

    def test_modify_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("fix the bug and update code", {})
        assert "apply modification" in result

    def test_verify_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("verify the test", {})
        assert "verify results" in result

    def test_summary_keywords(self):
        loop = _make_loop()
        result = loop._decompose_task("summarize the report", {})
        assert "summarize completion" in result

    def test_default_subtasks(self):
        loop = _make_loop()
        result = loop._decompose_task("hello world", {})
        assert result == ["understand request", "complete task", "verify output"]

    def test_max_5_subtasks(self):
        loop = _make_loop()
        result = loop._decompose_task("analyze find plan fix verify summarize", {})
        assert len(result) <= 5

    def test_deduplication(self):
        loop = _make_loop()
        result = loop._decompose_task("analyze analyze analyze", {})
        assert result.count("understand request") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _compress_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompressContext:
    def test_non_dict_returns_empty(self):
        loop = _make_loop()
        assert loop._compress_context("not a dict") == {}

    def test_operational_keys_preserved(self):
        loop = _make_loop()
        ctx = {"root": "/app", "path": "file.py", "goal": "fix"}
        result = loop._compress_context(ctx)
        assert result["root"] == "/app"
        assert result["path"] == "file.py"
        assert result["goal"] == "fix"

    def test_non_operational_keys_within_budget(self):
        loop = _make_loop()
        ctx = {"custom_key": "short value"}
        result = loop._compress_context(ctx)
        assert result["custom_key"] == "short value"

    def test_long_string_truncated(self):
        loop = _make_loop()
        ctx = {"big_field": "x" * 2000}
        result = loop._compress_context(ctx)
        assert "truncated" in str(result.get("big_field", ""))
        assert "_context_compaction" in result

    def test_derived_target_path(self):
        loop = _make_loop()
        ctx = {"path": "src/main.py"}
        result = loop._compress_context(ctx)
        assert result["target_path"] == "src/main.py"

    def test_derived_task_focus(self):
        loop = _make_loop()
        ctx = {"goal": "implement feature"}
        result = loop._compress_context(ctx)
        assert result["task_focus"] == "implement feature"

    def test_derived_patch_preview(self):
        loop = _make_loop()
        ctx = {"patches": [{"path": "a.py", "old_text": "x", "new_text": "y"}]}
        result = loop._compress_context(ctx)
        assert result["patch_count"] == 1
        assert result["patch_preview"][0]["path"] == "a.py"

    def test_nested_context_operational_keys(self):
        loop = _make_loop()
        ctx = {"context": {"root": "/nested"}}
        result = loop._compress_context(ctx)
        assert result["root"] == "/nested"

    def test_no_compaction_meta_when_no_truncation(self):
        loop = _make_loop()
        ctx = {"root": "/app"}
        result = loop._compress_context(ctx)
        assert "_context_compaction" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _safe_context_repr
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafeContextRepr:
    def test_normal_value(self):
        assert AgentLoop._safe_context_repr({"a": 1}) == '{"a": 1}'

    def test_unserializable_falls_back_to_repr(self):
        class Bad:
            def __repr__(self):
                return "<Bad>"
        result = AgentLoop._safe_context_repr(Bad())
        assert "Bad" in result

    def test_circular_reference(self):
        d = {}
        d["self"] = d
        result = AgentLoop._safe_context_repr(d)
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# _dump_model
# ═══════════════════════════════════════════════════════════════════════════════

class TestDumpModel:
    def test_pydantic_model(self):
        loop = _make_loop()
        obj = MagicMock()
        obj.model_dump = MagicMock(return_value={"key": "val"})
        assert loop._dump_model(obj) == {"key": "val"}

    def test_model_dump_returns_non_dict(self):
        loop = _make_loop()
        obj = MagicMock()
        obj.model_dump = MagicMock(return_value="scalar")
        assert loop._dump_model(obj) == {"value": "scalar"}

    def test_dict_object(self):
        loop = _make_loop()
        class Obj:
            def __init__(self):
                self.x = 1
        result = loop._dump_model(Obj())
        assert result == {"x": 1}

    def test_plain_value(self):
        loop = _make_loop()
        assert loop._dump_model(42) == {"value": 42}


# ═══════════════════════════════════════════════════════════════════════════════
# _test_mapping_from_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestTestMappingFromContext:
    def test_already_test_mapping_result(self):
        from backend.app.core.test_mapper import TestMappingResult
        loop = _make_loop()
        tmr = TestMappingResult(query="q")
        assert loop._test_mapping_from_context(tmr) is tmr

    def test_none_returns_none(self):
        loop = _make_loop()
        assert loop._test_mapping_from_context(None) is None

    def test_empty_dict_returns_none(self):
        loop = _make_loop()
        assert loop._test_mapping_from_context({}) is None

    def test_dict_rebuilds(self):
        loop = _make_loop()
        result = loop._test_mapping_from_context({
            "query": "test",
            "related_files": ["a.py"],
            "test_files": ["test_a.py"],
            "impact_hints": ["hint"],
            "dependency_hints": ["dep"],
            "recommended_commands": ["pytest"],
        })
        assert result.query == "test"
        assert result.related_files == ["a.py"]
        assert result.recommended_commands == ["pytest"]


# ═══════════════════════════════════════════════════════════════════════════════
# _build_initial_recovery_frame / _merge_recovery_from_repair
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecoveryFrames:
    def test_initial_recovery_frame(self):
        loop = _make_loop()
        frame = loop._build_initial_recovery_frame("my_tool")
        assert frame.branch == "continue"
        assert frame.tool_name == "my_tool"
        assert frame.retryable is False

    def test_initial_recovery_frame_no_tool(self):
        loop = _make_loop()
        frame = loop._build_initial_recovery_frame()
        assert frame.tool_name is None

    def test_merge_recovery_from_repair(self):
        loop = _make_loop()
        recovery = loop._build_initial_recovery_frame()
        suggestion = MagicMock()
        suggestion.follow_up = ["step1", "step2"]
        suggestion.confidence = 0.8
        suggestion.reason = "retry needed"
        result = loop._merge_recovery_from_repair(recovery, suggestion, "retry_tool")
        assert result.tool_name == "retry_tool"
        assert result.retryable is True
        assert result.confidence == 0.8
        assert "step1" in result.follow_up
        assert result.status_detail == "retry scheduled for retry_tool"

    def test_merge_recovery_confidence_max(self):
        loop = _make_loop()
        recovery = loop._build_initial_recovery_frame()
        recovery.confidence = 0.9
        suggestion = MagicMock()
        suggestion.follow_up = []
        suggestion.confidence = 0.3
        suggestion.reason = None
        result = loop._merge_recovery_from_repair(recovery, suggestion, "t")
        assert result.confidence == 0.9


# ═══════════════════════════════════════════════════════════════════════════════
# _build_final_recovery_frame
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildFinalRecoveryFrame:
    def test_basic_continue(self):
        loop = _make_loop()
        summary = {"status": "ok"}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "continue"

    def test_workflow_needs_approval(self):
        loop = _make_loop()
        summary = {"workflow_state": {"workflow_status": "needs_approval"}}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "approval_wait"

    def test_approval_pending_count(self):
        loop = _make_loop()
        summary = {"approval_state": {"pending_count": 2}}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "approval_wait"
        assert frame.pending_count == 2

    def test_browser_observe(self):
        loop = _make_loop()
        summary = {"browser_state": {"active_count": 1}}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "browser_observe"

    def test_desktop_observe(self):
        loop = _make_loop()
        summary = {"desktop_state": {"active_count": 1}}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "desktop_observe"

    def test_workflow_node_type_browser(self):
        loop = _make_loop()
        summary = {"workflow_state": {"workflow_node_type": "browser"}}
        frame = loop._build_final_recovery_frame(summary, "continue")
        assert frame.branch == "browser_observe"

    def test_empty_dict_summary(self):
        loop = _make_loop()
        frame = loop._build_final_recovery_frame({}, "continue")
        assert frame.branch == "continue"
        assert frame.retryable is False


# ═══════════════════════════════════════════════════════════════════════════════
# _acquire_context_bridge
# ═══════════════════════════════════════════════════════════════════════════════

class TestAcquireContextBridge:
    def test_no_session_id_returns_none(self):
        loop = _make_loop()
        assert loop._acquire_context_bridge(None) is None

    def test_explicit_bridge(self):
        bridge = MagicMock()
        loop = _make_loop(context_bridge=bridge)
        result = loop._acquire_context_bridge("s1")
        assert result is bridge
        assert loop._bridge_ephemeral is False

    def test_factory_bridge(self):
        factory = MagicMock(return_value=MagicMock())
        loop = _make_loop(context_bridge_factory=factory)
        result = loop._acquire_context_bridge("s1")
        factory.assert_called_once()
        assert loop._bridge_ephemeral is True

    @patch("backend.app.core.agent.loop.AgentLoopContextBridge")
    def test_default_bridge(self, mock_bridge_cls):
        mock_bridge_cls.create_default.return_value = MagicMock()
        loop = _make_loop()
        result = loop._acquire_context_bridge("s1")
        assert result is not None
        assert loop._bridge_ephemeral is True


# ═══════════════════════════════════════════════════════════════════════════════
# _fit_llm_messages
# ═══════════════════════════════════════════════════════════════════════════════

class TestFitLlmMessages:
    def test_with_active_bridge(self):
        loop = _make_loop()
        bridge = MagicMock()
        bridge.fit_messages.return_value = ([{"role": "user", "content": "hi"}], {"compressed": True})
        loop._active_bridge = bridge
        msgs = [{"role": "user", "content": "hello"}]
        result, meta = loop._fit_llm_messages(msgs)
        bridge.fit_messages.assert_called_once_with(msgs)
        assert meta == {"compressed": True}

    @patch("backend.app.core.agent.loop.fit_messages_to_token_budget")
    def test_without_active_bridge(self, mock_fit):
        mock_fit.return_value = ([{"role": "user", "content": "hi"}], None)
        loop = _make_loop()
        loop._active_bridge = None
        msgs = [{"role": "user", "content": "hello"}]
        result, meta = loop._fit_llm_messages(msgs)
        mock_fit.assert_called_once()
        assert meta is None


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_*_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractContexts:
    def test_extract_workflow_context_flat(self):
        loop = _make_loop()
        ctx = {"workflow_id": "w1", "workflow_status": "running"}
        result = loop._extract_workflow_context(ctx)
        assert result["workflow_id"] == "w1"

    def test_extract_workflow_context_nested(self):
        loop = _make_loop()
        ctx = {"workflow": {"workflow_id": "w2", "workflow_name": "wf"}}
        result = loop._extract_workflow_context(ctx)
        assert result["workflow_id"] == "w2"

    def test_extract_approval_context_flat(self):
        loop = _make_loop()
        ctx = {"approval_id": "ap1", "approval_status": "pending"}
        result = loop._extract_approval_context(ctx)
        assert result["approval_id"] == "ap1"

    def test_extract_approval_context_with_store(self):
        store = MagicMock()
        store.pending_count.return_value = 3
        store.count.return_value = 5
        store.list.return_value = []
        loop = _make_loop(approval_store=store)
        result = loop._extract_approval_context({})
        assert result["pending_count"] == 3

    def test_extract_browser_context_flat(self):
        loop = _make_loop()
        ctx = {"browser_session_id": "bs1"}
        result = loop._extract_browser_context(ctx)
        assert result["browser_session_id"] == "bs1"

    def test_extract_browser_context_with_store(self):
        store = MagicMock()
        session = MagicMock()
        session.active = True
        session.model_dump.return_value = {"id": "s1"}
        store.list_sessions.return_value = [session]
        loop = _make_loop(browser_store=store)
        result = loop._extract_browser_context({})
        assert result["session_count"] == 1
        assert result["active_count"] == 1

    def test_extract_desktop_context_flat(self):
        loop = _make_loop()
        ctx = {"desktop_session_id": "ds1"}
        result = loop._extract_desktop_context(ctx)
        assert result["desktop_session_id"] == "ds1"

    def test_extract_desktop_context_with_store(self):
        store = MagicMock()
        session = MagicMock()
        session.active = False
        session.provider = "pyautogui"
        session.model_dump.return_value = {"id": "d1"}
        store.list_sessions.return_value = [session]
        loop = _make_loop(desktop_store=store)
        result = loop._extract_desktop_context({})
        assert result["session_count"] == 1
        assert result["active_count"] == 0
        assert "pyautogui" in result["providers"]


# ═══════════════════════════════════════════════════════════════════════════════
# _infer_task_mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestInferTaskMode:
    def test_edit_mode(self):
        loop = _make_loop()
        assert loop._infer_task_mode("fix the bug", {}) == "edit"

    def test_analyze_mode(self):
        loop = _make_loop()
        assert loop._infer_task_mode("analyze the impact", {}) == "analyze"

    def test_summarize_mode(self):
        loop = _make_loop()
        assert loop._infer_task_mode("summarize the code", {}) == "summarize"

    def test_search_mode(self):
        loop = _make_loop()
        assert loop._infer_task_mode("find the file", {}) == "search"

    def test_general_mode(self):
        loop = _make_loop()
        assert loop._infer_task_mode("hello", {}) == "general"

    def test_extra_context_influences(self):
        loop = _make_loop()
        assert loop._infer_task_mode("hello", {"action": "edit"}) == "edit"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_task_profile
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildTaskProfile:
    def test_code_change_intent(self):
        loop = _make_loop()
        traj = _traj(task="fix the bug", goal="fix bug")
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["intent"] == "code_change"
        assert profile["mode"] == "edit"

    def test_analysis_intent(self):
        loop = _make_loop()
        traj = _traj(task="analyze the code", goal="understand")
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["intent"] == "analysis"

    def test_urgency_high(self):
        loop = _make_loop()
        traj = _traj(task="urgent fix now", goal="fix")
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["urgency"] == 0.7

    def test_urgency_low(self):
        loop = _make_loop()
        traj = _traj(task="fix the bug", goal="fix")
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["urgency"] == 0.4

    def test_complexity_increases_with_subtasks(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a", "b", "c"])
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["complexity"] > 0.25

    def test_constraints_from_extra_context(self):
        loop = _make_loop()
        traj = _traj()
        profile = loop._build_task_profile(traj, {"root": "/app", "path": "f.py"}, {})
        assert any(c.get("root") == "/app" for c in profile["constraints"])

    def test_next_action(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1", "step2"], current_subtask_index=1)
        profile = loop._build_task_profile(traj, {}, {})
        assert profile["next_action"] == "step2"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_tool_profile
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildToolProfile:
    def test_preferred_tool_from_related(self):
        loop = _make_loop()
        profile = loop._build_tool_profile(
            {"intent": "code_change", "mode": "edit", "urgency": 0.4, "complexity": 0.5},
            [{"name": "apply_text_patch"}, {"name": "read_file"}],
        )
        assert profile["preferred_tool"] == "apply_text_patch"

    def test_confidence_increases_with_intent(self):
        loop = _make_loop()
        p1 = loop._build_tool_profile({"intent": "general", "mode": "general", "urgency": 0.4, "complexity": 0.5}, [])
        p2 = loop._build_tool_profile({"intent": "code_change", "mode": "edit", "urgency": 0.4, "complexity": 0.5}, [])
        assert p2["confidence"] > p1["confidence"]

    def test_urgency_boosts_confidence(self):
        loop = _make_loop()
        p1 = loop._build_tool_profile({"intent": "code_change", "mode": "edit", "urgency": 0.4, "complexity": 0.5}, [])
        p2 = loop._build_tool_profile({"intent": "code_change", "mode": "edit", "urgency": 0.8, "complexity": 0.5}, [])
        assert p2["confidence"] > p1["confidence"]

    def test_automation_intent(self):
        loop = _make_loop()
        profile = loop._build_tool_profile(
            {"intent": "automation", "mode": "general", "urgency": 0.4, "complexity": 0.5},
            [{"name": "browser_click"}, {"name": "read_file"}],
        )
        assert profile["preferred_tool"] == "browser_click"


# ═══════════════════════════════════════════════════════════════════════════════
# _stringify
# ═══════════════════════════════════════════════════════════════════════════════

class TestStringify:
    def test_string_passthrough(self):
        assert AgentLoop._stringify("hello") == "hello"

    def test_int(self):
        assert AgentLoop._stringify(42) == "42"

    def test_none(self):
        assert AgentLoop._stringify(None) == "null"

    def test_dict(self):
        result = AgentLoop._stringify({"a": 1})
        assert '"a"' in result

    def test_bool(self):
        assert AgentLoop._stringify(True) == "true"


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestParsePlan:
    def test_empty_text(self):
        loop = _make_loop()
        assert loop._parse_plan("", [], _traj()) == []

    def test_json_list(self):
        loop = _make_loop()
        text = json.dumps([{"kind": "observe", "instruction": "look"}])
        steps = loop._parse_plan(text, [], _traj())
        assert len(steps) == 1
        assert steps[0].kind == "observe"

    def test_json_dict_with_steps(self):
        loop = _make_loop()
        text = json.dumps({"steps": [{"kind": "tool", "instruction": "run", "tool_name": "read_file"}]})
        steps = loop._parse_plan(text, [], _traj())
        assert steps[0].tool_name == "read_file"

    def test_mock_response(self):
        loop = _make_loop()
        text = "X-Agent Phase 0 mock response: done"
        steps = loop._parse_plan(text, [], _traj())
        assert steps[0].kind == "final"
        assert "mock response" in steps[0].instruction

    def test_line_format(self):
        loop = _make_loop()
        text = "observe the code\ntool: read_file main.py\nreflect on results\nfinal answer"
        steps = loop._parse_plan(text, [], _traj())
        assert len(steps) == 4
        assert steps[0].kind == "observe"
        assert steps[1].kind == "tool"
        assert steps[1].tool_name == "read_file"
        assert steps[2].kind == "reflect"
        assert steps[3].kind == "final"

    def test_invalid_json(self):
        loop = _make_loop()
        text = "{invalid json"
        steps = loop._parse_plan(text, [], _traj())
        assert steps == []


# ═══════════════════════════════════════════════════════════════════════════════
# _step_from_dict
# ═══════════════════════════════════════════════════════════════════════════════

class TestStepFromDict:
    def test_full_dict(self):
        loop = _make_loop()
        step = loop._step_from_dict({"kind": "tool", "instruction": "run", "tool_name": "read_file", "arguments": {"path": "a.py"}})
        assert step.kind == "tool"
        assert step.tool_name == "read_file"
        assert step.arguments == {"path": "a.py"}

    def test_type_fallback(self):
        loop = _make_loop()
        step = loop._step_from_dict({"type": "observe", "content": "look"})
        assert step.kind == "observe"
        assert step.instruction == "look"

    def test_defaults(self):
        loop = _make_loop()
        step = loop._step_from_dict({})
        assert step.kind == "final"
        assert step.tool_name is None


# ═══════════════════════════════════════════════════════════════════════════════
# _dedupe_plan_steps
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupePlanSteps:
    def test_removes_duplicates(self):
        loop = _make_loop()
        traj = _traj()
        steps = [
            AgentPlanStep(kind="observe", instruction="look"),
            AgentPlanStep(kind="observe", instruction="look"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        result = loop._dedupe_plan_steps(traj, steps)
        assert len(result) == 2

    def test_ensures_final_step(self):
        loop = _make_loop()
        traj = _traj()
        steps = [AgentPlanStep(kind="observe", instruction="look")]
        result = loop._dedupe_plan_steps(traj, steps)
        assert result[-1].kind == "final"

    def test_empty_returns_final(self):
        loop = _make_loop()
        traj = _traj()
        result = loop._dedupe_plan_steps(traj, [])
        assert len(result) == 1
        assert result[0].kind == "final"

    def test_skips_completed_subtask_labels(self):
        loop = _make_loop()
        traj = _traj(subtasks=["understand request", "apply modification"])
        steps = [
            AgentPlanStep(kind="observe", instruction="understand request"),
            AgentPlanStep(kind="tool", instruction="apply modification", tool_name="write_file"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        result = loop._dedupe_plan_steps(traj, steps)
        # "understand request" matches subtask label so skipped (non-final)
        assert not any(s.instruction == "understand request" for s in result)


# ═══════════════════════════════════════════════════════════════════════════════
# _filter_resumed_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestFilterResumedPlan:
    def test_filters_completed_kinds(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"])
        plan = [
            AgentPlanStep(kind="observe", instruction="look"),
            AgentPlanStep(kind="tool", instruction="run", tool_name="read_file"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        payload = {"completed_kinds": ["observe"]}
        result = loop._filter_resumed_plan(plan, payload, {}, traj)
        # observe filtered but tool with tool_name preserved
        assert any(s.kind == "tool" for s in result)

    def test_tool_steps_with_name_preserved(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"])
        plan = [AgentPlanStep(kind="tool", instruction="run", tool_name="write_file")]
        payload = {"completed_kinds": ["tool"]}
        result = loop._filter_resumed_plan(plan, payload, {}, traj)
        assert len(result) >= 1

    def test_skip_observe_on_resume(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"])
        plan = [
            AgentPlanStep(kind="observe", instruction="look"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        payload = {}
        result = loop._filter_resumed_plan(plan, payload, {"skip_observe_on_resume": True}, traj)
        assert not any(s.kind == "observe" for s in result)


# ═══════════════════════════════════════════════════════════════════════════════
# _mark_subtask_progress
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkSubtaskProgress:
    def test_observe_marks_observed(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1", "step2"])
        loop._mark_subtask_progress(traj, "observe")
        assert traj.subtask_status["step1"] == "observed"

    def test_success_marks_done_and_advances(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1", "step2"])
        loop._mark_subtask_progress(traj, "tool", succeeded=True)
        assert traj.subtask_status["step1"] == "done"
        assert traj.current_subtask_index == 1

    def test_failure_marks_blocked(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1"])
        loop._mark_subtask_progress(traj, "tool", succeeded=False)
        assert traj.subtask_status["step1"] == "blocked"

    def test_no_subtasks_noop(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        loop._mark_subtask_progress(traj, "observe")
        assert traj.subtask_status == {}

    def test_apply_modification_read_only_keeps_in_progress(self):
        loop = _make_loop()
        traj = _traj(subtasks=["apply modification"])
        loop._mark_subtask_progress(traj, "read_file", succeeded=True)
        assert traj.subtask_status["apply modification"] == "in_progress"


# ═══════════════════════════════════════════════════════════════════════════════
# _should_defer_step
# ═══════════════════════════════════════════════════════════════════════════════

class TestShouldDeferStep:
    def test_approval_defers_write_tools(self):
        loop = _make_loop()
        traj = _traj()
        step = AgentPlanStep(kind="tool", instruction="write", tool_name="write_file")
        # Need to mock _build_platform_context to return approval context
        with patch.object(loop, "_build_platform_context", return_value={
            "workflow": {}, "approval": {"pending_count": 1}, "browser": {}, "desktop": {}
        }):
            assert loop._should_defer_step(step, traj, {}) is True

    def test_no_defer_for_read_tools(self):
        loop = _make_loop()
        traj = _traj()
        step = AgentPlanStep(kind="tool", instruction="read", tool_name="read_file")
        with patch.object(loop, "_build_platform_context", return_value={
            "workflow": {}, "approval": {"pending_count": 1}, "browser": {}, "desktop": {}
        }):
            assert loop._should_defer_step(step, traj, {}) is False

    def test_browser_defers_desktop(self):
        loop = _make_loop()
        traj = _traj()
        step = AgentPlanStep(kind="tool", instruction="desktop", tool_name="desktop_click")
        with patch.object(loop, "_build_platform_context", return_value={
            "workflow": {}, "approval": {}, "browser": {"active_count": 1}, "desktop": {}
        }):
            assert loop._should_defer_step(step, traj, {}) is True

    def test_desktop_defers_browser(self):
        loop = _make_loop()
        traj = _traj()
        step = AgentPlanStep(kind="tool", instruction="browser", tool_name="browser_click")
        with patch.object(loop, "_build_platform_context", return_value={
            "workflow": {}, "approval": {}, "browser": {}, "desktop": {"active_count": 1}
        }):
            assert loop._should_defer_step(step, traj, {}) is True


# ═══════════════════════════════════════════════════════════════════════════════
# _prioritize_tools_for_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrioritizeToolsForContext:
    def test_browser_tools_prioritized(self):
        loop = _make_loop()
        tools = [{"name": "read_file"}, {"name": "browser_click"}]
        result = loop._prioritize_tools_for_context(tools, {}, {}, {"active_count": 1}, {})
        assert result[0]["name"] == "browser_click"

    def test_desktop_tools_prioritized(self):
        loop = _make_loop()
        tools = [{"name": "read_file"}, {"name": "desktop_click"}]
        result = loop._prioritize_tools_for_context(tools, {}, {}, {}, {"active_count": 1})
        assert result[0]["name"] == "desktop_click"

    def test_workflow_tools_prioritized(self):
        loop = _make_loop()
        tools = [{"name": "read_file"}, {"name": "workflow_trace"}]
        result = loop._prioritize_tools_for_context(tools, {"workflow_id": "w1"}, {}, {}, {})
        assert result[0]["name"] == "workflow_trace"


# ═══════════════════════════════════════════════════════════════════════════════
# _next_subtask_steps
# ═══════════════════════════════════════════════════════════════════════════════

class TestNextSubtaskSteps:
    def test_final_returns_empty(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a", "b"])
        assert loop._next_subtask_steps(traj, "final") == []

    def test_observe_returns_3(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a", "b", "c", "d"])
        result = loop._next_subtask_steps(traj, "observe")
        assert len(result) <= 3

    def test_mutating_tool_returns_2(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a", "b", "c"])
        result = loop._next_subtask_steps(traj, "tool", tool_name="write_file")
        assert len(result) <= 2

    def test_done_subtasks_excluded(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a", "b", "c"])
        traj.subtask_status["a"] = "done"
        traj.current_subtask_index = 1
        result = loop._next_subtask_steps(traj, "observe")
        assert "a" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _check_mainline
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckMainline:
    def test_no_subtasks_noop(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        loop._check_mainline(traj, "evidence")
        assert traj.subtask_status == {}

    def test_sets_in_progress_when_not_in_evidence(self):
        loop = _make_loop()
        traj = _traj(subtasks=["apply modification"])
        loop._check_mainline(traj, "unrelated evidence")
        assert traj.subtask_status.get("apply modification") == "in_progress"

    def test_no_change_when_in_evidence(self):
        loop = _make_loop()
        traj = _traj(subtasks=["apply modification"])
        loop._check_mainline(traj, "apply modification is happening")
        assert "apply modification" not in traj.subtask_status


# ═══════════════════════════════════════════════════════════════════════════════
# _apply_execution_plan
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyExecutionPlan:
    def test_concrete_tool_skips_injection(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="tool", instruction="run", tool_name="read_file")]
        result = loop._apply_execution_plan(steps, {"execution_plan": {"steps": ["do stuff"]}})
        assert result is steps

    def test_mock_final_skips_injection(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="final", instruction="X-Agent Phase 0 mock response: done")]
        result = loop._apply_execution_plan(steps, {"execution_plan": {"steps": ["do stuff"]}})
        assert result is steps

    def test_no_execution_plan_returns_steps(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="observe", instruction="look")]
        result = loop._apply_execution_plan(steps, {})
        assert result is steps

    def test_merges_planned_steps(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="final", instruction="done")]
        ctx = {"execution_plan": {"steps": ["apply the patch", "verify results"]}}
        result = loop._apply_execution_plan(steps, ctx)
        assert any(s.kind == "tool" for s in result)
        assert any(s.kind == "reflect" for s in result)

    def test_verification_steps_added(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="final", instruction="done")]
        ctx = {"execution_plan": {"steps": ["observe"], "verification_steps": ["check output"]}}
        result = loop._apply_execution_plan(steps, ctx)
        assert any("check output" in s.instruction for s in result)

    def test_suggested_test_commands(self):
        loop = _make_loop()
        steps = [AgentPlanStep(kind="final", instruction="done")]
        ctx = {"execution_plan": {"steps": ["observe"], "suggested_test_commands": ["pytest"]}}
        result = loop._apply_execution_plan(steps, ctx)
        assert any(s.tool_name == "summarize_text" for s in result)


# ═══════════════════════════════════════════════════════════════════════════════
# _finalize_answer
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinalizeAnswer:
    def test_mock_response_step(self):
        loop = _make_loop()
        traj = _traj()
        traj.steps = [AgentPlanStep(kind="final", instruction="X-Agent Phase 0 mock response: hello")]
        result = loop._finalize_answer("task", traj, None, {})
        assert "mock response" in result

    def test_reflections_used(self):
        loop = _make_loop()
        traj = _traj()
        traj.reflections = ["my reflection"]
        result = loop._finalize_answer("task", traj, None, {})
        assert result == "my reflection"

    def test_last_tool_result_used(self):
        loop = _make_loop()
        traj = _traj()
        result = loop._finalize_answer("task", traj, "tool output", {})
        assert "tool output" in result

    def test_open_items_low_confidence(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1"], subtask_status={"step1": "pending"})
        with patch.object(loop, "_build_tool_profile", return_value={"confidence": 0.4}):
            result = loop._finalize_answer("task", traj, None, {})
        assert "remaining steps" in result

    def test_open_items_high_confidence(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1"], subtask_status={"step1": "pending"})
        with patch.object(loop, "_build_tool_profile", return_value={"confidence": 0.8}):
            result = loop._finalize_answer("task", traj, None, {})
        assert "next step" in result

    def test_next_action_resume(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        traj.stage = "resuming:tr1"
        with patch.object(loop, "_build_task_profile", return_value={"next_action": "continue work", "urgency": 0.4, "branch_note": ""}):
            with patch.object(loop, "_build_tool_profile", return_value={"confidence": 0.8}):
                result = loop._finalize_answer("task", traj, None, {})
        assert "resume" in result

    def test_completed_no_subtasks(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        with patch.object(loop, "_build_task_profile", return_value={"next_action": None, "urgency": 0.4, "branch_note": ""}):
            with patch.object(loop, "_build_tool_profile", return_value={"confidence": 0.8}):
                result = loop._finalize_answer("task", traj, None, {})
        assert "Completed" in result

    def test_branch_note_appended(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        with patch.object(loop, "_build_task_profile", return_value={"next_action": None, "urgency": 0.4, "branch_note": "proceed carefully"}):
            with patch.object(loop, "_build_tool_profile", return_value={"confidence": 0.8}):
                result = loop._finalize_answer("task", traj, None, {})
        assert "proceed carefully" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _build_execution_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildExecutionSummary:
    def test_basic_summary(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"], subtask_status={"a": "done"})
        summary = loop._build_execution_summary(traj, ["obs"], [], [], "answer", {})
        assert summary["goal"] == "fix bug"
        assert summary["observations"] == 1
        assert summary["branch"] == "continue"

    def test_resume_branch(self):
        loop = _make_loop()
        traj = _traj()
        traj.stage = "resuming:tr1"
        summary = loop._build_execution_summary(traj, [], [], [], "ans", {})
        assert summary["branch"] == "resume"

    def test_approval_wait_branch(self):
        loop = _make_loop()
        traj = _traj()
        summary = loop._build_execution_summary(traj, [], [], [], "ans", {"approval_state": {"pending_count": 1}})
        assert summary["branch"] == "approval_wait"

    def test_urgent_continue_branch(self):
        loop = _make_loop()
        traj = _traj(task="urgent fix now", goal="fix")
        summary = loop._build_execution_summary(traj, [], [], [], "ans", {})
        assert summary["branch"] == "urgent_continue"

    def test_affected_files_from_tool_calls(self):
        loop = _make_loop()
        traj = _traj()
        call = MagicMock()
        call.tool_name = "write_file"
        call.success = True
        call.output = {"path": "src/main.py", "verified": True, "applied": True}
        summary = loop._build_execution_summary(traj, [], [call], [], "ans", {})
        assert "src/main.py" in summary["affected_files"]


# ═══════════════════════════════════════════════════════════════════════════════
# _record_audit
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordAudit:
    def test_no_audit_store_noop(self):
        loop = _make_loop(audit_store=None)
        traj = _traj()
        loop._record_audit("test.action", _ctx(), traj)  # should not raise

    def test_with_audit_store(self):
        store = MagicMock()
        loop = _make_loop(audit_store=store)
        traj = _traj()
        loop._record_audit("test.action", _ctx(), traj, outcome="success")
        store.record.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _build_tool_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildToolContext:
    def test_copies_fields(self):
        loop = _make_loop()
        ctx = _ctx(request_id="r1", permission_scope=["read"])
        step = AgentPlanStep(kind="tool", instruction="run", tool_name="read_file")
        result = loop._build_tool_context(ctx, step)
        assert result.trace_id == "tr1"
        assert result.tenant_id == "t1"
        assert result.permission_scope == ["read"]


# ═══════════════════════════════════════════════════════════════════════════════
# _system_prompt / prompt builders
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptBuilders:
    def test_system_prompt(self):
        loop = _make_loop()
        prompt = loop._system_prompt()
        assert "X-Agent" in prompt

    def test_workflow_prompt(self):
        loop = _make_loop()
        prompt = loop._build_workflow_prompt({"workflow_id": "w1"})
        assert "w1" in prompt

    def test_approval_prompt(self):
        loop = _make_loop()
        prompt = loop._build_approval_prompt({"approval_id": "ap1"})
        assert "ap1" in prompt

    def test_run_prompt(self):
        loop = _make_loop()
        prompt = loop._build_run_prompt({"related_runs": []})
        assert "Related run" in prompt

    def test_resume_prompt(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"])
        traj.stage = "resuming:tr1"
        prompt = loop._build_resume_prompt(traj, {"resume_trace_id": "tr1"})
        assert "tr1" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# _align_plan_with_subtasks (second definition at line 2933)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlignPlanWithSubtasks:
    def test_no_subtasks_returns_plan(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        plan = [AgentPlanStep(kind="observe", instruction="look")]
        assert loop._align_plan_with_subtasks(plan, traj) is plan

    def test_preserves_tool_steps(self):
        loop = _make_loop()
        traj = _traj(subtasks=["apply modification"])
        plan = [
            AgentPlanStep(kind="tool", instruction="write", tool_name="write_file"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        result = loop._align_plan_with_subtasks(plan, traj)
        assert any(s.tool_name == "write_file" for s in result)

    def test_preserves_reflect_steps(self):
        loop = _make_loop()
        traj = _traj(subtasks=["apply modification"])
        plan = [
            AgentPlanStep(kind="reflect", instruction="think"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        result = loop._align_plan_with_subtasks(plan, traj)
        assert any(s.kind == "reflect" for s in result)

    def test_ensures_final(self):
        loop = _make_loop()
        traj = _traj(subtasks=["step1"])
        plan = [AgentPlanStep(kind="observe", instruction="look")]
        result = loop._align_plan_with_subtasks(plan, traj)
        assert result[-1].kind == "final"


# ═══════════════════════════════════════════════════════════════════════════════
# _align_plan_with_context
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlignPlanWithContext:
    def test_no_platform_context_delegates(self):
        loop = _make_loop()
        traj = _traj(subtasks=["a"])
        plan = [AgentPlanStep(kind="observe", instruction="look"), AgentPlanStep(kind="final", instruction="done")]
        result = loop._align_plan_with_context(plan, {}, traj)
        assert len(result) >= 1

    def test_browser_context_filters(self):
        loop = _make_loop()
        traj = _traj(subtasks=[])
        plan = [
            AgentPlanStep(kind="tool", instruction="browser click", tool_name="browser_click"),
            AgentPlanStep(kind="observe", instruction="generic observe"),
            AgentPlanStep(kind="final", instruction="done"),
        ]
        result = loop._align_plan_with_context(plan, {"browser": {"active_count": 1}}, traj)
        assert any(s.tool_name == "browser_click" for s in result)


# ═══════════════════════════════════════════════════════════════════════════════
# _build_plan_frame
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPlanFrame:
    def test_basic(self):
        loop = _make_loop()
        plan = [AgentPlanStep(kind="observe", instruction="look"), AgentPlanStep(kind="final", instruction="done")]
        frame = loop._build_plan_frame(None, None, None, plan, "my goal")
        assert frame.goal == "my goal"
        assert frame.steps == ["look", "done"]
        assert frame.status == "ready"
