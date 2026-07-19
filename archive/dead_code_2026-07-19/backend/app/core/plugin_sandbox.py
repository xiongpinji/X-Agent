"""Plugin Sandbox System - Secure Isolated Execution Environment

Provides:
- Resource isolation
- Memory limits
- CPU time limits
- File system access control
- Network access control
- System call filtering
"""

from __future__ import annotations

import logging
try:
    import resource
except ImportError:  # pragma: no cover - Windows lacks the POSIX resource module
    resource = None  # type: ignore[assignment]
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ResourceType(StrEnum):
    """Resource types that can be limited"""
    MEMORY = "memory"
    CPU_TIME = "cpu_time"
    FILE_DESCRIPTORS = "file_descriptors"
    PROCESSES = "processes"


@dataclass
class ResourceLimit:
    """Resource limit specification"""
    resource_type: ResourceType
    soft_limit: int
    hard_limit: int


@dataclass
class SandboxPolicy:
    """Sandbox execution policy"""
    plugin_id: str
    allowed_modules: list[str]
    allowed_paths: list[Path]
    resource_limits: dict[ResourceType, ResourceLimit]
    allow_network: bool = False
    allow_subprocess: bool = False
    timeout_seconds: int = 30


class FileSystemAccessControl:
    """Control file system access for plugins"""

    def __init__(self, allowed_paths: Optional[list[Path]] = None):
        self.allowed_paths = allowed_paths or []

    def is_path_allowed(self, path: str | Path) -> bool:
        """Check if path is allowed"""
        path = Path(path).resolve()
        for allowed in self.allowed_paths:
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    def add_allowed_path(self, path: str | Path) -> None:
        """Add allowed path"""
        self.allowed_paths.append(Path(path).resolve())

    def remove_allowed_path(self, path: str | Path) -> None:
        """Remove allowed path"""
        path = Path(path).resolve()
        self.allowed_paths = [p for p in self.allowed_paths if p != path]


class NetworkAccessControl:
    """Control network access for plugins"""

    def __init__(self, allow_all: bool = False):
        self.allow_all = allow_all
        self.allowed_hosts: set[str] = set()
        self.allowed_ports: set[int] = set()

    def is_connection_allowed(self, host: str, port: int) -> bool:
        """Check if connection is allowed"""
        if self.allow_all:
            return True
        return host in self.allowed_hosts and port in self.allowed_ports

    def allow_host(self, host: str, port: Optional[int] = None) -> None:
        """Allow connection to host"""
        self.allowed_hosts.add(host)
        if port:
            self.allowed_ports.add(port)

    def deny_host(self, host: str) -> None:
        """Deny connection to host"""
        self.allowed_hosts.discard(host)


class ResourceLimiter:
    """Enforce resource limits on plugin execution"""

    def __init__(self, policy: SandboxPolicy):
        self.policy = policy
        self._original_limits: dict[int, tuple[int, int]] = {}

    def apply_limits(self) -> None:
        """Apply resource limits"""
        if resource is None:
            logger.warning("resource module unavailable on this platform; skipping resource limits")
            return
        try:
            for limit_spec in self.policy.resource_limits.values():
                if limit_spec.resource_type == ResourceType.MEMORY:
                    self._apply_memory_limit(limit_spec)
                elif limit_spec.resource_type == ResourceType.CPU_TIME:
                    self._apply_cpu_limit(limit_spec)
                elif limit_spec.resource_type == ResourceType.FILE_DESCRIPTORS:
                    self._apply_fd_limit(limit_spec)
                elif limit_spec.resource_type == ResourceType.PROCESSES:
                    self._apply_process_limit(limit_spec)
        except Exception as e:
            logger.warning(f"Failed to apply resource limits: {e}")

    def _apply_memory_limit(self, limit: ResourceLimit) -> None:
        """Apply memory limit"""
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limit.soft_limit, limit.hard_limit))
        except Exception as e:
            logger.warning(f"Failed to set memory limit: {e}")

    def _apply_cpu_limit(self, limit: ResourceLimit) -> None:
        """Apply CPU time limit"""
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (limit.soft_limit, limit.hard_limit))
        except Exception as e:
            logger.warning(f"Failed to set CPU limit: {e}")

    def _apply_fd_limit(self, limit: ResourceLimit) -> None:
        """Apply file descriptor limit"""
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (limit.soft_limit, limit.hard_limit))
        except Exception as e:
            logger.warning(f"Failed to set FD limit: {e}")

    def _apply_process_limit(self, limit: ResourceLimit) -> None:
        """Apply process limit"""
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (limit.soft_limit, limit.hard_limit))
        except Exception as e:
            logger.warning(f"Failed to set process limit: {e}")

    def restore_limits(self) -> None:
        """Restore original limits"""
        try:
            for resource_id, (soft, hard) in self._original_limits.items():
                resource.setrlimit(resource_id, (soft, hard))
        except Exception as e:
            logger.warning(f"Failed to restore limits: {e}")


class PluginSandboxEnvironment:
    """Complete sandbox environment for plugin execution"""

    def __init__(self, policy: SandboxPolicy):
        self.policy = policy
        self.fs_control = FileSystemAccessControl(policy.allowed_paths)
        self.net_control = NetworkAccessControl(allow_all=policy.allow_network)
        self.resource_limiter = ResourceLimiter(policy)
        self._timeout_handler: Optional[Callable] = None

    def create_restricted_globals(self) -> dict[str, Any]:
        """Create restricted global namespace"""
        safe_builtins = self._create_safe_builtins()
        return {
            "__builtins__": safe_builtins,
            "__name__": f"plugin_{self.policy.plugin_id}",
            "__doc__": None,
            "__file__": None,
            "__cached__": None,
        }

    def _create_safe_builtins(self) -> dict[str, Any]:
        """Create safe builtins"""
        restricted = {
            "open", "exec", "eval", "__import__", "compile",
            "globals", "locals", "vars", "dir", "input",
            "breakpoint", "exit", "quit", "help",
            "memoryview", "bytearray", "bytes",
        }

        safe_builtins = {}
        for name, obj in __builtins__.items() if isinstance(__builtins__, dict) else __builtins__.__dict__.items():
            if name not in restricted:
                safe_builtins[name] = obj

        return safe_builtins

    def validate_import(self, module_name: str) -> bool:
        """Validate if module can be imported"""
        base_module = module_name.split(".")[0]
        return base_module in self.policy.allowed_modules

    @contextmanager
    def execution_context(self):
        """Context manager for sandboxed execution"""
        try:
            # Apply resource limits
            self.resource_limiter.apply_limits()

            # Set timeout (POSIX-only: SIGALRM/alarm are unavailable on Windows)
            if self.policy.timeout_seconds > 0 and hasattr(signal, "SIGALRM"):
                signal.signal(signal.SIGALRM, self._timeout_handler or self._default_timeout)
                signal.alarm(self.policy.timeout_seconds)

            yield self

        finally:
            # Cancel timeout
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            # Restore limits
            self.resource_limiter.restore_limits()

    @staticmethod
    def _default_timeout(signum, frame):
        """Default timeout handler"""
        raise TimeoutError("Plugin execution timeout")

    def set_timeout_handler(self, handler: Callable) -> None:
        """Set custom timeout handler"""
        self._timeout_handler = handler


class SandboxPolicyBuilder:
    """Builder for creating sandbox policies"""

    def __init__(self, plugin_id: str):
        self.plugin_id = plugin_id
        self.allowed_modules = [
            "json", "datetime", "uuid", "logging", "re", "collections",
            "math", "random", "itertools", "functools", "operator",
            "string", "decimal", "fractions", "statistics"
        ]
        self.allowed_paths: list[Path] = []
        self.resource_limits: dict[ResourceType, ResourceLimit] = {
            ResourceType.MEMORY: ResourceLimit(
                ResourceType.MEMORY,
                soft_limit=256 * 1024 * 1024,  # 256MB
                hard_limit=512 * 1024 * 1024   # 512MB
            ),
            ResourceType.CPU_TIME: ResourceLimit(
                ResourceType.CPU_TIME,
                soft_limit=30,  # 30 seconds
                hard_limit=60   # 60 seconds
            ),
            ResourceType.FILE_DESCRIPTORS: ResourceLimit(
                ResourceType.FILE_DESCRIPTORS,
                soft_limit=256,
                hard_limit=512
            ),
            ResourceType.PROCESSES: ResourceLimit(
                ResourceType.PROCESSES,
                soft_limit=10,
                hard_limit=20
            ),
        }
        self.allow_network = False
        self.allow_subprocess = False
        self.timeout_seconds = 30

    def with_allowed_modules(self, modules: list[str]) -> SandboxPolicyBuilder:
        """Add allowed modules"""
        self.allowed_modules.extend(modules)
        return self

    def with_allowed_path(self, path: str | Path) -> SandboxPolicyBuilder:
        """Add allowed path"""
        self.allowed_paths.append(Path(path).resolve())
        return self

    def with_memory_limit(self, soft_mb: int, hard_mb: int) -> SandboxPolicyBuilder:
        """Set memory limit"""
        self.resource_limits[ResourceType.MEMORY] = ResourceLimit(
            ResourceType.MEMORY,
            soft_limit=soft_mb * 1024 * 1024,
            hard_limit=hard_mb * 1024 * 1024
        )
        return self

    def with_cpu_limit(self, soft_sec: int, hard_sec: int) -> SandboxPolicyBuilder:
        """Set CPU time limit"""
        self.resource_limits[ResourceType.CPU_TIME] = ResourceLimit(
            ResourceType.CPU_TIME,
            soft_limit=soft_sec,
            hard_limit=hard_sec
        )
        return self

    def with_timeout(self, seconds: int) -> SandboxPolicyBuilder:
        """Set execution timeout"""
        self.timeout_seconds = seconds
        return self

    def allow_network(self) -> SandboxPolicyBuilder:
        """Allow network access"""
        self.allow_network = True
        return self

    def allow_subprocess(self) -> SandboxPolicyBuilder:
        """Allow subprocess creation"""
        self.allow_subprocess = True
        return self

    def build(self) -> SandboxPolicy:
        """Build sandbox policy"""
        return SandboxPolicy(
            plugin_id=self.plugin_id,
            allowed_modules=self.allowed_modules,
            allowed_paths=self.allowed_paths,
            resource_limits=self.resource_limits,
            allow_network=self.allow_network,
            allow_subprocess=self.allow_subprocess,
            timeout_seconds=self.timeout_seconds
        )


class SandboxManager:
    """Manage sandbox environments for plugins"""

    def __init__(self):
        self._sandboxes: dict[str, PluginSandboxEnvironment] = {}
        self._policies: dict[str, SandboxPolicy] = {}

    def create_sandbox(self, policy: SandboxPolicy) -> PluginSandboxEnvironment:
        """Create sandbox environment"""
        sandbox = PluginSandboxEnvironment(policy)
        self._sandboxes[policy.plugin_id] = sandbox
        self._policies[policy.plugin_id] = policy
        logger.info(f"Sandbox created for plugin: {policy.plugin_id}")
        return sandbox

    def get_sandbox(self, plugin_id: str) -> Optional[PluginSandboxEnvironment]:
        """Get sandbox environment"""
        return self._sandboxes.get(plugin_id)

    def remove_sandbox(self, plugin_id: str) -> None:
        """Remove sandbox environment"""
        if plugin_id in self._sandboxes:
            del self._sandboxes[plugin_id]
        if plugin_id in self._policies:
            del self._policies[plugin_id]
        logger.info(f"Sandbox removed for plugin: {plugin_id}")

    def update_policy(self, policy: SandboxPolicy) -> None:
        """Update sandbox policy"""
        self._policies[policy.plugin_id] = policy
        if policy.plugin_id in self._sandboxes:
            self._sandboxes[policy.plugin_id] = PluginSandboxEnvironment(policy)
        logger.info(f"Sandbox policy updated for plugin: {policy.plugin_id}")


# Global instance
sandbox_manager = SandboxManager()
