"""代码评审 Agent 模块测试。"""
import pytest

from backend.app.core.code_review.diff_analyzer import DiffAnalyzer, DiffAnalysis
from backend.app.core.code_review.comment_generator import (
    CommentGenerator,
    CommentSeverity,
    ReviewResult,
)
from backend.app.core.code_review.reviewer import CodeReviewer

SAMPLE_DIFF = """\
diff --git a/backend/app/main.py b/backend/app/main.py
index abc1234..def5678 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -10,6 +10,8 @@ def create_app():
     app = FastAPI()
+    app.add_middleware(CORSMiddleware)
+    app.include_router(new_router)
     return app
diff --git a/backend/app/utils.py b/backend/app/utils.py
index 1111111..2222222 100644
--- a/backend/app/utils.py
+++ b/backend/app/utils.py
@@ -1,3 +1,4 @@
 def helper():
-    return old_value
+    return new_value
+    # TODO: cleanup
"""


class TestDiffAnalyzer:
    """Diff 解析测试。"""

    def test_parse_files(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SAMPLE_DIFF)
        assert result.file_count == 2
        assert result.files[0].path == "backend/app/main.py"
        assert result.files[1].path == "backend/app/utils.py"

    def test_count_additions_deletions(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SAMPLE_DIFF)
        assert result.total_additions == 4
        assert result.total_deletions == 1

    def test_detect_language(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SAMPLE_DIFF)
        assert result.files[0].language == "python"

    def test_affected_modules(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SAMPLE_DIFF)
        assert "backend/app" in result.affected_modules

    def test_risk_level_low(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze(SAMPLE_DIFF)
        assert result.risk_level == "low"

    def test_empty_diff(self):
        analyzer = DiffAnalyzer()
        result = analyzer.analyze("")
        assert result.file_count == 0
        assert result.risk_level == "low"


class TestCommentGenerator:
    """评审意见生成测试。"""

    def test_generate_no_findings(self):
        analyzer = DiffAnalyzer()
        analysis = analyzer.analyze(SAMPLE_DIFF)
        gen = CommentGenerator()
        result = gen.generate_from_analysis("rev-1", analysis)
        assert result.approval == "approve"
        assert result.blocking_count == 0

    def test_generate_with_blocking(self):
        analyzer = DiffAnalyzer()
        analysis = analyzer.analyze(SAMPLE_DIFF)
        gen = CommentGenerator()
        findings = [
            {"file": "main.py", "line": 12, "severity": "blocking", "message": "Security issue"}
        ]
        result = gen.generate_from_analysis("rev-2", analysis, findings)
        assert result.approval == "request_changes"
        assert result.blocking_count == 1

    def test_summary_generated(self):
        analyzer = DiffAnalyzer()
        analysis = analyzer.analyze(SAMPLE_DIFF)
        gen = CommentGenerator()
        result = gen.generate_from_analysis("rev-3", analysis)
        assert "2 个文件" in result.summary


class TestCodeReviewer:
    """评审器集成测试。"""

    @pytest.mark.asyncio
    async def test_review_diff_no_llm(self):
        reviewer = CodeReviewer(llm_router=None)
        result = await reviewer.review_diff(SAMPLE_DIFF, pr_number=42)
        assert result.pr_number == 42
        assert result.approval == "approve"
        assert result.review_id != ""

    @pytest.mark.asyncio
    async def test_get_review(self):
        reviewer = CodeReviewer(llm_router=None)
        result = await reviewer.review_diff(SAMPLE_DIFF)
        fetched = reviewer.get_review(result.review_id)
        assert fetched is not None
        assert fetched.review_id == result.review_id

    @pytest.mark.asyncio
    async def test_get_review_nonexistent(self):
        reviewer = CodeReviewer(llm_router=None)
        assert reviewer.get_review("nope") is None

    def test_review_result_serialization(self):
        result = ReviewResult(review_id="r1", summary="test")
        d = result.to_dict()
        assert d["review_id"] == "r1"
        assert "blocking_count" in d
