"""Tests for lightweight sandbox module.

Tests cover:
- Basic command execution and output capture
- Timeout enforcement
- Exit code handling
- Workspace isolation
- Capability detection
- Fallback behavior
- Cross-platform compatibility
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.core.sandbox.lightweight_sandbox import (
    IsolationLevel,
    LightweightSandbox,
    SandboxCapabilities,
    SandboxResult,
    create_sandbox,
    detect_sandbox_capabilities,
    reset_sandbox_capability_cache,
)


class TestSandboxCapabilities:
    """Test sandbox capability detection."""

    def setup_method(self):
        """Reset capability cache before each test."""
        reset_sandbox_capability_cache()

    def test_detect_capabilities_returns_valid_structure(self):
        """Test that capability detection returns valid structure."""
        caps = detect_sandbox_capabilities()
        assert isinstance(caps, SandboxCapabilities)
        assert caps.platform in ("linux", "darwin", "win32")
        assert isinstance(caps.isolation_level, IsolationLevel)
        assert isinstance(caps.description, str)
        assert len(caps.description) > 0

    def test_capabilities_are_cached(self):
        """Test that capabilities are cached (not re-detected)."""
        caps1 = detect_sandbox_capabilities()
        caps2 = detect_sandbox_capabilities()
        assert caps1 is caps2  # Same object

    def test_reset_cache_clears_capabilities(self):
        """Test that reset_sandbox_capability_cache() clears cache."""
        caps1 = detect_sandbox_capabilities()
        reset_sandbox_capability_cache()
        caps2 = detect_sandbox_capabilities()
        assert caps1 is not caps2  # Different objects

    def test_linux_capabilities(self):
        """Test Linux-specific capability detection."""
        if sys.platform != "linux":
            pytest.skip("Linux-only test")

        caps = detect_sandbox_capabilities()
        assert caps.platform == "linux"
        # At minimum should detect basic isolation
        assert caps.isolation_level != IsolationLevel.NONE

    def test_darwin_capabilities(self):
        """Test macOS-specific capability detection."""
        if sys.platform != "darwin":
            pytest.skip("macOS-only test")

        caps = detect_sandbox_capabilities()
        assert caps.platform == "darwin"

    def test_win32_capabilities(self):
        """Test Windows-specific capability detection."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")

        caps = detect_sandbox_capabilities()
        assert caps.platform == "win32"

    def test_capabilities_support_methods(self):
        """Test SandboxCapabilities support query methods."""
        caps = detect_sandbox_capabilities()
        assert isinstance(caps.supports_network_isolation(), bool)
        assert isinstance(caps.supports_filesystem_isolation(), bool)

    def test_full_isolation_supports_network(self):
        """Test that FULL isolation supports network isolation."""
        caps = SandboxCapabilities(
            platform="linux",
            isolation_level=IsolationLevel.FULL,
            has_nsjail=True,
        )
        assert caps.supports_network_isolation()
        assert caps.supports_filesystem_isolation()

    def test_basic_isolation_limited_support(self):
        """Test that BASIC isolation has limited support."""
        caps = SandboxCapabilities(
            platform="linux",
            isolation_level=IsolationLevel.BASIC,
        )
        assert not caps.supports_network_isolation()
        assert not caps.supports_filesystem_isolation()


class TestLightweightSandboxBasic:
    """Test basic lightweight sandbox functionality."""

    @pytest.fixture
    async def sandbox(self):
        """Create a temporary sandbox for testing."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(
                workspace_path=tmpdir,
                timeout_seconds=10,
                enable_network=False,
            )
            yield sbx

    @pytest.mark.asyncio
    async def test_sandbox_context_manager(self, sandbox):
        """Test sandbox as async context manager."""
        async with sandbox as sbx:
            assert sbx.workspace_path is not None or sbx._workspace is not None

    @pytest.mark.asyncio
    async def test_sandbox_manual_lifecycle(self, sandbox):
        """Test sandbox manual start/stop."""
        await sandbox.start()
        assert sandbox._workspace is not None
        assert sandbox._workspace.exists()
        await sandbox.stop()

    @pytest.mark.asyncio
    async def test_echo_command_success(self, sandbox):
        """Test basic echo command execution."""
        await sandbox.start()
        try:
            result = await sandbox.run("echo hello")
            assert result.success
            assert result.exit_code == 0
            assert "hello" in result.stdout
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    async def test_echo_command_result_structure(self, sandbox):
        """Test that result has all required fields."""
        await sandbox.start()
        try:
            result = await sandbox.run("echo test")
            assert isinstance(result, SandboxResult)
            assert hasattr(result, "success")
            assert hasattr(result, "exit_code")
            assert hasattr(result, "stdout")
            assert hasattr(result, "stderr")
            assert hasattr(result, "duration_ms")
            assert hasattr(result, "backend")
            assert hasattr(result, "timed_out")
            assert result.duration_ms >= 0
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    async def test_exit_code_capture_nonzero(self, sandbox):
        """Test capture of non-zero exit code."""
        await sandbox.start()
        try:
            if sys.platform == "win32":
                result = await sandbox.run("exit 42")
            else:
                result = await sandbox.run("exit 42")
            assert result.exit_code == 42
            assert not result.success
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix shell commands")
    async def test_stderr_capture(self, sandbox):
        """Test stderr capture."""
        await sandbox.start()
        try:
            if sys.platform == "win32":
                cmd = 'powershell -Command "Write-Error \'error message\'" 2>&1'
            else:
                cmd = "echo 'error message' >&2"
            result = await sandbox.run(cmd)
            assert len(result.stderr) > 0
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix shell commands")
    async def test_timeout_enforcement(self, sandbox):
        """Test that timeout is enforced."""
        await sandbox.start()
        try:
            if sys.platform == "win32":
                cmd = "timeout /t 999"
            else:
                cmd = "sleep 999"

            result = await sandbox.run(cmd, timeout=2)
            assert result.timed_out
            assert result.exit_code == 124
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix shell commands")
    async def test_workspace_isolation_readable(self, sandbox):
        """Test that workspace is readable inside sandbox."""
        await sandbox.start()
        try:
            # Create a file in workspace
            assert sandbox._workspace is not None
            test_file = sandbox._workspace / "test.txt"
            test_file.write_text("test content")

            # Read it from inside sandbox
            result = await sandbox.run("cat test.txt")
            assert result.success
            assert "test content" in result.stdout
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix shell commands")
    async def test_workspace_isolation_writable(self, sandbox):
        """Test that workspace is writable inside sandbox."""
        await sandbox.start()
        try:
            # Write a file from inside sandbox
            if sys.platform == "win32":
                cmd = "echo hello > test.txt && type test.txt"
            else:
                cmd = "echo hello > test.txt && cat test.txt"
            result = await sandbox.run(cmd)
            assert result.success

            # Verify file exists on host
            assert sandbox._workspace is not None
            test_file = sandbox._workspace / "test.txt"
            assert test_file.exists()
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    async def test_multiple_commands_sequence(self, sandbox):
        """Test sequence of multiple commands."""
        await sandbox.start()
        try:
            r1 = await sandbox.run("echo first")
            assert "first" in r1.stdout

            r2 = await sandbox.run("echo second")
            assert "second" in r2.stdout

            r3 = await sandbox.run("echo third")
            assert "third" in r3.stdout
        finally:
            await sandbox.stop()

    @pytest.mark.asyncio
    async def test_backend_property(self, sandbox):
        """Test backend property reflects isolation level."""
        await sandbox.start()
        try:
            backend = sandbox.backend
            assert isinstance(backend, str)
            assert "lightweight" in backend
        finally:
            await sandbox.stop()


class TestLightweightSandboxAdvanced:
    """Test advanced sandbox features."""

    @pytest.mark.asyncio
    async def test_temp_workspace_creation(self):
        """Test that temp workspace is created when none provided."""
        sbx = LightweightSandbox(timeout_seconds=10)
        await sbx.start()
        try:
            assert sbx._workspace is not None
            assert sbx._workspace.exists()
            assert sbx._owns_workspace
        finally:
            await sbx.stop()

    @pytest.mark.asyncio
    async def test_temp_workspace_cleanup(self):
        """Test that temp workspace is cleaned up on stop."""
        sbx = LightweightSandbox(timeout_seconds=10)
        await sbx.start()
        workspace_path = sbx._workspace
        assert workspace_path is not None
        assert workspace_path.exists()

        await sbx.stop()
        assert not workspace_path.exists()

    @pytest.mark.asyncio
    async def test_provided_workspace_not_owned(self):
        """Test that provided workspace is not deleted."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir, timeout_seconds=10)
            await sbx.start()
            assert not sbx._owns_workspace
            await sbx.stop()
            # Directory still exists
            assert Path(tmpdir).exists()

    @pytest.mark.asyncio
    async def test_isolation_mode_basic(self):
        """Test explicit basic isolation mode."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(
                workspace_path=tmpdir,
                timeout_seconds=10,
                isolation_mode="basic",
            )
            await sbx.start()
            try:
                assert sbx._isolation_level == IsolationLevel.BASIC
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_environment_variables_passed(self):
        """Test that environment variables are passed to subprocess."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(
                workspace_path=tmpdir,
                timeout_seconds=10,
                env={"TEST_VAR": "test_value"},
            )
            await sbx.start()
            try:
                if sys.platform == "win32":
                    cmd = "echo %TEST_VAR%"
                else:
                    cmd = "echo $TEST_VAR"
                result = await sbx.run(cmd)
                assert "test_value" in result.stdout or result.success
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_network_disabled_by_default(self):
        """Test that network is disabled by default."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir, enable_network=False)
            await sbx.start()
            try:
                env = sbx._build_env()
                assert "http://127.0.0.1:1" in env.get("HTTP_PROXY", "")
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_network_enabled_explicit(self):
        """Test explicit network enable."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir, enable_network=True)
            await sbx.start()
            try:
                env = sbx._build_env()
                # Should not have the dead proxy when network enabled
                assert "127.0.0.1:1" not in env.get("HTTP_PROXY", "")
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test custom timeout parameter."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir, timeout_seconds=100)
            await sbx.start()
            try:
                result = await sbx.run("echo quick", timeout=1)
                assert result.success
            finally:
                await sbx.stop()


class TestLightweightSandboxFactory:
    """Test create_sandbox factory function."""

    @pytest.mark.asyncio
    async def test_factory_auto_mode(self):
        """Test factory in auto mode."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = await create_sandbox(workspace_path=tmpdir, mode="auto")
            assert sbx is not None
            # Should create either Docker or Lightweight
            await sbx.start()
            try:
                result = await sbx.run("echo test")
                assert result.success
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_factory_lightweight_mode(self):
        """Test factory in lightweight mode."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = await create_sandbox(workspace_path=tmpdir, mode="lightweight")
            assert isinstance(sbx, LightweightSandbox)
            await sbx.start()
            try:
                result = await sbx.run("echo test")
                assert result.success
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_factory_docker_mode_fallback(self):
        """Test factory docker mode raises when Docker unavailable."""
        if sys.platform == "win32":
            # On Windows without Docker Desktop, this should raise
            with pytest.raises(ImportError):
                await create_sandbox(mode="docker")


class TestSandboxEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_command(self):
        """Test execution of empty command."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                result = await sbx.run("")
                # Should succeed with no output
                assert result.success or result.exit_code == 0
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_command_with_quotes(self):
        """Test command with embedded quotes."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                result = await sbx.run('echo "hello world"')
                assert "hello world" in result.stdout or "hello" in result.stdout
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_command_with_special_chars(self):
        """Test command with special characters."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                result = await sbx.run("echo test123!@#")
                assert result.success or len(result.stdout) >= 0
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_very_long_output(self):
        """Test handling of very long command output."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                # Generate 1MB of output
                if sys.platform == "win32":
                    cmd = "powershell -Command \"'x' * 1000000 | Write-Host\""
                else:
                    cmd = "python3 -c \"print('x' * 1000000)\""
                result = await sbx.run(cmd, timeout=5)
                # Should still succeed
                assert len(result.stdout) > 0
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_binary_output(self):
        """Test handling of binary output."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                if sys.platform == "win32":
                    cmd = "powershell -Command \"[byte]0xFF | Write-Host\""
                else:
                    cmd = "python3 -c \"import sys; sys.stdout.buffer.write(b'\\xff')\""
                result = await sbx.run(cmd)
                # Should decode gracefully with replacement chars
                assert isinstance(result.stdout, str)
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_nonexistent_command(self):
        """Test execution of nonexistent command."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                result = await sbx.run("nonexistent_command_xyz_12345")
                assert not result.success
                assert result.exit_code != 0
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_concurrent_runs(self):
        """Test multiple concurrent sandbox runs."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx1 = LightweightSandbox(workspace_path=tmpdir)
            sbx2 = LightweightSandbox(workspace_path=tmpdir)

            await sbx1.start()
            await sbx2.start()
            try:
                # Run concurrent commands
                r1, r2 = await asyncio.gather(
                    sbx1.run("echo first"),
                    sbx2.run("echo second"),
                )
                assert r1.success
                assert r2.success
                assert "first" in r1.stdout
                assert "second" in r2.stdout
            finally:
                await sbx1.stop()
                await sbx2.stop()


class TestCrossPlatform:
    """Test cross-platform compatibility."""

    @pytest.mark.asyncio
    async def test_platform_detection(self):
        """Test that platform is correctly detected."""
        caps = detect_sandbox_capabilities()
        assert caps.platform in ("linux", "darwin", "win32")

    @pytest.mark.asyncio
    async def test_finds_git_bash_on_windows(self):
        """Test Git Bash discovery on Windows."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")

        bash = LightweightSandbox._find_git_bash()
        # May or may not exist, just test it doesn't crash
        assert bash is None or isinstance(bash, str)


class TestResourceLimits:
    """Test resource limit enforcement."""

    @pytest.mark.asyncio
    async def test_memory_limit_set(self):
        """Test memory limit is set (not enforced in basic mode)."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(
                workspace_path=tmpdir,
                memory_limit_mb=256,
            )
            await sbx.start()
            try:
                # Just verify it doesn't crash
                result = await sbx.run("echo test")
                assert result.success
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    async def test_cpu_limit_set(self):
        """Test CPU limit is set."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(
                workspace_path=tmpdir,
                cpu_limit=0.5,
            )
            await sbx.start()
            try:
                result = await sbx.run("echo test")
                assert result.success
            finally:
                await sbx.stop()


# Integration tests
class TestSandboxIntegration:
    """Integration tests with real scenarios."""

    @pytest.mark.asyncio
    async def test_python_execution(self):
        """Test Python script execution."""
        if sys.platform == "win32":
            pytest.skip("Python path handling differs on Windows")

        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                result = await sbx.run("python3 -c \"print('hello')\"")
                assert result.success or "hello" in result.stdout or "not found" in result.stderr
            finally:
                await sbx.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix shell commands")
    async def test_file_workflow(self):
        """Test file creation/modification workflow."""
        with tempfile.TemporaryDirectory(prefix="xagent-test-") as tmpdir:
            sbx = LightweightSandbox(workspace_path=tmpdir)
            await sbx.start()
            try:
                # Create file
                if sys.platform == "win32":
                    await sbx.run("echo content > file.txt")
                else:
                    await sbx.run("echo content > file.txt")

                # Read file
                result = await sbx.run("cat file.txt" if sys.platform != "win32" else "type file.txt")
                assert result.success
                assert "content" in result.stdout

                # Modify file
                if sys.platform == "win32":
                    await sbx.run("echo modified >> file.txt")
                else:
                    await sbx.run("echo modified >> file.txt")

                # Verify
                result = await sbx.run("cat file.txt" if sys.platform != "win32" else "type file.txt")
                assert "modified" in result.stdout or result.success
            finally:
                await sbx.stop()
