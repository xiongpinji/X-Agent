"""Skill Executor - Executes skills with proper lifecycle management"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .skills_core import (
    SkillExecutionContext,
    SkillExecutionResult,
)
from .skills_loader import get_skill_loader
from .skills_registry import get_skill_registry
from .skills_sandbox import get_sandbox_manager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionAuditLog:
    """Audit log entry for skill execution"""
    execution_id: str
    skill_id: str
    user_id: str
    tenant_id: str
    status: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    error: str | None = None
    input_hash: str = ""
    output_hash: str = ""


class SkillExecutor:
    """Executes skills with proper lifecycle management and auditing"""

    def __init__(self):
        self.loader = get_skill_loader()
        self.registry = get_skill_registry()
        self.sandbox_manager = get_sandbox_manager()
        self.audit_logs: list[ExecutionAuditLog] = []
        self._lock = asyncio.Lock()

    async def execute_skill(
        self,
        skill_name: str,
        input_data: dict[str, Any],
        user_id: str = "",
        tenant_id: str = "",
        sandbox_id: str | None = None,
    ) -> SkillExecutionResult:
        """Execute a skill with full lifecycle management"""
        execution_id = None

        try:
            # Get skill instance
            skill = self.loader.get_skill(skill_name)
            if skill is None:
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill not found: {skill_name}",
                )

            # Get skill metadata
            metadata = self.loader.get_skill_metadata(skill_name)
            if metadata is None:
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill metadata not found: {skill_name}",
                )

            # Create execution context
            context = SkillExecutionContext(
                skill_id=metadata.skill_id,
                user_id=user_id,
                tenant_id=tenant_id,
                input_data=input_data,
            )
            execution_id = context.execution_id

            # Validate input
            valid, error = await skill.validate_input(input_data)
            if not valid:
                return SkillExecutionResult(
                    success=False,
                    error=f"Input validation failed: {error}",
                )

            # Initialize skill
            try:
                await skill.initialize()
            except Exception as e:
                logger.error(f"Skill initialization failed: {e!s}", exc_info=True)
                return SkillExecutionResult(
                    success=False,
                    error=f"Skill initialization failed: {e!s}",
                )

            # Execute skill
            context.start_time = datetime.now(UTC)
            context.status = "running"

            try:
                # Execute in sandbox if specified
                if sandbox_id:
                    sandbox = self.sandbox_manager.get_sandbox(sandbox_id)
                    if sandbox is None:
                        return SkillExecutionResult(
                            success=False,
                            error=f"Sandbox not found: {sandbox_id}",
                        )

                    sandbox_result = await sandbox.execute(
                        skill.execute(context),
                        context,
                        metadata,
                    )

                    if not sandbox_result.success:
                        return SkillExecutionResult(
                            success=False,
                            error=sandbox_result.error,
                            execution_time_ms=sandbox_result.execution_time_ms,
                            resource_usage={
                                "peak_memory_mb": sandbox_result.peak_memory_mb,
                                "peak_cpu_percent": sandbox_result.peak_cpu_percent,
                            },
                        )

                    context.output_data = sandbox_result.output or {}
                else:
                    # Execute directly with timeout
                    try:
                        output = await asyncio.wait_for(
                            skill.execute(context),
                            timeout=metadata.timeout_seconds,
                        )
                        context.output_data = output or {}
                    except TimeoutError:
                        return SkillExecutionResult(
                            success=False,
                            error=f"Skill execution timeout: {metadata.timeout_seconds}s",
                        )

                context.end_time = datetime.now(UTC)
                context.status = "completed"

                # Cleanup
                try:
                    await skill.cleanup()
                except Exception as e:
                    logger.warning(f"Skill cleanup failed: {e!s}")

                # Record audit log
                await self._record_audit_log(
                    execution_id=execution_id,
                    skill_id=metadata.skill_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    status="success",
                    start_time=context.start_time,
                    end_time=context.end_time,
                )

                # Update registry
                await self.registry.increment_download_count(metadata.skill_id)

                return SkillExecutionResult(
                    success=True,
                    data=context.output_data,
                    execution_time_ms=(
                        (context.end_time - context.start_time).total_seconds() * 1000
                        if context.end_time
                        else 0.0
                    ),
                )

            except Exception as e:
                context.end_time = datetime.now(UTC)
                context.status = "error"
                context.error = str(e)

                logger.error(f"Skill execution error: {e!s}", exc_info=True)

                # Record audit log
                await self._record_audit_log(
                    execution_id=execution_id,
                    skill_id=metadata.skill_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    status="error",
                    start_time=context.start_time,
                    end_time=context.end_time,
                    error=str(e),
                )

                return SkillExecutionResult(
                    success=False,
                    error=str(e),
                    execution_time_ms=(
                        (context.end_time - context.start_time).total_seconds() * 1000
                        if context.end_time
                        else 0.0
                    ),
                )

        except Exception as e:
            logger.error(f"Unexpected error in skill execution: {e!s}", exc_info=True)
            return SkillExecutionResult(
                success=False,
                error=f"Unexpected error: {e!s}",
            )

    async def execute_skill_batch(
        self,
        skill_name: str,
        batch_inputs: list[dict[str, Any]],
        user_id: str = "",
        tenant_id: str = "",
    ) -> list[SkillExecutionResult]:
        """Execute a skill multiple times with different inputs"""
        results = []

        for input_data in batch_inputs:
            result = await self.execute_skill(
                skill_name=skill_name,
                input_data=input_data,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            results.append(result)

        return results

    async def _record_audit_log(
        self,
        execution_id: str,
        skill_id: str,
        user_id: str,
        tenant_id: str,
        status: str,
        start_time: datetime,
        end_time: datetime | None = None,
        error: str | None = None,
    ) -> None:
        """Record execution audit log"""
        async with self._lock:
            duration_ms = 0.0
            if end_time:
                duration_ms = (end_time - start_time).total_seconds() * 1000

            log = ExecutionAuditLog(
                execution_id=execution_id,
                skill_id=skill_id,
                user_id=user_id,
                tenant_id=tenant_id,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                error=error,
            )

            self.audit_logs.append(log)

            # Keep only recent logs (last 10000)
            if len(self.audit_logs) > 10000:
                self.audit_logs = self.audit_logs[-10000:]

    def get_audit_logs(
        self,
        skill_id: str | None = None,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[ExecutionAuditLog]:
        """Get audit logs with optional filtering"""
        logs = self.audit_logs

        if skill_id:
            logs = [l for l in logs if l.skill_id == skill_id]

        if user_id:
            logs = [l for l in logs if l.user_id == user_id]

        # Return most recent logs
        return sorted(logs, key=lambda l: l.start_time, reverse=True)[:limit]

    def clear_audit_logs(self) -> None:
        """Clear all audit logs"""
        self.audit_logs.clear()


# Global executor instance
_skill_executor: SkillExecutor | None = None


def get_skill_executor() -> SkillExecutor:
    """Get or create the global skill executor"""
    global _skill_executor
    if _skill_executor is None:
        _skill_executor = SkillExecutor()
    return _skill_executor


__all__ = [
    "ExecutionAuditLog",
    "SkillExecutor",
    "get_skill_executor",
]
