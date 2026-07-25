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
    success_rate: float = 0.0
    promoted_at: float = field(default_factory=time.time)


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
            if score > best_score:
                best_score = score
                best_match = skill

        return best_match if best_score > 0 else None

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
