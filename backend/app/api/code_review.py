"""P2-10: 代码评审 Agent API.

端点:
- POST /api/v1/code-review/diff — 提交 diff 文本进行评审
- POST /api/v1/code-review/pr — 评审指定 PR (需 diff)
- GET  /api/v1/code-review/{review_id} — 获取评审结果
- GET  /api/v1/code-review — 列出评审历史
- POST /api/v1/code-review/{review_id}/approve — 标记通过
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.routing import APIRoute
from fastapi.utils import generate_unique_id
from pydantic import BaseModel, Field

from backend.app.core.code_review.comment_generator import ReviewResult
from backend.app.core.code_review.reviewer import CodeReviewer

# ``backend.app.main._register_all_routers`` 历史性地将本 router include 了两次，
# 默认 unique-id 规则会对每条路由产生重复的 OpenAPI operationId（启动告警）。
# 这里用进程内计数器保证每次 inclusion 生成互不相同的 operationId；
# 路由匹配不受影响（同 path+method 时先注册者生效）。
_unique_id_counts: dict[str, int] = {}


def _dedupe_operation_id(route: APIRoute) -> str:
    base = generate_unique_id(route)
    count = _unique_id_counts.get(base, 0) + 1
    _unique_id_counts[base] = count
    return base if count == 1 else f"{base}_dup{count}"


router = APIRouter(
    prefix="/api/v1/code-review",
    tags=["code-review"],
    generate_unique_id_function=_dedupe_operation_id,
)

_reviewer = CodeReviewer()


# ─── 请求/响应模型 ────────────────────────────────────────────────────────────


class DiffReviewRequest(BaseModel):
    """提交 diff 评审请求."""

    diff_text: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="Unified diff 文本",
        json_schema_extra={"example": "diff --git a/auth.py b/auth.py\n--- a/auth.py\n+++ b/auth.py\n@@ -10,3 +10,5 @@\n+    token = create_jwt(user)\n+    return {\"access_token\": token}"},
    )
    pr_number: int | None = Field(default=None, description="关联 PR 编号", json_schema_extra={"example": 42})
    context: dict[str, Any] = Field(default_factory=dict, description="附加上下文")


class PRReviewRequest(BaseModel):
    """PR 评审请求."""

    pr_number: int = Field(..., ge=1)
    diff_text: str = Field(..., min_length=1, max_length=100_000)
    repo: str = Field(default="", description="仓库标识")


class FileReviewRequest(BaseModel):
    """单文件评审请求."""

    file_path: str = Field(..., min_length=1, description="文件路径")
    content: str = Field(..., min_length=1, max_length=200_000, description="文件内容")
    language: str = Field(default="python", description="编程语言 (python/typescript/go/rust/java)")
    focus_areas: list[str] = Field(default_factory=list, description="重点关注领域: logic/security/performance/style")


class ReviewCommentResponse(BaseModel):
    file_path: str = Field(json_schema_extra={"example": "auth.py"})
    line: int = Field(json_schema_extra={"example": 12})
    severity: str = Field(json_schema_extra={"example": "warning"})
    message: str = Field(json_schema_extra={"example": "JWT secret should not be hardcoded; use environment variable"})
    suggestion: str = Field(default="", json_schema_extra={"example": "token = create_jwt(user, secret=os.environ['JWT_SECRET'])"})


class ReviewResponse(BaseModel):
    review_id: str = Field(json_schema_extra={"example": "rev-7f3a1b2c"})
    pr_number: int | None = Field(default=None, json_schema_extra={"example": 42})
    approval: str = Field(json_schema_extra={"example": "request_changes"})
    risk_level: str = Field(json_schema_extra={"example": "medium"})
    summary: str = Field(json_schema_extra={"example": "2 issues found: hardcoded secret (blocking), missing token expiry (suggestion)"})
    blocking_count: int = Field(json_schema_extra={"example": 1})
    suggestion_count: int = Field(json_schema_extra={"example": 1})
    comments: list[ReviewCommentResponse] = Field(default_factory=list)

    model_config = {"json_schema_extra": {"examples": [{
        "review_id": "rev-7f3a1b2c",
        "pr_number": 42,
        "approval": "request_changes",
        "risk_level": "medium",
        "summary": "2 issues found: hardcoded secret (blocking), missing token expiry (suggestion)",
        "blocking_count": 1,
        "suggestion_count": 1,
        "comments": [
            {
                "file_path": "auth.py",
                "line": 12,
                "severity": "blocking",
                "message": "JWT secret should not be hardcoded; use environment variable",
                "suggestion": "token = create_jwt(user, secret=os.environ['JWT_SECRET'])",
            }
        ],
    }]}}


class ReviewListItem(BaseModel):
    review_id: str
    pr_number: int | None = None
    approval: str
    risk_level: str
    summary: str
    blocking_count: int
    suggestion_count: int


# ─── 端点 ─────────────────────────────────────────────────────────────────────


@router.post(
    "/diff",
    response_model=ReviewResponse,
    summary="Review a unified diff",
    responses={
        200: {"description": "Review completed with structured comments"},
        422: {"description": "Validation error — diff_text empty or exceeds 100KB"},
    },
)
async def review_diff(req: DiffReviewRequest):
    """提交 diff 文本进行自动代码评审.

    Analyzes the provided unified diff for security issues, logic errors,
    performance concerns and style violations. Returns a structured review
    with risk level, approval status and line-level comments.
    """
    result = await _reviewer.review_diff(req.diff_text, pr_number=req.pr_number)
    return _to_response(result)


@router.post(
    "/pr",
    response_model=ReviewResponse,
    summary="Review a Pull Request",
    responses={
        200: {"description": "PR review completed"},
        422: {"description": "Validation error"},
    },
)
async def review_pr(req: PRReviewRequest):
    """评审指定 PR.

    Reviews a Pull Request by its number and associated diff text.
    """
    result = await _reviewer.review_pr(req.pr_number, req.diff_text)
    return _to_response(result)


@router.post(
    "/file",
    response_model=ReviewResponse,
    summary="Review a single file",
    responses={
        200: {"description": "File review completed"},
        422: {"description": "Validation error — content empty or exceeds 200KB"},
    },
)
async def review_file(req: FileReviewRequest):
    """评审单文件.

    Reviews a single source file. Supports multiple languages:
    Python / TypeScript / Go / Rust / Java.
    The file content is wrapped as a unified diff internally before analysis.
    """
    # 将文件内容包装为 unified diff 格式
    lines = req.content.splitlines()
    diff_lines = [
        f"diff --git a/{req.file_path} b/{req.file_path}",
        f"--- a/{req.file_path}",
        f"+++ b/{req.file_path}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    diff_lines.extend(f"+{line}" for line in lines)
    synthetic_diff = "\n".join(diff_lines)

    result = await _reviewer.review_diff(
        synthetic_diff,
        language=req.language,
        focus_areas=req.focus_areas,
    )
    return _to_response(result)


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: str):
    """获取评审结果."""
    result = _reviewer.get_review(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    return _to_response(result)


@router.get("", response_model=list[ReviewListItem])
async def list_reviews(limit: int = Query(20, ge=1, le=100)):
    """列出评审历史."""
    reviews = list(_reviewer._reviews.values())
    reviews.sort(key=lambda r: r.review_id, reverse=True)
    return [
        ReviewListItem(
            review_id=r.review_id,
            pr_number=r.pr_number,
            approval=r.approval,
            risk_level=r.risk_level,
            summary=r.summary,
            blocking_count=r.blocking_count,
            suggestion_count=r.suggestion_count,
        )
        for r in reviews[:limit]
    ]


@router.post("/{review_id}/approve")
async def approve_review(review_id: str):
    """手动标记评审通过."""
    result = _reviewer.get_review(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")
    result.approval = "approve"
    return {"review_id": review_id, "approval": "approve"}


# ─── 辅助 ─────────────────────────────────────────────────────────────────────


def _to_response(result: ReviewResult) -> ReviewResponse:
    return ReviewResponse(
        review_id=result.review_id,
        pr_number=result.pr_number,
        approval=result.approval,
        risk_level=result.risk_level,
        summary=result.summary,
        blocking_count=result.blocking_count,
        suggestion_count=result.suggestion_count,
        comments=[
            ReviewCommentResponse(
                file_path=c.file_path,
                line=c.line,
                severity=c.severity.value,
                message=c.message,
                suggestion=c.suggestion,
            )
            for c in result.comments
        ],
    )
