"""
数据验证模块 - 集中管理所有数据验证逻辑。

这个模块提供可重用的验证函数和TypedDict定义，
用于替代分散在各个API端点中的重复验证代码。
"""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class TaskInput(TypedDict, total=False):
    """任务输入的类型定义。"""
    task: str
    extra_context: dict[str, Any]
    resume_trace_id: str | None


class AgentConfig(TypedDict, total=False):
    """代理配置的类型定义。"""
    max_iterations: int
    timeout_seconds: int
    enable_memory: bool
    enable_audit: bool


class ExecutionContext(TypedDict, total=False):
    """执行上下文的类型定义。"""
    trace_id: str
    agent_id: str
    tenant_id: str
    user_id: str
    session_id: str | None
    risk_level: str


class ValidationResult(BaseModel):
    """验证结果模型。"""
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TaskValidator:
    """任务验证器 - 集中管理任务相关的验证逻辑。"""

    MIN_TASK_LENGTH = 1
    MAX_TASK_LENGTH = 20_000
    MIN_ITERATIONS = 1
    MAX_ITERATIONS = 100

    @staticmethod
    def validate_task(task: str) -> ValidationResult:
        """
        验证任务字符串。

        Args:
            task: 任务描述

        Returns:
            ValidationResult: 验证结果

        Raises:
            ValueError: 如果验证失败
        """
        errors: list[str] = []
        warnings: list[str] = []

        if not isinstance(task, str):
            errors.append("Task must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if len(task) < TaskValidator.MIN_TASK_LENGTH:
            errors.append(f"Task must be at least {TaskValidator.MIN_TASK_LENGTH} character")

        if len(task) > TaskValidator.MAX_TASK_LENGTH:
            errors.append(f"Task must not exceed {TaskValidator.MAX_TASK_LENGTH} characters")

        if not task.strip():
            errors.append("Task cannot be empty or whitespace only")

        if len(task) > 500:
            warnings.append("Task is quite long; consider breaking it into smaller subtasks")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    @staticmethod
    def validate_extra_context(context: dict[str, Any] | None) -> ValidationResult:
        """
        验证额外上下文。

        Args:
            context: 额外上下文字典

        Returns:
            ValidationResult: 验证结果
        """
        errors: list[str] = []

        if context is None:
            return ValidationResult(is_valid=True)

        if not isinstance(context, dict):
            errors.append("Extra context must be a dictionary")
            return ValidationResult(is_valid=False, errors=errors)

        # 检查上下文大小
        context_str = str(context)
        if len(context_str) > 100_000:
            errors.append("Extra context is too large (max 100KB)")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_resume_trace_id(trace_id: str | None) -> ValidationResult:
        """
        验证恢复trace ID。

        Args:
            trace_id: Trace ID

        Returns:
            ValidationResult: 验证结果
        """
        errors: list[str] = []

        if trace_id is None:
            return ValidationResult(is_valid=True)

        if not isinstance(trace_id, str):
            errors.append("Resume trace ID must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if not trace_id.strip():
            errors.append("Resume trace ID cannot be empty")

        if len(trace_id) > 256:
            errors.append("Resume trace ID is too long")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


class ConfigValidator:
    """配置验证器 - 集中管理配置相关的验证逻辑。"""

    @staticmethod
    def validate_max_iterations(value: int) -> ValidationResult:
        """
        验证最大迭代次数。

        Args:
            value: 最大迭代次数

        Returns:
            ValidationResult: 验证结果
        """
        errors: list[str] = []

        if not isinstance(value, int):
            errors.append("Max iterations must be an integer")
            return ValidationResult(is_valid=False, errors=errors)

        if value < TaskValidator.MIN_ITERATIONS:
            errors.append(f"Max iterations must be at least {TaskValidator.MIN_ITERATIONS}")

        if value > TaskValidator.MAX_ITERATIONS:
            errors.append(f"Max iterations must not exceed {TaskValidator.MAX_ITERATIONS}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_timeout(value: int) -> ValidationResult:
        """
        验证超时时间。

        Args:
            value: 超时时间（秒）

        Returns:
            ValidationResult: 验证结果
        """
        errors: list[str] = []

        if not isinstance(value, int):
            errors.append("Timeout must be an integer")
            return ValidationResult(is_valid=False, errors=errors)

        if value <= 0:
            errors.append("Timeout must be positive")

        if value > 3600:
            errors.append("Timeout must not exceed 3600 seconds (1 hour)")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


class ContextValidator:
    """上下文验证器 - 集中管理执行上下文的验证逻辑。"""

    @staticmethod
    def validate_trace_id(trace_id: str) -> ValidationResult:
        """验证trace ID。"""
        errors: list[str] = []

        if not isinstance(trace_id, str):
            errors.append("Trace ID must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if not trace_id.strip():
            errors.append("Trace ID cannot be empty")

        if len(trace_id) > 256:
            errors.append("Trace ID is too long")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_agent_id(agent_id: str) -> ValidationResult:
        """验证agent ID。"""
        errors: list[str] = []

        if not isinstance(agent_id, str):
            errors.append("Agent ID must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if not agent_id.strip():
            errors.append("Agent ID cannot be empty")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_tenant_id(tenant_id: str) -> ValidationResult:
        """验证tenant ID。"""
        errors: list[str] = []

        if not isinstance(tenant_id, str):
            errors.append("Tenant ID must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if not tenant_id.strip():
            errors.append("Tenant ID cannot be empty")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_risk_level(risk_level: str) -> ValidationResult:
        """验证风险等级。"""
        errors: list[str] = []
        valid_levels = {"low", "medium", "high", "critical"}

        if not isinstance(risk_level, str):
            errors.append("Risk level must be a string")
            return ValidationResult(is_valid=False, errors=errors)

        if risk_level.lower() not in valid_levels:
            errors.append(f"Risk level must be one of: {', '.join(valid_levels)}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
