"""Code review engine package."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.core.code_review.comment_generator import CommentGenerator
from backend.app.core.code_review.diff_analyzer import DiffAnalyzer
from backend.app.core.code_review.engine import (
    CodeReviewEngine as StructuredCodeReviewEngine,
)
from backend.app.core.code_review.engine import (
    ReviewComment as StructuredReviewComment,
)
from backend.app.core.code_review.engine import (
    ReviewResult as StructuredReviewResult,
)
from backend.app.core.code_review.reviewer import (
    CodeReviewEngine,
    CodeReviewer,
    ReviewIssue,
    ReviewResult,
    code_review_engine,
)

logger = logging.getLogger(__name__)

# ─── Vulnerability patterns (high-signal review) ─────────────────────────────

_VULN_PATTERNS: list[dict[str, str]] = [
    {"pattern": r"eval\s*\(", "severity": "critical", "desc": "Code injection via eval()"},
    {"pattern": r"exec\s*\(", "severity": "critical", "desc": "Code injection via exec()"},
    {"pattern": r"os\.system\s*\(", "severity": "high", "desc": "OS command injection"},
    {"pattern": r"subprocess\.call\s*\(.*shell\s*=\s*True", "severity": "high", "desc": "Shell injection"},
    {"pattern": r"pickle\.loads?\s*\(", "severity": "high", "desc": "Insecure deserialization"},
    {"pattern": r"(password|secret|token)\s*=\s*['\"][^'\"]+['\"]", "severity": "high", "desc": "Hardcoded credential"},
    {"pattern": r"verify\s*=\s*False", "severity": "medium", "desc": "SSL verification disabled"},
    {"pattern": r"innerHTML\s*=", "severity": "medium", "desc": "Potential XSS"},
]


async def quick_review_files(file_paths: list[str]) -> dict[str, Any] | None:
    """Quick security + quality review of recently written files.

    Called automatically by AgentLoop after file writes (Codex-style high-signal review).
    Returns None if no files could be reviewed.
    """
    import re

    issues: list[dict[str, Any]] = []
    reviewed = 0

    for fp in file_paths[:10]:  # Limit to 10 files
        path = Path(fp)
        if not path.exists() or not path.is_file():
            continue
        # Only review code files
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        reviewed += 1
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            for pat in _VULN_PATTERNS:
                if re.search(pat["pattern"], line):
                    issues.append({
                        "file": str(path),
                        "line": line_no,
                        "severity": pat["severity"],
                        "message": pat["desc"],
                        "code": line.strip()[:100],
                    })

    if reviewed == 0:
        return None

    critical_count = sum(1 for i in issues if i["severity"] == "critical")
    # Quality score: 100 - (critical*20 + high*10 + medium*5)
    score = max(0, 100 - critical_count * 20 - sum(10 for i in issues if i["severity"] == "high") - sum(5 for i in issues if i["severity"] == "medium"))

    return {
        "files_reviewed": reviewed,
        "issues": issues,
        "critical_count": critical_count,
        "quality_score": score,
    }


__all__ = [
    "CodeReviewEngine",
    "CodeReviewer",
    "CommentGenerator",
    "DiffAnalyzer",
    "ReviewIssue",
    "ReviewResult",
    "StructuredCodeReviewEngine",
    "StructuredReviewComment",
    "StructuredReviewResult",
    "code_review_engine",
    "quick_review_files",
]
