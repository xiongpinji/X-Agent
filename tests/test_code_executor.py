"""
Comprehensive test suite for secure code execution system.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest
from backend.app.core.code_executor import (
    CodeExecutor,
    ExecutionConfig,
    ExecutionLanguage,
    ExecutionStatus,
    SecurityValidator,
)


def _bash_works() -> bool:
    """Return True only if a real, runnable bash interpreter is present.

    On Windows the ``bash`` on PATH often resolves to the WSL relay, which can
    raise ``CreateProcessCommon`` errors and never actually execute the command
    (subprocess returns failure immediately rather than running). The bash
    *execution* tests below exercise the subprocess path, so they are only
    meaningful when bash can genuinely run a trivial command. Validation-only
    tests (which never spawn bash) are unaffected by this guard.
    """
    if shutil.which("bash") is None:
        return False
    try:
        completed = subprocess.run(
            ["bash", "-c", "echo ok"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return False
    return completed.returncode == 0 and "ok" in completed.stdout


# Evaluated once at collection time; bash execution tests skip cleanly when the
# environment lacks a functional bash (e.g. Windows with a broken WSL relay).
requires_bash = pytest.mark.skipif(
    not _bash_works(),
    reason="Functional bash interpreter not available in this environment",
)


class TestSecurityValidator:
    """Test security validation for different languages."""

    def test_validate_python_safe_code(self):
        """Test validation of safe Python code."""
        code = "print('Hello, World!')\nx = 1 + 2\nprint(x)"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is True
        assert error is None

    def test_validate_python_exec_violation(self):
        """Test detection of exec() in Python code."""
        code = "exec('print(1)')"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is False
        assert error is not None
        assert "exec" in error.lower()

    def test_validate_python_eval_violation(self):
        """Test detection of eval() in Python code."""
        code = "result = eval('1 + 2')"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is False
        assert error is not None

    def test_validate_python_import_violation(self):
        """Test detection of __import__ in Python code."""
        code = "__import__('os').system('ls')"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is False
        assert error is not None

    def test_validate_python_open_violation(self):
        """Test detection of open() in Python code."""
        code = "with open('/etc/passwd', 'r') as f: data = f.read()"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is False
        assert error is not None

    def test_validate_python_subprocess_violation(self):
        """Test detection of subprocess in Python code."""
        code = "import subprocess\nsubprocess.run(['ls'])"
        is_valid, error = SecurityValidator.validate_python(code)
        assert is_valid is False
        assert error is not None

    def test_validate_javascript_safe_code(self):
        """Test validation of safe JavaScript code."""
        code = "console.log('Hello, World!');\nconst x = 1 + 2;\nconsole.log(x);"
        is_valid, error = SecurityValidator.validate_javascript(code)
        assert is_valid is True
        assert error is None

    def test_validate_javascript_eval_violation(self):
        """Test detection of eval() in JavaScript code."""
        code = "eval('console.log(1)')"
        is_valid, error = SecurityValidator.validate_javascript(code)
        assert is_valid is False
        assert error is not None

    def test_validate_javascript_require_violation(self):
        """Test detection of require() in JavaScript code."""
        code = "const fs = require('fs');"
        is_valid, error = SecurityValidator.validate_javascript(code)
        assert is_valid is False
        assert error is not None

    def test_validate_javascript_process_violation(self):
        """Test detection of process in JavaScript code."""
        code = "process.exit(1);"
        is_valid, error = SecurityValidator.validate_javascript(code)
        assert is_valid is False
        assert error is not None

    def test_validate_bash_safe_command(self):
        """Test validation of safe Bash command."""
        command = "echo 'Hello, World!'"
        is_valid, error = SecurityValidator.validate_bash(command)
        assert is_valid is True
        assert error is None

    def test_validate_bash_rm_violation(self):
        """Test detection of rm -rf in Bash command."""
        command = "rm -rf /"
        is_valid, error = SecurityValidator.validate_bash(command)
        assert is_valid is False
        assert error is not None

    def test_validate_bash_dd_violation(self):
        """Test detection of dd in Bash command."""
        command = "dd if=/dev/zero of=/dev/sda"
        is_valid, error = SecurityValidator.validate_bash(command)
        assert is_valid is False
        assert error is not None

    def test_validate_bash_sudo_violation(self):
        """Test detection of sudo in Bash command."""
        command = "sudo rm -rf /"
        is_valid, error = SecurityValidator.validate_bash(command)
        assert is_valid is False
        assert error is not None


class TestCodeExecutor:
    """Test code execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_python_simple(self):
        """Test simple Python code execution."""
        executor = CodeExecutor()
        code = "print('Hello, World!')"
        result = await executor.execute_python(code)

        assert result.success is True
        assert "Hello, World!" in result.stdout
        assert result.exit_code == 0
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_python_with_imports(self):
        """Test Python code execution with imports."""
        executor = CodeExecutor()
        code = """
import json
data = {'name': 'test', 'value': 42}
print(json.dumps(data))
"""
        result = await executor.execute_python(code)

        assert result.success is True
        assert "test" in result.stdout
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_python_with_error(self):
        """Test Python code execution with error."""
        executor = CodeExecutor()
        code = "raise ValueError('Test error')"
        result = await executor.execute_python(code)

        assert result.success is False
        assert result.exit_code != 0
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_execute_python_timeout(self):
        """Test Python code execution timeout."""
        config = ExecutionConfig(timeout=1)
        executor = CodeExecutor(config=config)
        code = """
import time
time.sleep(5)
print('This should not print')
"""
        result = await executor.execute_python(code, timeout=1)

        assert result.success is False
        assert result.status == ExecutionStatus.TIMEOUT
        assert result.exit_code == 124

    @pytest.mark.asyncio
    async def test_execute_python_security_violation(self):
        """Test Python code execution with security violation."""
        executor = CodeExecutor()
        code = "exec('print(1)')"
        result = await executor.execute_python(code)

        assert result.success is False
        assert result.status == ExecutionStatus.SECURITY_VIOLATION
        assert "Security violation" in result.stderr or "dangerous" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_python_output_truncation(self):
        """Test Python code output truncation."""
        config = ExecutionConfig(max_output_size=100)
        executor = CodeExecutor(config=config)
        code = "print('x' * 1000)"
        result = await executor.execute_python(code)

        assert result.success is True
        assert len(result.stdout) <= 200  # 100 + truncation message

    @pytest.mark.asyncio
    async def test_execute_javascript_simple(self):
        """Test simple JavaScript code execution."""
        executor = CodeExecutor()
        code = "console.log('Hello, World!');"
        result = await executor.execute_javascript(code)

        assert result.success is True
        assert "Hello, World!" in result.stdout
        assert result.exit_code == 0
        assert result.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_javascript_with_error(self):
        """Test JavaScript code execution with error."""
        executor = CodeExecutor()
        code = "throw new Error('Test error');"
        result = await executor.execute_javascript(code)

        assert result.success is False
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_execute_javascript_timeout(self):
        """Test JavaScript code execution timeout."""
        config = ExecutionConfig(timeout=1)
        executor = CodeExecutor(config=config)
        code = """
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
await sleep(5000);
console.log('This should not print');
"""
        result = await executor.execute_javascript(code, timeout=1)

        assert result.success is False
        assert result.status == ExecutionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_javascript_security_violation(self):
        """Test JavaScript code execution with security violation."""
        executor = CodeExecutor()
        code = "const fs = require('fs');"
        result = await executor.execute_javascript(code)

        assert result.success is False
        assert result.status == ExecutionStatus.SECURITY_VIOLATION

    @requires_bash
    @pytest.mark.asyncio
    async def test_execute_bash_simple(self):
        """Test simple Bash command execution."""
        executor = CodeExecutor()
        command = "echo 'Hello, World!'"
        result = await executor.execute_bash(command)

        assert result.success is True
        assert "Hello, World!" in result.stdout
        assert result.exit_code == 0
        assert result.status == ExecutionStatus.SUCCESS

    @requires_bash
    @pytest.mark.asyncio
    async def test_execute_bash_with_error(self):
        """Test Bash command execution with error."""
        executor = CodeExecutor()
        command = "exit 1"
        result = await executor.execute_bash(command)

        assert result.success is False
        assert result.exit_code == 1

    @requires_bash
    @pytest.mark.asyncio
    async def test_execute_bash_timeout(self):
        """Test Bash command execution timeout."""
        config = ExecutionConfig(timeout=1)
        executor = CodeExecutor(config=config)
        command = "sleep 5"
        result = await executor.execute_bash(command, timeout=1)

        assert result.success is False
        assert result.status == ExecutionStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_execute_bash_security_violation(self):
        """Test Bash command execution with security violation."""
        executor = CodeExecutor()
        command = "rm -rf /"
        result = await executor.execute_bash(command)

        assert result.success is False
        assert result.status == ExecutionStatus.SECURITY_VIOLATION

    @requires_bash
    @pytest.mark.asyncio
    async def test_execute_bash_pipe(self):
        """Test Bash command with pipe."""
        executor = CodeExecutor()
        command = "echo 'hello world' | wc -w"
        result = await executor.execute_bash(command)

        assert result.success is True
        assert "2" in result.stdout

    @pytest.mark.asyncio
    async def test_execution_result_serialization(self):
        """Test execution result serialization."""
        executor = CodeExecutor()
        code = "print('test')"
        result = await executor.execute_python(code)

        # Test model_dump
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert "success" in dumped
        assert "stdout" in dumped
        assert "execution_id" in dumped
        assert "timestamp" in dumped

    @pytest.mark.asyncio
    async def test_execution_config_defaults(self):
        """Test execution config defaults."""
        config = ExecutionConfig()

        assert config.timeout == 30
        assert config.max_memory == 512
        assert config.max_cpu_percent == 80
        assert config.allow_network is False
        assert config.allow_file_system_write is False

    @pytest.mark.asyncio
    async def test_execution_config_custom(self):
        """Test execution config with custom values."""
        config = ExecutionConfig(
            timeout=60,
            max_memory=1024,
            allow_network=True,
            allow_file_system_write=True,
        )

        assert config.timeout == 60
        assert config.max_memory == 1024
        assert config.allow_network is True
        assert config.allow_file_system_write is True

    @pytest.mark.asyncio
    async def test_execution_environment_variables(self):
        """Test execution with environment variables."""
        config = ExecutionConfig(
            environment_vars={"TEST_VAR": "test_value"}
        )
        executor = CodeExecutor(config=config)
        code = "import os; print(os.environ.get('TEST_VAR', 'not_found'))"
        result = await executor.execute_python(code)

        assert result.success is True
        assert "test_value" in result.stdout

    @pytest.mark.asyncio
    async def test_execution_network_disabled(self):
        """Test that network access is disabled by default."""
        config = ExecutionConfig(allow_network=False)
        executor = CodeExecutor(config=config)
        code = """
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('example.com', 80))
    print('Network access allowed')
except Exception as e:
    print(f'Network access blocked: {type(e).__name__}')
"""
        result = await executor.execute_python(code)

        assert result.success is False
        # Should show security violation for socket usage
        assert "dangerous" in result.stderr.lower() or "security" in result.stderr.lower()


class TestExecutionEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_code(self):
        """Test execution of empty code."""
        executor = CodeExecutor()
        code = ""
        result = await executor.execute_python(code)

        assert result.success is True
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_code_with_syntax_error(self):
        """Test execution of code with syntax error."""
        executor = CodeExecutor()
        code = "print('unclosed string"
        result = await executor.execute_python(code)

        assert result.success is False
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_very_large_output(self):
        """Test handling of very large output."""
        config = ExecutionConfig(max_output_size=1024)
        executor = CodeExecutor(config=config)
        code = "print('x' * 10000)"
        result = await executor.execute_python(code)

        assert result.success is True
        assert len(result.stdout) <= 2048  # Should be truncated

    @pytest.mark.asyncio
    async def test_execution_with_stderr(self):
        """Test execution that produces stderr output."""
        executor = CodeExecutor()
        code = """
import sys
print('stdout message')
print('stderr message', file=sys.stderr)
"""
        result = await executor.execute_python(code)

        assert result.success is True
        assert "stdout message" in result.stdout
        assert "stderr message" in result.stderr

    @pytest.mark.asyncio
    async def test_execution_id_uniqueness(self):
        """Test that execution IDs are unique."""
        executor = CodeExecutor()
        code = "print('test')"

        result1 = await executor.execute_python(code)
        result2 = await executor.execute_python(code)

        assert result1.execution_id != result2.execution_id

    @pytest.mark.asyncio
    async def test_execution_timestamp(self):
        """Test that execution timestamp is set."""
        executor = CodeExecutor()
        code = "print('test')"
        result = await executor.execute_python(code)

        assert result.timestamp is not None
        assert result.timestamp.tzinfo is not None  # Should be timezone-aware


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
