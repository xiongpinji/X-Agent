"""Unit tests for backend.app.core.evolution_engine — GEPA self-evolution cycle."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.evolution_engine import (
    EvolutionEngine,
    PromotedSkill,
    Reflection,
    SkillDraft,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """Evolution engine without LLM (heuristic mode)."""
    return EvolutionEngine(llm_router=None, memory=None, min_confidence=0.5)


@pytest.fixture()
def engine_with_llm():
    """Evolution engine with a mocked LLM router."""
    mock_llm = AsyncMock()
    return EvolutionEngine(llm_router=mock_llm, memory=None, min_confidence=0.5), mock_llm


def _success_trajectory(tool_names: list[str]) -> dict:
    """Build a minimal successful trajectory."""
    return {"tool_calls": [{"name": n} for n in tool_names]}


def _success_result() -> dict:
    return {"status": "completed", "output": "Task done successfully"}


def _llm_reflection_response(
    skill_name: str = "test_skill",
    confidence: float = 0.9,
    description: str = "A reusable test pattern",
    patterns: list[str] | None = None,
) -> MagicMock:
    """Create a mock LLM response for reflection."""
    resp = MagicMock()
    resp.content = json.dumps({
        "should_create_skill": True,
        "skill_name": skill_name,
        "confidence": confidence,
        "pattern_description": description,
        "key_patterns": patterns or ["test", "auto"],
    })
    return resp


# ---------------------------------------------------------------------------
# on_task_complete — pattern extraction
# ---------------------------------------------------------------------------


class TestOnTaskComplete:
    """Test the on_task_complete lifecycle hook."""

    @pytest.mark.asyncio
    async def test_returns_none_for_failed_task(self, engine: EvolutionEngine):
        """Failed tasks should not trigger reflection."""
        result = await engine.on_task_complete(
            _success_trajectory(["read", "write"]),
            {"status": "failed", "output": "error"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_extracts_patterns_heuristic(self, engine: EvolutionEngine):
        """With >= 3 tool calls and no LLM, heuristic should suggest a skill."""
        reflection = await engine.on_task_complete(
            _success_trajectory(["search", "read", "write", "verify"]),
            _success_result(),
        )
        assert reflection is not None
        assert reflection.should_create_skill is True
        assert reflection.confidence == 0.6
        assert reflection.tool_sequence == ["search", "read", "write", "verify"]

    @pytest.mark.asyncio
    async def test_records_execution_history(self, engine: EvolutionEngine):
        """Every call should append to execution history."""
        await engine.on_task_complete(_success_trajectory(["a"]), _success_result())
        await engine.on_task_complete(_success_trajectory(["b"]), {"status": "failed"})
        assert len(engine._execution_history) == 2

    @pytest.mark.asyncio
    async def test_llm_reflection_parses_json(self, engine_with_llm):
        """When LLM returns valid JSON, reflection should be populated."""
        engine, mock_llm = engine_with_llm
        mock_llm.chat.return_value = _llm_reflection_response(
            skill_name="deploy_skill",
            confidence=0.9,
            description="CI/CD deployment pattern",
            patterns=["docker", "deploy", "k8s"],
        )

        reflection = await engine.on_task_complete(
            _success_trajectory(["docker_build", "docker_push", "kubectl_apply"]),
            _success_result(),
        )
        assert reflection is not None
        assert reflection.should_create_skill is True
        assert reflection.skill_name_suggestion == "deploy_skill"
        assert reflection.confidence == 0.9
        assert "docker" in reflection.key_patterns

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_gracefully(self, engine_with_llm):
        """LLM errors should not crash; confidence defaults to 0.3."""
        engine, mock_llm = engine_with_llm
        mock_llm.chat.side_effect = RuntimeError("LLM unavailable")

        reflection = await engine.on_task_complete(
            _success_trajectory(["a", "b", "c"]),
            _success_result(),
        )
        assert reflection is not None
        assert reflection.confidence == 0.3


# ---------------------------------------------------------------------------
# get_stats — correct structure
# ---------------------------------------------------------------------------


class TestGetStats:
    """Verify get_stats returns the expected structure."""

    def test_initial_stats(self, engine: EvolutionEngine):
        stats = engine.get_stats()
        assert stats == {
            "total_executions": 0,
            "skill_drafts": 0,
            "promoted_skills": 0,
            "skill_names": [],
        }

    @pytest.mark.asyncio
    async def test_stats_after_executions(self, engine: EvolutionEngine):
        await engine.on_task_complete(
            _success_trajectory(["x", "y", "z"]),
            _success_result(),
        )
        stats = engine.get_stats()
        assert stats["total_executions"] == 1
        assert isinstance(stats["skill_drafts"], int)
        assert isinstance(stats["promoted_skills"], int)
        assert isinstance(stats["skill_names"], list)


# ---------------------------------------------------------------------------
# promoted_skills list
# ---------------------------------------------------------------------------


class TestPromotedSkills:
    """Test skill promotion pipeline."""

    @pytest.mark.asyncio
    async def test_skill_promoted_when_confidence_high(self):
        """Skill with confidence >= min_confidence should be promoted."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = _llm_reflection_response(
            skill_name="promoted_skill", confidence=0.9,
            description="A reusable pattern", patterns=["test", "auto"],
        )
        engine = EvolutionEngine(llm_router=mock_llm, memory=None, min_confidence=0.5)

        await engine.on_task_complete(
            _success_trajectory(["a", "b", "c"]),
            _success_result(),
        )
        assert len(engine.promoted_skills) == 1
        skill = engine.promoted_skills[0]
        assert isinstance(skill, PromotedSkill)
        assert skill.name == "promoted_skill"
        assert skill.success_rate == 0.9

    @pytest.mark.asyncio
    async def test_skill_not_promoted_below_min_confidence(self):
        """If confidence is below min_confidence, no promotion."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = _llm_reflection_response(
            skill_name="weak_skill", confidence=0.3,
            description="Weak pattern",
        )
        engine = EvolutionEngine(llm_router=mock_llm, memory=None, min_confidence=0.7)

        await engine.on_task_complete(
            _success_trajectory(["a", "b", "c"]),
            _success_result(),
        )
        # confidence 0.3 < min_confidence 0.7 → skill extraction skipped
        assert len(engine.promoted_skills) == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_promotions(self):
        """Same skill name should not be promoted twice."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = _llm_reflection_response(
            skill_name="dup_skill", confidence=0.9,
            description="Duplicate pattern",
        )
        engine = EvolutionEngine(llm_router=mock_llm, memory=None, min_confidence=0.5)

        traj = _success_trajectory(["a", "b", "c"])
        await engine.on_task_complete(traj, _success_result())
        await engine.on_task_complete(traj, _success_result())
        # _curate rejects duplicate names
        assert len(engine.promoted_skills) == 1

    @pytest.mark.asyncio
    async def test_promoted_skill_persisted_to_memory(self):
        """If memory is provided, promoted skill should be stored."""
        mock_llm = AsyncMock()
        mock_llm.chat.return_value = _llm_reflection_response(
            skill_name="mem_skill", confidence=0.9,
            description="Memory pattern",
        )
        mock_memory = AsyncMock()
        engine = EvolutionEngine(llm_router=mock_llm, memory=mock_memory, min_confidence=0.5)

        await engine.on_task_complete(
            _success_trajectory(["x", "y", "z"]),
            _success_result(),
        )
        mock_memory.store.assert_called_once()
        call_kwargs = mock_memory.store.call_args[1]
        assert "evolution" in call_kwargs.get("tags", [])


# ---------------------------------------------------------------------------
# match_skill
# ---------------------------------------------------------------------------


class TestMatchSkill:
    """Test skill matching for incoming tasks."""

    def test_match_by_trigger_keywords(self, engine: EvolutionEngine):
        engine.promoted_skills.append(
            PromotedSkill(
                id="s1",
                name="deploy",
                trigger_pattern="docker,k8s,deploy",
                tool_sequence=["docker_build"],
            )
        )
        match = engine.match_skill("Please deploy the docker container to k8s")
        assert match is not None
        assert match.name == "deploy"

    def test_no_match_returns_none(self, engine: EvolutionEngine):
        engine.promoted_skills.append(
            PromotedSkill(id="s1", name="deploy", trigger_pattern="docker,k8s")
        )
        assert engine.match_skill("Write a poem about cats") is None


# ---------------------------------------------------------------------------
# _curate validation
# ---------------------------------------------------------------------------


class TestCurate:
    """Test curation gate logic."""

    def test_rejects_empty_name(self, engine: EvolutionEngine):
        draft = SkillDraft(name="", description="desc", quality_score=0.9, tool_sequence=["a"])
        assert engine._curate(draft) is False

    def test_rejects_low_quality(self, engine: EvolutionEngine):
        draft = SkillDraft(name="s", description="d", quality_score=0.1, tool_sequence=["a"])
        assert engine._curate(draft) is False

    def test_rejects_empty_tool_sequence(self, engine: EvolutionEngine):
        draft = SkillDraft(name="s", description="d", quality_score=0.9, tool_sequence=[])
        assert engine._curate(draft) is False

    def test_accepts_valid_draft(self, engine: EvolutionEngine):
        draft = SkillDraft(name="s", description="d", quality_score=0.9, tool_sequence=["a"])
        assert engine._curate(draft) is True
