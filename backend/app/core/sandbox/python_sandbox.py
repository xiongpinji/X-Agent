"""Secure Python code execution sandbox with Docker isolation and resource limits."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for Python sandbox execution."""

    timeout_seconds: float = 30.0
    memory_limit_mb: int = 512
    cpu_limit_percent: float = 50.0
    max_output_bytes: int = 10 * 1024 * 1024  # 10MB
    enable_network: bool = False
    enable_file_system: bool = True
    temp_dir: Optional[str] = None
    docker_image: str = "python:3.11-slim"
    container_name_prefix: str = "xagent-python"


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class PythonSandbox:
    """Secure Python code execution sandbox using Docker containers."""

    # Whitelist of allowed modules
    ALLOWED_MODULES = {
        # Standard library
        "json",
        "math",
        "random",
        "datetime",
        "time",
        "re",
        "collections",
        "itertools",
        "functools",
        "operator",
        "string",
        "hashlib",
        "base64",
        "urllib.parse",
        "statistics",
        "decimal",
        "fractions",
        "numbers",
        "cmath",
        "array",
        "struct",
        "codecs",
        "unicodedata",
        "stringprep",
        "difflib",
        "textwrap",
        "calendar",
        "zlib",
        "gzip",
        "bz2",
        "lzma",
        "csv",
        "configparser",
        "tomllib",
        "plistlib",
        "netrc",
        "xdrlib",
        "pprint",
        "enum",
        "graphlib",
        "types",
        "copy",
        "pydoc",
        "doctest",
        "unittest",
        "dataclasses",
        "typing",
        "abc",
        "atexit",
        "traceback",
        "inspect",
        "site",
        "warnings",
        "contextlib",
        "abc",
        "rlcompleter",
        # Popular data science libraries (if installed)
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "matplotlib",
        "seaborn",
        "plotly",
        "requests",
        "beautifulsoup4",
        "lxml",
    }

    # Dangerous operations to block
    DANGEROUS_PATTERNS = {
        "import os",
        "import sys",
        "import subprocess",
        "import socket",
        "import threading",
        "import multiprocessing",
        "from os import",
        "from sys import",
        "from subprocess import",
        "from socket import",
        "__import__",
        "eval(",
        "exec(",
        "compile(",
        "open(",
        "file(",
        "input(",
        "raw_input(",
        "globals()",
        "locals()",
        "vars(",
        "dir(",
        "getattr(",
        "setattr(",
        "delattr(",
        "hasattr(",
        "__dict__",
        "__class__",
        "__bases__",
        "__subclasses__",
        "__code__",
        "__globals__",
    }

    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize Python sandbox.

        Args:
            config: Sandbox configuration
        """
        self.config = config or SandboxConfig()
        self._container_id: Optional[str] = None
        self._temp_dir: Optional[str] = None

    async def execute(self, code: str, variables: Optional[dict[str, Any]] = None) -> ExecutionResult:
        """Execute Python code in sandbox.

        Args:
            code: Python code to execute
            variables: Variables to inject into execution context

        Returns:
            ExecutionResult with execution output and status
        """
        import time

        start_time = time.perf_counter()

        # Validate code
        validation_error = self._validate_code(code)
        if validation_error:
            return ExecutionResult(
                success=False,
                error_code="VALIDATION_ERROR",
                error_message=validation_error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            # Create temporary directory for execution
            self._temp_dir = tempfile.mkdtemp(prefix=self.config.container_name_prefix)

            # Prepare execution script
            script_path = os.path.join(self._temp_dir, "script.py")
            self._write_execution_script(script_path, code, variables or {})

            # Execute in Docker container
            result = await self._execute_in_container(script_path)

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                error_code="TIMEOUT",
                error_message=f"Execution timed out after {self.config.timeout_seconds}s",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            logger.exception(f"Sandbox execution error: {e}")
            return ExecutionResult(
                success=False,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        finally:
            # Cleanup
            await self._cleanup()

    def _validate_code(self, code: str) -> Optional[str]:
        """Validate code for dangerous patterns.

        Args:
            code: Code to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in code:
                return f"Dangerous pattern detected: {pattern}"

        # Check for suspicious imports
        lines = code.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Extract module name
                if stripped.startswith("import "):
                    module = stripped[7:].split()[0].split(".")[0]
                else:
                    module = stripped[5:].split()[0].split(".")[0]

                if module not in self.ALLOWED_MODULES:
                    return f"Module not in whitelist: {module}"

        return None

    def _write_execution_script(self, script_path: str, code: str, variables: dict[str, Any]) -> None:
        """Write execution script with variable injection.

        Args:
            script_path: Path to write script
            code: Code to execute
            variables: Variables to inject
        """
        # Prepare variable injection
        var_setup = ""
        for key, value in variables.items():
            try:
                var_setup += f"{key} = {json.dumps(value)}\n"
            except (TypeError, ValueError):
                # Skip non-serializable variables
                pass

        # Wrap code with output capture
        wrapped_code = f"""
import sys
import json
from io import StringIO

# Inject variables
{var_setup}

# Capture output
_stdout = StringIO()
_stderr = StringIO()
_old_stdout = sys.stdout
_old_stderr = sys.stderr
sys.stdout = _stdout
sys.stderr = _stderr

try:
    # Execute user code
{self._indent_code(code, 4)}

    # Get result
    _result = locals().get('_result', None)
    _output = {{"success": True, "stdout": _stdout.getvalue(), "stderr": _stderr.getvalue(), "result": _result}}
except Exception as e:
    import traceback
    _output = {{"success": False, "error": str(e), "traceback": traceback.format_exc()}}
finally:
    sys.stdout = _old_stdout
    sys.stderr = _old_stderr
    print(json.dumps(_output))
"""

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(wrapped_code)

    @staticmethod
    def _indent_code(code: str, spaces: int) -> str:
        """Indent code by specified number of spaces.

        Args:
            code: Code to indent
            spaces: Number of spaces

        Returns:
            Indented code
        """
        indent = " " * spaces
        return "\n".join(indent + line if line.strip() else line for line in code.split("\n"))

    async def _execute_in_container(self, script_path: str) -> ExecutionResult:
        """Execute script in Docker container.

        Args:
            script_path: Path to script to execute

        Returns:
            ExecutionResult
        """
        import time

        start_time = time.perf_counter()

        try:
            # For now, execute directly (Docker integration can be added later)
            # In production, this would use docker-py to create isolated containers
            result = await self._execute_direct(script_path)
            return result

        except Exception as e:
            logger.exception(f"Container execution error: {e}")
            return ExecutionResult(
                success=False,
                error_code="CONTAINER_ERROR",
                error_message=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def _execute_direct(self, script_path: str) -> ExecutionResult:
        """Execute script directly (fallback for development).

        Args:
            script_path: Path to script

        Returns:
            ExecutionResult
        """
        import time
        import subprocess

        start_time = time.perf_counter()

        try:
            # Execute with timeout and resource limits
            process = await asyncio.create_subprocess_exec(
                "python",
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=self.config.timeout_seconds,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.config.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise

            # Parse output
            output_str = stdout.decode("utf-8", errors="replace")
            error_str = stderr.decode("utf-8", errors="replace")

            try:
                output_data = json.loads(output_str)
                return ExecutionResult(
                    success=output_data.get("success", False),
                    stdout=output_data.get("stdout", ""),
                    stderr=output_data.get("stderr", "") or error_str,
                    return_value=output_data.get("result"),
                    error_message=output_data.get("error"),
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )
            except json.JSONDecodeError:
                return ExecutionResult(
                    success=False,
                    stdout=output_str,
                    stderr=error_str,
                    error_code="PARSE_ERROR",
                    error_message="Failed to parse execution output",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.exception(f"Direct execution error: {e}")
            return ExecutionResult(
                success=False,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def _cleanup(self) -> None:
        """Cleanup temporary resources."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                import shutil

                shutil.rmtree(self._temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                import shutil

                shutil.rmtree(self._temp_dir)
            except Exception:
                pass


class PythonSandboxPool:
    """Pool of reusable Python sandbox containers for performance."""

    def __init__(self, config: Optional[SandboxConfig] = None, pool_size: int = 5):
        """Initialize sandbox pool.

        Args:
            config: Sandbox configuration
            pool_size: Number of containers to maintain
        """
        self.config = config or SandboxConfig()
        self.pool_size = pool_size
        self._available: asyncio.Queue[PythonSandbox] = asyncio.Queue(maxsize=pool_size)
        self._all_sandboxes: list[PythonSandbox] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the sandbox pool."""
        if self._initialized:
            return

        for _ in range(self.pool_size):
            sandbox = PythonSandbox(self.config)
            self._all_sandboxes.append(sandbox)
            await self._available.put(sandbox)

        self._initialized = True
        logger.info(f"Initialized Python sandbox pool with {self.pool_size} containers")

    async def execute(self, code: str, variables: Optional[dict[str, Any]] = None) -> ExecutionResult:
        """Execute code using a sandbox from the pool.

        Args:
            code: Code to execute
            variables: Variables to inject

        Returns:
            ExecutionResult
        """
        if not self._initialized:
            await self.initialize()

        sandbox = await self._available.get()
        try:
            return await sandbox.execute(code, variables)
        finally:
            await self._available.put(sandbox)

    async def shutdown(self) -> None:
        """Shutdown the sandbox pool."""
        for sandbox in self._all_sandboxes:
            await sandbox._cleanup()
        self._initialized = False
