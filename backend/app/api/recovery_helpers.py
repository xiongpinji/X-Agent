from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecoveryContext(BaseModel):
    status: str
    status_detail: str | None = None
    pending_count: int = 0
    latest_decision: str | None = None
    resource_type: str
    resource_id: str
    branch: str | None = None
    plan: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
    summary: str | None = None
    error_type: str | None = None
    remediation: str | None = None
    retryable: bool | None = None
    confidence: float | None = None
    tool_name: str | None = None
    follow_up: list[str] = Field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_recovery_context(
    *,
    status: str,
    resource_type: str,
    resource_id: str,
    next_actions: list[str] | None = None,
    pending_count: int = 0,
    latest_decision: str | None = None,
    recovery_plan: dict[str, Any] | None = None,
    branch: str | None = None,
    summary: str | None = None,
    error_type: str | None = None,
    retryable: bool | None = None,
    confidence: float | None = None,
    tool_name: str | None = None,
    follow_up: list[str] | None = None,
    status_detail: str | None = None,
    remediation: str | None = None,
) -> RecoveryContext:
    plan = recovery_plan if isinstance(recovery_plan, dict) else {}
    actions = list(next_actions or plan.get("next_actions", []) or [])
    return RecoveryContext(
        status=status,
        status_detail=status_detail,
        pending_count=pending_count,
        latest_decision=latest_decision or status,
        resource_type=resource_type,
        resource_id=resource_id,
        branch=branch,
        plan=plan,
        next_actions=actions,
        summary=summary,
        error_type=error_type,
        remediation=remediation,
        retryable=retryable,
        confidence=confidence,
        tool_name=tool_name,
        follow_up=list(follow_up or []),
    )


def build_recovery_payload(**kwargs: Any) -> dict[str, Any]:
    return build_recovery_context(**kwargs).to_payload()
