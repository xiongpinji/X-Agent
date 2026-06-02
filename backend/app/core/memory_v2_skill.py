"""Memory V2 - Skill Memory Layer (Program Memory)

Automatic SKILL.md generation and management for Agent execution results.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillMetadata(BaseModel):
    """Metadata for a skill memory."""

    skill_id: str = Field(default_factory=lambda: str(uuid4()))
    skill_name: str
    description: str = ""
    category: str = "general"  # agent, tool, workflow, pattern, etc.
    version: str = "1.0.0"
    author_agent_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime | None = None
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0


class SkillExample(BaseModel):
    """Example usage of a skill."""

    title: str
    description: str = ""
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    notes: str = ""


class SkillMemory(BaseModel):
    """Skill memory item (SKILL.md content)."""

    metadata: SkillMetadata
    description: str
    parameters: dict = Field(default_factory=dict)
    returns: dict = Field(default_factory=dict)
    examples: list[SkillExample] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    common_pitfalls: list[str] = Field(default_factory=list)
    performance_notes: str = ""
    security_notes: str = ""
    compatibility_notes: str = ""


class SkillMemoryLayer:
    """Layer 1: Program Memory - Automatic SKILL.md generation and management."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        auto_generate: bool = True,
    ):
        self.storage_path = Path(storage_path) if storage_path else None
        self.auto_generate = auto_generate
        self._skills: dict[str, SkillMemory] = {}
        self._skill_index: dict[str, str] = {}  # skill_name -> skill_id

        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    async def generate_from_execution(
        self,
        agent_id: str,
        execution_result: dict[str, Any],
        skill_name: str,
        description: str = "",
    ) -> SkillMemory:
        """Generate skill memory from agent execution result."""

        if not self.auto_generate:
            raise ValueError("Auto-generation is disabled")

        # Extract skill information
        metadata = SkillMetadata(
            skill_name=skill_name,
            description=description or execution_result.get("description", ""),
            author_agent_id=agent_id,
            category=execution_result.get("category", "general"),
        )

        # Create skill memory
        skill = SkillMemory(
            metadata=metadata,
            description=description or execution_result.get("description", ""),
            parameters=execution_result.get("parameters", {}),
            returns=execution_result.get("returns", {}),
            examples=self._extract_examples(execution_result),
            prerequisites=execution_result.get("prerequisites", []),
            related_skills=execution_result.get("related_skills", []),
            best_practices=execution_result.get("best_practices", []),
            common_pitfalls=execution_result.get("common_pitfalls", []),
            performance_notes=execution_result.get("performance_notes", ""),
            security_notes=execution_result.get("security_notes", ""),
            compatibility_notes=execution_result.get("compatibility_notes", ""),
        )

        # Store skill
        self._skills[metadata.skill_id] = skill
        self._skill_index[skill_name] = metadata.skill_id

        # Save to disk
        if self.storage_path:
            self._save_skill_to_disk(skill)

        logger.info(f"Generated skill memory: {skill_name} ({metadata.skill_id})")
        return skill

    async def update_skill(
        self,
        skill_id: str,
        updates: dict[str, Any],
    ) -> SkillMemory | None:
        """Update an existing skill memory."""

        skill = self._skills.get(skill_id)
        if skill is None:
            return None

        # Update metadata
        if "description" in updates:
            skill.description = updates["description"]
        if "category" in updates:
            skill.metadata.category = updates["category"]
        if "best_practices" in updates:
            skill.best_practices = updates["best_practices"]
        if "common_pitfalls" in updates:
            skill.common_pitfalls = updates["common_pitfalls"]
        if "performance_notes" in updates:
            skill.performance_notes = updates["performance_notes"]
        if "security_notes" in updates:
            skill.security_notes = updates["security_notes"]

        # Update version
        version_parts = skill.metadata.version.split(".")
        version_parts[2] = str(int(version_parts[2]) + 1)
        skill.metadata.version = ".".join(version_parts)
        skill.metadata.updated_at = datetime.now(UTC)

        # Save to disk
        if self.storage_path:
            self._save_skill_to_disk(skill)

        logger.info(f"Updated skill: {skill.metadata.skill_name} v{skill.metadata.version}")
        return skill

    async def add_example(
        self,
        skill_id: str,
        example: SkillExample,
    ) -> SkillMemory | None:
        """Add an example to a skill."""

        skill = self._skills.get(skill_id)
        if skill is None:
            return None

        skill.examples.append(example)
        skill.metadata.updated_at = datetime.now(UTC)

        # Save to disk
        if self.storage_path:
            self._save_skill_to_disk(skill)

        logger.info(f"Added example to skill: {skill.metadata.skill_name}")
        return skill

    async def record_execution(
        self,
        skill_id: str,
        success: bool,
        execution_time_ms: float | None = None,
    ) -> SkillMemory | None:
        """Record skill execution result."""

        skill = self._skills.get(skill_id)
        if skill is None:
            return None

        skill.metadata.usage_count += 1
        skill.metadata.last_used = datetime.now(UTC)

        if success:
            skill.metadata.success_count += 1
        else:
            skill.metadata.failure_count += 1

        # Save to disk
        if self.storage_path:
            self._save_skill_to_disk(skill)

        return skill

    def get_skill(self, skill_id: str) -> SkillMemory | None:
        """Get skill by ID."""
        return self._skills.get(skill_id)

    def get_skill_by_name(self, skill_name: str) -> SkillMemory | None:
        """Get skill by name."""
        skill_id = self._skill_index.get(skill_name)
        if skill_id:
            return self._skills.get(skill_id)
        return None

    def list_skills(
        self,
        category: str | None = None,
        min_usage: int = 0,
    ) -> list[SkillMemory]:
        """List skills with optional filtering."""

        skills = list(self._skills.values())

        if category:
            skills = [s for s in skills if s.metadata.category == category]

        if min_usage > 0:
            skills = [s for s in skills if s.metadata.usage_count >= min_usage]

        return sorted(skills, key=lambda s: s.metadata.usage_count, reverse=True)

    def export_skill_as_markdown(self, skill_id: str) -> str | None:
        """Export skill as SKILL.md format."""

        skill = self._skills.get(skill_id)
        if skill is None:
            return None

        lines = [
            f"# {skill.metadata.skill_name}",
            "",
            "## 描述",
            skill.description,
            "",
            "## 参数",
        ]

        # Parameters
        if skill.parameters:
            for param_name, param_info in skill.parameters.items():
                lines.append(f"- `{param_name}`: {param_info.get('description', '')}")
        else:
            lines.append("无")

        lines.extend(["", "## 返回值"])

        # Returns
        if skill.returns:
            for return_name, return_info in skill.returns.items():
                lines.append(f"- `{return_name}`: {return_info.get('description', '')}")
        else:
            lines.append("无")

        # Examples
        if skill.examples:
            lines.extend(["", "## 示例"])
            for i, example in enumerate(skill.examples, 1):
                lines.append(f"### 示例 {i}: {example.title}")
                if example.description:
                    lines.append(example.description)
                lines.append("```python")
                lines.append(json.dumps(example.input, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("输出:")
                lines.append("```python")
                lines.append(json.dumps(example.output, indent=2, ensure_ascii=False))
                lines.append("```")

        # Best practices
        if skill.best_practices:
            lines.extend(["", "## 最佳实践"])
            for practice in skill.best_practices:
                lines.append(f"- {practice}")

        # Common pitfalls
        if skill.common_pitfalls:
            lines.extend(["", "## 常见陷阱"])
            for pitfall in skill.common_pitfalls:
                lines.append(f"- {pitfall}")

        # Performance notes
        if skill.performance_notes:
            lines.extend(["", "## 性能说明", skill.performance_notes])

        # Security notes
        if skill.security_notes:
            lines.extend(["", "## 安全说明", skill.security_notes])

        # Metadata
        lines.extend([
            "",
            "## 元数据",
            f"- 版本: {skill.metadata.version}",
            f"- 创建时间: {skill.metadata.created_at.isoformat()}",
            f"- 最后更新: {skill.metadata.updated_at.isoformat()}",
            f"- 使用次数: {skill.metadata.usage_count}",
            f"- 成功次数: {skill.metadata.success_count}",
            f"- 失败次数: {skill.metadata.failure_count}",
        ])

        return "\n".join(lines)

    def get_statistics(self) -> dict[str, Any]:
        """Get skill memory statistics."""

        total_usage = sum(s.metadata.usage_count for s in self._skills.values())
        total_success = sum(s.metadata.success_count for s in self._skills.values())
        total_failure = sum(s.metadata.failure_count for s in self._skills.values())

        return {
            "total_skills": len(self._skills),
            "total_usage": total_usage,
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": total_success / total_usage if total_usage > 0 else 0.0,
            "categories": self._get_category_stats(),
        }

    # Private methods

    def _extract_examples(self, execution_result: dict[str, Any]) -> list[SkillExample]:
        """Extract examples from execution result."""

        examples = []
        raw_examples = execution_result.get("examples", [])

        for raw in raw_examples:
            if isinstance(raw, dict):
                examples.append(SkillExample(**raw))

        return examples

    def _get_category_stats(self) -> dict[str, int]:
        """Get statistics by category."""

        stats: dict[str, int] = {}
        for skill in self._skills.values():
            category = skill.metadata.category
            stats[category] = stats.get(category, 0) + 1

        return stats

    def _load_from_disk(self) -> None:
        """Load skills from disk."""

        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    skill = SkillMemory(**data)
                    self._skills[skill.metadata.skill_id] = skill
                    self._skill_index[skill.metadata.skill_name] = skill.metadata.skill_id

            logger.info(f"Loaded {len(self._skills)} skills from disk")
        except Exception as e:
            logger.error(f"Failed to load skills from disk: {e}")

    def _save_skill_to_disk(self, skill: SkillMemory) -> None:
        """Save skill to disk."""

        if not self.storage_path:
            return

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(skill.model_dump_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to save skill to disk: {e}")


# Global instance
skill_memory_layer = SkillMemoryLayer()
