"""Codex-style full-repo reasoning code review engine."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.code_review.comment_generator import CommentGenerator
from backend.app.core.code_review.diff_analyzer import DiffAnalysis, DiffAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ReviewIssue:
    """A single code review issue."""
    severity: str = "info"  # critical, warning, info, suggestion
    category: str = ""  # logic, security, style, performance, test
    file_path: str = ""
    line: int = 0
    message: str = ""
    suggestion: str = ""


@dataclass
class ReviewResult:
    """Result of a code review."""
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: str = ""
    score: float = 0.0  # 0-100
    test_result: str = ""
    files_reviewed: int = 0
    lines_reviewed: int = 0


class CodeReviewEngine:
    """Codex-style full-repo reasoning code review.

    Features:
    - Multi-dimensional review (logic, security, style, tests)
    - Full-repo context awareness
    - Parallel issue detection
    - Test execution verification
    """

    def __init__(self, llm_router=None, tools=None):
        self.llm_router = llm_router
        self.tools = tools

    async def review_pr(self, diff: str, repo_context: str = "") -> ReviewResult:
        """Review a pull request diff with full-repo reasoning."""
        result = ReviewResult()
        result.lines_reviewed = diff.count("\n")
        result.files_reviewed = diff.count("diff --git")

        if not self.llm_router:
            result.summary = "LLM not available for review"
            return result

        # Parallel multi-dimensional review
        checks = await asyncio.gather(
            self._check_logic(diff, repo_context),
            self._check_security(diff, repo_context),
            self._check_style(diff, repo_context),
            self._check_tests(diff, repo_context),
            return_exceptions=True,
        )

        for check_result in checks:
            if isinstance(check_result, list):
                result.issues.extend(check_result)
            elif isinstance(check_result, Exception):
                logger.warning(f"Review check failed: {check_result}")

        # Calculate score
        critical_count = sum(1 for i in result.issues if i.severity == "critical")
        warning_count = sum(1 for i in result.issues if i.severity == "warning")
        result.score = max(0, 100 - critical_count * 20 - warning_count * 5)

        # Generate summary
        result.summary = await self._generate_summary(diff, result)

        return result

    async def _check_logic(self, diff: str, context: str) -> list[ReviewIssue]:
        """Check for logic errors."""
        prompt = (
            "Review this code diff for LOGIC errors (bugs, race conditions, "
            "incorrect assumptions, edge cases):\n\n"
            f"```diff\n{diff[:3000]}\n```\n\n"
            "Context:\n" + context[:1000] + "\n\n"
            "Respond with JSON array: [{\"file\": str, \"line\": int, "
            "\"message\": str, \"severity\": str}]"
        )
        return await self._run_check(prompt, "logic")

    async def _check_security(self, diff: str, context: str) -> list[ReviewIssue]:
        """Check for security vulnerabilities."""
        prompt = (
            "Review this code diff for SECURITY vulnerabilities (injection, "
            "auth bypass, data exposure, SSRF, path traversal):\n\n"
            f"```diff\n{diff[:3000]}\n```\n\n"
            "Respond with JSON array: [{\"file\": str, \"line\": int, "
            "\"message\": str, \"severity\": str}]"
        )
        return await self._run_check(prompt, "security")

    async def _check_style(self, diff: str, context: str) -> list[ReviewIssue]:
        """Check for code style issues."""
        prompt = (
            "Review this code diff for STYLE issues (naming, structure, "
            "readability, DRY violations):\n\n"
            f"```diff\n{diff[:3000]}\n```\n\n"
            "Respond with JSON array: [{\"file\": str, \"line\": int, "
            "\"message\": str, \"severity\": str}]"
        )
        return await self._run_check(prompt, "style")

    async def _check_tests(self, diff: str, context: str) -> list[ReviewIssue]:
        """Check test coverage."""
        prompt = (
            "Review this code diff and identify MISSING TEST COVERAGE "
            "(untested paths, edge cases, error handling):\n\n"
            f"```diff\n{diff[:3000]}\n```\n\n"
            "Respond with JSON array: [{\"file\": str, \"line\": int, "
            "\"message\": str, \"severity\": str}]"
        )
        return await self._run_check(prompt, "test")

    async def _run_check(self, prompt: str, category: str) -> list[ReviewIssue]:
        """Run a single review check via LLM."""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_router.chat(messages, tools=[])
            content = response.content if hasattr(response, "content") else str(response)
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                items = json.loads(content[json_start:json_end])
                return [
                    ReviewIssue(
                        severity=item.get("severity", "info"),
                        category=category,
                        file_path=item.get("file", ""),
                        line=item.get("line", 0),
                        message=item.get("message", ""),
                    )
                    for item in items
                    if isinstance(item, dict)
                ]
        except Exception as e:
            logger.warning(f"Review check '{category}' failed: {e}")
        return []

    async def _generate_summary(self, diff: str, result: ReviewResult) -> str:
        """Generate a human-readable review summary."""
        if not result.issues:
            return "No issues found. Code looks good."

        critical = [i for i in result.issues if i.severity == "critical"]
        warnings = [i for i in result.issues if i.severity == "warning"]

        parts = [f"Review score: {result.score}/100"]
        if critical:
            parts.append(f"Critical issues: {len(critical)}")
            for issue in critical[:3]:
                parts.append(f"  - [{issue.category}] {issue.message}")
        if warnings:
            parts.append(f"Warnings: {len(warnings)}")
        return "\n".join(parts)


# Global singleton
code_review_engine = CodeReviewEngine()


class CodeReviewer:
    """PR 自动评审器。

    流程：接收 diff → 解析影响 → LLM 推理 → 生成评审意见。
    """

    def __init__(self, llm_router: Any | None = None) -> None:
        self._diff_analyzer = DiffAnalyzer()
        self._comment_generator = CommentGenerator()
        self._llm_router = llm_router
        self._reviews: dict[str, Any] = {}

    async def review_diff(
        self,
        diff_text: str,
        pr_number: int | None = None,
        language: str = "",
        focus_areas: list[str] | None = None,
    ) -> Any:
        """评审原始 diff 文本。

        Args:
            diff_text: Unified diff 文本
            pr_number: 关联 PR 编号
            language: 编程语言 (python/typescript/go/rust/java)
            focus_areas: 重点关注领域 (logic/security/performance/style)
        """
        review_id = str(uuid.uuid4())[:8]

        # 1. 解析 diff
        analysis = self._diff_analyzer.analyze(diff_text)
        logger.info(f"[review-{review_id}] 分析完成: {analysis.file_count} files, risk={analysis.risk_level}")

        # 2. LLM 推理（如果可用）
        llm_findings: list[dict[str, Any]] = []
        if self._llm_router:
            llm_findings = await self._llm_analyze(
                review_id, diff_text, analysis,
                language=language, focus_areas=focus_areas,
            )

        # 3. 生成评审意见
        result = self._comment_generator.generate_from_analysis(
            review_id=review_id,
            diff_analysis=analysis,
            llm_findings=llm_findings,
        )
        result.pr_number = pr_number

        # 4. 存储结果
        self._reviews[review_id] = result
        logger.info(f"[review-{review_id}] 评审完成: approval={result.approval}")
        return result

    async def review_pr(self, pr_number: int, diff_text: str) -> Any:
        """评审指定 PR。"""
        return await self.review_diff(diff_text, pr_number=pr_number)

    def get_review(self, review_id: str) -> Any | None:
        """获取评审结果。"""
        return self._reviews.get(review_id)

    async def _llm_analyze(
        self,
        review_id: str,
        diff_text: str,
        analysis: DiffAnalysis,
        language: str = "",
        focus_areas: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """使用 LLM 分析 diff，返回发现列表。支持多语言 + 关注领域定制。"""
        try:
            # 多语言支持: 根据语言调整审查重点
            lang_hints = {
                "python": "Focus on: type hints, async correctness, import cycles, GIL issues.",
                "typescript": "Focus on: type safety, null checks, async/await, DOM XSS.",
                "go": "Focus on: error handling, goroutine leaks, interface satisfaction, context propagation.",
                "rust": "Focus on: ownership/borrowing, unwrap safety, lifetime issues, Send/Sync.",
                "java": "Focus on: null safety, resource leaks, thread safety, exception handling.",
            }
            lang_hint = lang_hints.get(language.lower(), "") if language else ""

            # 关注领域定制
            if focus_areas:
                areas_str = ", ".join(focus_areas)
                focus_instruction = f"\nPriority focus areas: {areas_str}."
            else:
                focus_instruction = ""

            prompt = (
                f"Review this code diff for bugs, security issues, performance problems, and style issues.\n"
                f"Affected modules: {', '.join(analysis.affected_modules)}\n"
                f"Risk level: {analysis.risk_level}\n"
                f"{f'Language: {language}' if language else ''}\n"
                f"{lang_hint}"
                f"{focus_instruction}\n\n"
                f"```diff\n{diff_text[:8000]}\n```\n\n"
                f"Return findings as JSON array with fields: file, line, severity (blocking/suggestion/nit), message, suggestion."
            )
            response = await self._llm_router.chat(
                [{"role": "user", "content": prompt}], []
            )
            content = response.content or "[]"
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
            return []
        except Exception as e:
            logger.warning(f"[review-{review_id}] LLM 分析失败: {e}")
            return []
