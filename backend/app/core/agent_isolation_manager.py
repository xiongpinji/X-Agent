"""
Agent Isolation Manager - Manages isolated execution environments for agents.

Features:
- Process isolation using multiprocessing
- Thread isolation using threading
- Git worktree isolation (optional)
- Resource limits (CPU, memory)
- Cleanup mechanisms
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

import psutil

logger = logging.getLogger(__name__)


class IsolationType(StrEnum):
    """Types of isolation."""
    PROCESS = "process"
    THREAD = "thread"
    WORKTREE = "worktree"


@dataclass
class ResourceLimits:
    """Resource limits for isolated environments."""
    max_cpu_percent: float = 80.0
    max_memory_mb: int = 512
    max_open_files: int = 1024
    timeout_seconds: int = 300


@dataclass
class IsolatedEnvironment:
    """Represents an isolated execution environment."""
    env_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    isolation_type: IsolationType = IsolationType.THREAD
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    process: mp.Process | None = None
    thread: threading.Thread | None = None
    worktree_path: Path | None = None
    temp_dir: Path | None = None
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    is_active: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "env_id": self.env_id,
            "agent_id": self.agent_id,
            "isolation_type": self.isolation_type.value,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


class AgentIsolationManager:
    """
    Manages isolated execution environments for agents.

    Supports:
    - Process isolation (full isolation, higher overhead)
    - Thread isolation (lighter weight, shared memory)
    - Git worktree isolation (for file system operations)
    - Resource monitoring and limits
    - Automatic cleanup
    """

    def __init__(self, enable_resource_monitoring: bool = True):
        """
        Initialize the isolation manager.

        Args:
            enable_resource_monitoring: Enable resource monitoring
        """
        self.enable_resource_monitoring = enable_resource_monitoring
        self.environments: dict[str, IsolatedEnvironment] = {}
        self.active_processes: dict[str, mp.Process] = {}
        self.active_threads: dict[str, threading.Thread] = {}
        self.worktree_paths: dict[str, Path] = {}
        self.temp_dirs: dict[str, Path] = {}
        self._lock = asyncio.Lock()
        self._cleanup_lock = threading.Lock()

    async def create_isolated_environment(
        self,
        agent_id: str,
        isolation_type: IsolationType = IsolationType.THREAD,
        resource_limits: ResourceLimits | None = None,
    ) -> IsolatedEnvironment:
        """
        Create an isolated execution environment.

        Args:
            agent_id: Agent ID
            isolation_type: Type of isolation
            resource_limits: Resource limits

        Returns:
            IsolatedEnvironment instance
        """
        env_id = str(uuid4())
        resource_limits = resource_limits or ResourceLimits()

        env = IsolatedEnvironment(
            env_id=env_id,
            agent_id=agent_id,
            isolation_type=isolation_type,
            resource_limits=resource_limits,
        )

        async with self._lock:
            self.environments[env_id] = env

        logger.info(
            f"Created isolated environment {env_id} for agent {agent_id} "
            f"with isolation type {isolation_type}"
        )

        try:
            if isolation_type == IsolationType.PROCESS:
                await self._setup_process_isolation(env)
            elif isolation_type == IsolationType.THREAD:
                await self._setup_thread_isolation(env)
            elif isolation_type == IsolationType.WORKTREE:
                await self._setup_worktree_isolation(env)
            else:
                raise ValueError(f"Unknown isolation type: {isolation_type}")

            env.is_active = True

        except Exception as e:
            logger.error(f"Error setting up isolation environment: {e}", exc_info=True)
            await self.cleanup_environment(env_id)
            raise

        return env

    async def _setup_process_isolation(self, env: IsolatedEnvironment) -> None:
        """Setup process isolation."""
        # Create a temporary directory for the process
        temp_dir = Path(tempfile.mkdtemp(prefix=f"agent_{env.agent_id}_"))
        env.temp_dir = temp_dir
        self.temp_dirs[env.env_id] = temp_dir

        logger.debug(f"Created temp directory for process isolation: {temp_dir}")

    async def _setup_thread_isolation(self, env: IsolatedEnvironment) -> None:
        """Setup thread isolation."""
        # Create a temporary directory for thread-local storage
        temp_dir = Path(tempfile.mkdtemp(prefix=f"thread_{env.agent_id}_"))
        env.temp_dir = temp_dir
        self.temp_dirs[env.env_id] = temp_dir

        logger.debug(f"Created temp directory for thread isolation: {temp_dir}")

    async def _setup_worktree_isolation(self, env: IsolatedEnvironment) -> None:
        """Setup git worktree isolation."""
        try:
            # Get current git repository
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                raise RuntimeError("Not in a git repository")

            repo_root = Path(result.stdout.strip())
            worktree_name = f"agent_{env.agent_id}_{env.env_id[:8]}"
            worktree_path = repo_root.parent / worktree_name

            # Create worktree
            subprocess.run(
                ["git", "worktree", "add", str(worktree_path)],
                cwd=repo_root,
                capture_output=True,
                timeout=10,
            )

            env.worktree_path = worktree_path
            self.worktree_paths[env.env_id] = worktree_path

            logger.info(f"Created git worktree at {worktree_path}")

        except Exception as e:
            logger.error(f"Error setting up worktree isolation: {e}", exc_info=True)
            raise

    async def cleanup_environment(self, env_id: str) -> None:
        """
        Cleanup an isolated environment.

        Args:
            env_id: Environment ID
        """
        async with self._lock:
            env = self.environments.get(env_id)
            if not env:
                return

            try:
                # Cleanup process
                if env.process and env.process.is_alive():
                    env.process.terminate()
                    env.process.join(timeout=5)
                    if env.process.is_alive():
                        env.process.kill()

                # Cleanup thread
                if env.thread and env.thread.is_alive():
                    # Threads can't be forcefully terminated
                    logger.warning(f"Thread {env_id} still running during cleanup")

                # Cleanup worktree
                if env.worktree_path:
                    try:
                        subprocess.run(
                            ["git", "worktree", "remove", str(env.worktree_path)],
                            capture_output=True,
                            timeout=10,
                        )
                    except Exception as e:
                        logger.error(f"Error removing worktree: {e}")

                # Cleanup temp directory
                if env.temp_dir and env.temp_dir.exists():
                    shutil.rmtree(env.temp_dir, ignore_errors=True)

                env.is_active = False
                del self.environments[env_id]

                logger.info(f"Cleaned up environment {env_id}")

            except Exception as e:
                logger.error(f"Error during environment cleanup: {e}", exc_info=True)

    async def get_environment(self, env_id: str) -> IsolatedEnvironment | None:
        """Get an environment by ID."""
        async with self._lock:
            return self.environments.get(env_id)

    async def list_environments(self) -> list[IsolatedEnvironment]:
        """List all active environments."""
        async with self._lock:
            return list(self.environments.values())

    async def monitor_resources(self, env_id: str) -> dict[str, Any]:
        """
        Monitor resource usage of an environment.

        Args:
            env_id: Environment ID

        Returns:
            Resource usage information
        """
        if not self.enable_resource_monitoring:
            return {}

        env = await self.get_environment(env_id)
        if not env:
            return {}

        resources = {
            "env_id": env_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            if env.process:
                process = psutil.Process(env.process.pid)
                resources["cpu_percent"] = process.cpu_percent(interval=0.1)
                resources["memory_mb"] = process.memory_info().rss / 1024 / 1024
                resources["num_threads"] = process.num_threads()

                # Check against limits
                if resources["cpu_percent"] > env.resource_limits.max_cpu_percent:
                    logger.warning(
                        f"Environment {env_id} exceeds CPU limit: "
                        f"{resources['cpu_percent']}%"
                    )

                if resources["memory_mb"] > env.resource_limits.max_memory_mb:
                    logger.warning(
                        f"Environment {env_id} exceeds memory limit: "
                        f"{resources['memory_mb']}MB"
                    )

        except Exception as e:
            logger.error(f"Error monitoring resources: {e}")

        return resources

    async def enforce_resource_limits(self, env_id: str) -> bool:
        """
        Enforce resource limits on an environment.

        Args:
            env_id: Environment ID

        Returns:
            True if limits were enforced
        """
        env = await self.get_environment(env_id)
        if not env or not env.process:
            return False

        try:
            resources = await self.monitor_resources(env_id)

            if resources.get("cpu_percent", 0) > env.resource_limits.max_cpu_percent:
                logger.warning(f"Terminating environment {env_id} due to CPU limit")
                env.process.terminate()
                return True

            if resources.get("memory_mb", 0) > env.resource_limits.max_memory_mb:
                logger.warning(f"Terminating environment {env_id} due to memory limit")
                env.process.terminate()
                return True

        except Exception as e:
            logger.error(f"Error enforcing resource limits: {e}")

        return False

    async def cleanup_all(self) -> None:
        """Cleanup all environments."""
        async with self._lock:
            env_ids = list(self.environments.keys())

        for env_id in env_ids:
            await self.cleanup_environment(env_id)

        logger.info("Cleaned up all environments")

    def __del__(self):
        """Cleanup on deletion."""
        try:
            # Try to cleanup synchronously
            for env_id in list(self.environments.keys()):
                env = self.environments[env_id]

                if env.process and env.process.is_alive():
                    env.process.terminate()

                if env.temp_dir and env.temp_dir.exists():
                    shutil.rmtree(env.temp_dir, ignore_errors=True)

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
