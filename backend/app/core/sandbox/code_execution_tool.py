"""Code execution tool for X-Agent that integrates with the sandbox system."""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.sandbox import (
    ExecutionLanguage,
    RiskLevel,
    SecurityPolicy,
    get_sandbox_manager,
    validate_javascript_code,
    validate_python_code,
)

logger = logging.getLogger(__name__)


class CodeExecutionTool:
    """Tool for executing Python and JavaScript code in sandboxes."""

    def __init__(self, security_policy: SecurityPolicy | None = None):
        """Initialize code execution tool.

        Args:
            security_policy: Security policy for execution
        """
        self.security_policy = security_policy or SecurityPolicy(
            allow_network=False,
            allow_file_system=False,
            allow_subprocess=False,
            timeout_seconds=30.0,
            memory_limit_mb=512,
            require_approval=False,
            log_execution=True,
            audit_trail=True,
        )

    async def execute_python(
        self,
        code: str,
        variables: dict[str, Any] | None = None,
        require_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute Python code.

        Args:
            code: Python code to execute
            variables: Variables to inject
            require_approval: Whether to require approval before execution

        Returns:
            Dictionary with execution result
        """
        # Validate code
        _is_safe, violations = validate_python_code(code)

        # Check for critical violations
        critical_violations = [v for v in violations if v.risk_level == RiskLevel.CRITICAL]
        if critical_violations:
            return {
                "success": False,
                "error": "Code contains critical security violations",
                "violations": [
                    {
                        "risk_level": v.risk_level.value,
                        "pattern": v.pattern,
                        "message": v.message,
                        "line_number": v.line_number,
                        "suggestion": v.suggestion,
                    }
                    for v in critical_violations
                ],
            }

        # Log high-risk violations
        high_risk_violations = [v for v in violations if v.risk_level == RiskLevel.HIGH]
        if high_risk_violations:
            logger.warning(f"High-risk patterns detected in Python code: {len(high_risk_violations)}")

        # Check if approval is required
        if require_approval or self.security_policy.require_approval:
            if high_risk_violations:
                return {
                    "success": False,
                    "error": "Code requires approval due to high-risk patterns",
                    "violations": [
                        {
                            "risk_level": v.risk_level.value,
                            "pattern": v.pattern,
                            "message": v.message,
                            "line_number": v.line_number,
                        }
                        for v in high_risk_violations
                    ],
                    "requires_approval": True,
                }

        # Execute code
        manager = await get_sandbox_manager()
        result = await manager.execute(
            code,
            language=ExecutionLanguage.PYTHON,
            variables=variables,
        )

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "result": result.return_value,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error_message,
            "error_code": result.error_code,
        }

    async def execute_javascript(
        self,
        code: str,
        variables: dict[str, Any] | None = None,
        require_approval: bool = False,
    ) -> dict[str, Any]:
        """Execute JavaScript code.

        Args:
            code: JavaScript code to execute
            variables: Variables to inject
            require_approval: Whether to require approval before execution

        Returns:
            Dictionary with execution result
        """
        # Validate code
        _is_safe, violations = validate_javascript_code(code)

        # Check for critical violations
        critical_violations = [v for v in violations if v.risk_level == RiskLevel.CRITICAL]
        if critical_violations:
            return {
                "success": False,
                "error": "Code contains critical security violations",
                "violations": [
                    {
                        "risk_level": v.risk_level.value,
                        "pattern": v.pattern,
                        "message": v.message,
                        "line_number": v.line_number,
                        "suggestion": v.suggestion,
                    }
                    for v in critical_violations
                ],
            }

        # Log high-risk violations
        high_risk_violations = [v for v in violations if v.risk_level == RiskLevel.HIGH]
        if high_risk_violations:
            logger.warning(f"High-risk patterns detected in JavaScript code: {len(high_risk_violations)}")

        # Check if approval is required
        if require_approval or self.security_policy.require_approval:
            if high_risk_violations:
                return {
                    "success": False,
                    "error": "Code requires approval due to high-risk patterns",
                    "violations": [
                        {
                            "risk_level": v.risk_level.value,
                            "pattern": v.pattern,
                            "message": v.message,
                            "line_number": v.line_number,
                        }
                        for v in high_risk_violations
                    ],
                    "requires_approval": True,
                }

        # Execute code
        manager = await get_sandbox_manager()
        result = await manager.execute(
            code,
            language=ExecutionLanguage.NODEJS,
            variables=variables,
        )

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "result": result.return_value,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error_message,
            "error_code": result.error_code,
        }

    async def validate_code(self, code: str, language: str) -> dict[str, Any]:
        """Validate code without executing it.

        Args:
            code: Code to validate
            language: Programming language (python or javascript)

        Returns:
            Dictionary with validation results
        """
        if language.lower() in ("python", "py"):
            is_safe, violations = validate_python_code(code)
        elif language.lower() in ("javascript", "js", "nodejs", "node"):
            is_safe, violations = validate_javascript_code(code)
        else:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
            }

        return {
            "success": True,
            "is_safe": is_safe,
            "violations": [
                {
                    "risk_level": v.risk_level.value,
                    "pattern": v.pattern,
                    "message": v.message,
                    "line_number": v.line_number,
                    "suggestion": v.suggestion,
                }
                for v in violations
            ],
            "critical_count": sum(1 for v in violations if v.risk_level == RiskLevel.CRITICAL),
            "high_count": sum(1 for v in violations if v.risk_level == RiskLevel.HIGH),
            "medium_count": sum(1 for v in violations if v.risk_level == RiskLevel.MEDIUM),
        }

    async def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary with execution stats
        """
        manager = await get_sandbox_manager()
        return manager.get_execution_stats()

    async def get_execution_history(self, limit: int = 100) -> dict[str, Any]:
        """Get execution history.

        Args:
            limit: Maximum number of records

        Returns:
            Dictionary with execution history
        """
        manager = await get_sandbox_manager()
        history = manager.get_execution_history(limit)
        return {
            "success": True,
            "count": len(history),
            "history": history,
        }


# Global tool instance
_code_execution_tool: CodeExecutionTool | None = None


async def get_code_execution_tool(
    security_policy: SecurityPolicy | None = None,
) -> CodeExecutionTool:
    """Get or create global code execution tool.

    Args:
        security_policy: Security policy

    Returns:
        CodeExecutionTool instance
    """
    global _code_execution_tool

    if _code_execution_tool is None:
        _code_execution_tool = CodeExecutionTool(security_policy)

    return _code_execution_tool
