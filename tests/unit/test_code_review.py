"""Unit tests for backend.app.core.code_review — DiffAnalyzer, CommentGenerator, CodeReviewer."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.core.code_review.comment_generator import (
    CommentGenerator,
    CommentSeverity,
    ReviewComment,
    ReviewResult as CommentReviewResult,
)
from backend.app.core.code_review.diff_analyzer import DiffAnalysis, DiffAnalyzer, FileChange
from backend.app.core.code_review.reviewer import CodeReviewer


# ---------------------------------------------------------------------------
# Sample diffs
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git a/backend/app/main.py b/backend/app/main.py
index abc1234..def5678 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -10,6 +10,8 @@ from fastapi import FastAPI
 def create_app():
     app = FastAPI()
+    app.add_middleware(CORSMiddleware)
+    app.include_router(new_router)
     return app
-# old comment
diff --git a/tests/test_main.py b/tests/test_main.py
index 1111111..2222222 100644
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1,3 +1,5 @@
 def test_app():
     assert True
+    assert app is not None
+    assert app.title == "X-Agent"
"""

SINGLE_FILE_DIFF = """\
diff --git a/src/utils.py b/src/utils.py
--- a/src/utils.py
+++ b/src/utils.py
@@ -5,3 +5,4 @@ def helper():
     pass
+    return 42
"""


# ---------------------------------------------------------------------------
# DiffAnalyzer tests
# ---------------------------------------------------------------------------


class TestDiffAnalyzer:
    """Verify unified diff parsing."""

    @pytest.fixture()
    def analyzer(self):
        return DiffAnalyzer()

    def test_parses_file_paths(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        paths = [f.path for f in result.files]
        assert "backend/app/main.py" in paths
        assert "tests/test_main.py" in paths

    def test_counts_additions_and_deletions(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        # main.py: +2 additions, -1 deletion; test_main.py: +2 additions
        assert result.total_additions == 4
        assert result.total_deletions == 1

    def test_file_count(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        assert result.file_count == 2

    def test_language_detection(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        main_file = next(f for f in result.files if f.path.endswith("main.py"))
        assert main_file.language == "python"

    def test_affected_modules(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        assert "backend/app" in result.affected_modules
        assert "tests/test_main.py" in result.affected_modules or "tests" in " ".join(result.affected_modules)

    def test_risk_level_low_for_small_diff(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SINGLE_FILE_DIFF)
        assert result.risk_level == "low"

    def test_risk_level_high_for_large_diff(self, analyzer: DiffAnalyzer):
        # Generate a diff with > 500 changes
        lines = ["diff --git a/big.py b/big.py", "--- a/big.py", "+++ b/big.py"]
        lines += [f"+line_{i}" for i in range(600)]
        big_diff = "\n".join(lines)
        result = analyzer.analyze(big_diff)
        assert result.risk_level == "high"

    def test_empty_diff(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze("")
        assert result.file_count == 0
        assert result.total_additions == 0

    def test_diff_hunks_captured(self, analyzer: DiffAnalyzer):
        result = analyzer.analyze(SAMPLE_DIFF)
        main_file = next(f for f in result.files if "main.py" in f.path and "test" not in f.path)
        assert len(main_file.diff_hunks) > 0


# ---------------------------------------------------------------------------
# CommentGenerator tests
# ---------------------------------------------------------------------------


class TestCommentGenerator:
    """Verify structured comment generation."""

    @pytest.fixture()
    def generator(self):
        return CommentGenerator()

    def test_formats_comments_from_llm_findings(self, generator: CommentGenerator):
        analysis = DiffAnalysis(
            files=[FileChange(path="a.py", additions=5, deletions=2)],
            total_additions=5,
            total_deletions=2,
            risk_level="low",
        )
        findings = [
            {"file": "a.py", "line": 10, "severity": "blocking", "message": "Bug found", "suggestion": "Fix it"},
            {"file": "a.py", "line": 20, "severity": "suggestion", "message": "Consider refactor"},
        ]
        result = generator.generate_from_analysis("rev-1", analysis, findings)
        assert len(result.comments) == 2
        assert result.comments[0].severity == CommentSeverity.BLOCKING
        assert result.comments[1].severity == CommentSeverity.SUGGESTION

    def test_approval_request_changes_when_blocking(self, generator: CommentGenerator):
        analysis = DiffAnalysis(risk_level="low")
        findings = [{"file": "x.py", "line": 1, "severity": "blocking", "message": "Critical"}]
        result = generator.generate_from_analysis("rev-2", analysis, findings)
        assert result.approval == "request_changes"

    def test_approval_approve_when_no_blocking(self, generator: CommentGenerator):
        analysis = DiffAnalysis(risk_level="low")
        findings = [{"file": "x.py", "line": 1, "severity": "nit", "message": "Minor"}]
        result = generator.generate_from_analysis("rev-3", analysis, findings)
        assert result.approval == "approve"

    def test_summary_includes_stats(self, generator: CommentGenerator):
        analysis = DiffAnalysis(
            files=[FileChange(path="a.py", additions=3, deletions=1)],
            total_additions=3,
            total_deletions=1,
            risk_level="medium",
        )
        result = generator.generate_from_analysis("rev-4", analysis, [])
        assert "1 个文件" in result.summary
        assert "+3/-1" in result.summary

    def test_to_dict_structure(self, generator: CommentGenerator):
        analysis = DiffAnalysis(risk_level="low")
        result = generator.generate_from_analysis("rev-5", analysis, [])
        d = result.to_dict()
        assert "review_id" in d
        assert "comments" in d
        assert "blocking_count" in d
        assert d["review_id"] == "rev-5"


# ---------------------------------------------------------------------------
# CodeReviewer.review_diff with mocked LLM
# ---------------------------------------------------------------------------


class TestCodeReviewerWithLLM:
    """Test review_diff returns structured result with mocked LLM."""

    @pytest.mark.asyncio
    async def test_review_diff_returns_structured_result(self):
        mock_llm = AsyncMock()
        llm_response = MagicMock()
        llm_response.content = json.dumps([
            {"file": "backend/app/main.py", "line": 12, "severity": "suggestion",
             "message": "Missing type annotation", "suggestion": "Add -> FastAPI"},
        ])
        mock_llm.chat.return_value = llm_response

        reviewer = CodeReviewer(llm_router=mock_llm)
        result = await reviewer.review_diff(SAMPLE_DIFF, pr_number=42)

        assert result.pr_number == 42
        assert len(result.comments) == 1
        assert result.comments[0].message == "Missing type annotation"
        assert result.approval == "approve"  # only suggestion, no blocking

    @pytest.mark.asyncio
    async def test_review_diff_without_llm(self):
        """Without LLM, review should still produce a result based on diff analysis."""
        reviewer = CodeReviewer(llm_router=None)
        result = await reviewer.review_diff(SAMPLE_DIFF)
        assert result is not None
        assert result.risk_level in ("low", "medium", "high")
        assert len(result.comments) == 0  # no LLM findings

    @pytest.mark.asyncio
    async def test_review_stores_result(self):
        reviewer = CodeReviewer(llm_router=None)
        result = await reviewer.review_diff(SAMPLE_DIFF)
        stored = reviewer.get_review(result.review_id)
        assert stored is result


# ---------------------------------------------------------------------------
# Multi-language hints
# ---------------------------------------------------------------------------


class TestMultiLanguageHints:
    """Verify language-specific review hints are applied."""

    @pytest.mark.asyncio
    async def test_python_hint_in_prompt(self):
        mock_llm = AsyncMock()
        llm_response = MagicMock()
        llm_response.content = "[]"
        mock_llm.chat.return_value = llm_response

        reviewer = CodeReviewer(llm_router=mock_llm)
        await reviewer.review_diff(SAMPLE_DIFF, language="python")

        # Check the prompt sent to LLM contains python-specific hints
        call_args = mock_llm.chat.call_args
        prompt_text = call_args[0][0][0]["content"]
        assert "type hints" in prompt_text or "async correctness" in prompt_text

    @pytest.mark.asyncio
    async def test_typescript_hint_in_prompt(self):
        mock_llm = AsyncMock()
        llm_response = MagicMock()
        llm_response.content = "[]"
        mock_llm.chat.return_value = llm_response

        reviewer = CodeReviewer(llm_router=mock_llm)
        ts_diff = "diff --git a/src/app.ts b/src/app.ts\n+const x: number = 1;\n"
        await reviewer.review_diff(ts_diff, language="typescript")

        call_args = mock_llm.chat.call_args
        prompt_text = call_args[0][0][0]["content"]
        assert "type safety" in prompt_text or "null checks" in prompt_text

    @pytest.mark.asyncio
    async def test_focus_areas_in_prompt(self):
        mock_llm = AsyncMock()
        llm_response = MagicMock()
        llm_response.content = "[]"
        mock_llm.chat.return_value = llm_response

        reviewer = CodeReviewer(llm_router=mock_llm)
        await reviewer.review_diff(SAMPLE_DIFF, focus_areas=["security", "performance"])

        call_args = mock_llm.chat.call_args
        prompt_text = call_args[0][0][0]["content"]
        assert "security" in prompt_text
        assert "performance" in prompt_text
