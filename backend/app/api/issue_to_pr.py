from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.pipelines.issue_to_pr import (
    IssueToPRExecutionResult,
    dry_run_issue_to_pr,
)

router = APIRouter(prefix="/api/v1/issue-to-pr", tags=["issue-to-pr"])

IssueToPRExecutor = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class IssueToPRRequest(BaseModel):
    issue_url: str | None = Field(default=None)
    issue: dict[str, Any] | None = Field(default=None)
    execute: bool = False

    def payload(self) -> dict[str, Any]:
        data = dict(self.issue or {})
        if self.issue_url:
            data["issue_url"] = self.issue_url
        return data


def get_issue_to_pr_executor() -> IssueToPRExecutor | None:
    return None


ExecutorDependency = Annotated[IssueToPRExecutor | None, Depends(get_issue_to_pr_executor)]


@router.post("/dry-run")
async def dry_run_issue_to_pr_endpoint(request: IssueToPRRequest) -> dict[str, Any]:
    try:
        return dry_run_issue_to_pr(request.payload()).to_dict()
    except ValueError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))


@router.post("/execute")
async def execute_issue_to_pr_endpoint(
    request: IssueToPRRequest,
    executor: ExecutorDependency,
) -> dict[str, Any]:
    if not request.execute:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, "execute=true is required.")
    token = os.getenv("GITHUB_TOKEN") or os.getenv("XAGENT_GITHUB_TOKEN")
    if not token:
        raise api_error(403, ErrorCode.AUTHORIZATION_FAILED, "GITHUB_TOKEN is required for execute mode.")

    try:
        dry_run = dry_run_issue_to_pr(request.payload())
    except ValueError as exc:
        raise api_error(400, ErrorCode.VALIDATION_ERROR, str(exc))

    if executor is None:
        return IssueToPRExecutionResult(
            status="ready",
            execute=True,
            dry_run=dry_run,
            pipeline_result=None,
            error="No execute runner configured; dry-run plan returned only.",
        ).to_dict()

    result = executor(dry_run.to_dict())
    if hasattr(result, "__await__"):
        result = await result  # type: ignore[assignment]
    return IssueToPRExecutionResult(
        status=str(result.get("status", "executed")),
        execute=True,
        dry_run=dry_run,
        pipeline_result=dict(result),
    ).to_dict()
