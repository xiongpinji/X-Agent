"""Y. AI Code Review Engine — PR analysis, quality scoring, vulnerability detection, suggestions."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/code-review", tags=["code-review"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# ─── In-memory review store ──────────────────────────────────────────────────

_reviews: list[dict[str, Any]] = []

# ─── Vulnerability patterns ──────────────────────────────────────────────────

VULN_PATTERNS: list[dict[str, str]] = [
    {"pattern": r"eval\s*\(", "severity": "critical", "cwe": "CWE-95", "desc": "Code injection via eval()"},
    {"pattern": r"exec\s*\(", "severity": "critical", "cwe": "CWE-95", "desc": "Code injection via exec()"},
    {"pattern": r"os\.system\s*\(", "severity": "high", "cwe": "CWE-78", "desc": "OS command injection"},
    {"pattern": r"subprocess\.call\s*\(.*shell\s*=\s*True", "severity": "high", "cwe": "CWE-78", "desc": "Shell injection via subprocess"},
    {"pattern": r"pickle\.loads?\s*\(", "severity": "high", "cwe": "CWE-502", "desc": "Insecure deserialization"},
    {"pattern": r"yaml\.load\s*\((?!.*Loader)", "severity": "medium", "cwe": "CWE-502", "desc": "Unsafe YAML load without Loader"},
    {"pattern": r"SELECT.*FROM.*\+.*\b(var|param|input|arg)", "severity": "high", "cwe": "CWE-89", "desc": "Potential SQL injection"},
    {"pattern": r"innerHTML\s*=", "severity": "medium", "cwe": "CWE-79", "desc": "Potential XSS via innerHTML"},
    {"pattern": r"dangerouslySetInnerHTML", "severity": "medium", "cwe": "CWE-79", "desc": "React XSS via dangerouslySetInnerHTML"},
    {"pattern": r"(password|secret|token)\s*=\s*['\"][^'\"]+['\"]", "severity": "high", "cwe": "CWE-798", "desc": "Hardcoded credential"},
    {"pattern": r"verify\s*=\s*False", "severity": "medium", "cwe": "CWE-295", "desc": "SSL verification disabled"},
    {"pattern": r"MD5|SHA1", "severity": "low", "cwe": "CWE-328", "desc": "Weak hash algorithm"},
]

# ─── Quality metrics ─────────────────────────────────────────────────────────


def _compute_quality_score(code: str) -> dict[str, Any]:
    """Compute code quality metrics from source text."""
    lines = code.split("\n")
    total_lines = len(lines)
    blank_lines = sum(1 for l in lines if not l.strip())
    comment_lines = sum(1 for l in lines if l.strip().startswith(("#", "//", "/*", "*")))
    code_lines = total_lines - blank_lines - comment_lines

    # Complexity indicators
    long_lines = sum(1 for l in lines if len(l) > 120)
    deep_indent = sum(1 for l in lines if len(l) - len(l.lstrip()) > 24)
    todo_count = len(re.findall(r"TODO|FIXME|HACK|XXX", code))

    # Function length heuristic
    func_defs = re.findall(r"(?:def |function |async def )\w+", code)
    avg_func_len = code_lines / max(len(func_defs), 1)

    # Score calculation (0-100)
    score = 100.0
    score -= min(long_lines * 2, 20)
    score -= min(deep_indent * 3, 15)
    score -= min(todo_count * 1.5, 10)
    score -= max(0, (avg_func_len - 30) * 0.5)
    if code_lines > 0 and comment_lines / code_lines < 0.1:
        score -= 10  # Low comment ratio
    score = max(0, min(100, round(score, 1)))

    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

    return {
        "score": score,
        "grade": grade,
        "metrics": {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
            "comment_ratio": round(comment_lines / max(code_lines, 1), 3),
            "long_lines_120": long_lines,
            "deep_indent_lines": deep_indent,
            "todo_fixme_count": todo_count,
            "function_count": len(func_defs),
            "avg_function_length": round(avg_func_len, 1),
        },
    }


def _detect_vulnerabilities(code: str) -> list[dict[str, Any]]:
    """Scan code for known vulnerability patterns."""
    findings = []
    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        for vp in VULN_PATTERNS:
            if re.search(vp["pattern"], line, re.IGNORECASE):
                findings.append({
                    "line": i,
                    "severity": vp["severity"],
                    "cwe": vp["cwe"],
                    "description": vp["desc"],
                    "snippet": line.strip()[:100],
                })
    return findings


def _generate_suggestions(code: str, quality: dict, vulns: list) -> list[dict[str, str]]:
    """Generate improvement suggestions based on analysis."""
    suggestions = []
    metrics = quality["metrics"]

    if metrics["comment_ratio"] < 0.1:
        suggestions.append({"type": "documentation", "priority": "medium", "suggestion": "Add docstrings/comments — comment ratio below 10%"})
    if metrics["long_lines_120"] > 5:
        suggestions.append({"type": "style", "priority": "low", "suggestion": f"Break {metrics['long_lines_120']} lines exceeding 120 chars"})
    if metrics["avg_function_length"] > 50:
        suggestions.append({"type": "complexity", "priority": "high", "suggestion": "Split large functions — avg length {:.0f} lines".format(metrics["avg_function_length"])})
    if metrics["deep_indent_lines"] > 3:
        suggestions.append({"type": "complexity", "priority": "medium", "suggestion": "Reduce nesting depth — extract helper functions"})
    if any(v["severity"] == "critical" for v in vulns):
        suggestions.append({"type": "security", "priority": "critical", "suggestion": "CRITICAL: Remove eval/exec usage — use safe alternatives"})
    if any(v["cwe"] == "CWE-798" for v in vulns):
        suggestions.append({"type": "security", "priority": "high", "suggestion": "Move hardcoded credentials to environment variables"})
    if metrics["todo_fixme_count"] > 3:
        suggestions.append({"type": "maintenance", "priority": "low", "suggestion": f"Resolve {metrics['todo_fixme_count']} TODO/FIXME markers"})

    return suggestions


# ─── Y1: Submit Code for Review ──────────────────────────────────────────────


@router.post("/analyze")
async def analyze_code(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Y: Analyze code snippet — quality score, vulnerabilities, suggestions."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    code = body.get("code", "")
    filename = body.get("filename", "snippet.py")
    language = body.get("language", "python")

    if not code:
        return {"error": "No code provided", "field": "code"}

    quality = _compute_quality_score(code)
    vulns = _detect_vulnerabilities(code)
    suggestions = _generate_suggestions(code, quality, vulns)

    review = {
        "id": str(uuid4()),
        "filename": filename,
        "language": language,
        "reviewed_at": datetime.now(UTC).isoformat(),
        "reviewed_by": principal.user_id,
        "quality": quality,
        "vulnerabilities": vulns,
        "vulnerability_count": len(vulns),
        "suggestions": suggestions,
        "verdict": "approve" if quality["score"] >= 75 and not any(v["severity"] == "critical" for v in vulns) else "request_changes",
    }
    _reviews.append(review)

    return review


# ─── Y2: PR Diff Analysis ────────────────────────────────────────────────────


@router.post("/pr-diff")
async def analyze_pr_diff(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Y: Analyze a PR diff — changed files summary, risk assessment, review checklist."""
    enforce_scope(principal, "agent:run")
    body = await request.json()

    files: list[dict] = body.get("files", [])
    title = body.get("title", "Untitled PR")

    file_analyses = []
    total_additions = 0
    total_deletions = 0
    risk_score = 0.0

    for f in files:
        path = f.get("path", "")
        additions = f.get("additions", 0)
        deletions = f.get("deletions", 0)
        patch = f.get("patch", "")
        total_additions += additions
        total_deletions += deletions

        # Risk heuristics
        file_risk = 0.0
        if any(k in path for k in ("auth", "security", "permission", "crypto")):
            file_risk += 30
        if any(k in path for k in ("migration", "schema", "model")):
            file_risk += 20
        if additions + deletions > 200:
            file_risk += 15
        if deletions > additions * 2:
            file_risk += 10  # Large deletion risk

        vulns = _detect_vulnerabilities(patch) if patch else []
        file_risk += len([v for v in vulns if v["severity"] in ("critical", "high")]) * 15

        file_analyses.append({
            "path": path,
            "additions": additions,
            "deletions": deletions,
            "risk": min(100, file_risk),
            "vulnerabilities": vulns,
        })
        risk_score += file_risk

    avg_risk = round(risk_score / max(len(files), 1), 1)
    risk_level = "low" if avg_risk < 20 else "medium" if avg_risk < 50 else "high"

    # Review checklist
    checklist = [
        {"item": "No hardcoded secrets", "auto_checked": not any(v["cwe"] == "CWE-798" for fa in file_analyses for v in fa["vulnerabilities"])},
        {"item": "No SQL injection vectors", "auto_checked": not any(v["cwe"] == "CWE-89" for fa in file_analyses for v in fa["vulnerabilities"])},
        {"item": "PR size reasonable (<500 lines)", "auto_checked": total_additions + total_deletions < 500},
        {"item": "Security-sensitive files reviewed", "auto_checked": not any(fa["risk"] > 50 for fa in file_analyses)},
        {"item": "Tests included", "auto_checked": any("test" in fa["path"] for fa in file_analyses)},
    ]

    return {
        "title": title,
        "files_analyzed": len(files),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "risk_level": risk_level,
        "risk_score": avg_risk,
        "files": file_analyses,
        "checklist": checklist,
        "recommendation": "approve" if risk_level == "low" else "request_changes" if risk_level == "high" else "review_carefully",
        "analyzed_at": datetime.now(UTC).isoformat(),
    }


# ─── Y3: Review History ──────────────────────────────────────────────────────


@router.get("/history")
async def get_review_history(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Y: Get code review history with trend analysis."""
    enforce_scope(principal, "agent:run")

    tenant_reviews = [r for r in _reviews if r.get("reviewed_by") == principal.user_id or True]
    scores = [r["quality"]["score"] for r in tenant_reviews]
    vuln_counts = [r["vulnerability_count"] for r in tenant_reviews]

    return {
        "total_reviews": len(tenant_reviews),
        "reviews": tenant_reviews[-20:],  # Last 20
        "trend": {
            "avg_score": round(sum(scores) / max(len(scores), 1), 1),
            "score_direction": "improving" if len(scores) > 1 and scores[-1] > scores[0] else "declining" if len(scores) > 1 and scores[-1] < scores[0] else "stable",
            "total_vulnerabilities_found": sum(vuln_counts),
            "approve_rate": round(sum(1 for r in tenant_reviews if r["verdict"] == "approve") / max(len(tenant_reviews), 1) * 100, 1),
        },
    }


# ─── Y4: Language-specific Rules ─────────────────────────────────────────────


@router.get("/rules")
async def get_review_rules(principal: PrincipalDependency = None) -> dict[str, Any]:
    """Y: Get configurable review rules by language."""
    enforce_scope(principal, "agent:run")

    return {
        "languages": {
            "python": {
                "max_line_length": 120,
                "max_function_length": 50,
                "require_docstrings": True,
                "banned_patterns": ["eval(", "exec(", "os.system("],
                "style_guide": "PEP 8",
            },
            "javascript": {
                "max_line_length": 100,
                "max_function_length": 40,
                "require_jsdoc": False,
                "banned_patterns": ["innerHTML", "document.write", "eval("],
                "style_guide": "Airbnb",
            },
            "typescript": {
                "max_line_length": 100,
                "max_function_length": 40,
                "strict_types": True,
                "banned_patterns": ["any", "innerHTML", "eval("],
                "style_guide": "TypeScript Strict",
            },
        },
        "vulnerability_patterns": len(VULN_PATTERNS),
        "severity_levels": ["critical", "high", "medium", "low"],
    }


# ─── Y5: Codex-style Inline PR Review ────────────────────────────────────────


@router.post("/inline-review")
async def inline_pr_review(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """Codex-style structured inline review: line-level comments with suggestions.

    Body:
        files: [{"path": str, "diff": str}]  — unified diff per file
        title: str (optional)
        focus: str (optional) — "security" | "performance" | "style" | "all"

    Returns structured inline comments suitable for GitHub/GitLab PR annotation.
    """
    enforce_scope(principal, "agent:run")
    body = await request.json()
    files: list[dict] = body.get("files", [])
    title = body.get("title", "Inline Review")
    focus = body.get("focus", "all")

    if not files:
        return {"error": "No files provided", "field": "files"}

    all_comments: list[dict[str, Any]] = []
    summary_stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "nitpick": 0}

    for f in files:
        path = f.get("path", "")
        diff_text = f.get("diff", "")
        if not diff_text:
            continue

        # Parse diff lines and analyze added lines
        lines = diff_text.split("\n")
        current_line = 0
        for line in lines:
            # Track line numbers from hunk headers
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", line)
            if hunk_match:
                current_line = int(hunk_match.group(1)) - 1
                continue
            if line.startswith("+") and not line.startswith("+++"):
                current_line += 1
                content = line[1:]  # Strip the '+' prefix

                # Security checks
                if focus in ("all", "security"):
                    for vp in VULN_PATTERNS:
                        if re.search(vp["pattern"], content, re.IGNORECASE):
                            comment = {
                                "path": path,
                                "line": current_line,
                                "severity": vp["severity"],
                                "category": "security",
                                "body": f"⚠️ {vp['desc']} ({vp['cwe']})",
                                "suggestion": _get_security_suggestion(vp["cwe"]),
                            }
                            all_comments.append(comment)
                            summary_stats[vp["severity"]] = summary_stats.get(vp["severity"], 0) + 1

                # Performance checks
                if focus in ("all", "performance"):
                    perf_issues = _check_performance(content, current_line, path)
                    for pi in perf_issues:
                        all_comments.append(pi)
                        summary_stats[pi["severity"]] = summary_stats.get(pi["severity"], 0) + 1

                # Style checks
                if focus in ("all", "style"):
                    style_issues = _check_style(content, current_line, path)
                    for si in style_issues:
                        all_comments.append(si)
                        summary_stats[si["severity"]] = summary_stats.get(si["severity"], 0) + 1

            elif line.startswith("-") and not line.startswith("---"):
                pass  # Deleted lines don't increment new line counter
            else:
                current_line += 1

    # Determine verdict
    has_critical = summary_stats["critical"] > 0
    has_high = summary_stats["high"] > 0
    verdict = "request_changes" if has_critical or has_high else "comment" if all_comments else "approve"

    review_record = {
        "id": str(uuid4()),
        "title": title,
        "verdict": verdict,
        "total_comments": len(all_comments),
        "comments": all_comments,
        "summary": summary_stats,
        "files_reviewed": len(files),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "reviewed_by": principal.user_id,
    }
    _reviews.append(review_record)
    return review_record


def _get_security_suggestion(cwe: str) -> str:
    """Return actionable fix suggestion for a CWE."""
    suggestions = {
        "CWE-95": "Use ast.literal_eval() or a safe parser instead of eval()/exec()",
        "CWE-78": "Use subprocess.run() with a list of args (shell=False)",
        "CWE-502": "Use json.loads() or a safe deserializer with allow-list",
        "CWE-89": "Use parameterized queries (placeholders) instead of string concatenation",
        "CWE-79": "Sanitize output with a templating engine or DOMPurify",
        "CWE-798": "Move secrets to environment variables or a vault (e.g. HashiCorp Vault)",
        "CWE-295": "Remove verify=False; use proper CA certificates",
        "CWE-328": "Use SHA-256 or stronger (hashlib.sha256)",
    }
    return suggestions.get(cwe, "Review and remediate according to OWASP guidelines")


def _check_performance(content: str, line: int, path: str) -> list[dict[str, Any]]:
    """Detect common performance anti-patterns."""
    issues = []
    stripped = content.strip()
    if re.search(r"for .+ in .+:.*for .+ in", stripped):
        issues.append({"path": path, "line": line, "severity": "medium", "category": "performance", "body": "🐌 Nested loop detected — consider O(n) algorithm or lookup table", "suggestion": "Use a dict/set for O(1) lookups instead of nested iteration"})
    if re.search(r"\.count\(|\.index\(", stripped) and "for " in stripped:
        issues.append({"path": path, "line": line, "severity": "low", "category": "performance", "body": "📊 .count()/.index() inside loop is O(n²)", "suggestion": "Pre-compute with Counter or a dict"})
    if re.search(r"SELECT .* FROM", stripped, re.IGNORECASE) and "for " in stripped:
        issues.append({"path": path, "line": line, "severity": "high", "category": "performance", "body": "🗄️ N+1 query: SQL inside loop", "suggestion": "Batch into a single query with IN clause or use eager loading"})
    return issues


def _check_style(content: str, line: int, path: str) -> list[dict[str, Any]]:
    """Detect style issues."""
    issues = []
    if len(content) > 120:
        issues.append({"path": path, "line": line, "severity": "nitpick", "category": "style", "body": f"📏 Line too long ({len(content)} > 120 chars)", "suggestion": "Break into multiple lines"})
    if re.search(r"\t", content) and path.endswith(".py"):
        issues.append({"path": path, "line": line, "severity": "nitpick", "category": "style", "body": "🔀 Tab character in Python file (PEP 8: use spaces)", "suggestion": "Replace tabs with 4 spaces"})
    return issues
