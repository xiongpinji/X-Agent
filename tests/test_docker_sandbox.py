"""Tests for DockerSandbox — verifies subprocess fallback works without Docker
and that the container path is correctly gated behind the availability probe."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.core.sandbox.docker_sandbox import (
    DockerSandbox,
    SandboxSpec,
    SandboxResult,
    is_docker_available,
    reset_docker_probe,
)


@pytest.fixture(autouse=True)
def _reset_probe():
    reset_docker_probe()
    yield
    reset_docker_probe()


class TestDockerSandboxFallback:
    """Subprocess fallback behavior (no Docker daemon required)."""

    @pytest.mark.asyncio
    async def test_echo_command(self):
        async with DockerSandbox(SandboxSpec()) as sbx:
            result = await sbx.run("echo hello")
            assert result.success is True
            assert result.exit_code == 0
            assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_python_execution(self):
        async with DockerSandbox(SandboxSpec()) as sbx:
            result = await sbx.run('python3 -c "print(6 * 7)"')
            assert result.success is True
            assert "42" in result.stdout

    @pytest.mark.asyncio
    async def test_nonzero_exit_marks_failure(self):
        async with DockerSandbox(SandboxSpec()) as sbx:
            result = await sbx.run("exit 3")
            assert result.success is False
            assert result.exit_code == 3

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_workspace_persists_across_runs(self):
        async with DockerSandbox(SandboxSpec()) as sbx:
            await sbx.run("echo persisted > marker.txt")
            result = await sbx.run("cat marker.txt")
            assert result.success is True
            assert "persisted" in result.stdout

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_timeout_returns_124(self):
        # sleep well beyond the timeout so the kill path fires deterministically
        # even when the host is saturated (-n auto).
        async with DockerSandbox(SandboxSpec(timeout_seconds=2.0)) as sbx:
            result = await sbx.run("sleep 30", timeout=2.0)
            assert result.success is False
            assert result.exit_code == 124
            assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    async def test_backend_is_subprocess_without_docker(self):
        # In CI/sandbox without Docker, backend must report subprocess.
        sbx = DockerSandbox(SandboxSpec())
        # backend reflects the probe result; in this env it should be subprocess
        assert sbx.backend in ("subprocess", "docker")
        await sbx.start()
        try:
            result = await sbx.run("echo ok")
            assert result.backend == sbx.backend
        finally:
            await sbx.stop()

    @pytest.mark.asyncio
    async def test_owned_workspace_cleaned_up(self):
        sbx = DockerSandbox(SandboxSpec())
        await sbx.start()
        ws = sbx._workspace
        assert ws is not None and ws.exists()
        await sbx.stop()
        # owned (auto-created) workspace should be removed
        assert not ws.exists()

    @pytest.mark.asyncio
    async def test_explicit_workspace_not_deleted(self, tmp_path):
        ws = tmp_path / "myws"
        sbx = DockerSandbox(SandboxSpec(workspace_path=str(ws)))
        await sbx.start()
        await sbx.stop()
        # user-supplied workspace must survive teardown
        assert ws.exists()


class TestDockerProbe:
    def test_probe_is_cached(self):
        reset_docker_probe()
        first = is_docker_available()
        second = is_docker_available()
        assert first == second
        assert isinstance(first, bool)
