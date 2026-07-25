"""P2-10 + P2-11: 代码评审 Agent + 技能自沉淀测试.

P2-10 覆盖:
- Diff 解析 (文件数/增删行/风险级别)
- 评审意见生成 (blocking/suggestion/nit)
- 审批决策逻辑
- CodeReviewer 端到端

P2-11 覆盖:
- 模式提取 (PatternHarvester)
- 技能生成 (SkillGenerator)
- Curator 去重/淘汰
- 沉淀引擎闭环
"""

import pytest

from backend.app.core.code_review.diff_analyzer import DiffAnalyzer, DiffAnalysis
from backend.app.core.code_review.comment_generator import (
    CommentGenerator,
    CommentSeverity,
    ReviewResult,
)
from backend.app.core.code_review.reviewer import CodeReviewer
from backend.app.core.skill_distillation.harvester import PatternHarvester
from backend.app.core.skill_distillation.generator import SkillGenerator, SkillDraft
from backend.app.core.skill_distillation.curator import SkillCurator
from backend.app.core.skill_distillation.sedimentation import (
    SkillSedimentationEngine,
    SedimentationEvent,
)


# ─── P2-10: Diff 解析 ─────────────────────────────────────────────────────────

SAMPLE_DIFF = """\
diff --git a/backend/app/core/agent.py b/backend/app/core/agent.py
index abc1234..def5678 100644
--- a/backend/app/core/agent.py
+++ b/backend/app/core/agent.py
@@ -10,6 +10,8 @@ class Agent:
     def run(self):
         pass
+    def new_method(self):
+        return True
diff --git a/backend/app/api/routes.py b/backend/app/api/routes.py
index 1111111..2222222 100644
--- a/backend/app/api/routes.py
+++ b/backend/app/api/routes.py
@@ -1,3 +1,5 @@
 from fastapi import APIRouter
+import os
+import sys
 router = APIRouter()
"""


class TestDiffAnalyzer:
    def setup_method(self):
        self.analyzer = DiffAnalyzer()

    def test_file_count(self):
        result = self.analyzer.analyze(SAMPLE_DIFF)
        assert result.file_count == 2

    def test_additions_deletions(self):
        result = self.analyzer.analyze(SAMPLE_DIFF)
        assert result.total_additions == 4
        assert result.total_deletions == 0

    def test_affected_modules(self):
        result = self.analyzer.analyze(SAMPLE_DIFF)
        assert "backend/app" in result.affected_modules

    def test_risk_level_low(self):
        result = self.analyzer.analyze(SAMPLE_DIFF)
        assert result.risk_level == "low"

    def test_risk_level_high(self):
        # 生成大量变更
        big_diff = "\n".join(
            f"diff --git a/file{i}.py b/file{i}.py\n+line\n" for i in range(25)
        )
        result = self.analyzer.analyze(big_diff)
        assert result.risk_level == "high"

    def test_language_detection(self):
        result = self.analyzer.analyze(SAMPLE_DIFF)
        assert result.files[0].language == "python"

    def test_empty_diff(self):
        result = self.analyzer.analyze("")
        assert result.file_count == 0
        assert result.risk_level == "low"


class TestCommentGenerator:
    def setup_method(self):
        self.generator = CommentGenerator()
        self.analyzer = DiffAnalyzer()

    def test_generate_from_analysis_no_findings(self):
        analysis = self.analyzer.analyze(SAMPLE_DIFF)
        result = self.generator.generate_from_analysis("test-1", analysis)
        assert result.approval == "approve"
        assert result.blocking_count == 0

    def test_generate_with_blocking_findings(self):
        analysis = self.analyzer.analyze(SAMPLE_DIFF)
        findings = [
            {"file": "agent.py", "line": 12, "severity": "blocking", "message": "SQL injection risk"}
        ]
        result = self.generator.generate_from_analysis("test-2", analysis, findings)
        assert result.approval == "request_changes"
        assert result.blocking_count == 1

    def test_summary_generation(self):
        analysis = self.analyzer.analyze(SAMPLE_DIFF)
        result = self.generator.generate_from_analysis("test-3", analysis)
        assert "2 个文件" in result.summary
        assert "low" in result.summary


class TestCodeReviewer:
    @pytest.mark.asyncio
    async def test_review_diff_end_to_end(self):
        reviewer = CodeReviewer()
        result = await reviewer.review_diff(SAMPLE_DIFF, pr_number=42)
        assert result.pr_number == 42
        assert result.review_id
        assert result.approval in ("approve", "comment", "request_changes")

    @pytest.mark.asyncio
    async def test_review_stored(self):
        reviewer = CodeReviewer()
        result = await reviewer.review_diff(SAMPLE_DIFF)
        fetched = reviewer.get_review(result.review_id)
        assert fetched is not None
        assert fetched.review_id == result.review_id

    @pytest.mark.asyncio
    async def test_review_pr(self):
        reviewer = CodeReviewer()
        result = await reviewer.review_pr(99, SAMPLE_DIFF)
        assert result.pr_number == 99

    def test_get_review_not_found(self):
        reviewer = CodeReviewer()
        assert reviewer.get_review("nonexistent") is None


# ─── P2-11: 模式提取 ──────────────────────────────────────────────────────────


class TestPatternHarvester:
    def setup_method(self):
        self.harvester = PatternHarvester(min_frequency=2, min_sequence_length=2)

    def _make_trajectory(self, tools: list[str]) -> list[dict]:
        return [{"tool": t, "type": "tool_call", "success": True, "duration_ms": 100} for t in tools]

    def test_harvest_repeated_pattern(self):
        trajectories = [
            self._make_trajectory(["search", "read", "write"]),
            self._make_trajectory(["search", "read", "write"]),
            self._make_trajectory(["search", "read", "write"]),
        ]
        result = self.harvester.harvest(trajectories)
        assert result.reusable_candidates > 0
        assert result.patterns[0].frequency >= 3

    def test_harvest_no_pattern(self):
        trajectories = [
            self._make_trajectory(["a", "b"]),
            self._make_trajectory(["c", "d"]),
        ]
        result = self.harvester.harvest(trajectories)
        assert result.reusable_candidates == 0

    def test_harvest_empty(self):
        result = self.harvester.harvest([])
        assert result.reusable_candidates == 0
        assert result.total_trajectories_analyzed == 0


class TestSkillGenerator:
    def setup_method(self):
        self.generator = SkillGenerator()

    def test_generate_from_pattern(self):
        from backend.app.core.skill_distillation.harvester import ToolCallPattern
        pattern = ToolCallPattern(
            sequence=["search_code", "read_file", "write_file"],
            frequency=5,
            success_rate=0.9,
        )
        draft = self.generator.generate_from_pattern(pattern)
        assert draft.name
        assert "workflow" in draft.name
        assert len(draft.steps) == 3
        assert draft.status == "draft"

    def test_to_skill_md(self):
        from backend.app.core.skill_distillation.harvester import ToolCallPattern
        pattern = ToolCallPattern(sequence=["a", "b"], frequency=3, success_rate=1.0)
        draft = self.generator.generate_from_pattern(pattern)
        md = draft.to_skill_md()
        assert "# " in md
        assert "触发条件" in md
        assert "执行步骤" in md

    def test_generate_batch(self):
        from backend.app.core.skill_distillation.harvester import ToolCallPattern
        patterns = [
            ToolCallPattern(sequence=["x", "y"], frequency=3),
            ToolCallPattern(sequence=["a", "b", "c"], frequency=4),
        ]
        drafts = self.generator.generate_batch(patterns)
        assert len(drafts) == 2


class TestSkillCurator:
    def setup_method(self):
        self.curator = SkillCurator(max_skills=50, similarity_threshold=0.8)

    def _make_draft(self, name: str, steps: list[str]) -> SkillDraft:
        return SkillDraft(name=name, description="test", steps=steps)

    def test_add_candidate(self):
        draft = self._make_draft("skill-a", ["step1", "step2"])
        status = self.curator.add_candidate(draft)
        assert status == "added"

    def test_duplicate_detection(self):
        d1 = self._make_draft("skill-a", ["step1", "step2", "step3"])
        d2 = self._make_draft("skill-b", ["step1", "step2", "step3"])
        self.curator.add_candidate(d1)
        status = self.curator.add_candidate(d2)
        assert status == "duplicate"

    def test_promote(self):
        draft = self._make_draft("skill-x", ["a", "b"])
        self.curator.add_candidate(draft)
        assert self.curator.promote("skill-x")
        assert self.curator.stats.promoted == 1

    def test_reject(self):
        draft = self._make_draft("skill-y", ["c", "d"])
        self.curator.add_candidate(draft)
        assert self.curator.reject("skill-y")
        assert self.curator.stats.rejected == 1

    def test_promote_not_found(self):
        assert not self.curator.promote("nonexistent")

    def test_list_candidates(self):
        self.curator.add_candidate(self._make_draft("s1", ["a"]))
        self.curator.add_candidate(self._make_draft("s2", ["b", "c"]))
        candidates = self.curator.list_candidates()
        assert len(candidates) == 2


# ─── P2-11: 沉淀引擎闭环 ─────────────────────────────────────────────────────


class TestSedimentationEngine:
    def setup_method(self):
        self.engine = SkillSedimentationEngine(
            min_frequency=2,
            min_sequence_length=2,
            auto_promote=False,
        )

    def _make_trajectory(self, tools: list[str]) -> list[dict]:
        return [{"tool": t, "type": "tool_call", "success": True, "duration_ms": 50} for t in tools]

    @pytest.mark.asyncio
    async def test_sediment_with_pattern(self):
        # 先积累足够的轨迹
        for _ in range(3):
            self.engine.record_trajectory("t", self._make_trajectory(["search", "read", "write"]))

        event = await self.engine.try_sediment(
            trace_id="trace-1",
            task="分析代码",
            trajectory=self._make_trajectory(["search", "read", "write"]),
            success=True,
        )
        assert event.decision == "sedimented"
        assert event.drafts_accepted > 0
        assert len(event.skill_names) > 0

    @pytest.mark.asyncio
    async def test_sediment_failed_task(self):
        event = await self.engine.try_sediment(
            trace_id="trace-2", task="失败任务", trajectory=[], success=False
        )
        assert event.decision == "task_failed"

    @pytest.mark.asyncio
    async def test_sediment_no_pattern(self):
        event = await self.engine.try_sediment(
            trace_id="trace-3", task="单步", trajectory=[{"tool": "x"}], success=True
        )
        assert event.decision == "no_pattern"

    @pytest.mark.asyncio
    async def test_duplicate_rejection(self):
        # 先沉淀一次
        for _ in range(3):
            self.engine.record_trajectory("t", self._make_trajectory(["a", "b", "c"]))
        await self.engine.try_sediment("t1", "task1", self._make_trajectory(["a", "b", "c"]), True)

        # 再次尝试相同模式
        event = await self.engine.try_sediment("t2", "task2", self._make_trajectory(["a", "b", "c"]), True)
        assert event.drafts_rejected_duplicate > 0 or event.decision == "all_duplicate"

    def test_get_stats(self):
        stats = self.engine.get_stats()
        assert "total_events" in stats
        assert "total_skills" in stats
        assert stats["total_events"] == 0

    @pytest.mark.asyncio
    async def test_promote_and_reject(self):
        for _ in range(3):
            self.engine.record_trajectory("t", self._make_trajectory(["x", "y", "z"]))
        event = await self.engine.try_sediment("t1", "task", self._make_trajectory(["x", "y", "z"]), True)
        if event.skill_names:
            name = event.skill_names[0]
            assert self.engine.promote_skill(name)
            skills = self.engine.list_skills(status="promoted")
            assert any(s["name"] == name for s in skills)

    def test_record_trajectory_buffer_limit(self):
        for i in range(120):
            self.engine.record_trajectory(f"t{i}", [{"tool": "a"}])
        assert len(self.engine._trajectory_buffer) <= 100
