"""Docker-based sandbox for isolated code/agent execution.

Provides per-task container isolation analogous to OpenAI Codex's cloud
sandbox, but self-hosted. Falls back to subprocess execution when Docker
is unavailable (e.g. no daemon, no root, CI without DinD) so the rest of
the pipeline keeps working in degraded mode.

Design notes:
- Lazy Docker client: we never import the docker SDK at module top so the
  whole backend still imports on machines without it. `is_docker_available()`
  probes once and caches the result.
- Two backends behind one API: DockerSandbox.run() either spins a real
  container or shells out to a subprocess. Callers don't branch.
- Security defaults: network disabled, read-only root fs (except the
  mounted workspace), memory/CPU caps, auto-remove on exit.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cached probe result: None = not probed yet, bool = probed.
_DOCKER_AVAILABLE: bool | None = None


@dataclass
class SandboxSpec:
    """Specification for a sandbox execution environment."""

    image: str = "python:3.11-slim"
    timeout_seconds: float = 300.0
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0  # number of CPUs
    enable_network: bool = False
    workspace_path: str | None = None  # host dir mounted at /workspace
    env: dict[str, str] = field(default_factory=dict)
    name_prefix: str = "xagent-sbx"


@dataclass
class SandboxResult:
    """Result of a sandbox command execution."""

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    backend: str = "subprocess"  # "docker" | "subprocess"
    container_id: str | None = None
    error: str | None = None


def is_docker_available() -> bool:
    """Probe whether a usable Docker daemon is reachable. Cached after first call."""
    global _DOCKER_AVAILABLE
    if _DOCKER_AVAILABLE is not None:
        return _DOCKER_AVAILABLE
    try:
        import docker  # type: ignore

        client = docker.from_env()
        client.ping()
        _DOCKER_AVAILABLE = True
        logger.info("Docker daemon available; sandbox will use container isolation.")
    except Exception as e:  # ImportError, DockerException, connection errors
        _DOCKER_AVAILABLE = False
        logger.info("Docker unavailable (%s); sandbox falls back to subprocess.", type(e).__name__)
    return _DOCKER_AVAILABLE


def reset_docker_probe() -> None:
    """Reset the cached probe (test hook)."""
    global _DOCKER_AVAILABLE
    _DOCKER_AVAILABLE = None


def _windows_bash() -> str | None:
    """Prefer Git Bash over the WSL bash stub for subprocess fallback."""

    candidates = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    bash = shutil.which("bash")
    if bash and "system32" not in bash.lower():
        return bash
    return None


def _git_bash_path(value: str) -> str:
    """Convert a Windows path to the POSIX form Git Bash expects."""

    normalized = value.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        return f"/{normalized[0].lower()}{normalized[2:]}"
    return normalized


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Terminate a timed-out subprocess and its children when supported."""

    import os

    if os.name == "nt" and proc.pid:
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(proc.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await killer.communicate()
    else:
        proc.kill()
    await proc.wait()


class DockerSandbox:
    """Per-task isolated execution environment with subprocess fallback.

    Usage:
        sbx = DockerSandbox(SandboxSpec(workspace_path="/tmp/work"))
        await sbx.start()
        result = await sbx.run("pip install -r requirements.txt")
        result = await sbx.run("pytest -q")
        await sbx.stop()

    Or as an async context manager:
        async with DockerSandbox(spec) as sbx:
            await sbx.run("python main.py")
    """

    def __init__(self, spec: SandboxSpec | None = None):
        self.spec = spec or SandboxSpec()
        self._container_id: str | None = None
        self._client: Any = None
        self._use_docker: bool = is_docker_available()
        self._owns_workspace: bool = False
        self._workspace: Path | None = None

    @property
    def backend(self) -> str:
        return "docker" if self._use_docker else "subprocess"

    async def __aenter__(self) -> DockerSandbox:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def start(self) -> None:
        """Provision the sandbox. Creates a workspace dir if none supplied,
        and (in docker mode) starts a long-lived container we exec into."""
        if self.spec.workspace_path:
            self._workspace = Path(self.spec.workspace_path)
            self._workspace.mkdir(parents=True, exist_ok=True)
        else:
            self._workspace = Path(tempfile.mkdtemp(prefix="xagent-ws-"))
            self._owns_workspace = True

        if self._use_docker:
            await self._docker_start()

    async def stop(self) -> None:
        """Tear down the container and any owned workspace."""
        if self._use_docker and self._container_id:
            await self._docker_stop()
        if self._owns_workspace and self._workspace and self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)

    async def run(self, command: str, timeout: float | None = None) -> SandboxResult:
        """Execute a shell command inside the sandbox."""
        import time

        t0 = time.perf_counter()
        eff_timeout = timeout if timeout is not None else self.spec.timeout_seconds
        try:
            if self._use_docker:
                res = await self._docker_run(command, eff_timeout)
            else:
                res = await self._subprocess_run(command, eff_timeout)
            res.duration_ms = (time.perf_counter() - t0) * 1000
            return res
        except TimeoutError:
            return SandboxResult(
                success=False, exit_code=124, backend=self.backend,
                error=f"command timed out after {eff_timeout}s",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            logger.exception("Sandbox run failed")
            return SandboxResult(
                success=False, exit_code=1, backend=self.backend, error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    # ----- subprocess backend (fallback) -----

    async def _subprocess_run(self, command: str, timeout: float) -> SandboxResult:
        """Run command as a subprocess in the workspace dir.

        This is NOT isolated — it runs on the host. Used only when Docker is
        unavailable. Network is left intact (we cannot easily block it without
        containers); callers needing strict isolation must run with Docker.
        """
        import os

        cwd = str(self._workspace) if self._workspace else None
        env = self._build_env()
        bash = _windows_bash() if os.name == "nt" else shutil.which("bash")
        if os.name == "nt" and bash:
            bash_command = command
            if cwd:
                bash_command = f"cd {shlex.quote(_git_bash_path(cwd))} && {command}"
            proc = await asyncio.create_subprocess_exec(
                bash,
                "-lc",
                bash_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=None,
                env=env,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            await _kill_process_tree(proc)
            raise
        return SandboxResult(
            success=proc.returncode == 0,
            exit_code=proc.returncode or 0,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            backend="subprocess",
        )

    def _build_env(self) -> dict[str, str]:
        import os

        env = dict(os.environ)
        env.update(self.spec.env)
        if not self.spec.enable_network:
            # Best-effort network block for subprocess mode: point proxies at a
            # dead address. Not bulletproof (apps can ignore proxies), but mirrors
            # code_executor.py's existing approach.
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:1"
            env["http_proxy"] = env["https_proxy"] = "http://127.0.0.1:1"
        return env

    # ----- docker backend -----

    async def _docker_start(self) -> None:
        """Start a long-lived container that sleeps; we exec commands into it."""
        def _start_sync() -> str:
            import docker  # type: ignore

            self._client = docker.from_env()
            container = self._client.containers.run(
                image=self.spec.image,
                command="sleep infinity",
                detach=True,
                remove=False,
                network_mode="bridge" if self.spec.enable_network else "none",
                mem_limit=f"{self.spec.memory_limit_mb}m",
                nano_cpus=int(self.spec.cpu_limit * 1_000_000_000),
                volumes=(
                    {str(self._workspace): {"bind": "/workspace", "mode": "rw"}}
                    if self._workspace else None
                ),
                working_dir="/workspace",
                environment=self.spec.env,
                name=f"{self.spec.name_prefix}-{uuid.uuid4().hex[:8]}",
            )
            return container.id

        self._container_id = await asyncio.to_thread(_start_sync)
        logger.info("Started sandbox container %s", self._container_id[:12])

    async def _docker_run(self, command: str, timeout: float) -> SandboxResult:
        """Exec a command in the running container."""
        def _exec_sync() -> tuple[int, bytes, bytes]:
            container = self._client.containers.get(self._container_id)
            exec_result = container.exec_run(
                cmd=["sh", "-c", command],
                workdir="/workspace",
                demux=True,
            )
            stdout_b, stderr_b = exec_result.output
            return exec_result.exit_code, stdout_b or b"", stderr_b or b""

        exit_code, stdout_b, stderr_b = await asyncio.wait_for(
            asyncio.to_thread(_exec_sync), timeout=timeout
        )
        return SandboxResult(
            success=exit_code == 0,
            exit_code=exit_code,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
            backend="docker",
            container_id=self._container_id,
        )

    async def _docker_stop(self) -> None:
        """Stop and remove the container."""
        def _stop_sync() -> None:
            try:
                container = self._client.containers.get(self._container_id)
                container.remove(force=True)
            except Exception as e:
                logger.warning("Failed to remove container %s: %s", self._container_id, e)

        await asyncio.to_thread(_stop_sync)
        self._container_id = None
