"""
X-Agent 技能系统 v2 - 完善的技能定义、注册、执行和管理

.. deprecated:: P1-11（2026-07-20）
   LEGACY。X-Agent 唯一技能运行时为 ``backend.app.core.skills``
   （目录扫描加载 skills/ 与 custom-skills/，经 ``skill_agent_adapter`` 注入 AgentLoop）。
   本模块仅保留供 skill_chain 使用，不再作为技能运行时入口。
   详见 SKILLS_SYSTEM_README.md。
"""

from __future__ import annotations

import logging
import asyncio
import uuid
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


class SkillStatus(str, Enum):
    """技能状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    INSTALLED = "installed"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    ERROR = "error"


class SkillCategory(str, Enum):
    """技能分类"""
    PRODUCTIVITY = "productivity"
    DEVELOPMENT = "development"
    DATA = "data"
    INTEGRATION = "integration"
    AUTOMATION = "automation"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    CUSTOM = "custom"


class SkillRiskLevel(str, Enum):
    """技能风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None  # regex pattern for validation

    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """验证参数值"""
        if value is None:
            if self.required:
                return False, f"Parameter '{self.name}' is required"
            return True, None

        # Type validation
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_type = type_map.get(self.type)
        if expected_type and not isinstance(value, expected_type):
            return False, f"Parameter '{self.name}' must be of type {self.type}"

        # Enum validation
        if self.enum and value not in self.enum:
            return False, f"Parameter '{self.name}' must be one of {self.enum}"

        # Range validation
        if self.type == "number":
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"

        # Pattern validation
        if self.type == "string" and self.pattern:
            import re
            if not re.match(self.pattern, value):
                return False, f"Parameter '{self.name}' does not match pattern {self.pattern}"

        return True, None


@dataclass
class SkillMetadata:
    """技能元数据"""
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    name_zh: str = ""
    version: str = "1.0.0"
    description: str = ""
    description_zh: str = ""
    author: str = ""
    author_email: Optional[str] = None
    license: str = "MIT"
    category: SkillCategory = SkillCategory.CUSTOM
    icon_emoji: str = "🔧"

    # Capabilities and requirements
    capabilities: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)  # skill_name -> version_spec

    # Parameters
    parameters: List[SkillParameter] = field(default_factory=list)

    # Security and resource limits
    risk_level: SkillRiskLevel = SkillRiskLevel.MEDIUM
    requires_approval: bool = False
    allowed_actions: List[str] = field(default_factory=lambda: ["read", "execute"])
    timeout_seconds: int = 300
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0

    # Metadata
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    documentation_url: str = ""
    repository_url: str = ""
    homepage_url: str = ""

    # Versioning
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    published_at: Optional[datetime] = None

    # Status
    status: SkillStatus = SkillStatus.DRAFT

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "name_zh": self.name_zh,
            "version": self.version,
            "description": self.description,
            "description_zh": self.description_zh,
            "author": self.author,
            "author_email": self.author_email,
            "license": self.license,
            "category": self.category.value,
            "icon_emoji": self.icon_emoji,
            "capabilities": self.capabilities,
            "required_capabilities": self.required_capabilities,
            "dependencies": self.dependencies,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "pattern": p.pattern,
                }
                for p in self.parameters
            ],
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "allowed_actions": self.allowed_actions,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "tags": self.tags,
            "keywords": self.keywords,
            "documentation_url": self.documentation_url,
            "repository_url": self.repository_url,
            "homepage_url": self.homepage_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "status": self.status.value,
        }


@dataclass
class SkillExecutionContext:
    """技能执行上下文"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    skill_name: str = ""
    user_id: str = ""
    tenant_id: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    error: Optional[str] = None
    error_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Execution metadata
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

    def get_duration_ms(self) -> float:
        """获取执行时长（毫秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "execution_id": self.execution_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "status": self.status.value,
            "error": self.error,
            "error_type": self.error_type,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "created_at": self.created_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "duration_ms": self.get_duration_ms(),
        }


@dataclass
class SkillExecutionResult:
    """技能执行结果"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: float = 0.0
    resource_usage: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "error_type": self.error_type,
            "execution_time_ms": self.execution_time_ms,
            "resource_usage": self.resource_usage,
            "metadata": self.metadata,
        }


class Skill(ABC):
    """技能基类 - 所有技能必须继承此类"""

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """返回技能元数据"""
        pass

    @abstractmethod
    async def execute(
        self, context: SkillExecutionContext, **kwargs
    ) -> SkillExecutionResult:
        """
        执行技能

        Args:
            context: 技能执行上下文
            **kwargs: 技能特定的参数

        Returns:
            SkillExecutionResult: 执行结果
        """
        pass

    async def validate_input(
        self, input_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        验证输入参数

        Args:
            input_data: 输入数据

        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        for param in self.metadata.parameters:
            if param.name in input_data:
                valid, error = param.validate(input_data[param.name])
                if not valid:
                    return False, error
            elif param.required:
                return False, f"Required parameter '{param.name}' is missing"

        return True, None

    async def initialize(self) -> None:
        """初始化技能资源"""
        pass

    async def cleanup(self) -> None:
        """清理技能资源"""
        pass

    async def health_check(self) -> bool:
        """检查技能健康状态"""
        return True

    def get_capabilities(self) -> List[str]:
        """获取技能的所有能力"""
        return self.metadata.capabilities

    def get_dependencies(self) -> Dict[str, str]:
        """获取技能的依赖"""
        return self.metadata.dependencies


class SkillRegistry:
    """技能注册表 - 管理已注册的技能"""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._metadata: Dict[str, SkillMetadata] = {}
        self._lock = asyncio.Lock()

    async def register(self, skill: Skill) -> None:
        """
        注册技能

        Args:
            skill: 要注册的技能实例

        Raises:
            ValueError: 如果技能已存在或元数据无效
        """
        async with self._lock:
            metadata = skill.metadata

            if metadata.name in self._skills:
                raise ValueError(f"Skill '{metadata.name}' is already registered")

            if not metadata.name or not metadata.version:
                raise ValueError("Skill metadata must have name and version")

            self._skills[metadata.name] = skill
            self._metadata[metadata.name] = metadata
            logger.info(f"Skill registered: {metadata.name} v{metadata.version}")

    async def unregister(self, skill_name: str) -> bool:
        """
        注销技能

        Args:
            skill_name: 技能名称

        Returns:
            bool: 是否成功注销
        """
        async with self._lock:
            if skill_name in self._skills:
                del self._skills[skill_name]
                del self._metadata[skill_name]
                logger.info(f"Skill unregistered: {skill_name}")
                return True
            return False

    async def get(self, skill_name: str) -> Optional[Skill]:
        """
        获取技能

        Args:
            skill_name: 技能名称

        Returns:
            Skill: 技能实例，如果不存在则返回None
        """
        return self._skills.get(skill_name)

    async def get_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        获取技能元数据

        Args:
            skill_name: 技能名称

        Returns:
            SkillMetadata: 技能元数据，如果不存在则返回None
        """
        return self._metadata.get(skill_name)

    async def list_skills(self) -> List[str]:
        """
        列出所有已注册的技能

        Returns:
            List[str]: 技能名称列表
        """
        return list(self._skills.keys())

    async def list_metadata(self) -> List[SkillMetadata]:
        """
        列出所有技能的元数据

        Returns:
            List[SkillMetadata]: 技能元数据列表
        """
        return list(self._metadata.values())

    async def exists(self, skill_name: str) -> bool:
        """
        检查技能是否存在

        Args:
            skill_name: 技能名称

        Returns:
            bool: 技能是否存在
        """
        return skill_name in self._skills

    async def get_by_capability(self, capability: str) -> List[Skill]:
        """
        根据能力获取技能

        Args:
            capability: 能力名称

        Returns:
            List[Skill]: 具有该能力的技能列表
        """
        result = []
        for skill in self._skills.values():
            if capability in skill.get_capabilities():
                result.append(skill)
        return result

    async def get_by_category(self, category: SkillCategory) -> List[Skill]:
        """
        根据分类获取技能

        Args:
            category: 分类

        Returns:
            List[Skill]: 该分类的技能列表
        """
        result = []
        for skill in self._skills.values():
            if skill.metadata.category == category:
                result.append(skill)
        return result

    async def get_by_tag(self, tag: str) -> List[Skill]:
        """
        根据标签获取技能

        Args:
            tag: 标签名称

        Returns:
            List[Skill]: 具有该标签的技能列表
        """
        result = []
        for skill in self._skills.values():
            if tag in skill.metadata.tags:
                result.append(skill)
        return result

    async def validate_dependencies(self, skill_name: str) -> Tuple[bool, Optional[str]]:
        """
        验证技能的依赖是否都已注册

        Args:
            skill_name: 技能名称

        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        skill = await self.get(skill_name)
        if not skill:
            return False, f"Skill '{skill_name}' not found"

        for dep_name in skill.get_dependencies().keys():
            if not await self.exists(dep_name):
                return False, f"Dependency '{dep_name}' not found"

        return True, None

    async def clear(self) -> None:
        """清空所有已注册的技能"""
        async with self._lock:
            self._skills.clear()
            self._metadata.clear()


class SkillExecutor:
    """技能执行引擎"""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._execution_history: Dict[str, SkillExecutionContext] = {}
        self._lock = asyncio.Lock()

    async def execute(
        self,
        skill_name: str,
        input_data: Dict[str, Any],
        user_id: str = "",
        tenant_id: str = "",
        timeout_seconds: Optional[int] = None,
    ) -> SkillExecutionResult:
        """
        执行技能

        Args:
            skill_name: 技能名称
            input_data: 输入数据
            user_id: 用户ID
            tenant_id: 租户ID
            timeout_seconds: 超时时间（秒）

        Returns:
            SkillExecutionResult: 执行结果
        """
        skill = await self.registry.get(skill_name)
        if not skill:
            return SkillExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' not found",
                error_type="SkillNotFound",
            )

        metadata = skill.metadata
        timeout = timeout_seconds or metadata.timeout_seconds

        # Create execution context
        context = SkillExecutionContext(
            skill_id=metadata.skill_id,
            skill_name=skill_name,
            user_id=user_id,
            tenant_id=tenant_id,
            input_data=input_data,
            timeout_seconds=timeout,
        )

        try:
            # Validate input
            valid, error = await skill.validate_input(input_data)
            if not valid:
                return SkillExecutionResult(
                    success=False,
                    error=error,
                    error_type="ValidationError",
                )

            # Initialize skill
            try:
                await skill.initialize()
            except Exception as e:
                logger.error(f"Skill initialization failed: {str(e)}", exc_info=True)
                return SkillExecutionResult(
                    success=False,
                    error=f"Initialization failed: {str(e)}",
                    error_type="InitializationError",
                )

            # Execute skill with timeout
            context.status = ExecutionStatus.RUNNING
            context.start_time = datetime.now(UTC)

            try:
                result = await asyncio.wait_for(
                    skill.execute(context, **input_data),
                    timeout=timeout,
                )
                context.end_time = datetime.now(UTC)
                context.status = ExecutionStatus.SUCCESS

                # Store execution history
                async with self._lock:
                    self._execution_history[context.execution_id] = context

                return result

            except asyncio.TimeoutError:
                context.end_time = datetime.now(UTC)
                context.status = ExecutionStatus.TIMEOUT
                context.error = f"Execution timeout after {timeout} seconds"

                async with self._lock:
                    self._execution_history[context.execution_id] = context

                return SkillExecutionResult(
                    success=False,
                    error=context.error,
                    error_type="TimeoutError",
                    execution_time_ms=context.get_duration_ms(),
                )

            except Exception as e:
                context.end_time = datetime.now(UTC)
                context.status = ExecutionStatus.FAILED
                context.error = str(e)
                context.error_type = type(e).__name__

                async with self._lock:
                    self._execution_history[context.execution_id] = context

                logger.error(f"Skill execution failed: {str(e)}", exc_info=True)
                return SkillExecutionResult(
                    success=False,
                    error=str(e),
                    error_type=type(e).__name__,
                    execution_time_ms=context.get_duration_ms(),
                )

        finally:
            # Cleanup
            try:
                await skill.cleanup()
            except Exception as e:
                logger.error(f"Skill cleanup failed: {str(e)}", exc_info=True)

    async def get_execution_history(
        self, execution_id: str
    ) -> Optional[SkillExecutionContext]:
        """获取执行历史"""
        return self._execution_history.get(execution_id)

    async def list_execution_history(
        self, skill_name: str, limit: int = 100
    ) -> List[SkillExecutionContext]:
        """列出执行历史"""
        results = []
        for context in self._execution_history.values():
            if context.skill_name == skill_name:
                results.append(context)
        return sorted(results, key=lambda x: x.created_at, reverse=True)[:limit]

    async def clear_execution_history(self) -> None:
        """清空执行历史"""
        async with self._lock:
            self._execution_history.clear()


# Global instances
_registry: Optional[SkillRegistry] = None
_executor: Optional[SkillExecutor] = None
_lock = asyncio.Lock()


async def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表"""
    global _registry
    if _registry is None:
        async with _lock:
            if _registry is None:
                _registry = SkillRegistry()
    return _registry


async def get_skill_executor() -> SkillExecutor:
    """获取全局技能执行引擎"""
    global _executor
    if _executor is None:
        async with _lock:
            if _executor is None:
                _executor = SkillExecutor(await get_skill_registry())
    return _executor


__all__ = [
    "SkillStatus",
    "SkillCategory",
    "SkillRiskLevel",
    "ExecutionStatus",
    "SkillParameter",
    "SkillMetadata",
    "SkillExecutionContext",
    "SkillExecutionResult",
    "Skill",
    "SkillRegistry",
    "SkillExecutor",
    "get_skill_registry",
    "get_skill_executor",
]
