from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.api.errors import api_error
from backend.app.core.contracts import ErrorCode
from backend.app.core.security import Principal, anonymous_principal
from backend.app.core.skill_curator import (
    SkillDraftRequest,
    SkillEvidence,
    analyze_skill_evidence,
    draft_skill,
)
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/skill-curator", tags=["skill-curator"])


class SkillCuratorAnalyzeRequest(BaseModel):
    evidence: list[SkillEvidence] = Field(default_factory=list)


class SkillCuratorDraftRequest(SkillDraftRequest):
    draft_root: str | None = None


def _local_dev_exception_enabled() -> bool:
    settings = get_settings()
    return (
        settings.app_mode != "production"
        and not settings.require_api_key
    )


def get_skill_curator_principal(request: Request) -> Principal:
    has_credentials = bool(
        request.headers.get("x-api-key")
        or request.headers.get("authorization", "").lower().startswith("bearer ")
    )
    if _local_dev_exception_enabled() and not has_credentials:
        return anonymous_principal()
    return get_current_principal(request)


def _enforce_skill_curator_access(principal: Principal) -> None:
    if not principal.authenticated and _local_dev_exception_enabled():
        return
    enforce_scope(principal, "skill:install")


def _draft_root_from_request(request: SkillCuratorDraftRequest) -> Path:
    default_root = Path(".xagent") / "skill-curator" / "drafts"
    if not request.draft_root:
        return default_root

    settings = get_settings()
    require_api_key_requested = os.getenv("XAGENT_REQUIRE_API_KEY", "").strip().lower() in {"1", "true", "yes", "on"}
    if settings.require_api_key or require_api_key_requested or settings.app_mode == "production":
        raise api_error(
            403,
            ErrorCode.AUTHORIZATION_FAILED,
            "Custom skill draft roots are only allowed in local development.",
        )
    return Path(request.draft_root)


@router.post("/analyze")
async def analyze_skills(
    request: SkillCuratorAnalyzeRequest,
    principal: Principal = Depends(get_skill_curator_principal),
) -> dict[str, object]:
    _enforce_skill_curator_access(principal)
    return analyze_skill_evidence(request.evidence).model_dump(mode="json")


@router.post("/draft")
async def draft_skill_endpoint(
    request: SkillCuratorDraftRequest,
    principal: Principal = Depends(get_skill_curator_principal),
) -> dict[str, object]:
    _enforce_skill_curator_access(principal)
    result = draft_skill(
        SkillDraftRequest.model_validate(request.model_dump(exclude={"draft_root"})),
        draft_root=_draft_root_from_request(request),
    )
    return result.model_dump(mode="json")
