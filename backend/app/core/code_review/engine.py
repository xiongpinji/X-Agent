"""Code Review Engine — LLM-powered structured code review.

P1-07: Provides a high-level code review engine that leverages the project's
LLM routing infrastructure for structured, multi-dimensional code analysis.

Supports:
- Diff-based review (unified diff format)
- Single file review
- Pull Request review with title/description context
- Structured output with severity, category, line references, and suggestions
- Quality scoring (0-100) with approve/reject decision
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReviewComment:
    """A single structured code review comment."""

    severity: str  # "critical" | "warning" | "suggestion" | "info"
    category: str  # "logic_error" | "security" | "performance" | "style" | "best_practice"
    file_path: str
    line_start: int
    line_end: int
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "severity": self.severity,
            "category": self.category,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ReviewResult:
    """Complete result of a code review."""

    summary: str = ""
    comments: list[ReviewComment] = field(default_factory=list)
    score: int = 100  # 0-100
    approved: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "summary": self.summary,
            "comments": [c.to_dict() for c in self.comments],
            "score": self.score,
            "approved": self.approved,
            "metadata": self.metadata,
        }


# ─── Prompt Templates ──────────────────────────────────────────────────────────

_REVIEW_SYSTEM_PROMPT = """\
You are an expert code reviewer. Analyze the provided code and return findings \
as a JSON array. Each finding must have:
- severity: "critical" | "warning" | "suggestion" | "info"
- category: "logic_error" | "security" | "performance" | "style" | "best_practice"
- file_path: string (the file being reviewed)
- line_start: integer (first affected line)
- line_end: integer (last affected line)
- message: string (clear explanation of the issue)
- suggestion: string or null (proposed fix)

Also provide a top-level JSON object with:
- summary: string (brief overall assessment)
- score: integer 0-100 (code quality)
- approved: boolean (whether the code is acceptable)
- comments: array of findings

Return ONLY valid JSON, no markdown fences."""

_DIFF_REVIEW_PROMPT = """\
Review the following {language} code diff for issues:

{context_section}

```diff
{diff}
```

Analyze for: logic errors, security vulnerabilities, performance issues, \
style problems, and best practice violations. \
Return a JSON object with keys: summary, score (0-100), approved (bool), comments (array)."""

_FILE_REVIEW_PROMPT = """\
Review the following {language} source file for issues:

File: {file_path}

```{language}
{content}
```

Analyze for: logic errors, security vulnerabilities, performance issues, \
style problems, and best practice violations. \
Return a JSON object with keys: summary, score (0-100), approved (bool), comments (array)."""

_PR_REVIEW_PROMPT = """\
Review this Pull Request:

Title: {title}
Description: {description}

```diff
{pr_diff}
```

Analyze for: logic errors, security vulnerabilities, performance issues, \
style problems, and best practice violations. Consider whether the PR \
achieves its stated goal. \
Return a JSON object with keys: summary, score (0-100), approved (bool), comments (array)."""


class CodeReviewEngine:
    """LLM-powered structured code review engine.

    Uses the project's LLM routing infrastructure to perform multi-dimensional
    code analysis with structured output.

    Args:
        llm_router: Optional LLM router instance. If None, attempts lazy initialization.
    """

    def __init__(self, llm_router: Any | None = None) -> None:
        self._llm_router = llm_router

    @property
    def llm_router(self) -> Any:
        """Lazy-load the LLM router if not provided at construction."""
        if self._llm_router is None:
            try:
                from backend.app.dependencies import get_llm_router
                self._llm_router = get_llm_router()
            except Exception as exc:
                logger.warning(f"Could not initialize LLM router: {exc}")
        return self._llm_router

    async def review_diff(
        self,
        diff: str,
        language: str = "python",
        context: str = "",
    ) -> ReviewResult:
        """Review a unified diff for code quality issues.

        Args:
            diff: Unified diff text to review.
            language: Programming language of the diff (python/typescript/go/rust/java).
            context: Additional context (e.g., related code, requirements).

        Returns:
            ReviewResult with structured comments, score, and approval decision.
        """
        context_section = f"Additional context:\n{context}\n" if context else ""
        prompt = _DIFF_REVIEW_PROMPT.format(
            language=language,
            context_section=context_section,
            diff=diff[:12000],
        )
        return await self._execute_review(prompt, file_hint=self._extract_file_from_diff(diff))

    async def review_file(
        self,
        content: str,
        file_path: str,
        language: str = "python",
    ) -> ReviewResult:
        """Review a single source file for code quality issues.

        Args:
            content: Full file content to review.
            file_path: Path of the file being reviewed.
            language: Programming language (python/typescript/go/rust/java).

        Returns:
            ReviewResult with structured comments, score, and approval decision.
        """
        prompt = _FILE_REVIEW_PROMPT.format(
            language=language,
            file_path=file_path,
            content=content[:15000],
        )
        return await self._execute_review(prompt, file_hint=file_path)

    async def review_pr(
        self,
        pr_diff: str,
        title: str,
        description: str = "",
    ) -> ReviewResult:
        """Review a Pull Request with title and description context.

        Args:
            pr_diff: The PR's unified diff.
            title: PR title.
            description: PR description/body.

        Returns:
            ReviewResult with structured comments, score, and approval decision.
        """
        prompt = _PR_REVIEW_PROMPT.format(
            title=title,
            description=description or "(no description)",
            pr_diff=pr_diff[:12000],
        )
        return await self._execute_review(prompt, file_hint=self._extract_file_from_diff(pr_diff))

    # ─── Internal ─────────────────────────────────────────────────────────────

    async def _execute_review(self, prompt: str, file_hint: str = "") -> ReviewResult:
        """Execute the LLM review and parse structured output."""
        if not self.llm_router:
            logger.warning("LLM router not available; returning empty review")
            return ReviewResult(
                summary="LLM not available for code review",
                score=0,
                approved=False,
                metadata={"error": "llm_unavailable"},
            )

        try:
            messages = [
                {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            response = await self.llm_router.chat(messages, tools=[])
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_review_response(content, file_hint)
        except Exception as exc:
            logger.error(f"Code review LLM call failed: {exc}", exc_info=True)
            return ReviewResult(
                summary=f"Review failed: {exc}",
                score=0,
                approved=False,
                metadata={"error": str(exc)},
            )

    def _parse_review_response(self, content: str, file_hint: str = "") -> ReviewResult:
        """Parse LLM response into a structured ReviewResult."""
        # Extract JSON from response (handle potential markdown fences)
        json_str = content.strip()
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            json_str = "\n".join(lines)

        # Try to find JSON object
        obj_start = json_str.find("{")
        obj_end = json_str.rfind("}") + 1
        if obj_start < 0 or obj_end <= obj_start:
            logger.warning("Could not parse LLM review response as JSON")
            return ReviewResult(
                summary=content[:500],
                score=50,
                approved=False,
                metadata={"parse_error": True},
            )

        try:
            data = json.loads(json_str[obj_start:obj_end])
        except json.JSONDecodeError as exc:
            logger.warning(f"JSON parse error in review response: {exc}")
            return ReviewResult(
                summary=content[:500],
                score=50,
                approved=False,
                metadata={"parse_error": str(exc)},
            )

        # Parse comments
        comments: list[ReviewComment] = []
        raw_comments = data.get("comments", [])
        if isinstance(raw_comments, list):
            for item in raw_comments:
                if not isinstance(item, dict):
                    continue
                comments.append(ReviewComment(
                    severity=item.get("severity", "info"),
                    category=item.get("category", "best_practice"),
                    file_path=item.get("file_path", file_hint),
                    line_start=int(item.get("line_start", item.get("line", 0))),
                    line_end=int(item.get("line_end", item.get("line", 0))),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion"),
                ))

        score = int(data.get("score", 50))
        score = max(0, min(100, score))
        approved = bool(data.get("approved", score >= 70 and not any(
            c.severity == "critical" for c in comments
        )))

        return ReviewResult(
            summary=data.get("summary", ""),
            comments=comments,
            score=score,
            approved=approved,
            metadata={"comment_count": len(comments)},
        )

    @staticmethod
    def _extract_file_from_diff(diff: str) -> str:
        """Extract the primary file path from a unified diff."""
        for line in diff.split("\n"):
            if line.startswith("+++ b/"):
                return line[6:]
            if line.startswith("--- a/"):
                return line[6:]
        return ""


# Module-level singleton for convenience
code_review_engine = CodeReviewEngine()
