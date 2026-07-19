"""
技能基类 - 定义所有技能必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime


class SkillMetadata(BaseModel):
    """技能元数据"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = []
    capabilities: List[str] = []
    tags: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SkillContext(BaseModel):
    """技能执行上下文"""
    skill_name: str
    execution_id: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    timeout: int = 300
    metadata: Dict[str, Any] = {}


class SkillResult(BaseModel):
    """技能执行结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = {}


class Skill(ABC):
    """技能基类 - 所有技能必须继承此类"""

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """返回技能元数据"""
        pass

    @abstractmethod
    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        """
        执行技能

        Args:
            context: 技能执行上下文
            **kwargs: 技能特定的参数

        Returns:
            SkillResult: 执行结果
        """
        pass

    async def validate(self, context: SkillContext, **kwargs) -> bool:
        """
        验证输入参数

        Args:
            context: 技能执行上下文
            **kwargs: 技能特定的参数

        Returns:
            bool: 验证是否通过
        """
        return True

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

    def get_dependencies(self) -> List[str]:
        """获取技能的依赖"""
        return self.metadata.dependencies
