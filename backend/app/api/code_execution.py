"""
Code execution API endpoints with security controls and audit logging.
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.code_executor import (
    CodeExecutor,
    ExecutionConfig,
    ExecutionLanguage,
)
from backend.app.core.contracts import ErrorCode
from backend.app.dependencies import get_agent, get_current_principal, enforce_scope
from backend.app.core.security import Principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/code", tags=["code_execution"])
AgentDependency = Annotated[object, Depends(get_agent)]
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class CodeExecutionRequest(BaseModel):
    """Request model for code execution."""
    code: str = Field(..., description="Code to execute")
    language: ExecutionLanguage = Field(
        default=ExecutionLanguage.PYTHON,
        description="Programming language"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Execution timeout in seconds (1-300)"
    )
    allow_network: bool = Field(
        default=False,
        description="Allow network access"
    )
    allow_file_system_write: bool = Field(
        default=False,
        description="Allow file system write access"
    )
    environment_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables"
    )


class CodeExecutionResponse(BaseModel):
    """Response model for code execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    status: str
    error: Optional[str] = None
    execution_id: str
    language: str
    resource_usage: dict = Field(default_factory=dict)


@router.post("/execute/python")
async def execute_python_code(
    request: CodeExecutionRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> CodeExecutionResponse:
    """Execute Python code in a sandboxed environment.

    Security features:
    - Code validation for dangerous patterns
    - Execution timeout (default 30s, max 300s)
    - Network access disabled by default
    - File system write disabled by default
    - Output size limited to 1MB
    - Audit logging enabled

    Args:
        request: Code execution request with code and configuration
        agent: Agent instance
        principal: Current principal for authorization

    Returns:
        Execution result with stdout, stderr, and metadata

    Raises:
        HTTPException: If code contains security violations or execution fails
    """
    enforce_scope(principal, "code:execute")

    if request.language != ExecutionLanguage.PYTHON:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Language mismatch: expected Python",
        )

    try:
        # Create executor with configuration
        config = ExecutionConfig(
            timeout=request.timeout,
            allow_network=request.allow_network,
            allow_file_system_write=request.allow_file_system_write,
            environment_vars=request.environment_vars,
        )
        executor = CodeExecutor(config=config)

        # Execute code
        result = await executor.execute_python(request.code, timeout=request.timeout)

        # Audit log
        logger.info(
            f"Python code execution: {result.execution_id}, "
            f"success={result.success}, time={result.execution_time}s"
        )

        return CodeExecutionResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            status=result.status,
            error=result.error,
            execution_id=result.execution_id,
            language=result.language,
            resource_usage=result.resource_usage,
        )

    except Exception as e:
        logger.error(f"Python execution error: {e}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Code execution failed: {str(e)}",
        )


@router.post("/execute/javascript")
async def execute_javascript_code(
    request: CodeExecutionRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> CodeExecutionResponse:
    """Execute JavaScript code in a sandboxed environment.

    Security features:
    - Code validation for dangerous patterns
    - Execution timeout (default 30s, max 300s)
    - Network access disabled by default
    - File system write disabled by default
    - Output size limited to 1MB
    - Audit logging enabled

    Args:
        request: Code execution request with code and configuration
        agent: Agent instance
        principal: Current principal for authorization

    Returns:
        Execution result with stdout, stderr, and metadata

    Raises:
        HTTPException: If code contains security violations or execution fails
    """
    enforce_scope(principal, "code:execute")

    if request.language != ExecutionLanguage.JAVASCRIPT:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Language mismatch: expected JavaScript",
        )

    try:
        # Create executor with configuration
        config = ExecutionConfig(
            timeout=request.timeout,
            allow_network=request.allow_network,
            allow_file_system_write=request.allow_file_system_write,
            environment_vars=request.environment_vars,
        )
        executor = CodeExecutor(config=config)

        # Execute code
        result = await executor.execute_javascript(request.code, timeout=request.timeout)

        # Audit log
        logger.info(
            f"JavaScript code execution: {result.execution_id}, "
            f"success={result.success}, time={result.execution_time}s"
        )

        return CodeExecutionResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            status=result.status,
            error=result.error,
            execution_id=result.execution_id,
            language=result.language,
            resource_usage=result.resource_usage,
        )

    except Exception as e:
        logger.error(f"JavaScript execution error: {e}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Code execution failed: {str(e)}",
        )


@router.post("/execute/bash")
async def execute_bash_command(
    request: CodeExecutionRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> CodeExecutionResponse:
    """Execute Bash command in a sandboxed environment.

    Security features:
    - Command validation for dangerous patterns
    - Execution timeout (default 30s, max 300s)
    - Network access disabled by default
    - File system write disabled by default
    - Output size limited to 1MB
    - Audit logging enabled

    Args:
        request: Code execution request with command and configuration
        agent: Agent instance
        principal: Current principal for authorization

    Returns:
        Execution result with stdout, stderr, and metadata

    Raises:
        HTTPException: If command contains security violations or execution fails
    """
    enforce_scope(principal, "code:execute")

    if request.language != ExecutionLanguage.BASH:
        raise api_error(
            400,
            ErrorCode.VALIDATION_ERROR,
            "Language mismatch: expected Bash",
        )

    try:
        # Create executor with configuration
        config = ExecutionConfig(
            timeout=request.timeout,
            allow_network=request.allow_network,
            allow_file_system_write=request.allow_file_system_write,
            environment_vars=request.environment_vars,
        )
        executor = CodeExecutor(config=config)

        # Execute command
        result = await executor.execute_bash(request.code, timeout=request.timeout)

        # Audit log
        logger.info(
            f"Bash command execution: {result.execution_id}, "
            f"success={result.success}, time={result.execution_time}s"
        )

        return CodeExecutionResponse(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            status=result.status,
            error=result.error,
            execution_id=result.execution_id,
            language=result.language,
            resource_usage=result.resource_usage,
        )

    except Exception as e:
        logger.error(f"Bash execution error: {e}")
        raise api_error(
            500,
            ErrorCode.INTERNAL_ERROR,
            f"Code execution failed: {str(e)}",
        )


@router.get("/execution/{execution_id}")
async def get_execution_result(
    execution_id: str,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict:
    """Get execution result by ID.

    Args:
        execution_id: Execution ID
        agent: Agent instance
        principal: Current principal for authorization

    Returns:
        Execution result metadata

    Raises:
        HTTPException: If execution not found
    """
    enforce_scope(principal, "code:read")

    # Note: In a production system, this would query a database
    # For now, we return a placeholder response
    return {
        "execution_id": execution_id,
        "status": "completed",
        "message": "Execution result storage not yet implemented",
    }


@router.post("/validate")
async def validate_code(
    request: CodeExecutionRequest,
    agent: AgentDependency,
    principal: PrincipalDependency,
) -> dict:
    """Validate code for security violations without executing.

    Args:
        request: Code execution request
        agent: Agent instance
        principal: Current principal for authorization

    Returns:
        Validation result with any detected issues

    Raises:
        HTTPException: If validation fails
    """
    enforce_scope(principal, "code:validate")

    from backend.app.core.code_executor import SecurityValidator

    validator = SecurityValidator()
    is_valid = True
    issues = []

    if request.language == ExecutionLanguage.PYTHON:
        is_valid, error_msg = validator.validate_python(request.code)
        if not is_valid:
            issues.append(error_msg)

    elif request.language == ExecutionLanguage.JAVASCRIPT:
        is_valid, error_msg = validator.validate_javascript(request.code)
        if not is_valid:
            issues.append(error_msg)

    elif request.language == ExecutionLanguage.BASH:
        is_valid, error_msg = validator.validate_bash(request.code)
        if not is_valid:
            issues.append(error_msg)

    return {
        "valid": is_valid,
        "language": request.language,
        "issues": issues,
    }
