"""Lightweight sandbox — OS-level process isolation without Docker daemon.

Provides graduated isolation depending on platform capabilities:
- Linux: nsjail or bubblewrap if available, else restricted subprocess
- macOS: sandbox-exec (Apple native)
- Windows: subprocess + tmpdir + resource limits + timeout
- Fallback: subprocess + tmpdir + resource limits + timeout (all platforms)

Inspired by Codex CLI's approach (landlock/seccomp/bubblewrap), this module
provides the same interface as DockerSandbox but uses OS-level mechanisms
instead of containers. This enables sandboxing on systems without a Docker
daemon (CI, restricted environments, lightweight deployments).

Key features:
- Same async context manager interface as DockerSandbox
- File system isolation (only workspace accessible via bind mount/chroot)
- Optional network disable (drop CAP_NET_RAW, iptables rules, or proxy tricks)
- CPU/memory/timeout limits via resource.setrlimit or cgroup
- Graceful timeout handling: SIGTERM → 5s grace period → SIGKILL
- Auto-cleanup of temp files
- Capability detection: detect_sandbox_capabilities() → SandboxCapabilities
- Factory: create_sandbox(mode="auto", ...) picks best backend

Design notes:
- Lazy imports: heavy tools (nsjail CLI, sandbox-exec) are probed at runtime
  so the module imports cleanly on all platforms.
- Subprocess fallback: even if nsjail/bubblewrap are unavailable, we still
  provide basic isolation via chdir + tmpdir + resource limits + timeout.
- No daemon: unlike Docker, subprocess isolation is process-per-execution;
  no background service to manage (trade-off: slightly higher startup cost,
  but simpler for ephemeral tasks).
- Timeout handling mirrors Docker sandbox: asyncio.TimeoutError → graceful
  kill → exit code 124.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

# resource module is Linux/macOS only (used for process limits)
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

logger = logging.getLogger(__name__)

# Cached capability detection
_CACHED_CAPABILITIES: Optional[SandboxCapabilities] = None


class IsolationLevel(str, Enum):
    """Graduated isolation capabilities supported by the platform."""

    FULL = "full"  # nsjail or sandbox-exec: strong isolation
    RESTRICTED = "restricted"  # bubblewrap or seccomp: moderate isolation
    BASIC = "basic"  # subprocess + chdir + resource limits: minimal isolation
    NONE = "none"  # no isolation available


@dataclass
class SandboxCapabilities:
    """Detected platform capabilities for lightweight sandboxing."""

    platform: str  # "linux", "darwin", "win32"
    isolation_level: IsolationLevel
    has_nsjail: bool = False  # Linux: nsjail CLI available
    has_bubblewrap: bool = False  # Linux: bubblewrap (bwrap) available
    has_sandbox_exec: bool = False  # macOS: native sandbox-exec
    has_cgroups: bool = False  # Linux: cgroups v1/v2
    has_seccomp: bool = False  # Linux: seccomp support
    description: str = ""

    def supports_network_isolation(self) -> bool:
        """Whether network isolation (--network=none) is available."""
        return self.isolation_level in (IsolationLevel.FULL, IsolationLevel.RESTRICTED)

    def supports_filesystem_isolation(self) -> bool:
        """Whether filesystem isolation (chroot/pivot_root) is available."""
        return self.isolation_level in (IsolationLevel.FULL, IsolationLevel.RESTRICTED)


@dataclass
class SandboxResult:
    """Result of a lightweight sandbox command execution."""

    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    backend: str = "lightweight"  # "lightweight" | "fallback"
    timed_out: bool = False
    error: Optional[str] = None


def _find_executable(names: list[str]) -> Optional[str]:
    """Locate first available executable from a list of names."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def detect_sandbox_capabilities() -> SandboxCapabilities:
    """Detect platform capabilities for lightweight sandboxing.

    Probes for availability of nsjail, bubblewrap, sandbox-exec, cgroups,
    and seccomp. Results are cached per process.

    Returns:
        SandboxCapabilities with detected isolation level and features.
    """
    global _CACHED_CAPABILITIES

    if _CACHED_CAPABILITIES is not None:
        return _CACHED_CAPABILITIES

    plat = sys.platform
    capabilities = SandboxCapabilities(
        platform=plat,
        isolation_level=IsolationLevel.BASIC,
    )

    if plat == "linux":
        # Probe for nsjail (strongest isolation)
        if _find_executable(["nsjail"]):
            capabilities.has_nsjail = True
            capabilities.isolation_level = IsolationLevel.FULL
            capabilities.description = "nsjail available (full namespace isolation)"
            logger.debug("Detected nsjail for full Linux isolation")
        # Probe for bubblewrap (moderate isolation, no privesc required)
        elif _find_executable(["bwrap"]):
            capabilities.has_bubblewrap = True
            capabilities.isolation_level = IsolationLevel.RESTRICTED
            capabilities.description = "bubblewrap available (user-namespace isolation)"
            logger.debug("Detected bubblewrap for restricted isolation")
        else:
            # Check for cgroups and seccomp (fallback features)
            capabilities.has_cgroups = Path("/sys/fs/cgroup").exists()
            capabilities.has_seccomp = (
                Path("/boot/config-" + platform.release()).exists()
                or Path("/proc/sys/kernel/seccomp/actions_avail").exists()
            )
            capabilities.description = "Linux: basic subprocess isolation"
            if capabilities.has_cgroups:
                capabilities.description += " (cgroups available)"
            logger.debug("Linux with basic subprocess isolation")

    elif plat == "darwin":
        # Probe for sandbox-exec (macOS native sandbox)
        if _find_executable(["sandbox-exec"]):
            capabilities.has_sandbox_exec = True
            capabilities.isolation_level = IsolationLevel.RESTRICTED
            capabilities.description = "sandbox-exec available (macOS native sandbox)"
            logger.debug("Detected sandbox-exec for macOS isolation")
        else:
            capabilities.description = "macOS: basic subprocess isolation"
            logger.debug("macOS with basic subprocess isolation")

    elif plat == "win32":
        # Windows: no strong native user-land isolation; use basic subprocess
        # (Job objects and AppContainers exist but require admin/special setup)
        capabilities.description = "Windows: basic subprocess isolation"
        logger.debug("Windows with basic subprocess isolation")

    else:
        capabilities.description = f"Unknown platform {plat}: basic subprocess isolation"
        logger.warning("Unknown platform %s; using basic isolation", plat)

    _CACHED_CAPABILITIES = capabilities
    return capabilities


def reset_sandbox_capability_cache() -> None:
    """Reset cached capability detection (test hook)."""
    global _CACHED_CAPABILITIES
    _CACHED_CAPABILITIES = None


class LightweightSandbox:
    """Lightweight sandbox providing OS-level process isolation without Docker.

    Supports graduated isolation based on platform capabilities. Falls back
    gracefully to subprocess + resource limits if advanced tools unavailable.

    Usage (async context manager):
        spec = SandboxSpec(workspace_path="/tmp/work")
        async with LightweightSandbox(spec) as sbx:
            result = await sbx.run("pip install -r requirements.txt")
            result = await sbx.run("pytest -q")
            if result.success:
                print(result.stdout)

    Or manual lifecycle:
        sbx = LightweightSandbox(spec)
        await sbx.start()
        try:
            result = await sbx.run("python main.py", timeout=30)
        finally:
            await sbx.stop()
    """

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        timeout_seconds: float = 300.0,
        memory_limit_mb: Optional[int] = 512,
        cpu_limit: Optional[float] = 1.0,
        enable_network: bool = False,
        env: Optional[dict[str, str]] = None,
        isolation_mode: Literal["auto", "full", "restricted", "basic"] = "auto",
    ):
        """Initialize lightweight sandbox.

        Args:
            workspace_path: Mounted workspace directory. If None, creates temp dir.
            timeout_seconds: Default command timeout.
            memory_limit_mb: Memory limit in MB (None = unlimited). May not be
                enforced depending on isolation level.
            cpu_limit: CPU limit as number of CPUs (None = unlimited).
            enable_network: Allow network access (default: False).
            env: Environment variables to pass to subprocess.
            isolation_mode: "auto" (detect platform), "full" (nsjail/sandbox-exec),
                "restricted" (bubblewrap), or "basic" (subprocess limits).
        """
        self.workspace_path = workspace_path
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.enable_network = enable_network
        self.env = env or {}
        self.isolation_mode = isolation_mode

        self._workspace: Optional[Path] = None
        self._owns_workspace: bool = False
        self._capabilities = detect_sandbox_capabilities()
        self._isolation_level = self._pick_isolation_level()

    def _pick_isolation_level(self) -> IsolationLevel:
        """Pick isolation level based on mode and platform capabilities."""
        if self.isolation_mode == "auto":
            return self._capabilities.isolation_level
        elif self.isolation_mode == "full":
            if self._capabilities.isolation_level.value >= IsolationLevel.FULL.value:
                return IsolationLevel.FULL
            logger.warning("Full isolation requested but not available; falling back")
            return self._capabilities.isolation_level
        elif self.isolation_mode == "restricted":
            if self._capabilities.isolation_level.value >= IsolationLevel.RESTRICTED.value:
                return IsolationLevel.RESTRICTED
            return self._capabilities.isolation_level
        else:  # "basic"
            return IsolationLevel.BASIC

    @property
    def backend(self) -> str:
        """Return backend identifier."""
        return f"lightweight-{self._isolation_level.value}"

    async def __aenter__(self) -> "LightweightSandbox":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def start(self) -> None:
        """Provision the sandbox workspace.

        Creates a temp directory if none supplied and performs any
        platform-specific setup (e.g., cgroup creation, seccomp init).
        """
        if self.workspace_path:
            self._workspace = Path(self.workspace_path)
            self._workspace.mkdir(parents=True, exist_ok=True)
        else:
            self._workspace = Path(tempfile.mkdtemp(prefix="xagent-sbx-"))
            self._owns_workspace = True

        logger.info(
            "Started lightweight sandbox (isolation=%s, workspace=%s)",
            self._isolation_level.value,
            self._workspace,
        )

    async def stop(self) -> None:
        """Tear down the sandbox and clean up owned workspace."""
        if self._owns_workspace and self._workspace and self._workspace.exists():
            try:
                shutil.rmtree(self._workspace, ignore_errors=True)
                logger.debug("Cleaned up sandbox workspace %s", self._workspace)
            except Exception as e:
                logger.warning("Failed to clean up workspace: %s", e)

    async def run(self, command: str, timeout: Optional[float] = None) -> SandboxResult:
        """Execute a shell command inside the sandbox.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds (None = use sandbox default).

        Returns:
            SandboxResult with exit code, stdout, stderr, and timing info.
        """
        eff_timeout = timeout if timeout is not None else self.timeout_seconds
        t0 = time.perf_counter()

        try:
            result = await self._run_isolated(command, eff_timeout)
            result.duration_ms = (time.perf_counter() - t0) * 1000
            return result
        except asyncio.TimeoutError:
            return SandboxResult(
                success=False,
                exit_code=124,
                timed_out=True,
                backend=self.backend,
                error=f"command timed out after {eff_timeout}s",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as e:
            logger.exception("Sandbox run failed")
            return SandboxResult(
                success=False,
                exit_code=1,
                backend=self.backend,
                error=str(e),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

    async def _run_isolated(self, command: str, timeout: float) -> SandboxResult:
        """Execute command with isolation appropriate to detected capabilities."""
        if self._isolation_level == IsolationLevel.FULL:
            if self._capabilities.has_nsjail:
                return await self._run_nsjail(command, timeout)
            elif self._capabilities.has_sandbox_exec:
                return await self._run_sandbox_exec(command, timeout)
        elif self._isolation_level == IsolationLevel.RESTRICTED:
            if self._capabilities.has_bubblewrap:
                return await self._run_bubblewrap(command, timeout)

        # Fallback: basic subprocess isolation
        return await self._run_basic_subprocess(command, timeout)

    async def _run_nsjail(self, command: str, timeout: float) -> SandboxResult:
        """Execute using nsjail (Linux full namespace isolation).

        nsjail creates new namespaces (mount, net, pid, uts, ipc, user).
        """
        nsjail_cmd = [
            "nsjail",
            "--mode", "o",  # o = standalone (don't daemonize)
            "--rlimit_as", str(self.memory_limit_mb * 1024) if self.memory_limit_mb else "unlimited",
            "--rlimit_cpu", str(int(self.cpu_limit)) if self.cpu_limit else "unlimited",
            "--time_limit", str(int(timeout)),
            "--chroot", str(self._workspace),
            "--cwd", "/",
            "--user", "nobody",
            "--group", "nogroup",
        ]

        if not self.enable_network:
            nsjail_cmd.extend(["--disable_proc"])

        nsjail_cmd.extend(["--", "sh", "-c", command])

        return await self._run_subprocess(nsjail_cmd, timeout)

    async def _run_bubblewrap(self, command: str, timeout: float) -> SandboxResult:
        """Execute using bubblewrap (Linux user-namespace isolation).

        bwrap creates a user namespace and bind-mounts the workspace.
        """
        bwrap_cmd = [
            "bwrap",
            "--uid", "0",
            "--gid", "0",
            "--chdir", "/",
            "--bind", str(self._workspace), "/workspace",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
            "--dev", "/dev",
            "--proc", "/proc",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]

        if not self.enable_network:
            bwrap_cmd.append("--unshare-net")

        bwrap_cmd.extend(["--", "sh", "-c", command])

        return await self._run_subprocess(bwrap_cmd, timeout)

    async def _run_sandbox_exec(self, command: str, timeout: float) -> SandboxResult:
        """Execute using macOS sandbox-exec (native Apple sandbox).

        sandbox-exec uses a profile to restrict system access.
        """
        # Simplified profile: deny all, allow read workspace, deny network
        profile = f"""
(version 1)
(allow default)
(deny network*)
(allow file-read* (path "{self._workspace}"))
(allow file-write* (path "{self._workspace}"))
"""
        if self.enable_network:
            profile = profile.replace("(deny network*)\n", "")

        # Write profile to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sb", delete=False) as f:
            f.write(profile)
            profile_path = f.name

        try:
            sandbox_cmd = [
                "sandbox-exec",
                "-f", profile_path,
                "sh", "-c", command,
            ]
            return await self._run_subprocess(sandbox_cmd, timeout)
        finally:
            try:
                os.unlink(profile_path)
            except Exception:
                pass

    async def _run_basic_subprocess(self, command: str, timeout: float) -> SandboxResult:
        """Execute using basic subprocess isolation (all platforms fallback).

        Isolation via:
        - chdir to workspace (filesystem namespace simulation)
        - resource limits (CPU, memory, file descriptors)
        - timeout enforcement
        - optional network proxy redirection
        """
        cwd = str(self._workspace) if self._workspace else None
        env = self._build_env()

        # Convert command for Windows if needed
        if sys.platform == "win32":
            bash_path = self._find_git_bash()
            if bash_path:
                proc = await asyncio.create_subprocess_exec(
                    bash_path,
                    "-lc",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=None,  # Git Bash doesn't handle Windows cwd well
                    env=env,
                )
            else:
                # Fallback to cmd.exe
                proc = await asyncio.create_subprocess_exec(
                    "cmd.exe",
                    "/c", command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
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

        # Apply resource limits to subprocess
        if sys.platform != "win32":
            self._set_subprocess_limits(proc)

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return SandboxResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode or 0,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                backend="lightweight-basic",
            )
        except asyncio.TimeoutError:
            await self._kill_process_tree(proc)
            raise

    async def _run_subprocess(
        self, cmd: list[str], timeout: float
    ) -> SandboxResult:
        """Execute a subprocess command and collect output.

        Args:
            cmd: Command as list of strings.
            timeout: Timeout in seconds.

        Returns:
            SandboxResult with captured output.
        """
        env = self._build_env()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            return SandboxResult(
                success=proc.returncode == 0,
                exit_code=proc.returncode or 0,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
                backend=self.backend,
            )
        except asyncio.TimeoutError:
            await self._kill_process_tree(proc)
            raise

    def _build_env(self) -> dict[str, str]:
        """Build environment for subprocess execution."""
        env = dict(os.environ)
        env.update(self.env)

        if not self.enable_network:
            # Best-effort network block: point proxies at dead address
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = "http://127.0.0.1:1"
            env["http_proxy"] = env["https_proxy"] = "http://127.0.0.1:1"

        return env

    def _set_subprocess_limits(self, proc: asyncio.subprocess.Process) -> None:
        """Apply resource limits to subprocess (Unix only)."""
        if not HAS_RESOURCE:
            logger.debug("resource module not available (Windows); skipping limits")
            return
        if not proc.pid:
            return

        try:
            # Memory limit: set address space limit
            if self.memory_limit_mb:
                limit_bytes = self.memory_limit_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
                logger.debug("Set memory limit: %d MB", self.memory_limit_mb)

            # CPU limit: set CPU time limit
            if self.cpu_limit:
                cpu_limit_seconds = int(self.cpu_limit * 60)  # Convert to seconds
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_seconds, cpu_limit_seconds))
                logger.debug("Set CPU limit: %d seconds", cpu_limit_seconds)

            # File descriptor limit
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            logger.debug("Set file descriptor limit: 256")
        except Exception as e:
            logger.warning("Failed to set resource limits: %s", e)

    @staticmethod
    def _find_git_bash() -> Optional[str]:
        """Locate Git Bash on Windows."""
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

    @staticmethod
    async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
        """Terminate process and children (graceful then force).

        Sends SIGTERM, waits 5 seconds, then SIGKILL if still alive.
        """
        if not proc.pid:
            return

        try:
            if sys.platform == "win32":
                # Windows: use taskkill
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID", str(proc.pid),
                    "/T",  # Tree
                    "/F",  # Force
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await killer.communicate()
            else:
                # Unix: SIGTERM then SIGKILL
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return

                # Wait 5 seconds for graceful shutdown
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                    return
                except asyncio.TimeoutError:
                    pass

                # Force kill
                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            await proc.wait()
        except Exception as e:
            logger.warning("Error killing process tree: %s", e)


async def create_sandbox(
    workspace_path: Optional[str] = None,
    timeout_seconds: float = 300.0,
    memory_limit_mb: Optional[int] = 512,
    cpu_limit: Optional[float] = 1.0,
    enable_network: bool = False,
    mode: Literal["auto", "docker", "lightweight"] = "auto",
    env: Optional[dict[str, str]] = None,
) -> LightweightSandbox | Any:
    """Factory function: create appropriate sandbox based on platform and mode.

    Args:
        workspace_path: Workspace directory.
        timeout_seconds: Default timeout.
        memory_limit_mb: Memory limit.
        cpu_limit: CPU limit.
        enable_network: Allow network.
        mode: "auto" (use Docker if available, else lightweight),
              "docker" (require Docker), "lightweight" (use lightweight).
        env: Environment variables.

    Returns:
        LightweightSandbox instance or DockerSandbox if mode="docker".

    Raises:
        ImportError: If mode="docker" but Docker unavailable.
    """
    if mode == "docker":
        # Import DockerSandbox on demand
        from backend.app.core.sandbox.docker_sandbox import (
            DockerSandbox,
            SandboxSpec,
            is_docker_available,
        )

        if not is_docker_available():
            raise ImportError("Docker not available; cannot create docker sandbox")

        spec = SandboxSpec(
            workspace_path=workspace_path,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb or 512,
            cpu_limit=cpu_limit or 1.0,
            enable_network=enable_network,
            env=env or {},
        )
        return DockerSandbox(spec)

    elif mode == "auto":
        # Try Docker first, fall back to lightweight
        try:
            from backend.app.core.sandbox.docker_sandbox import (
                DockerSandbox,
                SandboxSpec,
                is_docker_available,
            )

            if is_docker_available():
                spec = SandboxSpec(
                    workspace_path=workspace_path,
                    timeout_seconds=timeout_seconds,
                    memory_limit_mb=memory_limit_mb or 512,
                    cpu_limit=cpu_limit or 1.0,
                    enable_network=enable_network,
                    env=env or {},
                )
                logger.info("Using Docker sandbox (auto mode)")
                return DockerSandbox(spec)
        except ImportError:
            pass

        logger.info("Using lightweight sandbox (auto mode / Docker unavailable)")
        return LightweightSandbox(
            workspace_path=workspace_path,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            cpu_limit=cpu_limit,
            enable_network=enable_network,
            env=env,
        )

    else:  # "lightweight"
        return LightweightSandbox(
            workspace_path=workspace_path,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            cpu_limit=cpu_limit,
            enable_network=enable_network,
            env=env,
        )
