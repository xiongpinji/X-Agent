"""Docker-based sandbox for isolated code/agent execution.

Provides per-task container isolation analogous to OpenAI Codex's cloud
sandbox, but self-hosted. Falls back to subprocess execution when Docker
is unavailable (e.g. no daemon, no root, CI without DinD) so the rest of
the pipeline keeps working in degraded mode.

Design notes:
- CLI backend (P1-5): the container path shells out to the `docker` CLI and
  does NOT import the `docker` Python SDK. The SDK is an optional dependency
  that may be absent (offline installs), and when it was missing the old probe
  silently returned False, degrading the sandbox to unisolated subprocess
  execution. `is_docker_available()` now probes the CLI once and caches it.
  (`DockerContainerPool` in container_cache.py still uses the SDK; see
  `is_docker_sdk_available()`.)
- Two backends behind one API: DockerSandbox.run() either spins a real
  container or shells out to a subprocess. Callers don't branch.
- Security defaults: read-only root fs (except the mounted workspace), non-root
  user, no-new-privileges, all capabilities dropped, pids/memory/CPU caps and
  network disabled — all built by `build_container_security_kwargs()`.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import shutil
import subprocess
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

    # ─── P1-5 沙箱硬化（安全默认，可逐项放宽）───────────────────────────────
    # 硬化前实测缺口：仅设置了 mem_limit / nano_cpus / network_mode，缺少
    # 只读根文件系统、非 root 用户、no-new-privileges、capability 降权与
    # pids 限额 —— 容器内进程可改镜像文件系统、可提权、可 fork 炸弹。
    read_only_root: bool = True          # 根 fs 只读；/workspace 单独挂载 rw
    tmpfs_size_mb: int = 64              # /tmp 可写 tmpfs（只读根 fs 下仍需临时空间）
    run_as_user: str | None = "65534:65534"  # nobody:nogroup，非 root
    drop_all_capabilities: bool = True   # cap_drop=ALL
    no_new_privileges: bool = True       # security_opt: no-new-privileges:true
    pids_limit: int = 256                # 防 fork 炸弹


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


def docker_cli_bin() -> str:
    """Path to the ``docker`` CLI binary (``"docker"`` if not resolvable)."""
    return shutil.which("docker") or "docker"


def is_docker_available() -> bool:
    """Probe whether a usable Docker daemon is reachable **via the docker CLI**.

    P1-5: 探测从 Python SDK 改为 **CLI**。原因：``docker>=7.0.0`` 是 optional 依赖，
    可能未安装（本机 pip 离线就是这种情况），而 CLI 由 Docker Desktop 随附。
    旧实现里 SDK 缺失 → 恒返回 False → 沙箱静默退化到 subprocess，**容器硬化
    参数全部形同虚设**。CLI 后端不依赖任何 Python 包，故可用性只应取决于
    「CLI 可执行文件 + 守护进程可达」。Cached after first call.
    """
    global _DOCKER_AVAILABLE
    if _DOCKER_AVAILABLE is not None:
        return _DOCKER_AVAILABLE

    cli = shutil.which("docker")
    if not cli:
        _DOCKER_AVAILABLE = False
        logger.warning(
            "docker CLI not found on PATH; sandbox falls back to the subprocess "
            "backend with NO container isolation."
        )
        return _DOCKER_AVAILABLE

    try:
        proc = subprocess.run(
            [cli, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception as e:  # timeout, permission, OSError
        _DOCKER_AVAILABLE = False
        logger.warning(
            "docker CLI probe failed (%s); sandbox falls back to the subprocess "
            "backend with NO container isolation.",
            e,
        )
        return _DOCKER_AVAILABLE

    if proc.returncode == 0:
        _DOCKER_AVAILABLE = True
        logger.info("Docker CLI + daemon available; sandbox will use container isolation.")
    else:
        _DOCKER_AVAILABLE = False
        logger.warning(
            "docker daemon unreachable (rc=%s: %s); sandbox falls back to the "
            "subprocess backend with NO container isolation.",
            proc.returncode,
            (proc.stderr or b"").decode("utf-8", errors="replace").strip()[:200],
        )
    return _DOCKER_AVAILABLE


def is_docker_sdk_available() -> bool:
    """Probe the **Python SDK** (used by the container pool, not by the sandbox).

    ``DockerSandbox`` 已改造为走 CLI，但 ``DockerContainerPool`` 仍基于 SDK
    （其测试注入的是假 SDK client）。把两者探测分开，避免"CLI 在、SDK 不在"时
    误判池可用。
    """
    try:
        import docker  # type: ignore

        docker.from_env().ping()
        return True
    except Exception:
        return False



def reset_docker_probe() -> None:
    """Reset the cached probe (test hook)."""
    global _DOCKER_AVAILABLE
    _DOCKER_AVAILABLE = None


def build_container_security_kwargs(
    spec: "SandboxSpec", workspace: str | Path | None = None
) -> dict[str, Any]:
    """构造容器创建的隔离参数（P1-5，**单一事实源**）。

    直连路径（``DockerSandbox._docker_start``）与池化路径
    （``ContainerPool._create_container_sync``）共用本函数，避免两处硬化参数漂移
    ——硬化前池化路径的 ``container_kwargs`` 默认为空，等于**完全没有隔离**。

    设计取舍：根文件系统只读 + ``/workspace`` 单独挂载 rw。这样既能让沙箱正常
    读写工作目录，又能阻止进程篡改镜像自带的可执行文件/配置（持久化后门）。
    需要临时可写空间时由 ``/tmp`` 的 tmpfs 提供。
    """
    kwargs: dict[str, Any] = {
        "network_mode": "bridge" if spec.enable_network else "none",
        "mem_limit": f"{spec.memory_limit_mb}m",
        "nano_cpus": int(spec.cpu_limit * 1_000_000_000),
        "working_dir": "/workspace",
    }

    if spec.pids_limit:
        kwargs["pids_limit"] = spec.pids_limit

    if spec.read_only_root:
        kwargs["read_only"] = True
        if spec.tmpfs_size_mb:
            kwargs["tmpfs"] = {"/tmp": f"size={spec.tmpfs_size_mb}m"}

    if spec.run_as_user:
        kwargs["user"] = spec.run_as_user

    if spec.no_new_privileges:
        kwargs["security_opt"] = ["no-new-privileges:true"]

    if spec.drop_all_capabilities:
        kwargs["cap_drop"] = ["ALL"]

    if workspace:
        kwargs["volumes"] = {str(workspace): {"bind": "/workspace", "mode": "rw"}}

    return kwargs


def container_security_kwargs_to_cli(kwargs: dict[str, Any]) -> list[str]:
    """把 ``build_container_security_kwargs()`` 的输出翻译成 ``docker run`` 参数。

    P1-5：这是 **CLI 后端的单一事实源**。生产路径（``DockerSandbox._docker_start``）
    与测试消费的是同一份翻译逻辑，杜绝"生产一套、测试再抄一套"的漂移 —— 一旦
    有人弱化硬化参数，两侧会同时反映出来。
    """
    args: list[str] = []

    if kwargs.get("read_only"):
        args.append("--read-only")

    for target, spec in (kwargs.get("tmpfs") or {}).items():
        args += ["--tmpfs", f"{target}:{spec}"]

    if kwargs.get("user"):
        args += ["--user", str(kwargs["user"])]

    for opt in kwargs.get("security_opt") or []:
        args += ["--security-opt", str(opt)]

    for cap in kwargs.get("cap_drop") or []:
        args += ["--cap-drop", str(cap)]

    if kwargs.get("pids_limit"):
        args += ["--pids-limit", str(kwargs["pids_limit"])]

    args += ["--network", str(kwargs.get("network_mode") or "none")]

    if kwargs.get("mem_limit"):
        args += ["--memory", str(kwargs["mem_limit"])]

    nano_cpus = kwargs.get("nano_cpus")
    if nano_cpus:
        # docker CLI 用小数 CPU 数（--cpus 1.5），SDK 用 nano_cpus 整数。
        args += ["--cpus", f"{int(nano_cpus) / 1_000_000_000:g}"]

    for host, mount in (kwargs.get("volumes") or {}).items():
        if isinstance(mount, dict):
            bind = mount.get("bind")
            mode = mount.get("mode") or "rw"
        else:  # 宽松兼容："host:bind" 字符串形式
            bind, mode = str(mount), "rw"
        if bind:
            # Docker Desktop 接受正斜杠形式的 Windows 路径（D:/a/b）。
            host_posix = str(host).replace("\\", "/")
            args += ["-v", f"{host_posix}:{bind}:{mode}"]

    if kwargs.get("working_dir"):
        args += ["-w", str(kwargs["working_dir"])]

    return args


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

    def __init__(self, spec: SandboxSpec | None = None, *, pool: Any = None):
        self.spec = spec or SandboxSpec()
        self._container_id: str | None = None
        self._client: Any = None
        self._use_docker: bool = is_docker_available()
        self._owns_workspace: bool = False
        self._workspace: Path | None = None
        # Optional DockerContainerPool (container_cache). When set and docker
        # is available, start() acquires a warm container and stop() releases
        # it back instead of create/remove — Codex-style container caching.
        self._pool: Any = pool
        self._pooled: bool = False

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
            # 不用 wait_for 包 communicate：取消该任务在 Linux asyncio 子进程
            # 管道上有竞态（CI xdist 曾致 worker 崩溃）。改为等待超时后 kill
            # 进程再收割输出，communicate 任务本身永不取消。
            communicate_task = asyncio.create_task(proc.communicate())
            done, _ = await asyncio.wait({communicate_task}, timeout=timeout)
            if not done:
                await _kill_process_tree(proc)
                import contextlib

                with contextlib.suppress(Exception):
                    await asyncio.wait_for(communicate_task, timeout=5.0)
                raise TimeoutError(f"Command timed out after {timeout}s")
            stdout_b, stderr_b = communicate_task.result()
        except TimeoutError:
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

    # ----- docker backend (CLI-first; no Python SDK required) -----
    #
    # 容器管理遵循"谁创建谁管理"：
    #   · 专用容器 —— 由本类通过 `docker` CLI 创建/exec/移除，**不需要 Python SDK**；
    #   · 池化容器 —— 由基于 SDK 的 DockerContainerPool 创建，exec/release 沿用其
    #     SDK client（池本身就要求 SDK 可用）。
    # 这样 CLI 后端让沙箱在"无 SDK"环境下也能真正隔离，同时不破坏池化语义。

    async def _docker_start(self) -> None:
        """Start a long-lived container that sleeps; we exec commands into it.

        P1-5：专用容器改用 ``docker run`` **CLI** 创建，不再依赖 ``docker``
        Python SDK。旧实现走 SDK，而 SDK 是 optional 依赖且可能未安装（本机 pip
        离线），导致 ``is_docker_available()`` 恒 False、沙箱静默退化为 subprocess，
        **硬化参数一个都没生效**。CLI 由 Docker Desktop 随附，无需任何 Python 包。
        """
        if self._pool is not None:
            pooled_id = None
            try:
                pooled_id = await self._pool.acquire()
            except Exception as e:
                # 池基于 SDK；SDK 缺失时不应拖垮沙箱，落到 CLI 创建即可。
                logger.warning(
                    "Container pool acquire failed (%s); creating a dedicated container.",
                    e,
                )
            if pooled_id:
                self._container_id = pooled_id
                self._pooled = True
                # 池化容器归 pool 管理，exec 用它自己的 SDK client。
                self._client = getattr(self._pool, "_get_client", lambda: None)()
                logger.info("Reusing pooled sandbox container %s", pooled_id[:12])
                return
            logger.info("Container pool exhausted or unavailable; creating dedicated container")

        self._container_id = await self._create_dedicated_container()
        logger.info("Started sandbox container %s", self._container_id[:12])

    async def _create_dedicated_container(self) -> str:
        """Create a dedicated sandbox container via the ``docker`` CLI.

        隔离参数由单一事实源 ``build_container_security_kwargs`` 构造，再经
        ``container_security_kwargs_to_cli`` 翻译 —— 两处都不复制参数。
        """
        name = f"{self.spec.name_prefix}-{uuid.uuid4().hex[:8]}"
        cmd: list[str] = [docker_cli_bin(), "run", "-d", "--name", name]
        cmd += container_security_kwargs_to_cli(
            build_container_security_kwargs(self.spec, self._workspace)
        )
        for key, value in self.spec.env.items():
            cmd += ["-e", f"{key}={value}"]
        cmd += [self.spec.image, "sleep", "infinity"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                "docker run failed (rc={}): {}".format(
                    proc.returncode,
                    (stderr_b or b"").decode("utf-8", errors="replace").strip()[:500],
                )
            )
        container_id = (stdout_b or b"").decode("utf-8", errors="replace").strip()
        if not container_id:
            raise RuntimeError("docker run produced no container id")
        return container_id

    async def _remove_container(self, container_id: str) -> None:
        """Force-remove a container via the ``docker`` CLI."""
        proc = await asyncio.create_subprocess_exec(
            docker_cli_bin(), "rm", "-f", container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_b = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(
                "Failed to remove container %s: %s",
                container_id,
                (stderr_b or b"").decode("utf-8", errors="replace").strip()[:300],
            )

    async def _docker_run(self, command: str, timeout: float) -> SandboxResult:
        """Exec a command in the running container (SDK for pooled, CLI otherwise)."""
        if not self._container_id:
            raise RuntimeError("sandbox container is not running")
        if self._pooled and self._client is not None:
            return await self._docker_run_sdk(command, timeout)
        return await self._docker_run_cli(command, timeout)

    async def _docker_run_sdk(self, command: str, timeout: float) -> SandboxResult:
        """Exec into a pooled container through the pool's SDK client."""
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

    async def _docker_run_cli(self, command: str, timeout: float) -> SandboxResult:
        """Exec into a dedicated container via ``docker exec`` (no SDK)."""
        cmd = [
            docker_cli_bin(),
            "exec",
            "-w",
            "/workspace",
            self._container_id,
            "sh",
            "-c",
            command,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # 与 _subprocess_run 保持一致：不取消 communicate 任务，超时后先 kill 再收割。
        # （取消 communicate 在 Linux asyncio 子进程管道上有竞态，CI xdist 曾致 worker 崩溃。）
        communicate_task = asyncio.create_task(proc.communicate())
        done, _ = await asyncio.wait({communicate_task}, timeout=timeout)
        if not done:
            # 杀掉 docker exec 客户端；残余的容器内进程受容器 pids_limit / mem_limit
            # 约束，并会在 stop() 移除容器时一并终止。
            await _kill_process_tree(proc)
            import contextlib

            with contextlib.suppress(Exception):
                await asyncio.wait_for(communicate_task, timeout=5.0)
            raise TimeoutError(f"Command timed out after {timeout}s")

        stdout_b, stderr_b = communicate_task.result()
        exit_code = proc.returncode or 0
        return SandboxResult(
            success=exit_code == 0,
            exit_code=exit_code,
            stdout=(stdout_b or b"").decode("utf-8", errors="replace"),
            stderr=(stderr_b or b"").decode("utf-8", errors="replace"),
            backend="docker",
            container_id=self._container_id,
        )

    async def _docker_stop(self) -> None:
        """Stop and remove the container — or release it back to the pool."""
        if self._pooled and self._pool is not None:
            cid = self._container_id
            self._container_id = None
            self._pooled = False
            if cid:
                await self._pool.release(cid)
            return

        cid = self._container_id
        self._container_id = None
        if cid:
            await self._remove_container(cid)


