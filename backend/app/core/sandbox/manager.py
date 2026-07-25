"""Unified sandbox manager for Python and Node.js code execution with security policies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from backend.app.core.sandbox.node_sandbox import (
    NodeExecutionResult,
    NodeSandboxConfig,
    NodeSandboxPool,
)
from backend.app.core.sandbox.python_sandbox import (
    ExecutionResult,
    PythonSandboxPool,
    SandboxConfig,
)

logger = logging.getLogger(__name__)


class ExecutionLanguage(StrEnum):
    """Supported execution languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    NODEJS = "nodejs"


@dataclass
class SecurityPolicy:
    """Security policy for code execution."""

    allow_network: bool = False
    allow_file_system: bool = False
    allow_subprocess: bool = False
    timeout_seconds: float = 30.0
    memory_limit_mb: int = 512
    max_output_bytes: int = 10 * 1024 * 1024
    require_approval: bool = False
    log_execution: bool = True
    audit_trail: bool = True


class SandboxManager:
    """Unified manager for Python and Node.js sandboxes."""

    def __init__(
        self,
        python_config: SandboxConfig | None = None,
        node_config: NodeSandboxConfig | None = None,
        security_policy: SecurityPolicy | None = None,
        python_pool_size: int = 5,
        node_pool_size: int = 5,
    ):
        """Initialize sandbox manager.

        Args:
            python_config: Python sandbox configuration
            node_config: Node.js sandbox configuration
            security_policy: Security policy for execution
            python_pool_size: Size of Python sandbox pool
            node_pool_size: Size of Node.js sandbox pool
        """
        self.security_policy = security_policy or SecurityPolicy()

        # Initialize Python sandbox pool
        self.python_config = python_config or SandboxConfig(
            timeout_seconds=self.security_policy.timeout_seconds,
            memory_limit_mb=self.security_policy.memory_limit_mb,
            max_output_bytes=self.security_policy.max_output_bytes,
            enable_network=self.security_policy.allow_network,
            enable_file_system=self.security_policy.allow_file_system,
        )
        self.python_pool = PythonSandboxPool(self.python_config, pool_size=python_pool_size)

        # Initialize Node.js sandbox pool
        self.node_config = node_config or NodeSandboxConfig(
            timeout_seconds=self.security_policy.timeout_seconds,
            memory_limit_mb=self.security_policy.memory_limit_mb,
            max_output_bytes=self.security_policy.max_output_bytes,
            enable_network=self.security_policy.allow_network,
            enable_file_system=self.security_policy.allow_file_system,
        )
        self.node_pool = NodeSandboxPool(self.node_config, pool_size=node_pool_size)

        self._initialized = False
        self._execution_count = 0
        self._execution_history: list[dict[str, Any]] = []

    async def initialize(self) -> None:
        """Initialize sandbox pools."""
        if self._initialized:
            return

        await self.python_pool.initialize()
        await self.node_pool.initialize()
        self._initialized = True
        logger.info("Sandbox manager initialized")

    async def execute(
        self,
        code: str,
        language: ExecutionLanguage = ExecutionLanguage.PYTHON,
        variables: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> ExecutionResult | NodeExecutionResult:
        """Execute code in appropriate sandbox.

        Args:
            code: Code to execute
            language: Programming language
            variables: Variables to inject
            execution_id: Optional execution ID for tracking

        Returns:
            ExecutionResult or NodeExecutionResult
        """
        if not self._initialized:
            await self.initialize()

        # Log execution if enabled
        if self.security_policy.log_execution:
            logger.info(f"Executing {language} code (ID: {execution_id})")

        try:
            if language in (ExecutionLanguage.PYTHON,):
                result = await self.python_pool.execute(code, variables)
            elif language in (ExecutionLanguage.JAVASCRIPT, ExecutionLanguage.NODEJS):
                result = await self.node_pool.execute(code, variables)
            else:
                raise ValueError(f"Unsupported language: {language}")

            # Track execution
            self._execution_count += 1
            if self.security_policy.audit_trail:
                self._record_execution(execution_id, language, code, result)

            return result

        except Exception as e:
            logger.exception(f"Execution failed: {e}")
            if language in (ExecutionLanguage.PYTHON,):
                return ExecutionResult(
                    success=False,
                    error_code="MANAGER_ERROR",
                    error_message=str(e),
                )
            else:
                return NodeExecutionResult(
                    success=False,
                    error_code="MANAGER_ERROR",
                    error_message=str(e),
                )

    def _record_execution(
        self,
        execution_id: str | None,
        language: ExecutionLanguage,
        code: str,
        result: ExecutionResult | NodeExecutionResult,
    ) -> None:
        """Record execution in audit trail.

        Args:
            execution_id: Execution ID
            language: Programming language
            code: Code executed
            result: Execution result
        """
        import time

        record = {
            "execution_id": execution_id,
            "language": language.value,
            "timestamp": time.time(),
            "code_length": len(code),
            "success": result.success,
            "error_code": result.error_code,
            "execution_time_ms": result.execution_time_ms,
        }

        self._execution_history.append(record)

        # Keep only last 1000 records
        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-1000:]

    def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with execution stats
        """
        if not self._execution_history:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time_ms": 0.0,
            }

        successful = sum(1 for r in self._execution_history if r["success"])
        failed = len(self._execution_history) - successful
        avg_time = sum(r["execution_time_ms"] for r in self._execution_history) / len(
            self._execution_history
        )

        return {
            "total_executions": len(self._execution_history),
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": successful / len(self._execution_history) if self._execution_history else 0,
            "average_execution_time_ms": avg_time,
        }

    def get_execution_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent execution history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of execution records
        """
        return self._execution_history[-limit:]

    async def shutdown(self) -> None:
        """Shutdown sandbox pools."""
        await self.python_pool.shutdown()
        await self.node_pool.shutdown()
        self._initialized = False
        logger.info("Sandbox manager shutdown")


# Global sandbox manager instance
_sandbox_manager: SandboxManager | None = None


async def get_sandbox_manager(
    python_config: SandboxConfig | None = None,
    node_config: NodeSandboxConfig | None = None,
    security_policy: SecurityPolicy | None = None,
) -> SandboxManager:
    """Get or create global sandbox manager.

    Args:
        python_config: Python sandbox configuration
        node_config: Node.js sandbox configuration
        security_policy: Security policy

    Returns:
        SandboxManager instance
    """
    global _sandbox_manager

    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager(
            python_config=python_config,
            node_config=node_config,
            security_policy=security_policy,
        )
        await _sandbox_manager.initialize()

    return _sandbox_manager


async def execute_code(
    code: str,
    language: ExecutionLanguage = ExecutionLanguage.PYTHON,
    variables: dict[str, Any] | None = None,
    execution_id: str | None = None,
) -> ExecutionResult | NodeExecutionResult:
    """Execute code using global sandbox manager.

    Args:
        code: Code to execute
        language: Programming language
        variables: Variables to inject
        execution_id: Optional execution ID

    Returns:
        ExecutionResult or NodeExecutionResult
    """
    manager = await get_sandbox_manager()
    return await manager.execute(code, language, variables, execution_id)
