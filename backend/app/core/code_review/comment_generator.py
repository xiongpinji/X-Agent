"""评审意见生成器。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CommentSeverity(StrEnum):
    """评审意见严重级别。"""

    BLOCKING = "blocking"
    SUGGESTION = "suggestion"
    NIT = "nit"


@dataclass
class ReviewComment:
    """单条评审意见。"""

    file_path: str
    line: int
    severity: CommentSeverity
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "line": self.line,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class ReviewResult:
    """完整评审结果。"""

    review_id: str
    pr_number: int | None = None
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""
    approval: str = "request_changes"  # approve / request_changes / comment
    risk_level: str = "low"

    @property
    def blocking_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == CommentSeverity.BLOCKING)

    @property
    def suggestion_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == CommentSeverity.SUGGESTION)

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "pr_number": self.pr_number,
            "comments": [c.to_dict() for c in self.comments],
            "summary": self.summary,
            "approval": self.approval,
            "risk_level": self.risk_level,
            "blocking_count": self.blocking_count,
            "suggestion_count": self.suggestion_count,
        }


class CommentGenerator:
    """从分析结果生成结构化评审意见。"""

    def generate_from_analysis(
        self,
        review_id: str,
        diff_analysis: Any,
        llm_findings: list[dict[str, Any]] | None = None,
    ) -> ReviewResult:
        """基于 diff 分析和 LLM 发现生成评审结果。"""
        result = ReviewResult(
            review_id=review_id,
            risk_level=diff_analysis.risk_level if diff_analysis else "low",
        )

        # 从 LLM 发现生成意见
        if llm_findings:
            for finding in llm_findings:
                result.comments.append(
                    ReviewComment(
                        file_path=finding.get("file", ""),
                        line=finding.get("line", 0),
                        severity=CommentSeverity(finding.get("severity", "suggestion")),
                        message=finding.get("message", ""),
                        suggestion=finding.get("suggestion", ""),
                    )
                )

        # 基于风险级别决定审批状态
        if result.blocking_count > 0:
            result.approval = "request_changes"
        elif diff_analysis and diff_analysis.risk_level == "high":
            result.approval = "comment"
        else:
            result.approval = "approve"

        # 生成摘要
        result.summary = self._build_summary(result, diff_analysis)
        return result

    def _build_summary(self, result: ReviewResult, diff_analysis: Any) -> str:
        parts = []
        if diff_analysis:
            parts.append(f"变更 {diff_analysis.file_count} 个文件")
            parts.append(f"+{diff_analysis.total_additions}/-{diff_analysis.total_deletions}")
            parts.append(f"风险: {diff_analysis.risk_level}")
        parts.append(f"评审意见: {result.blocking_count} blocking, {result.suggestion_count} suggestion")
        return " | ".join(parts)
