from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    skill_name: str = Field(..., min_length=1)
    task: str = Field(default="")
    success: bool = True
    error: str | None = None
    manual_rating: float | None = Field(default=None, ge=0.0, le=1.0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    used_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, object] = Field(default_factory=dict)


class SkillScore(BaseModel):
    skill_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    frequency: int = Field(..., ge=0)
    error_rate: float = Field(..., ge=0.0, le=1.0)
    recency_score: float = Field(..., ge=0.0, le=1.0)
    rating_score: float = Field(..., ge=0.0, le=1.0)


class SkillImprovementProposal(BaseModel):
    skill_name: str
    action: Literal["improve", "create", "review"]
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    safety_level: Literal["safe", "review_required", "blocked"] = "safe"


class SkillDraftRequest(BaseModel):
    skill_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    trigger: str = Field(default="", max_length=2000)
    steps: list[str] = Field(default_factory=list)
    evidence: list[SkillEvidence] = Field(default_factory=list)
    dry_run: bool = True


class SkillDraftResult(BaseModel):
    skill_name: str
    status: Literal["planned", "drafted"]
    draft_path: str
    content: str
    activated: bool = False


class SkillCuratorAnalysis(BaseModel):
    scores: list[SkillScore]
    proposals: list[SkillImprovementProposal]
    evidence_count: int
