"""技能自沉淀闭环模块测试。"""
import pytest

from backend.app.core.skill_distillation.harvester import PatternHarvester, ToolCallPattern
from backend.app.core.skill_distillation.generator import SkillGenerator, SkillDraft
from backend.app.core.skill_distillation.curator import SkillCurator


def _make_trajectory(tools: list[str]) -> list[dict]:
    return [{"type": "tool_call", "tool": t, "duration_ms": 10, "success": True} for t in tools]


class TestPatternHarvester:
    """模式提取测试。"""

    def test_harvest_repeated_pattern(self):
        harvester = PatternHarvester(min_frequency=3, min_sequence_length=2)
        trajectories = [
            _make_trajectory(["search", "read", "write"]),
            _make_trajectory(["search", "read", "write"]),
            _make_trajectory(["search", "read", "write"]),
        ]
        result = harvester.harvest(trajectories)
        assert result.reusable_candidates > 0
        assert result.patterns[0].frequency >= 3

    def test_harvest_no_pattern(self):
        harvester = PatternHarvester(min_frequency=5)
        trajectories = [_make_trajectory(["a", "b"])]
        result = harvester.harvest(trajectories)
        assert result.reusable_candidates == 0

    def test_harvest_empty(self):
        harvester = PatternHarvester()
        result = harvester.harvest([])
        assert result.total_trajectories_analyzed == 0
        assert result.reusable_candidates == 0

    def test_pattern_signature(self):
        p = ToolCallPattern(sequence=["search", "read"])
        assert p.signature == "search → read"


class TestSkillGenerator:
    """技能生成测试。"""

    def test_generate_from_pattern(self):
        gen = SkillGenerator()
        pattern = ToolCallPattern(sequence=["search", "read", "write"], frequency=5)
        draft = gen.generate_from_pattern(pattern)
        assert draft.name != ""
        assert len(draft.steps) == 3
        assert "search" in draft.steps[0]

    def test_skill_md_generation(self):
        gen = SkillGenerator()
        pattern = ToolCallPattern(sequence=["deploy", "verify"], frequency=3)
        draft = gen.generate_from_pattern(pattern)
        md = draft.to_skill_md()
        assert "# " in md
        assert "触发条件" in md
        assert "执行步骤" in md

    def test_main_py_generation(self):
        gen = SkillGenerator()
        pattern = ToolCallPattern(sequence=["build", "test"], frequency=4)
        draft = gen.generate_from_pattern(pattern)
        py = draft.to_main_py()
        assert "async def execute" in py
        assert draft.name in py

    def test_generate_batch(self):
        gen = SkillGenerator()
        patterns = [
            ToolCallPattern(sequence=["a", "b"], frequency=3),
            ToolCallPattern(sequence=["c", "d"], frequency=4),
        ]
        drafts = gen.generate_batch(patterns)
        assert len(drafts) == 2

    def test_draft_serialization(self):
        draft = SkillDraft(name="test-skill", description="desc")
        d = draft.to_dict()
        assert d["name"] == "test-skill"
        assert d["status"] == "draft"


class TestSkillCurator:
    """技能管理测试。"""

    def test_add_candidate(self):
        curator = SkillCurator()
        draft = SkillDraft(name="s1", description="d", steps=["step1", "step2"])
        status = curator.add_candidate(draft)
        assert status == "added"

    def test_duplicate_detection(self):
        curator = SkillCurator(similarity_threshold=0.8)
        d1 = SkillDraft(name="s1", description="d", steps=["a", "b", "c"])
        d2 = SkillDraft(name="s2", description="d", steps=["a", "b", "c"])
        curator.add_candidate(d1)
        status = curator.add_candidate(d2)
        assert status == "duplicate"

    def test_promote(self):
        curator = SkillCurator()
        draft = SkillDraft(name="s1", description="d", steps=["x"])
        curator.add_candidate(draft)
        assert curator.promote("s1")
        assert curator.stats.promoted == 1

    def test_reject(self):
        curator = SkillCurator()
        draft = SkillDraft(name="s1", description="d", steps=["x"])
        curator.add_candidate(draft)
        assert curator.reject("s1")
        assert curator.stats.rejected == 1

    def test_list_candidates(self):
        curator = SkillCurator()
        curator.add_candidate(SkillDraft(name="s1", description="d", steps=["a"]))
        curator.add_candidate(SkillDraft(name="s2", description="d", steps=["b"]))
        curator.promote("s1")
        candidates = curator.list_candidates()
        assert len(candidates) == 1
        assert candidates[0].name == "s2"
