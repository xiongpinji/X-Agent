"""Tests for the Docker container cache / reuse pool (container_cache.py).

Uses an injected fake docker client — no Docker daemon required. Verifies
image pre-pull, warm acquire/release reuse, exhaustion behavior, and that
DockerSandbox releases pooled containers instead of removing them.
"""

from __future__ import annotations

import itertools
import logging

import pytest

from backend.app.core.sandbox.container_cache import (
    DockerContainerPool,
    get_container_pool,
    reset_container_pools,
)
from backend.app.core.sandbox.docker_sandbox import DockerSandbox, SandboxSpec


class FakeExecResult:
    def __init__(self, exit_code=0, output=(b"", b"")):
        self.exit_code = exit_code
        self.output = output


class FakeContainer:
    def __init__(self, cid):
        self.id = cid
        self.removed = False
        self.exec_calls: list[list[str]] = []

    def exec_run(self, cmd, workdir=None, demux=False):
        self.exec_calls.append(cmd)
        if cmd[:2] == ["sh", "-c"] and "rm -rf" in cmd[2]:
            return FakeExecResult(0, (b"", b""))
        return FakeExecResult(0, (b"pooled-out", b""))

    def remove(self, force=False):
        self.removed = True


class FakeContainers:
    def __init__(self):
        self.created: list[FakeContainer] = []
        self._ids = itertools.count(1)

    def run(self, **kwargs):
        c = FakeContainer(f"fake-{next(self._ids)}")
        self.created.append(c)
        return c

    def get(self, cid):
        for c in self.created:
            if c.id == cid:
                return c
        raise KeyError(cid)


class FakeImages:
    def __init__(self):
        self.pulled: list[str] = []
        self.local: set[str] = set()

    def get(self, image):
        if image in self.local:
            return object()
        raise KeyError(image)

    def pull(self, image):
        self.pulled.append(image)
        self.local.add(image)


class FakeDockerClient:
    def __init__(self):
        self.containers = FakeContainers()
        self.images = FakeImages()


@pytest.fixture
def fake_client():
    return FakeDockerClient()


@pytest.fixture(autouse=True)
def _reset_pools():
    reset_container_pools()
    yield
    reset_container_pools()


class TestPrePull:
    @pytest.mark.asyncio
    async def test_initialize_pre_pulls_image_once(self, fake_client, tmp_path):
        pool = DockerContainerPool(
            "python:3.11-slim", warm_size=0, client_factory=lambda: fake_client
        )
        await pool.initialize(workspace_path=str(tmp_path))
        assert fake_client.images.pulled == ["python:3.11-slim"]
        assert pool.stats["pre_pulls"] == 1

    @pytest.mark.asyncio
    async def test_pre_pull_skipped_when_disabled(self, fake_client, tmp_path):
        pool = DockerContainerPool(
            "python:3.11-slim", warm_size=0, pre_pull=False,
            client_factory=lambda: fake_client,
        )
        await pool.initialize(workspace_path=str(tmp_path))
        assert fake_client.images.pulled == []

    @pytest.mark.asyncio
    async def test_pre_pull_skipped_when_image_local(self, fake_client, tmp_path):
        fake_client.images.local.add("python:3.11-slim")
        pool = DockerContainerPool(
            "python:3.11-slim", warm_size=0, client_factory=lambda: fake_client
        )
        await pool.initialize(workspace_path=str(tmp_path))
        assert fake_client.images.pulled == []


class TestReusePool:
    @pytest.mark.asyncio
    async def test_warm_containers_created_on_initialize(self, fake_client, tmp_path):
        pool = DockerContainerPool(
            "img", warm_size=2, client_factory=lambda: fake_client
        )
        await pool.initialize(workspace_path=str(tmp_path))
        assert len(fake_client.containers.created) == 2

    @pytest.mark.asyncio
    async def test_acquire_release_reuses_same_container(self, fake_client, tmp_path):
        pool = DockerContainerPool("img", warm_size=1, client_factory=lambda: fake_client)
        await pool.initialize(workspace_path=str(tmp_path))
        first = await pool.acquire()
        await pool.release(first)
        second = await pool.acquire()
        assert first == second
        assert pool.stats["hits"] == 2
        assert len(fake_client.containers.created) == 1  # no new container created

    @pytest.mark.asyncio
    async def test_release_resets_workspace(self, fake_client, tmp_path):
        pool = DockerContainerPool("img", warm_size=1, client_factory=lambda: fake_client)
        await pool.initialize(workspace_path=str(tmp_path))
        cid = await pool.acquire()
        await pool.release(cid)
        container = fake_client.containers.get(cid)
        assert any("rm -rf" in call[2] for call in container.exec_calls)

    @pytest.mark.asyncio
    async def test_exhausted_pool_returns_none(self, fake_client, tmp_path):
        pool = DockerContainerPool(
            "img", warm_size=1, max_size=1, client_factory=lambda: fake_client
        )
        await pool.initialize(workspace_path=str(tmp_path))
        first = await pool.acquire()
        assert first is not None
        assert await pool.acquire() is None  # at max_size, all in use

    @pytest.mark.asyncio
    async def test_pool_grows_to_max_on_miss(self, fake_client, tmp_path):
        pool = DockerContainerPool(
            "img", warm_size=0, max_size=3, pre_pull=False,
            client_factory=lambda: fake_client,
        )
        await pool.initialize(workspace_path=str(tmp_path))
        a = await pool.acquire()
        b = await pool.acquire()
        assert a != b
        assert len(fake_client.containers.created) == 2
        assert pool.stats["misses"] == 2

    @pytest.mark.asyncio
    async def test_shutdown_removes_all(self, fake_client, tmp_path):
        pool = DockerContainerPool("img", warm_size=2, client_factory=lambda: fake_client)
        await pool.initialize(workspace_path=str(tmp_path))
        await pool.shutdown()
        assert all(c.removed for c in fake_client.containers.created)


class TestSharedRegistry:
    @pytest.mark.asyncio
    async def test_get_container_pool_shares_per_image(self, fake_client, monkeypatch, tmp_path):
        monkeypatch.setenv("XAGENT_SANDBOX_POOL_SIZE", "1")
        monkeypatch.setenv("XAGENT_SANDBOX_PRE_PULL", "0")
        import backend.app.core.sandbox.container_cache as cc

        monkeypatch.setattr(cc, "tempfile", __import__("tempfile"))
        p1 = await get_container_pool("shared-img", client_factory=lambda: fake_client)
        p2 = await get_container_pool("shared-img", client_factory=lambda: fake_client)
        assert p1 is p2
        p3 = await get_container_pool("other-img", client_factory=lambda: fake_client)
        assert p3 is not p1


class TestDockerSandboxPoolIntegration:
    @pytest.mark.asyncio
    async def test_sandbox_acquires_and_releases_pooled_container(
        self, fake_client, tmp_path, monkeypatch, caplog
    ):
        pool = DockerContainerPool("img", warm_size=1, client_factory=lambda: fake_client)
        await pool.initialize(workspace_path=str(tmp_path))

        sbx = DockerSandbox(SandboxSpec(), pool=pool)
        monkeypatch.setattr(sbx, "_use_docker", True)
        with caplog.at_level(logging.INFO):
            await sbx.start()
            assert sbx._pooled is True
            result = await sbx.run("echo hi")
            assert result.backend == "docker"
            assert result.stdout == "pooled-out"
            await sbx.stop()
        container = fake_client.containers.created[0]
        assert container.removed is False  # released, not removed
        assert any("Reusing pooled" in r.message for r in caplog.records)
        # container is back in the idle pool
        assert await pool.acquire() == container.id

    @pytest.mark.asyncio
    async def test_exhausted_pool_falls_back_to_dedicated_container(
        self, fake_client, tmp_path, monkeypatch
    ):
        pool = DockerContainerPool(
            "img", warm_size=1, max_size=1, client_factory=lambda: fake_client
        )
        await pool.initialize(workspace_path=str(tmp_path))
        await pool.acquire()  # drain the only warm container

        sbx = DockerSandbox(SandboxSpec(), pool=pool)
        monkeypatch.setattr(sbx, "_use_docker", True)

        # Dedicated create path needs the real docker import — fake it.
        import sys
        import types

        fake_module = types.SimpleNamespace(from_env=lambda: fake_client)
        monkeypatch.setitem(sys.modules, "docker", fake_module)

        await sbx.start()
        assert sbx._pooled is False  # pool exhausted -> dedicated container
        await sbx.stop()
        dedicated = fake_client.containers.created[-1]
        assert dedicated.removed is True  # non-pooled containers are removed
