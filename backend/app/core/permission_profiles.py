from __future__ import annotations

from enum import StrEnum
from fnmatch import fnmatchcase

from pydantic import BaseModel, Field


class PermissionAction(StrEnum):
    READ = "read"
    WRITE = "write"
    TOOL = "tool"
    NETWORK = "network"


class PermissionGrants(BaseModel):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)
    tool: list[str] = Field(default_factory=list)
    network: list[str] = Field(default_factory=list)

    def patterns_for(self, action: PermissionAction | str) -> list[str]:
        action_value = PermissionAction(action).value
        return list(getattr(self, action_value))


class PermissionProfile(BaseModel):
    profile_id: str = Field(default="default", min_length=1, max_length=120)
    description: str = Field(default="", max_length=1_000)
    allow: PermissionGrants = Field(default_factory=PermissionGrants)
    deny: PermissionGrants = Field(default_factory=PermissionGrants)


class PermissionDecision(BaseModel):
    allowed: bool
    action: PermissionAction
    target: str
    profile_id: str
    reason: str
    effect: str
    matched_pattern: str | None = None


def evaluate_permission(
    profile: PermissionProfile,
    action: PermissionAction | str,
    target: str,
) -> PermissionDecision:
    checked_action = PermissionAction(action)
    normalized_target = _normalize_target(target)

    denied_pattern = _first_matching_pattern(
        normalized_target,
        profile.deny.patterns_for(checked_action),
    )
    if denied_pattern is not None:
        return PermissionDecision(
            allowed=False,
            action=checked_action,
            target=normalized_target,
            profile_id=profile.profile_id,
            reason=f"{checked_action.value} denied by profile rule {denied_pattern}.",
            effect="deny",
            matched_pattern=denied_pattern,
        )

    allowed_pattern = _first_matching_pattern(
        normalized_target,
        profile.allow.patterns_for(checked_action),
    )
    if allowed_pattern is not None:
        return PermissionDecision(
            allowed=True,
            action=checked_action,
            target=normalized_target,
            profile_id=profile.profile_id,
            reason=f"{checked_action.value} allowed by profile rule {allowed_pattern}.",
            effect="allow",
            matched_pattern=allowed_pattern,
        )

    return PermissionDecision(
        allowed=False,
        action=checked_action,
        target=normalized_target,
        profile_id=profile.profile_id,
        reason=f"{checked_action.value} is not allowed by profile {profile.profile_id}.",
        effect="none",
    )


def is_permission_allowed(
    profile: PermissionProfile,
    action: PermissionAction | str,
    target: str,
) -> bool:
    return evaluate_permission(profile, action, target).allowed


def _first_matching_pattern(target: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        normalized_pattern = _normalize_target(pattern)
        if normalized_pattern == "*" or fnmatchcase(target, normalized_pattern):
            return pattern
    return None


def _normalize_target(value: str) -> str:
    return value.strip().replace("\\", "/")
