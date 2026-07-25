"""X-Agent Skills System - Core skill definitions and protocols"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class SkillStatus(StrEnum):
    """Skill lifecycle status"""
    UNREGISTERED = "unregistered"
    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    DEPRECATED = "deprecated"


class SkillCapability(StrEnum):
    """Built-in skill capabilities"""
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_CONVERT = "document:convert"
    DATA_ANALYZE = "data:analyze"
    DATA_TRANSFORM = "data:transform"
    DATA_AGGREGATE = "data:aggregate"
    TEXT_EXTRACT = "text:extract"
    TEXT_ANALYZE = "text:analyze"
    TEXT_GENERATE = "text:generate"
    IMAGE_PROCESS = "image:process"
    IMAGE_ANALYZE = "image:analyze"
    IMAGE_GENERATE = "image:generate"
    NETWORK_REQUEST = "network:request"
    NETWORK_STREAM = "network:stream"
    SYSTEM_EXECUTE = "system:execute"
    SYSTEM_MONITOR = "system:monitor"
    CUSTOM = "custom"


class SkillRiskLevel(StrEnum):
    """Risk assessment for skills"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SkillMetadata:
    """Metadata for a skill"""
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    capabilities: list[SkillCapability] = field(default_factory=list)
    required_capabilities: list[SkillCapability] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    risk_level: SkillRiskLevel = SkillRiskLevel.MEDIUM
    requires_approval: bool = False
    allowed_actions: list[str] = field(default_factory=lambda: ["read", "execute"])
    timeout_seconds: int = 300
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    tags: list[str] = field(default_factory=list)
    documentation_url: str = ""
    repository_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "capabilities": [c.value for c in self.capabilities],
            "required_capabilities": [c.value for c in self.required_capabilities],
            "dependencies": self.dependencies,
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "allowed_actions": self.allowed_actions,
            "timeout_seconds": self.timeout_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "tags": self.tags,
            "documentation_url": self.documentation_url,
            "repository_url": self.repository_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SkillExecutionContext:
    """Context for skill execution"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    user_id: str = ""
    tenant_id: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    error: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SkillProtocol(Protocol):
    """Protocol for skill implementations"""
    metadata: SkillMetadata

    async def initialize(self) -> None:
        """Initialize the skill"""
        ...

    async def execute(self, context: SkillExecutionContext) -> dict[str, Any]:
        """Execute the skill with given context"""
        ...

    async def validate_input(self, input_data: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate input data"""
        ...

    async def cleanup(self) -> None:
        """Cleanup resources"""
        ...


@dataclass
class SkillExecutionResult:
    """Result of skill execution"""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    resource_usage: dict[str, float] = field(default_factory=dict)


__all__ = [
    "SkillCapability",
    "SkillExecutionContext",
    "SkillExecutionResult",
    "SkillMetadata",
    "SkillProtocol",
    "SkillRiskLevel",
    "SkillStatus",
]
