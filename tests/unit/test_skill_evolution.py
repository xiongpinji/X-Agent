"""Unit tests for backend.app.core.skill_evolution — closed-loop skill evolution."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from backend.app.core.skill_evolution import (
    AuditAction,
    EvolutionStore,
    EvolvedSkill,
    PatternStatus,
    RestrictedSandbox,
    SkillEvolutionSystem,
    SkillStatus,
    _signature,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    return EvolutionStore(path=tmp_path / "state.json")


@pytest.fixture()
def system(store):
    # A failing LLM keeps tests deterministic and offline (template path).
    failing_llm = AsyncMock()
    failing_llm.chat.side_effect = RuntimeError("llm unavailable")
    return SkillEvolutionSystem(store=store, llm_router=failing_llm)


def _feed(system, text="convert csv file into json report", n=5,
          tools=None, duration_ms=8000.0):
    tools = tools or ["read_file", "parse_csv", "to_json", "write_file"]
    for _ in range(n):
        system.record_interaction(text, tool_calls=tools, duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_signature_normalizes_and_dedupes():
    assert _signature("Convert the CSV file into JSON!") == _signature(
        "please convert csv file to json")


def test_discovery_scores_and_proposes(system):
    system.discovery.propose_threshold = 1.0
    _feed(system, n=5)
    system.record_interaction("a one-off unique request", tool_calls=["x"], duration_ms=10)

    proposed = system.discovery.discover()
    assert len(proposed) == 1
    pattern = proposed[0]
    assert pattern.frequency == 5
    assert pattern.status == PatternStatus.PROPOSED
    assert pattern.score > 0
    # complexity reflects the 4-tool sequence (4/5 = 0.8)
    assert pattern.complexity == pytest.approx(0.8)


def test_discovery_ignores_singletons(system):
    system.discovery.propose_threshold = 0.0
    system.record_interaction("only once", tool_calls=["a"], duration_ms=100)
    assert system.discovery.discover() == []


# ---------------------------------------------------------------------------
# Sandbox security
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_sandbox_neutralizes_dangerous_import_usage():
    sb = RestrictedSandbox()
    # `import os` is stripped and the `system` attribute is blocked, so the
    # dangerous call can never succeed.
    code = "import os\nasync def execute(c):\n    return {'r': os.system('echo hi')}"
    outcome = await sb.run_skill(code, "")
    assert not outcome.success


@pytest.mark.asyncio()
async def test_sandbox_blocks_dunder_escape():
    sb = RestrictedSandbox()
    code = "async def execute(c):\n    return (1).__class__.__bases__"
    outcome = await sb.run_skill(code, "")
    assert not outcome.success
    assert outcome.violations


@pytest.mark.asyncio()
async def test_sandbox_runs_valid_skill():
    sb = RestrictedSandbox()
    code = (
        "import json\n"
        "async def execute(context):\n"
        "    return {'status': 'completed', 'n': len(context)}\n"
    )
    test = (
        "TEST_CASES = [{'input': {}}, {'input': {'a': 1}}]\n"
        "def validate(result, case):\n"
        "    return result.get('status') == 'completed'\n"
    )
    outcome = await sb.run_skill(code, test)
    assert outcome.success
    assert outcome.tests_run == 2
    assert outcome.tests_passed == 2


@pytest.mark.asyncio()
async def test_sandbox_strips_unused_disallowed_import():
    sb = RestrictedSandbox()
    # asyncio is unused and disallowed — should be stripped, not fatal.
    code = (
        "import asyncio\n"
        "async def execute(context):\n"
        "    return {'status': 'ok'}\n"
    )
    outcome = await sb.run_skill(code, "")
    assert outcome.success


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_generator_template_fallback(store):
    # An LLM that always fails forces the deterministic template path.
    failing_llm = AsyncMock()
    failing_llm.chat.side_effect = RuntimeError("llm unavailable")
    system = SkillEvolutionSystem(store=store, llm_router=failing_llm)
    system.discovery.propose_threshold = 1.0
    _feed(system)
    pattern = system.discovery.discover()[0]
    skill = await system.generator.generate(pattern)
    assert skill.current is not None
    assert skill.current.generation_source == "template"
    assert "async def execute" in skill.current.code
    assert pattern.status == PatternStatus.GENERATED


@pytest.mark.asyncio()
async def test_generator_uses_llm_when_available(store):
    mock_llm = AsyncMock()
    mock_llm.chat.return_value.content = (
        "```python\n"
        "async def execute(context):\n"
        "    return {'status': 'completed'}\n"
        "```\n"
        "```test\n"
        "TEST_CASES = [{'input': {}}]\n"
        "def validate(result, case):\n"
        "    return result.get('status') == 'completed'\n"
        "```\n"
    )
    system = SkillEvolutionSystem(store=store, llm_router=mock_llm)
    system.discovery.propose_threshold = 1.0
    _feed(system)
    pattern = system.discovery.discover()[0]
    skill = await system.generator.generate(pattern)
    assert skill.current.generation_source == "llm"
    assert "TEST_CASES" in skill.current.test_code


# ---------------------------------------------------------------------------
# Evaluation + deployment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_evaluate_and_deploy(system):
    system.discovery.propose_threshold = 1.0
    _feed(system)
    pattern = system.discovery.discover()[0]
    skill = await system.generator.generate(pattern)
    evaluation = await system.evaluator.evaluate(skill)
    assert evaluation.tests_run > 0
    assert evaluation.passed
    assert evaluation.ab_test.get("winner") == "skill"


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_optimizer_refactors_underperformer(system):
    skill = EvolvedSkill(name="weak", description="d", pattern_id="p")
    from backend.app.core.skill_evolution import SkillVersion
    skill.versions.append(SkillVersion(version=1, code="async def execute(c):\n    return {}",
                                       test_code=""))
    skill.active_version = 1
    skill.status = SkillStatus.ACTIVE
    skill.usage_count = 5
    skill.success_count = 1
    skill.failure_count = 4
    skill.success_rate = 0.2
    system.store.skills.append(skill)

    assert system.optimizer.needs_refactor(skill)
    result = await system.optimizer.optimize(skill.id)
    assert result["status"] == "optimized"
    assert len(skill.versions) >= 2
    assert system.store.metrics.total_optimizations == 1


def test_optimizer_deprecates_stale(system):
    skill = EvolvedSkill(name="stale", description="d", pattern_id="p")
    skill.status = SkillStatus.ACTIVE
    skill.last_used_at = time.time() - 31 * 86400  # 31 days ago
    system.store.skills.append(skill)

    deprecated = system.optimizer.deprecate_stale()
    assert len(deprecated) == 1
    assert skill.status == SkillStatus.DEPRECATED
    assert system.store.metrics.skills_deprecated == 1


def test_optimizer_keeps_recent_skills(system):
    skill = EvolvedSkill(name="fresh", description="d", pattern_id="p")
    skill.status = SkillStatus.ACTIVE
    skill.last_used_at = time.time()
    system.store.skills.append(skill)
    assert system.optimizer.deprecate_stale() == []


# ---------------------------------------------------------------------------
# Loop + persistence + audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_full_loop_cycle(system):
    system.discovery.propose_threshold = 1.0
    _feed(system)
    summary = await system.loop.run_cycle()
    assert summary["proposed_patterns"] >= 1
    assert summary["skills_generated"] >= 1
    assert summary["cycle"] == 1
    assert system.store.metrics.loop_cycles == 1


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    store = EvolutionStore(path=path)
    skill = EvolvedSkill(name="persisted", description="d", pattern_id="p")
    skill.status = SkillStatus.ACTIVE
    store.skills.append(skill)
    store.audit(AuditAction.SKILL_DEPLOYED, skill_id=skill.id)
    store.save()

    reloaded = EvolutionStore(path=path)
    assert len(reloaded.skills) == 1
    assert reloaded.skills[0].name == "persisted"
    assert reloaded.skills[0].status == SkillStatus.ACTIVE
    assert len(reloaded.audit_log) == 1


def test_audit_trail_records_actions(system):
    system.discovery.propose_threshold = 1.0
    _feed(system)
    system.discovery.discover()
    actions = {e.action for e in system.store.audit_log}
    assert AuditAction.PATTERN_DISCOVERED in actions
    assert AuditAction.PATTERN_PROPOSED in actions


def test_match_skill_returns_active_only(system):
    skill = EvolvedSkill(name="m", description="d", pattern_id="p",
                         trigger_keywords=["csv", "json", "convert"])
    skill.status = SkillStatus.ACTIVE
    skill.success_rate = 0.9
    system.store.skills.append(skill)
    assert system.match_skill("convert csv to json") is skill

    skill.status = SkillStatus.DEPRECATED
    assert system.match_skill("convert csv to json") is None
