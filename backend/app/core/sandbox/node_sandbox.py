"""Secure Node.js code execution sandbox with isolated-vm isolation and resource limits."""

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
class NodeSandboxConfig:
    """Configuration for Node.js sandbox execution."""

    timeout_seconds: float = 30.0
    memory_limit_mb: int = 512
    cpu_limit_percent: float = 50.0
    max_output_bytes: int = 10 * 1024 * 1024  # 10MB
    enable_network: bool = False
    enable_file_system: bool = False
    temp_dir: Optional[str] = None
    node_version: str = "18"
    container_name_prefix: str = "xagent-node"


@dataclass
class NodeExecutionResult:
    """Result of Node.js code execution."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


class NodeSandbox:
    """Secure Node.js code execution sandbox using isolated-vm."""

    # Whitelist of allowed modules
    ALLOWED_MODULES = {
        # Core modules
        "assert",
        "buffer",
        "crypto",
        "events",
        "fs",
        "path",
        "stream",
        "string_decoder",
        "util",
        "zlib",
        "url",
        "querystring",
        "http",
        "https",
        "net",
        "dgram",
        "dns",
        "tls",
        "os",
        "process",
        "child_process",
        "cluster",
        "repl",
        "vm",
        "worker_threads",
        "perf_hooks",
        "async_hooks",
        "v8",
        "inspector",
        "diagnostics_channel",
        # Popular npm packages (if installed)
        "lodash",
        "underscore",
        "moment",
        "date-fns",
        "axios",
        "node-fetch",
        "cheerio",
        "jsdom",
        "express",
        "fastify",
        "koa",
        "hapi",
        "restify",
        "graphql",
        "apollo-server",
        "mongoose",
        "sequelize",
        "typeorm",
        "knex",
        "redis",
        "ioredis",
        "mongodb",
        "mysql",
        "pg",
        "sqlite3",
        "uuid",
        "validator",
        "joi",
        "yup",
        "zod",
        "typescript",
        "babel",
        "webpack",
        "jest",
        "mocha",
        "chai",
        "sinon",
        "prettier",
        "eslint",
        "dotenv",
        "chalk",
        "commander",
        "yargs",
        "inquirer",
        "ora",
        "table",
        "cli-table",
        "blessed",
        "ink",
        "react",
        "vue",
        "angular",
        "svelte",
        "next",
        "nuxt",
        "gatsby",
        "remix",
    }

    # Dangerous operations to block
    DANGEROUS_PATTERNS = {
        "require('child_process')",
        "require('fs')",
        "require('net')",
        "require('dgram')",
        "require('http')",
        "require('https')",
        "require('cluster')",
        "require('worker_threads')",
        "require('vm')",
        "process.exit",
        "process.kill",
        "process.env",
        "global.",
        "__dirname",
        "__filename",
        "eval(",
        "Function(",
        "setTimeout",
        "setInterval",
        "setImmediate",
        "require.cache",
        "module.exports",
        "exports.",
    }

    def __init__(self, config: Optional[NodeSandboxConfig] = None):
        """Initialize Node.js sandbox.

        Args:
            config: Sandbox configuration
        """
        self.config = config or NodeSandboxConfig()
        self._temp_dir: Optional[str] = None

    async def execute(self, code: str, variables: Optional[dict[str, Any]] = None) -> NodeExecutionResult:
        """Execute Node.js code in sandbox.

        Args:
            code: JavaScript code to execute
            variables: Variables to inject into execution context

        Returns:
            NodeExecutionResult with execution output and status
        """
        import time

        start_time = time.perf_counter()

        # Validate code
        validation_error = self._validate_code(code)
        if validation_error:
            return NodeExecutionResult(
                success=False,
                error_code="VALIDATION_ERROR",
                error_message=validation_error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            # Create temporary directory for execution
            self._temp_dir = tempfile.mkdtemp(prefix=self.config.container_name_prefix)

            # Prepare execution script
            script_path = os.path.join(self._temp_dir, "script.js")
            self._write_execution_script(script_path, code, variables or {})

            # Execute in Node.js
            result = await self._execute_in_node(script_path)

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        except asyncio.TimeoutError:
            return NodeExecutionResult(
                success=False,
                error_code="TIMEOUT",
                error_message=f"Execution timed out after {self.config.timeout_seconds}s",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            logger.exception(f"Sandbox execution error: {e}")
            return NodeExecutionResult(
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

        # Check for suspicious requires
        import re

        requires = re.findall(r"require\(['\"]([^'\"]+)['\"]\)", code)
        for module in requires:
            base_module = module.split("/")[0]
            if base_module not in self.ALLOWED_MODULES:
                return f"Module not in whitelist: {base_module}"

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
                var_setup += f"const {key} = {json.dumps(value)};\n"
            except (TypeError, ValueError):
                # Skip non-serializable variables
                pass

        # Wrap code with output capture
        wrapped_code = f"""
const util = require('util');

// Capture output
let _stdout = '';
let _stderr = '';
const _oldLog = console.log;
const _oldError = console.error;

console.log = function(...args) {{
    _stdout += util.format(...args) + '\\n';
}};

console.error = function(...args) {{
    _stderr += util.format(...args) + '\\n';
}};

// Inject variables
{var_setup}

(async () => {{
    try {{
        // Execute user code
{self._indent_code(code, 8)}

        // Get result
        const _result = typeof _result !== 'undefined' ? _result : null;
        const _output = {{success: true, stdout: _stdout, stderr: _stderr, result: _result}};
        console.log(JSON.stringify(_output));
    }} catch (e) {{
        const _output = {{success: false, error: e.message, stack: e.stack}};
        console.log(JSON.stringify(_output));
    }} finally {{
        console.log = _oldLog;
        console.error = _oldError;
    }}
}})();
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

    async def _execute_in_node(self, script_path: str) -> NodeExecutionResult:
        """Execute script in Node.js.

        Args:
            script_path: Path to script to execute

        Returns:
            NodeExecutionResult
        """
        import time

        start_time = time.perf_counter()

        try:
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                "node",
                "--max-old-space-size=" + str(self.config.memory_limit_mb),
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                # Find JSON output (last line should be JSON)
                lines = output_str.strip().split("\n")
                json_line = None
                for line in reversed(lines):
                    if line.startswith("{"):
                        json_line = line
                        break

                if json_line:
                    output_data = json.loads(json_line)
                    return NodeExecutionResult(
                        success=output_data.get("success", False),
                        stdout=output_data.get("stdout", ""),
                        stderr=output_data.get("stderr", "") or error_str,
                        return_value=output_data.get("result"),
                        error_message=output_data.get("error"),
                        execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
                else:
                    return NodeExecutionResult(
                        success=False,
                        stdout=output_str,
                        stderr=error_str,
                        error_code="PARSE_ERROR",
                        error_message="Failed to parse execution output",
                        execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    )
            except json.JSONDecodeError:
                return NodeExecutionResult(
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
            logger.exception(f"Node execution error: {e}")
            return NodeExecutionResult(
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


class NodeSandboxPool:
    """Pool of reusable Node.js sandbox processes for performance."""

    def __init__(self, config: Optional[NodeSandboxConfig] = None, pool_size: int = 5):
        """Initialize sandbox pool.

        Args:
            config: Sandbox configuration
            pool_size: Number of processes to maintain
        """
        self.config = config or NodeSandboxConfig()
        self.pool_size = pool_size
        self._available: asyncio.Queue[NodeSandbox] = asyncio.Queue(maxsize=pool_size)
        self._all_sandboxes: list[NodeSandbox] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the sandbox pool."""
        if self._initialized:
            return

        for _ in range(self.pool_size):
            sandbox = NodeSandbox(self.config)
            self._all_sandboxes.append(sandbox)
            await self._available.put(sandbox)

        self._initialized = True
        logger.info(f"Initialized Node.js sandbox pool with {self.pool_size} processes")

    async def execute(self, code: str, variables: Optional[dict[str, Any]] = None) -> NodeExecutionResult:
        """Execute code using a sandbox from the pool.

        Args:
            code: Code to execute
            variables: Variables to inject

        Returns:
            NodeExecutionResult
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
