"""Container cache & reuse pool for the Docker sandbox backend.

Aligns with Codex's container-caching speedups: instead of paying
image-pull + container-create cost per task, we

1. pre-pull sandbox images once (XAGENT_SANDBOX_PRE_PULL=1, default on);
2. keep a warm pool of long-lived `sleep infinity` containers per image
   (XAGENT_SANDBOX_POOL_SIZE, default 0 = pooling off) that DockerSandbox
   acquires/releases instead of create/remove.

The in-repo backend/app/core/execution/container_pool.py pool is coupled
to the OptimizedExecutionManager (language executors, health-check task)
and cannot be reused here without crossing module scope, so this module
implements a lean, sandbox-local pool with the same acquire/release ideas.

Pool containers share one mounted workspace per image (pooled containers
cannot carry per-task host mounts); commands run in /workspace as usual.
Between acquisitions a best-effort reset (`sh -c 'rm -rf /workspace/*'`)
keeps reuse clean.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENV_POOL_SIZE = "XAGENT_SANDBOX_POOL_SIZE"
ENV_PRE_PULL = "XAGENT_SANDBOX_PRE_PULL"
ENV_POOL_MAX = "XAGENT_SANDBOX_POOL_MAX"


def pool_size_from_env() -> int:
    try:
        return max(0, int(os.environ.get(ENV_POOL_SIZE, "0")))
    except ValueError:
        return 0


def pool_max_from_env(default: int) -> int:
    try:
        return max(default, int(os.environ.get(ENV_POOL_MAX, str(default * 2))))
    except ValueError:
        return default * 2


def pre_pull_enabled() -> bool:
    return os.environ.get(ENV_PRE_PULL, "1").strip().lower() not in ("0", "false", "no")


@dataclass
class PooledContainer:
    container_id: str
    in_use: bool = False
    uses: int = 0
    created_at: float = field(default_factory=time.monotonic)


class DockerContainerPool:
    """Warm container pool for one image. Async-safe acquire/release.

    `client_factory` allows tests to inject a fake docker client
    (must expose .images.pull / .containers.run / .containers.get).
    """

    def __init__(
        self,
        image: str,
        *,
        warm_size: int = 2,
        max_size: int | None = None,
        pre_pull: bool | None = None,
        container_kwargs: dict[str, Any] | None = None,
        client_factory: Callable[[], Any] | None = None,
    ):
        self.image = image
        self.warm_size = warm_size
        self.max_size = max_size if max_size is not None else pool_max_from_env(max(warm_size, 1))
        self.pre_pull = pre_pull_enabled() if pre_pull is None else pre_pull
        self._container_kwargs = container_kwargs or {}
        self._client_factory = client_factory
        self._client: Any = None
        self._idle: list[PooledContainer] = []
        self._all: dict[str, PooledContainer] = {}
        self._lock = asyncio.Lock()
        self._workspace: Path | None = None
        self._image_pulled = False
        self.stats = {"hits": 0, "misses": 0, "pre_pulls": 0}

    # -- docker plumbing -------------------------------------------------
    def _get_client(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                import docker  # type: ignore

                self._client = docker.from_env()
        return self._client

    def _pull_image_sync(self) -> None:
        client = self._get_client()
        try:
            client.images.get(self.image)  # type: ignore[attr-defined]
            self._image_pulled = True
            return
        except Exception:
            pass
        logger.info("Pre-pulling sandbox image %s ...", self.image)
        client.images.pull(self.image)
        self._image_pulled = True
        self.stats["pre_pulls"] += 1

    def _create_container_sync(self) -> str:
        client = self._get_client()
        kwargs = {
            "image": self.image,
            "command": "sleep infinity",
            "detach": True,
            "remove": False,
            "working_dir": "/workspace",
            "name": f"xagent-pool-{uuid.uuid4().hex[:8]}",
            **self._container_kwargs,
        }
        if self._workspace is not None and "volumes" not in kwargs:
            kwargs["volumes"] = {str(self._workspace): {"bind": "/workspace", "mode": "rw"}}
        container = client.containers.run(**kwargs)
        return container.id

    def _remove_container_sync(self, container_id: str) -> None:
        try:
            self._get_client().containers.get(container_id).remove(force=True)
        except Exception as e:
            logger.warning("Pool: failed to remove container %s: %s", container_id[:12], e)

    def _reset_container_sync(self, container_id: str) -> None:
        """Best-effort cleanup between reuses."""
        try:
            self._get_client().containers.get(container_id).exec_run(
                cmd=["sh", "-c", "rm -rf /workspace/* /workspace/.[!.]* 2>/dev/null || true"],
                workdir="/workspace",
            )
        except Exception as e:
            logger.warning("Pool: reset of %s failed: %s", container_id[:12], e)

    # -- lifecycle -------------------------------------------------------
    async def initialize(self, workspace_path: str | None = None) -> None:
        """Pre-pull the image and warm `warm_size` containers."""
        if workspace_path:
            self._workspace = Path(workspace_path)
            self._workspace.mkdir(parents=True, exist_ok=True)
        elif self._workspace is None:
            self._workspace = Path(tempfile.mkdtemp(prefix=f"xagent-pool-{self.image.replace(':', '-')}-"))
        if self.pre_pull:
            await asyncio.to_thread(self._pull_image_sync)
        for _ in range(self.warm_size):
            cid = await asyncio.to_thread(self._create_container_sync)
            entry = PooledContainer(container_id=cid)
            self._idle.append(entry)
            self._all[cid] = entry
        logger.info(
            "Container pool ready for %s: %d warm containers", self.image, len(self._idle)
        )

    async def acquire(self) -> str | None:
        """Get a container id from the pool, creating one up to max_size.

        Returns None when the pool is exhausted (caller should fall back to
        its own create/remove path).
        """
        async with self._lock:
            if self._idle:
                entry = self._idle.pop()
                entry.in_use = True
                entry.uses += 1
                self.stats["hits"] += 1
                logger.debug("Pool hit: reusing %s (uses=%d)", entry.container_id[:12], entry.uses)
                return entry.container_id
            if len(self._all) < self.max_size:
                self.stats["misses"] += 1
            else:
                self.stats["misses"] += 1
                return None
        cid = await asyncio.to_thread(self._create_container_sync)
        async with self._lock:
            entry = PooledContainer(container_id=cid, in_use=True, uses=1)
            self._all[cid] = entry
        return cid

    async def release(self, container_id: str) -> None:
        """Return a container to the pool (reset + mark idle)."""
        await asyncio.to_thread(self._reset_container_sync, container_id)
        async with self._lock:
            entry = self._all.get(container_id)
            if entry is None:
                return
            entry.in_use = False
            self._idle.append(entry)

    async def discard(self, container_id: str) -> None:
        """Remove a broken container from the pool permanently."""
        async with self._lock:
            entry = self._all.pop(container_id, None)
            if entry in self._idle:
                self._idle.remove(entry)
        if entry is not None:
            await asyncio.to_thread(self._remove_container_sync, container_id)

    async def shutdown(self) -> None:
        """Remove every pooled container."""
        async with self._lock:
            ids = list(self._all)
            self._all.clear()
            self._idle.clear()
        for cid in ids:
            await asyncio.to_thread(self._remove_container_sync, cid)
        logger.info("Container pool for %s shut down (%d removed)", self.image, len(ids))


# Shared pools keyed by image so all sandboxes in the process reuse them.
_pools: dict[str, DockerContainerPool] = {}
_pools_lock = asyncio.Lock()


async def get_container_pool(image: str, *, client_factory: Callable[[], Any] | None = None) -> DockerContainerPool:
    """Get or lazily initialize the shared pool for `image`."""
    async with _pools_lock:
        pool = _pools.get(image)
        if pool is None:
            pool = DockerContainerPool(
                image,
                warm_size=pool_size_from_env(),
                client_factory=client_factory,
            )
            _pools[image] = pool
    if not pool._all and not pool._image_pulled:
        await pool.initialize()
    return pool


async def shutdown_container_pools() -> None:
    async with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
    for pool in pools:
        await pool.shutdown()


def reset_container_pools() -> None:
    """Test hook: drop pool registry without touching docker."""
    _pools.clear()
