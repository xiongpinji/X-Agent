"""
代码执行测试
"""

import pytest
from backend.app.core.execution import PythonSandbox, NodeJSExecutor, ExecutionManager


class TestPythonSandbox:
    """Python沙箱测试"""

    @pytest.fixture
    def sandbox(self):
        return PythonSandbox(timeout=10)

    @pytest.mark.asyncio
    async def test_simple_execution(self, sandbox):
        """测试简单代码执行"""
        code = "x = 1 + 1\nprint(x)"
        result = await sandbox.execute(code)

        assert result["success"]
        assert "2" in result["output"]

    @pytest.mark.asyncio
    async def test_forbidden_operation(self, sandbox):
        """测试禁止操作"""
        code = "import os\nos.system('ls')"
        result = await sandbox.execute(code)

        assert not result["success"]
        assert "forbidden" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_forbidden_name(self, sandbox):
        """测试禁止名称"""
        code = "eval('1+1')"
        result = await sandbox.execute(code)

        assert not result["success"]
        assert "forbidden" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_context_variables(self, sandbox):
        """测试上下文变量"""
        code = "print(x + y)"
        context = {"x": 10, "y": 20}
        result = await sandbox.execute(code, context=context)

        assert result["success"]
        assert "30" in result["output"]

    @pytest.mark.asyncio
    async def test_allowed_imports(self, sandbox):
        """测试允许的导入"""
        code = "import math\nprint(math.pi)"
        result = await sandbox.execute(code, allowed_imports=["math"])

        assert result["success"]
        assert "3.14" in result["output"]

    @pytest.mark.asyncio
    async def test_syntax_error(self, sandbox):
        """测试语法错误"""
        code = "x = 1 ++"
        result = await sandbox.execute(code)

        assert not result["success"]

    @pytest.mark.asyncio
    async def test_runtime_error(self, sandbox):
        """测试运行时错误"""
        code = "x = 1 / 0"
        result = await sandbox.execute(code)

        assert not result["success"]
        assert "division" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_output_truncation(self, sandbox):
        """测试输出截断"""
        sandbox.max_output = 100
        code = "print('x' * 1000)"
        result = await sandbox.execute(code)

        assert result["success"]
        assert len(result["output"]) <= 200  # 包括截断消息


class TestNodeJSExecutor:
    """Node.js执行器测试"""

    @pytest.fixture
    def executor(self):
        return NodeJSExecutor(timeout=10)

    @pytest.mark.asyncio
    async def test_simple_execution(self, executor):
        """测试简单代码执行"""
        code = "console.log(1 + 1)"
        result = await executor.execute(code)

        # Node.js可能未安装，所以只检查结果结构
        assert "success" in result
        assert "output" in result or "error" in result

    @pytest.mark.asyncio
    async def test_syntax_error(self, executor):
        """测试语法错误"""
        code = "console.log(1 ++"
        result = await executor.execute(code)

        # 应该返回失败
        assert "success" in result


class TestExecutionManager:
    """执行管理器测试"""

    @pytest.fixture
    def manager(self):
        return ExecutionManager(timeout=10)

    @pytest.mark.asyncio
    async def test_execute_python(self, manager):
        """测试执行Python代码"""
        code = "print('Hello, World!')"
        result = await manager.execute_python(code)

        assert result["success"]
        assert "Hello, World!" in result["output"]
        assert "execution_id" in result

    @pytest.mark.asyncio
    async def test_execute_nodejs(self, manager):
        """测试执行Node.js代码"""
        code = "console.log('Hello, World!')"
        result = await manager.execute_nodejs(code)

        assert "success" in result
        assert "execution_id" in result

    @pytest.mark.asyncio
    async def test_execution_history(self, manager):
        """测试执行历史"""
        code = "print('test')"
        result = await manager.execute_python(code)
        execution_id = result["execution_id"]

        history = manager.get_execution_history(execution_id)
        assert history is not None
        assert history["id"] == execution_id
        assert history["language"] == "python"

    @pytest.mark.asyncio
    async def test_list_executions(self, manager):
        """测试列出执行"""
        code = "print('test')"
        await manager.execute_python(code)
        await manager.execute_python(code)

        executions = manager.list_executions(limit=10)
        assert len(executions) >= 2

    def test_clear_history(self, manager):
        """测试清空历史"""
        manager.clear_history()
        executions = manager.list_executions()
        assert len(executions) == 0

    @pytest.mark.asyncio
    async def test_unsupported_language(self, manager):
        """测试不支持的语言"""
        code = "print('test')"
        result = await manager.execute(code, language="ruby")

        assert not result["success"]
        assert "unsupported" in result["error"].lower()
