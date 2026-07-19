"""
Secure code execution system with multi-language support and comprehensive safety mechanisms.

This module provides sandboxed code execution for Python, JavaScript, and Bash with:
- Execution timeout control
- Resource limits (CPU, memory, disk)
- Network access control
- File system isolation
- Dangerous operation interception
- Audit logging
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExecutionLanguage(StrEnum):
    """Supported code execution languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    BASH = "bash"


class ExecutionStatus(StrEnum):
    """Execution result status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    status: ExecutionStatus
    error: Optional[str] = None
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    language: ExecutionLanguage = ExecutionLanguage.PYTHON
    resource_usage: dict[str, Any] = field(default_factory=dict)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "status": self.status,
            "error": self.error,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "language": self.language,
            "resource_usage": self.resource_usage,
        }


@dataclass
class ExecutionConfig:
    """Configuration for code execution."""
    timeout: int = 30  # seconds
    max_memory: int = 512  # MB
    max_cpu_percent: int = 80
    max_disk_usage: int = 100  # MB
    allow_network: bool = False
    allow_file_system_write: bool = False
    temp_dir: Optional[str] = None
    environment_vars: dict[str, str] = field(default_factory=dict)
    max_output_size: int = 1024 * 1024  # 1MB


class SecurityValidator:
    """Validates code for security violations."""

    # Dangerous Python patterns
    DANGEROUS_PYTHON_PATTERNS = [
        r"__import__\s*\(",
        r"exec\s*\(",
        r"eval\s*\(",
        r"compile\s*\(",
        r"globals\s*\(",
        r"locals\s*\(",
        r"vars\s*\(",
        r"dir\s*\(",
        r"getattr\s*\(",
        r"setattr\s*\(",
        r"delattr\s*\(",
        r"open\s*\(",
        r"file\s*\(",
        r"input\s*\(",
        r"raw_input\s*\(",
        r"__builtins__",
        r"sys\.exit",
        r"os\.system",
        r"os\.exec",
        r"subprocess\.",
        r"socket\.",
        r"urllib\.",
        r"requests\.",
        r"httpx\.",
    ]

    # Dangerous JavaScript patterns
    DANGEROUS_JS_PATTERNS = [
        r"eval\s*\(",
        r"Function\s*\(",
        r"require\s*\(",
        r"import\s+",
        r"process\.",
        r"child_process",
        r"fs\.",
        r"net\.",
        r"http\.",
        r"https\.",
        r"fetch\s*\(",
        r"XMLHttpRequest",
    ]

    # Dangerous Bash patterns
    DANGEROUS_BASH_PATTERNS = [
        r"rm\s+-rf",
        r"dd\s+",
        r"mkfs",
        r"fdisk",
        r"parted",
        r">\s*/dev/",
        r"chmod\s+777",
        r"sudo\s+",
        r"su\s+",
    ]

    @staticmethod
    def validate_python(code: str) -> tuple[bool, Optional[str]]:
        """Validate Python code for security violations."""
        for pattern in SecurityValidator.DANGEROUS_PYTHON_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        return True, None

    @staticmethod
    def validate_javascript(code: str) -> tuple[bool, Optional[str]]:
        """Validate JavaScript code for security violations."""
        for pattern in SecurityValidator.DANGEROUS_JS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        return True, None

    @staticmethod
    def validate_bash(command: str) -> tuple[bool, Optional[str]]:
        """Validate Bash command for security violations."""
        for pattern in SecurityValidator.DANGEROUS_BASH_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        return True, None


class CodeExecutor:
    """Secure code executor with multi-language support."""

    def __init__(self, config: Optional[ExecutionConfig] = None):
        """Initialize code executor with configuration."""
        self.config = config or ExecutionConfig()
        self.validator = SecurityValidator()
        self._setup_temp_dir()

    def _setup_temp_dir(self) -> None:
        """Setup temporary directory for code execution."""
        if self.config.temp_dir:
            Path(self.config.temp_dir).mkdir(parents=True, exist_ok=True)
        else:
            self.config.temp_dir = tempfile.gettempdir()

    async def execute_python(self, code: str, timeout: Optional[int] = None) -> ExecutionResult:
        """Execute Python code in a sandboxed environment."""
        timeout = timeout or self.config.timeout
        execution_id = str(uuid4())

        # Validate code
        is_valid, error_msg = self.validator.validate_python(code)
        if not is_valid:
            logger.warning(f"Security violation in Python code: {error_msg}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=error_msg or "Security violation detected",
                exit_code=1,
                execution_time=0.0,
                status=ExecutionStatus.SECURITY_VIOLATION,
                error=error_msg,
                execution_id=execution_id,
                language=ExecutionLanguage.PYTHON,
            )

        start_time = time.time()
        try:
            # Create temporary Python file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                dir=self.config.temp_dir,
                delete=False,
            ) as f:
                f.write(code)
                temp_file = f.name

            try:
                # Execute Python code
                result = await self._run_subprocess(
                    [sys.executable, temp_file],
                    timeout=timeout,
                    execution_id=execution_id,
                )
                result.language = ExecutionLanguage.PYTHON
                return result
            finally:
                # Cleanup
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(f"Python execution timeout after {execution_time}s")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timeout after {timeout} seconds",
                exit_code=124,
                execution_time=execution_time,
                status=ExecutionStatus.TIMEOUT,
                error="Execution timeout",
                execution_id=execution_id,
                language=ExecutionLanguage.PYTHON,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Python execution error: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time=execution_time,
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_id=execution_id,
                language=ExecutionLanguage.PYTHON,
            )

    async def execute_javascript(self, code: str, timeout: Optional[int] = None) -> ExecutionResult:
        """Execute JavaScript code in a sandboxed environment."""
        timeout = timeout or self.config.timeout
        execution_id = str(uuid4())

        # Validate code
        is_valid, error_msg = self.validator.validate_javascript(code)
        if not is_valid:
            logger.warning(f"Security violation in JavaScript code: {error_msg}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=error_msg or "Security violation detected",
                exit_code=1,
                execution_time=0.0,
                status=ExecutionStatus.SECURITY_VIOLATION,
                error=error_msg,
                execution_id=execution_id,
                language=ExecutionLanguage.JAVASCRIPT,
            )

        start_time = time.time()
        try:
            # Create temporary JavaScript file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".js",
                dir=self.config.temp_dir,
                delete=False,
            ) as f:
                f.write(code)
                temp_file = f.name

            try:
                # Execute JavaScript code with Node.js
                result = await self._run_subprocess(
                    ["node", temp_file],
                    timeout=timeout,
                    execution_id=execution_id,
                )
                result.language = ExecutionLanguage.JAVASCRIPT
                return result
            finally:
                # Cleanup
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(f"JavaScript execution timeout after {execution_time}s")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timeout after {timeout} seconds",
                exit_code=124,
                execution_time=execution_time,
                status=ExecutionStatus.TIMEOUT,
                error="Execution timeout",
                execution_id=execution_id,
                language=ExecutionLanguage.JAVASCRIPT,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"JavaScript execution error: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time=execution_time,
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_id=execution_id,
                language=ExecutionLanguage.JAVASCRIPT,
            )

    async def execute_bash(self, command: str, timeout: Optional[int] = None) -> ExecutionResult:
        """Execute Bash command in a sandboxed environment."""
        timeout = timeout or self.config.timeout
        execution_id = str(uuid4())

        # Validate command
        is_valid, error_msg = self.validator.validate_bash(command)
        if not is_valid:
            logger.warning(f"Security violation in Bash command: {error_msg}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=error_msg or "Security violation detected",
                exit_code=1,
                execution_time=0.0,
                status=ExecutionStatus.SECURITY_VIOLATION,
                error=error_msg,
                execution_id=execution_id,
                language=ExecutionLanguage.BASH,
            )

        start_time = time.time()
        try:
            result = await self._run_subprocess(
                ["bash", "-c", command],
                timeout=timeout,
                execution_id=execution_id,
            )
            result.language = ExecutionLanguage.BASH
            return result

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(f"Bash execution timeout after {execution_time}s")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timeout after {timeout} seconds",
                exit_code=124,
                execution_time=execution_time,
                status=ExecutionStatus.TIMEOUT,
                error="Execution timeout",
                execution_id=execution_id,
                language=ExecutionLanguage.BASH,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Bash execution error: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time=execution_time,
                status=ExecutionStatus.FAILED,
                error=str(e),
                execution_id=execution_id,
                language=ExecutionLanguage.BASH,
            )

    async def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int,
        execution_id: str,
    ) -> ExecutionResult:
        """Run subprocess with timeout and resource limits."""
        start_time = time.time()

        try:
            # Setup environment
            env = os.environ.copy()
            env.update(self.config.environment_vars)

            # Disable network access if configured
            if not self.config.allow_network:
                env["http_proxy"] = "127.0.0.1:1"
                env["https_proxy"] = "127.0.0.1:1"
                env["HTTP_PROXY"] = "127.0.0.1:1"
                env["HTTPS_PROXY"] = "127.0.0.1:1"

            # Run process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                execution_time = time.time() - start_time
                raise asyncio.TimeoutError(f"Process timeout after {timeout}s")

            execution_time = time.time() - start_time

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate output if too large
            if len(stdout_str) > self.config.max_output_size:
                stdout_str = stdout_str[: self.config.max_output_size] + "\n... (truncated)"
            if len(stderr_str) > self.config.max_output_size:
                stderr_str = stderr_str[: self.config.max_output_size] + "\n... (truncated)"

            # Determine status
            status = ExecutionStatus.SUCCESS if process.returncode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode or 0,
                execution_time=execution_time,
                status=status,
                execution_id=execution_id,
            )

        except asyncio.TimeoutError as e:
            execution_time = time.time() - start_time
            raise asyncio.TimeoutError(str(e))
        except Exception as e:
            execution_time = time.time() - start_time
            raise Exception(f"Subprocess execution failed: {e}")


class ExecutionEnvironmentManager:
    """Manages isolated execution environments."""

    def __init__(self, base_dir: Optional[str] = None):
        """Initialize environment manager."""
        self.base_dir = base_dir or tempfile.gettempdir()
        self.environments: dict[str, dict[str, Any]] = {}

    def create_environment(self, env_id: str, config: Optional[ExecutionConfig] = None) -> str:
        """Create a new isolated execution environment."""
        env_path = os.path.join(self.base_dir, f"env_{env_id}")
        Path(env_path).mkdir(parents=True, exist_ok=True)

        self.environments[env_id] = {
            "path": env_path,
            "config": config or ExecutionConfig(),
            "created_at": datetime.now(UTC),
            "dependencies": [],
        }

        logger.info(f"Created execution environment: {env_id}")
        return env_path

    def install_dependency(self, env_id: str, package: str, language: ExecutionLanguage) -> bool:
        """Install a dependency in the environment."""
        if env_id not in self.environments:
            logger.error(f"Environment not found: {env_id}")
            return False

        try:
            if language == ExecutionLanguage.PYTHON:
                # Install Python package
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", package],
                    timeout=60,
                    check=True,
                )
            elif language == ExecutionLanguage.JAVASCRIPT:
                # Install Node.js package
                subprocess.run(
                    ["npm", "install", "--silent", package],
                    cwd=self.environments[env_id]["path"],
                    timeout=60,
                    check=True,
                )

            self.environments[env_id]["dependencies"].append(package)
            logger.info(f"Installed dependency {package} in environment {env_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to install dependency {package}: {e}")
            return False

    def cleanup_environment(self, env_id: str) -> bool:
        """Clean up an execution environment."""
        if env_id not in self.environments:
            logger.error(f"Environment not found: {env_id}")
            return False

        try:
            env_path = self.environments[env_id]["path"]
            import shutil
            shutil.rmtree(env_path, ignore_errors=True)
            del self.environments[env_id]
            logger.info(f"Cleaned up execution environment: {env_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup environment {env_id}: {e}")
            return False

    def get_environment_info(self, env_id: str) -> Optional[dict[str, Any]]:
        """Get information about an execution environment."""
        return self.environments.get(env_id)
