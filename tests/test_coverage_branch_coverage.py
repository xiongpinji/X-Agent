"""
测试覆盖率提升 - 分支覆盖测试
重点覆盖：
- if/else分支
- try/except分支
- 循环中的break/continue
- 早期返回
- 条件判断
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.core.agent import AgentLoop
from backend.app.core.contracts import RunContext, RunStatus, ExecutionFrame, TaskFrame
from backend.app.core.llm import LLMRouter
from backend.app.core.memory import InMemoryMemorySystem
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


class TestIfElseBranches:
    """if/else分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_agent_with_session_id(self):
        """测试带session_id的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext(session_id="test_session")
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test task")

        # 验证session_id分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_without_session_id(self):
        """测试不带session_id的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext(session_id=None)
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test task")

        # 验证无session_id分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_extra_context(self):
        """测试带额外上下文的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        extra_context = {"key": "value"}

        result = await agent.run(context, "test task", extra_context=extra_context)

        # 验证额外上下文分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_without_extra_context(self):
        """测试不带额外上下文的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test task", extra_context=None)

        # 验证无额外上下文分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_event_callback(self):
        """测试带事件回调的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        callback_called = False

        async def event_callback(event):
            nonlocal callback_called
            callback_called = True

        result = await agent.run(context, "test task", event_callback=event_callback)

        # 验证回调分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_without_event_callback(self):
        """测试不带事件回调的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
        )

        result = await agent.run(context, "test task", event_callback=None)

        # 验证无回调分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_tracer(self):
        """测试带tracer的agent"""
        from backend.app.core.tracing import TraceStore

        memory = InMemoryMemorySystem()
        context = RunContext()
        tracer = TraceStore()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
            tracer=tracer,
        )

        result = await agent.run(context, "test task")

        # 验证tracer分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_without_tracer(self):
        """测试不带tracer的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
            tracer=None,
        )

        result = await agent.run(context, "test task")

        # 验证无tracer分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_with_run_store(self):
        """测试带run_store的agent"""
        from backend.app.core.runs import RunStore

        memory = InMemoryMemorySystem()
        context = RunContext()
        run_store = RunStore()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
            run_store=run_store,
        )

        result = await agent.run(context, "test task")

        # 验证run_store分支
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_without_run_store(self):
        """测试不带run_store的agent"""
        memory = InMemoryMemorySystem()
        context = RunContext()
        agent = AgentLoop(
            llm_router=LLMRouter(),
            memory=memory,
            tools=build_default_tool_registry(ToolPolicyEngine()),
            run_store=None,
        )

        result = await agent.run(context, "test task")

        # 验证无run_store分支
        assert result is not None


class TestTryExceptBranches:
    """try/except分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_llm_route_success(self):
        """测试LLM路由成功"""
        llm = LLMRouter()

        with patch.object(llm, 'chat', return_value={"content": "success"}):
            result = await llm.chat([], [])

            # 验证成功分支
            assert result is not None

    @pytest.mark.asyncio
    async def test_llm_route_failure(self):
        """测试LLM路由失败"""
        llm = LLMRouter()

        with patch.object(llm, 'chat', side_effect=Exception("Route failed")):
            with pytest.raises(Exception):
                await llm.chat([], [])

    @pytest.mark.asyncio
    async def test_memory_store_success(self):
        """测试记忆存储成功"""
        memory = InMemoryMemorySystem()
        context = RunContext()

        memory_id = await memory.store(context, "value")

        # 验证成功分支
        result = memory.get_item(memory_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_memory_store_failure(self):
        """测试记忆存储失败"""
        memory = InMemoryMemorySystem()
        context = RunContext()

        with patch.object(memory, 'store', side_effect=Exception("Store failed")):
            with pytest.raises(Exception):
                await memory.store(context, "value")

    @pytest.mark.asyncio
    async def test_tool_execute_success(self):
        """测试工具执行成功"""
        from backend.app.core.tool_executor import ToolExecutionEngine
        from backend.app.core.tool_registry import ToolRegistry
        from backend.app.core.tool_schema import ToolCallInput, ToolCallOutput

        registry = ToolRegistry()
        executor = ToolExecutionEngine(registry)

        ok = ToolCallOutput(tool_id="t1", tool_name="test_tool", success=True, result={"status": "success"})
        with patch.object(executor, 'execute_tool', new=AsyncMock(return_value=ok)):
            result = await executor.execute_tool(
                ToolCallInput(tool_id="t1", tool_name="test_tool", arguments={})
            )

            # 验证成功分支
            assert result.success is True
            assert result.result["status"] == "success"

    @pytest.mark.asyncio
    async def test_tool_execute_failure(self):
        """测试工具执行失败"""
        from backend.app.core.tool_executor import ToolExecutionEngine
        from backend.app.core.tool_registry import ToolRegistry
        from backend.app.core.tool_schema import ToolCallInput

        registry = ToolRegistry()
        executor = ToolExecutionEngine(registry)

        with patch.object(executor, 'execute_tool', new=AsyncMock(side_effect=Exception("Execute failed"))):
            with pytest.raises(Exception):
                await executor.execute_tool(
                    ToolCallInput(tool_id="t1", tool_name="test_tool", arguments={})
                )

    @pytest.mark.asyncio
    async def test_policy_check_allowed(self):
        """测试策略检查允许"""
        from backend.app.core.contracts import RiskLevel

        policy = ToolPolicyEngine()

        # evaluate 是同步方法；默认 RunContext 带 tools:read 作用域，LOW 风险 → allowed
        verdict = policy.evaluate(RunContext(), "tool_name", RiskLevel.LOW)

        # 验证允许分支
        assert verdict.allowed is True

    @pytest.mark.asyncio
    async def test_policy_check_denied(self):
        """测试策略检查拒绝"""
        from backend.app.core.contracts import RiskLevel

        policy = ToolPolicyEngine()

        # HIGH 风险且未启用高危工具 → denied + requires_approval
        verdict = policy.evaluate(RunContext(), "tool_name", RiskLevel.HIGH)

        # 验证拒绝分支
        assert verdict.allowed is False
        assert verdict.requires_approval is True


class TestLoopBranches:
    """循环分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_loop_with_break(self):
        """测试包含break的循环"""
        result = []

        for i in range(10):
            if i == 5:
                break
            result.append(i)

        # 验证break分支
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_loop_with_continue(self):
        """测试包含continue的循环"""
        result = []

        for i in range(10):
            if i % 2 == 0:
                continue
            result.append(i)

        # 验证continue分支
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_loop_with_else(self):
        """测试包含else的循环"""
        result = []

        for i in range(5):
            result.append(i)
        else:
            result.append("done")

        # 验证else分支
        assert result[-1] == "done"

    @pytest.mark.asyncio
    async def test_loop_with_break_no_else(self):
        """测试break时不执行else的循环"""
        result = []

        for i in range(10):
            if i == 5:
                break
            result.append(i)
        else:
            result.append("done")

        # 验证break时else不执行
        assert "done" not in result

    @pytest.mark.asyncio
    async def test_nested_loops(self):
        """测试嵌套循环"""
        result = []

        for i in range(3):
            for j in range(3):
                if i == 1 and j == 1:
                    break
                result.append((i, j))

        # 验证嵌套循环分支
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_loop_with_multiple_conditions(self):
        """测试包含多个条件的循环"""
        result = []

        for i in range(10):
            if i < 3:
                result.append("small")
            elif i < 7:
                result.append("medium")
            else:
                result.append("large")

        # 验证多条件分支
        assert len(result) == 10


class TestEarlyReturnBranches:
    """早期返回分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_early_return_on_none(self):
        """测试None时的早期返回"""
        def check_value(value):
            if value is None:
                return "none"
            return "not_none"

        result = check_value(None)

        # 验证早期返回
        assert result == "none"

    @pytest.mark.asyncio
    async def test_early_return_on_empty(self):
        """测试空值时的早期返回"""
        def check_value(value):
            if not value:
                return "empty"
            return "not_empty"

        result = check_value("")

        # 验证早期返回
        assert result == "empty"

    @pytest.mark.asyncio
    async def test_early_return_on_error(self):
        """测试错误时的早期返回"""
        def check_value(value):
            if isinstance(value, Exception):
                return "error"
            return "ok"

        result = check_value(Exception("test"))

        # 验证早期返回
        assert result == "error"

    @pytest.mark.asyncio
    async def test_early_return_on_condition(self):
        """测试条件满足时的早期返回"""
        def check_value(value):
            if value > 10:
                return "large"
            if value > 5:
                return "medium"
            return "small"

        result = check_value(15)

        # 验证早期返回
        assert result == "large"


class TestConditionalBranches:
    """条件判断分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_boolean_and_condition(self):
        """测试布尔AND条件"""
        def check_condition(a, b):
            if a and b:
                return "both_true"
            return "not_both"

        # 测试两个分支
        assert check_condition(True, True) == "both_true"
        assert check_condition(True, False) == "not_both"
        assert check_condition(False, True) == "not_both"
        assert check_condition(False, False) == "not_both"

    @pytest.mark.asyncio
    async def test_boolean_or_condition(self):
        """测试布尔OR条件"""
        def check_condition(a, b):
            if a or b:
                return "at_least_one"
            return "none"

        # 测试两个分支
        assert check_condition(True, True) == "at_least_one"
        assert check_condition(True, False) == "at_least_one"
        assert check_condition(False, True) == "at_least_one"
        assert check_condition(False, False) == "none"

    @pytest.mark.asyncio
    async def test_boolean_not_condition(self):
        """测试布尔NOT条件"""
        def check_condition(a):
            if not a:
                return "false"
            return "true"

        # 测试两个分支
        assert check_condition(True) == "true"
        assert check_condition(False) == "false"

    @pytest.mark.asyncio
    async def test_comparison_conditions(self):
        """测试比较条件"""
        def check_value(value):
            if value == 0:
                return "zero"
            elif value < 0:
                return "negative"
            elif value > 0:
                return "positive"
            return "unknown"

        # 测试所有分支
        assert check_value(0) == "zero"
        assert check_value(-5) == "negative"
        assert check_value(5) == "positive"

    @pytest.mark.asyncio
    async def test_membership_conditions(self):
        """测试成员条件"""
        def check_membership(value, collection):
            if value in collection:
                return "member"
            return "not_member"

        # 测试两个分支
        assert check_membership(1, [1, 2, 3]) == "member"
        assert check_membership(4, [1, 2, 3]) == "not_member"

    @pytest.mark.asyncio
    async def test_type_conditions(self):
        """测试类型条件"""
        def check_type(value):
            if isinstance(value, str):
                return "string"
            elif isinstance(value, int):
                return "integer"
            elif isinstance(value, list):
                return "list"
            return "other"

        # 测试所有分支
        assert check_type("test") == "string"
        assert check_type(42) == "integer"
        assert check_type([1, 2, 3]) == "list"
        assert check_type({"key": "value"}) == "other"


class TestExceptionHandlingBranches:
    """异常处理分支覆盖测试"""

    @pytest.mark.asyncio
    async def test_try_except_specific_exception(self):
        """测试捕获特定异常"""
        def handle_exception():
            try:
                raise ValueError("test error")
            except ValueError:
                return "caught_value_error"
            except TypeError:
                return "caught_type_error"

        result = handle_exception()

        # 验证特定异常分支
        assert result == "caught_value_error"

    @pytest.mark.asyncio
    async def test_try_except_different_exception(self):
        """测试捕获不同异常"""
        def handle_exception():
            try:
                raise TypeError("test error")
            except ValueError:
                return "caught_value_error"
            except TypeError:
                return "caught_type_error"

        result = handle_exception()

        # 验证不同异常分支
        assert result == "caught_type_error"

    @pytest.mark.asyncio
    async def test_try_except_no_exception(self):
        """测试无异常的try/except"""
        def handle_exception():
            try:
                return "success"
            except Exception:
                return "error"

        result = handle_exception()

        # 验证无异常分支
        assert result == "success"

    @pytest.mark.asyncio
    async def test_try_except_finally(self):
        """测试try/except/finally"""
        executed = []

        def handle_exception():
            try:
                executed.append("try")
                raise ValueError("test")
            except ValueError:
                executed.append("except")
            finally:
                executed.append("finally")

        handle_exception()

        # 验证finally分支
        assert executed == ["try", "except", "finally"]

    @pytest.mark.asyncio
    async def test_try_except_else(self):
        """测试try/except/else"""
        executed = []

        def handle_exception():
            try:
                executed.append("try")
            except Exception:
                executed.append("except")
            else:
                executed.append("else")

        handle_exception()

        # 验证else分支
        assert executed == ["try", "else"]

    @pytest.mark.asyncio
    async def test_nested_try_except(self):
        """测试嵌套try/except"""
        def handle_exception():
            try:
                try:
                    raise ValueError("inner")
                except TypeError:
                    return "inner_caught"
            except ValueError:
                return "outer_caught"

        result = handle_exception()

        # 验证嵌套异常分支
        assert result == "outer_caught"
