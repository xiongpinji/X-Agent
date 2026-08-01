"""Closed-loop self-evolution engine (对标 Hermes GEPA).

Flow: Execute -> Reflect -> Extract Skill -> Curate -> Promote -> Reuse
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class Reflection:
    """Result of reflecting on a task execution."""
    task_summary: str = ""
    key_patterns: list[str] = field(default_factory=list)
    tool_sequence: list[str] = field(default_factory=list)
    should_create_skill: bool = False
    skill_name_suggestion: str = ""
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class SkillDraft:
    """A draft skill extracted from successful execution."""
    name: str = ""
    description: str = ""
    trigger_pattern: str = ""
    code: str = ""
    tool_sequence: list[str] = field(default_factory=list)
    success_count: int = 0
    quality_score: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class PromotedSkill:
    """A skill that passed curation and is available for reuse."""
    id: str = ""
    name: str = ""
    description: str = ""
    trigger_pattern: str = ""
    code: str = ""
    tool_sequence: list[str] = field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    promoted_at: float = field(default_factory=time.time)
    last_used_at: float = 0.0
    version: int = 1
    improvement_history: list[dict[str, Any]] = field(default_factory=list)

    def record_usage(self, success: bool) -> None:
        """Record skill usage outcome for self-improvement tracking."""
        self.usage_count += 1
        self.last_used_at = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.success_rate = self.success_count / self.usage_count if self.usage_count > 0 else 0.0

    def needs_improvement(self) -> bool:
        """Check if skill needs improvement based on success rate."""
        return self.usage_count >= 3 and self.success_rate < 0.7


class EvolutionEngine:
    """Hermes-style closed-loop self-evolution engine.

    Implements the GEPA cycle:
    - Generate: Extract patterns from successful executions
    - Evaluate: Score and curate extracted skills
    - Promote: Mount qualified skills for reuse
    - Apply: Match incoming tasks to available skills
    """

    def __init__(self, llm_router=None, memory=None, min_confidence: float = 0.7):
        self.llm_router = llm_router
        self.memory = memory
        self.min_confidence = min_confidence
        self.skill_drafts: list[SkillDraft] = []
        self.promoted_skills: list[PromotedSkill] = []
        self._execution_history: list[dict[str, Any]] = []

    async def on_task_complete(self, trajectory: dict[str, Any], result: dict[str, Any]) -> Reflection | None:
        """Called after each task execution completes."""
        self._execution_history.append({
            "trajectory": trajectory,
            "result": result,
            "timestamp": time.time(),
        })

        status = result.get("status", "")
        if status not in ("completed", "success"):
            return None

        # 1. Reflect
        reflection = await self._reflect(trajectory, result)

        # 2. Extract skill if warranted
        if reflection.should_create_skill and reflection.confidence >= self.min_confidence:
            skill_draft = await self._extract_skill(trajectory, reflection)
            # 3. Curate
            if self._curate(skill_draft):
                # 4. Promote
                await self._promote_skill(skill_draft)

        return reflection

    async def _reflect(self, trajectory: dict[str, Any], result: dict[str, Any]) -> Reflection:
        """Analyze execution trajectory to extract reusable patterns."""
        reflection = Reflection()
        tool_calls = trajectory.get("tool_calls", [])
        reflection.tool_sequence = [tc.get("name", "") for tc in tool_calls if isinstance(tc, dict)]

        if self.llm_router:
            try:
                prompt = (
                    "Analyze this agent execution trajectory and determine if it contains "
                    "a reusable workflow pattern:\n\n"
                    f"Tool sequence: {reflection.tool_sequence}\n"
                    f"Result status: {result.get('status')}\n"
                    f"Output summary: {str(result.get('output', ''))[:500]}\n\n"
                    'Respond with JSON: {"should_create_skill": bool, '
                    '"skill_name": str, "confidence": float, '
                    '"pattern_description": str, "key_patterns": [str]}'
                )
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_router.chat(messages, tools=[])
                content = response.content if hasattr(response, "content") else str(response)
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(content[json_start:json_end])
                    reflection.should_create_skill = data.get("should_create_skill", False)
                    reflection.skill_name_suggestion = data.get("skill_name", "")
                    reflection.confidence = float(data.get("confidence", 0.0))
                    reflection.key_patterns = data.get("key_patterns", [])
                    reflection.reasoning = data.get("pattern_description", "")
            except Exception as e:
                logger.warning(f"LLM reflection failed: {e}")
                reflection.confidence = 0.3
        else:
            # Heuristic reflection without LLM
            if len(reflection.tool_sequence) >= 3:
                reflection.should_create_skill = True
                reflection.confidence = 0.6
                reflection.skill_name_suggestion = f"auto_skill_{len(self._execution_history)}"

        return reflection

    async def _extract_skill(self, trajectory: dict[str, Any], reflection: Reflection) -> SkillDraft:
        """Extract a reusable skill from the trajectory."""
        draft = SkillDraft(
            name=reflection.skill_name_suggestion or f"skill_{int(time.time())}",
            description=reflection.reasoning,
            trigger_pattern=",".join(reflection.key_patterns[:3]),
            tool_sequence=reflection.tool_sequence,
            quality_score=reflection.confidence,
        )

        if self.llm_router:
            try:
                prompt = (
                    f"Generate a reusable Python async function for this task pattern:\n"
                    f"Name: {draft.name}\n"
                    f"Description: {draft.description}\n"
                    f"Tool sequence: {draft.tool_sequence}\n\n"
                    "Generate a complete `async def execute(context: dict) -> dict` function "
                    "with error handling and type annotations."
                )
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_router.chat(messages, tools=[])
                draft.code = response.content if hasattr(response, "content") else str(response)
            except Exception as e:
                logger.warning(f"Skill code generation failed: {e}")
                draft.code = (
                    f"# Auto-generated skill: {draft.name}\n"
                    "async def execute(context: dict) -> dict:\n"
                    "    raise NotImplementedError('Skill code generation requires LLM')\n"
                )

        self.skill_drafts.append(draft)
        return draft

    def _curate(self, draft: SkillDraft) -> bool:
        """Evaluate skill quality. Only promote high-quality skills."""
        if not draft.name or not draft.description:
            return False
        if draft.quality_score < self.min_confidence:
            return False
        if not draft.tool_sequence:
            return False
        return all(existing.name != draft.name for existing in self.promoted_skills)

    async def _promote_skill(self, draft: SkillDraft) -> None:
        """Promote a curated skill to active use."""
        skill = PromotedSkill(
            id=str(uuid4()),
            name=draft.name,
            description=draft.description,
            trigger_pattern=draft.trigger_pattern,
            code=draft.code,
            tool_sequence=draft.tool_sequence,
            success_rate=draft.quality_score,
        )
        self.promoted_skills.append(skill)
        logger.info(f"Promoted skill: {skill.name} (confidence={skill.success_rate:.2f})")

        if self.memory:
            try:
                await self.memory.store(
                    content=f"Evolved skill: {skill.name}\n{skill.description}\nTools: {skill.tool_sequence}",
                    layer=8,
                    importance=0.8,
                    tags=["evolution", "skill", skill.name],
                )
            except Exception as e:
                logger.warning(f"Failed to persist skill to memory: {e}")

    def match_skill(self, task_description: str) -> PromotedSkill | None:
        """Match an incoming task to an available skill."""
        task_lower = task_description.lower()
        best_match: PromotedSkill | None = None
        best_score = 0.0

        for skill in self.promoted_skills:
            keywords = skill.trigger_pattern.split(",")
            score = sum(1 for kw in keywords if kw.strip().lower() in task_lower)
            # Boost score for high-success-rate skills
            score *= (1.0 + skill.success_rate * 0.5)
            if score > best_score:
                best_score = score
                best_match = skill

        return best_match if best_score > 0 else None

    async def record_skill_usage(
        self,
        skill_id: str,
        success: bool,
        execution_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record skill usage and trigger self-improvement if needed.

        This implements Hermes-like skill self-improvement during use:
        skills that underperform are automatically flagged for refinement.
        """
        skill = next((s for s in self.promoted_skills if s.id == skill_id), None)
        if not skill:
            return {"status": "error", "reason": "skill not found"}

        skill.record_usage(success)

        result = {
            "status": "recorded",
            "skill_name": skill.name,
            "usage_count": skill.usage_count,
            "success_rate": skill.success_rate,
        }

        # Check if skill needs improvement
        if skill.needs_improvement():
            improvement = await self._improve_skill(skill, execution_context)
            result["improvement_triggered"] = True
            result["improvement"] = improvement
        else:
            result["improvement_triggered"] = False

        return result

    async def _improve_skill(
        self,
        skill: PromotedSkill,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Attempt to improve an underperforming skill.

        Uses LLM to analyze failures and generate improved code.
        """
        improvement_record = {
            "version": skill.version,
            "timestamp": time.time(),
            "success_rate_before": skill.success_rate,
            "trigger": "auto_improvement",
        }

        if self.llm_router:
            try:
                prompt = (
                    f"The skill '{skill.name}' has a low success rate ({skill.success_rate:.0%}).\n"
                    f"Current code:\n```python\n{skill.code}\n```\n\n"
                    f"Tool sequence: {skill.tool_sequence}\n"
                    f"Recent context: {context or 'N/A'}\n\n"
                    "Generate an improved version with better error handling and edge case coverage."
                )
                messages = [{"role": "user", "content": prompt}]
                response = await self.llm_router.chat(messages, tools=[])
                new_code = response.content if hasattr(response, "content") else str(response)

                # Extract code block if present
                if "```python" in new_code:
                    start = new_code.find("```python") + 9
                    end = new_code.find("```", start)
                    if end > start:
                        new_code = new_code[start:end].strip()

                skill.code = new_code
                skill.version += 1
                improvement_record["success"] = True
                improvement_record["new_version"] = skill.version
            except Exception as e:
                logger.warning(f"Skill improvement failed: {e}")
                improvement_record["success"] = False
                improvement_record["error"] = str(e)
        else:
            improvement_record["success"] = False
            improvement_record["error"] = "LLM not available for improvement"

        skill.improvement_history.append(improvement_record)
        return improvement_record

    async def nudge_memory_persistence(self) -> dict[str, Any]:
        """Periodic nudge to persist learned knowledge to memory.

        Implements Hermes-like memory nudge system: periodically
        consolidates learnings into long-term memory.
        """
        if not self.memory:
            return {"status": "skipped", "reason": "no memory backend"}

        persisted = 0
        # Persist high-value skills
        for skill in self.promoted_skills:
            if skill.success_rate >= 0.8 and skill.usage_count >= 5:
                try:
                    await self.memory.store(
                        content=(
                            f"Proven skill: {skill.name}\n"
                            f"Success rate: {skill.success_rate:.0%} over {skill.usage_count} uses\n"
                            f"Tools: {skill.tool_sequence}\n"
                            f"Trigger: {skill.trigger_pattern}"
                        ),
                        layer=8,  # Long-term skill memory
                        importance=0.9,
                        tags=["evolution", "proven_skill", skill.name],
                    )
                    persisted += 1
                except Exception as e:
                    logger.warning(f"Failed to persist skill {skill.name}: {e}")

        return {
            "status": "completed",
            "persisted_skills": persisted,
            "total_promoted": len(self.promoted_skills),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get evolution engine statistics."""
        return {
            "total_executions": len(self._execution_history),
            "skill_drafts": len(self.skill_drafts),
            "promoted_skills": len(self.promoted_skills),
            "skill_names": [s.name for s in self.promoted_skills],
        }


# Global singleton
evolution_engine = EvolutionEngine()
