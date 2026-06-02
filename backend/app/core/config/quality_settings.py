"""轻量配置值对象(供 test_code_quality_improvements 等使用)。

这些类是独立的、可单独实例化的配置片段(LogSettings / DatabaseSettings /
CacheSettings / ExecutionSettings / SecuritySettings),与 `settings.py` 里
聚合的 `Settings` 不同:它们用于按领域分组的简单参数校验,字段带边界约束,
非法取值会触发 pydantic 的 ValidationError(其继承自 ValueError)。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LogSettings(BaseModel):
    """日志配置。"""

    level: str = "INFO"
    format: str = "plain"


class DatabaseSettings(BaseModel):
    """数据库连接池配置。"""

    pool_size: int = Field(default=10, ge=1, le=100)


class CacheSettings(BaseModel):
    """缓存配置。"""

    enabled: bool = False
    backend: str = "memory"


class ExecutionSettings(BaseModel):
    """执行器配置。"""

    max_iterations: int = Field(default=4, ge=1, le=100)
    timeout: int = Field(default=300, ge=1)


class SecuritySettings(BaseModel):
    """安全配置。"""

    api_key: str = ""
