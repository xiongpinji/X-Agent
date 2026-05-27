"""Skill Sandbox - Resource-limited execution environment for skills"""

from __future__ import annotations

import asyncio
import logging
import psutil
import signal
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Callable, Coroutine
from pathlib import Path

from .skills_core import SkillMetadata, SkillExecutionContext

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits for skill execution"""
    timeout_seconds: int = 300
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_file_size_mb: int = 100
    allowed_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)
    allow_network: bool = False
    allow_subprocess: bool = False


@dataclass
class SandboxExecutionResult:
    """Result of sandboxed execution"""
    success: bool
    output: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    peak_cpu_percent: float = 0.0


class SkillSandbox:
    """Sandbox for safe skill execution with resource limits"""

    def __init__(self, limits: ResourceLimits | None = None):
        self.limits = limits or ResourceLimits()
        self.active_processes: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        coro: Coroutine,
        context: SkillExecutionContext,
        metadata: SkillMetadata | None = None,
    ) -> SandboxExecutionResult:
        """Execute a coroutine in the sandbox with resource limits"""
        execution_id = context.execution_id
        start_time = datetime.now(UTC)
        start_memory = self._get_memory_usage()
        peak_memory = start_memory
        peak_cpu = 0.0

        try:
            # Use metadata limits if provided
            limits = self.limits
            if metadata:
                limits = ResourceLimits(
                    timeout_seconds=metadata.timeout_seconds,
                    max_memory_mb=metadata.max_memory_mb,
                    max_cpu_percent=metadata.max_cpu_percent,
                )

            # Register the task
            async with self._lock:
                task = asyncio.current_task()
                if task:
                    self.active_processes[execution_id] = task

            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    coro,
                    timeout=limits.timeout_seconds,
                )

                # Monitor resources
                current_memory = self._get_memory_usage()
                peak_memory = max(peak_memory, current_memory)

                end_time = datetime.now(UTC)
                execution_time_ms = (end_time - start_time).total_seconds() * 1000

                return SandboxExecutionResult(
                    success=True,
                    output=result,
                    execution_time_ms=execution_time_ms,
                    peak_memory_mb=peak_memory,
                    peak_cpu_percent=peak_cpu,
                )

            except asyncio.TimeoutError:
                error = f"Skill execution timeout: {limits.timeout_seconds}s exceeded"
                logger.warning(f"{execution_id}: {error}")
                return SandboxExecutionResult(
                    success=False,
                    error=error,
                    execution_time_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
                    peak_memory_mb=peak_memory,
                )

            except Exception as e:
                error = f"Skill execution error: {str(e)}"
                logger.error(f"{execution_id}: {error}", exc_info=True)
                return SandboxExecutionResult(
                    success=False,
                    error=error,
                    execution_time_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
                    peak_memory_mb=peak_memory,
                )

        finally:
            # Cleanup
            async with self._lock:
                if execution_id in self.active_processes:
                    del self.active_processes[execution_id]

    def validate_file_access(self, file_path: str) -> tuple[bool, str | None]:
        """Validate if a file path is allowed"""
        path = Path(file_path).resolve()

        # Check blocked paths
        for blocked in self.limits.blocked_paths:
            blocked_path = Path(blocked).resolve()
            try:
                path.relative_to(blocked_path)
                return False, f"Access to {blocked} is blocked"
            except ValueError:
                pass

        # Check allowed paths (if specified)
        if self.limits.allowed_paths:
            allowed = False
            for allowed_dir in self.limits.allowed_paths:
                allowed_path = Path(allowed_dir).resolve()
                try:
                    path.relative_to(allowed_path)
                    allowed = True
                    break
                except ValueError:
                    pass

            if not allowed:
                return False, f"Access to {file_path} is not allowed"

        return True, None

    def validate_network_access(self, url: str) -> tuple[bool, str | None]:
        """Validate if network access is allowed"""
        if not self.limits.allow_network:
            return False, "Network access is not allowed"
        return True, None

    def validate_subprocess_execution(self, command: str) -> tuple[bool, str | None]:
        """Validate if subprocess execution is allowed"""
        if not self.limits.allow_subprocess:
            return False, "Subprocess execution is not allowed"
        return True, None

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            process = psutil.Process()
            return process.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    async def get_active_executions(self) -> list[str]:
        """Get list of active execution IDs"""
        async with self._lock:
            return list(self.active_processes.keys())

    async def cancel_execution(self, execution_id: str) -> tuple[bool, str | None]:
        """Cancel a running execution"""
        async with self._lock:
            if execution_id not in self.active_processes:
                return False, f"Execution not found: {execution_id}"

            task = self.active_processes[execution_id]
            task.cancel()
            del self.active_processes[execution_id]

            return True, None


class SandboxManager:
    """Manages multiple sandboxes for different skill execution contexts"""

    def __init__(self):
        self.sandboxes: dict[str, SkillSandbox] = {}
        self._lock = asyncio.Lock()

    async def create_sandbox(
        self,
        sandbox_id: str,
        limits: ResourceLimits | None = None,
    ) -> tuple[bool, str | None]:
        """Create a new sandbox"""
        async with self._lock:
            if sandbox_id in self.sandboxes:
                return False, f"Sandbox already exists: {sandbox_id}"

            self.sandboxes[sandbox_id] = SkillSandbox(limits)
            logger.info(f"Created sandbox: {sandbox_id}")
            return True, None

    async def destroy_sandbox(self, sandbox_id: str) -> tuple[bool, str | None]:
        """Destroy a sandbox"""
        async with self._lock:
            if sandbox_id not in self.sandboxes:
                return False, f"Sandbox not found: {sandbox_id}"

            del self.sandboxes[sandbox_id]
            logger.info(f"Destroyed sandbox: {sandbox_id}")
            return True, None

    def get_sandbox(self, sandbox_id: str) -> SkillSandbox | None:
        """Get a sandbox by ID"""
        return self.sandboxes.get(sandbox_id)

    async def execute_in_sandbox(
        self,
        sandbox_id: str,
        coro: Coroutine,
        context: SkillExecutionContext,
        metadata: SkillMetadata | None = None,
    ) -> SandboxExecutionResult:
        """Execute a coroutine in a specific sandbox"""
        sandbox = self.get_sandbox(sandbox_id)
        if sandbox is None:
            return SandboxExecutionResult(
                success=False,
                error=f"Sandbox not found: {sandbox_id}",
            )

        return await sandbox.execute(coro, context, metadata)

    def list_sandboxes(self) -> list[str]:
        """List all sandbox IDs"""
        return list(self.sandboxes.keys())


# Global sandbox manager instance
_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    """Get or create the global sandbox manager"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager


__all__ = [
    "ResourceLimits",
    "SkillSandbox",
    "SandboxManager",
    "SandboxExecutionResult",
    "get_sandbox_manager",
]
