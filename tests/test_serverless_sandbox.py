"""Tests for serverless sandbox backends (Daytona / Modal) and degradation.

Uses httpx.MockTransport to simulate the remote APIs — no real network.
Covers: create -> execute -> destroy chain, explicit unavailability without
credentials, and graceful degradation to the docker/subprocess chain with
a WARNING when the serverless API fails.
"""

from __future__ import annotations

import json
import logging

import pytest

httpx = pytest.importorskip("httpx")

from backend.app.core.sandbox.docker_sandbox import SandboxSpec
from backend.app.core.sandbox.serverless import (
    DaytonaSandbox,
    ModalSandbox,
    ServerlessSandboxError,
    UnifiedSandbox,
    create_sandbox,
)

DAYTONA_ENV = {
    "XAGENT_DAYTONA_API_KEY": "dy-test-key",
    "XAGENT_DAYTONA_API_URL": "https://daytona.mock",
}
MODAL_ENV = {
    "XAGENT_MODAL_TOKEN_ID": "tk-test-id",
    "XAGENT_MODAL_TOKEN_SECRET": "tk-test-secret",
    "XAGENT_MODAL_API_URL": "https://modal.mock",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "XAGENT_SANDBOX_BACKEND",
        "XAGENT_DAYTONA_API_KEY",
        "XAGENT_DAYTONA_API_URL",
        "XAGENT_MODAL_TOKEN_ID",
        "XAGENT_MODAL_TOKEN_SECRET",
        "XAGENT_MODAL_API_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def _daytona_app(calls: list[dict], *, fail_create: bool = False, fail_exec: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"method": request.method, "path": request.url.path,
                      "auth": request.headers.get("authorization")})
        if request.method == "POST" and request.url.path == "/workspace":
            if fail_create:
                return httpx.Response(503, json={"error": "capacity"})
            return httpx.Response(200, json={"id": "ws-123"})
        if request.method == "POST" and request.url.path == "/workspace/ws-123/execute":
            if fail_exec:
                return httpx.Response(500, json={"error": "boom"})
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "exit_code": 0,
                "stdout": f"ran:{body['command']}",
                "stderr": "",
            })
        if request.method == "DELETE" and request.url.path == "/workspace/ws-123":
            return httpx.Response(204)
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


def _modal_app(calls: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append({"method": request.method, "path": request.url.path,
                      "key": request.headers.get("modal-key"),
                      "secret": request.headers.get("modal-secret")})
        if request.method == "POST" and request.url.path == "/sandbox":
            return httpx.Response(200, json={"sandbox_id": "sb-9"})
        if request.method == "POST" and request.url.path == "/sandbox/sb-9/exec":
            body = json.loads(request.content)
            return httpx.Response(200, json={
                "returncode": 0, "stdout": f"modal-ran:{body['command']}", "stderr": "",
            })
        if request.method == "DELETE" and request.url.path == "/sandbox/sb-9":
            return httpx.Response(200, json={"terminated": True})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


class TestCredentialGating:
    def test_daytona_unavailable_without_key(self):
        assert DaytonaSandbox.is_configured() is False
        with pytest.raises(ServerlessSandboxError, match="XAGENT_DAYTONA_API_KEY"):
            DaytonaSandbox(SandboxSpec())

    def test_modal_unavailable_without_token_pair(self, monkeypatch):
        monkeypatch.setenv("XAGENT_MODAL_TOKEN_ID", "only-id")
        assert ModalSandbox.is_configured() is False
        with pytest.raises(ServerlessSandboxError, match="XAGENT_MODAL_TOKEN"):
            ModalSandbox(SandboxSpec())


class TestDaytonaLifecycle:
    @pytest.mark.asyncio
    async def test_create_execute_destroy_chain(self, monkeypatch):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        calls: list[dict] = []
        transport = _daytona_app(calls)
        async with DaytonaSandbox(SandboxSpec(), transport=transport) as sbx:
            result = await sbx.run("pytest -q")
            assert result.success is True
            assert result.stdout == "ran:pytest -q"
            assert result.backend == "daytona"
            assert result.container_id == "ws-123"
        paths = [(c["method"], c["path"]) for c in calls]
        assert ("POST", "/workspace") in paths
        assert ("POST", "/workspace/ws-123/execute") in paths
        assert ("DELETE", "/workspace/ws-123") in paths
        assert all(c["auth"] == "Bearer dy-test-key" for c in calls)

    @pytest.mark.asyncio
    async def test_run_before_start_raises(self, monkeypatch):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        sbx = DaytonaSandbox(SandboxSpec(), transport=_daytona_app([]))
        with pytest.raises(ServerlessSandboxError, match="not started"):
            await sbx.run("echo hi")


class TestModalLifecycle:
    @pytest.mark.asyncio
    async def test_create_execute_destroy_chain(self, monkeypatch):
        for k, v in MODAL_ENV.items():
            monkeypatch.setenv(k, v)
        calls: list[dict] = []
        transport = _modal_app(calls)
        async with ModalSandbox(SandboxSpec(), transport=transport) as sbx:
            result = await sbx.run("python main.py")
            assert result.success is True
            assert result.stdout == "modal-ran:python main.py"
            assert result.backend == "modal"
            assert result.container_id == "sb-9"
        paths = [(c["method"], c["path"]) for c in calls]
        assert ("POST", "/sandbox") in paths
        assert ("POST", "/sandbox/sb-9/exec") in paths
        assert ("DELETE", "/sandbox/sb-9") in paths
        assert all(c["key"] == "tk-test-id" and c["secret"] == "tk-test-secret" for c in calls)


class TestUnifiedSelection:
    def test_auto_prefers_daytona_when_configured(self, monkeypatch):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        assert create_sandbox(SandboxSpec(), backend="auto").backend == "daytona"

    def test_auto_falls_to_modal_without_daytona(self, monkeypatch):
        for k, v in MODAL_ENV.items():
            monkeypatch.setenv(k, v)
        assert create_sandbox(SandboxSpec(), backend="auto").backend == "modal"

    def test_explicit_unconfigured_backend_is_not_selected(self):
        sbx = create_sandbox(SandboxSpec(), backend="daytona")
        assert sbx.backend in ("docker", "subprocess")

    @pytest.mark.asyncio
    async def test_missing_credentials_warns_and_degrades(self, monkeypatch, caplog):
        monkeypatch.setenv("XAGENT_SANDBOX_BACKEND", "daytona")
        with caplog.at_level(logging.WARNING):
            async with create_sandbox(SandboxSpec()) as sbx:
                assert sbx.backend in ("docker", "subprocess")
                result = await sbx.run("echo degraded-ok")
                assert result.success is True
                assert "degraded-ok" in result.stdout
                assert result.backend in ("docker", "subprocess")
        assert any("no credentials" in r.message for r in caplog.records)


class TestDegradationOnApiFailure:
    @pytest.mark.asyncio
    async def test_create_failure_degrades_to_local(self, monkeypatch, caplog):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        calls: list[dict] = []
        transport = _daytona_app(calls, fail_create=True)
        with caplog.at_level(logging.WARNING):
            async with UnifiedSandbox(SandboxSpec(), backend="daytona", transport=transport) as sbx:
                assert sbx.backend in ("docker", "subprocess")
                result = await sbx.run("echo recovered")
                assert result.success is True
                assert "recovered" in result.stdout
        assert any("degrading" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_exec_failure_degrades_and_retries_locally(self, monkeypatch, caplog):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        calls: list[dict] = []
        transport = _daytona_app(calls, fail_exec=True)
        with caplog.at_level(logging.WARNING):
            async with UnifiedSandbox(SandboxSpec(), backend="daytona", transport=transport) as sbx:
                assert sbx.backend == "daytona"
                result = await sbx.run("echo after-failure")
                # serverless exec blew up -> WARNING + local retry, no fake success
                assert result.backend in ("docker", "subprocess")
                assert result.success is True
                assert "after-failure" in result.stdout
                # permanently degraded
                assert sbx.backend in ("docker", "subprocess")
        assert any("degrading" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_unreachable_api_degrades(self, monkeypatch, caplog):
        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)

        def boom(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("dns failure", request=request)

        with caplog.at_level(logging.WARNING):
            async with UnifiedSandbox(
                SandboxSpec(), backend="daytona", transport=httpx.MockTransport(boom)
            ) as sbx:
                result = await sbx.run("echo offline")
                assert result.success is True
                assert "offline" in result.stdout
                assert result.backend in ("docker", "subprocess")
        assert any("degrading" in r.message for r in caplog.records)


class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_orchestrator_uses_unified_sandbox(self, monkeypatch):
        from backend.app.core.sandbox.orchestrator import SandboxOrchestrator
        from backend.app.core.task_queue import TaskQueue

        for k, v in DAYTONA_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("XAGENT_SANDBOX_BACKEND", "daytona")

        calls: list[dict] = []

        # Patch create_sandbox in the orchestrator module to inject transport.
        import backend.app.core.sandbox.orchestrator as orch

        real_create = orch.create_sandbox

        def with_transport(spec):
            return real_create(spec, transport=_daytona_app(calls))

        monkeypatch.setattr(orch, "create_sandbox", with_transport)

        queue = TaskQueue()
        orch_obj = SandboxOrchestrator(queue, handler=lambda sbx, task, res: None)
        task_id = await orch_obj.submit(name="t1", payload={})
        results = await orch_obj.run_until_empty()
        assert results[task_id].success is True
        assert results[task_id].backend == "daytona"
        assert any(c["path"] == "/workspace" for c in calls)
