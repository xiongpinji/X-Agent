from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class AdvisoryRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AdvisoryPolicyAction(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass(frozen=True)
class PolicyRiskAssessment:
    risk_level: AdvisoryRiskLevel = AdvisoryRiskLevel.LOW
    action: AdvisoryPolicyAction = AdvisoryPolicyAction.ALLOW
    score: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""
    executable: str = ""

    @property
    def blocked(self) -> bool:
        return self.action == AdvisoryPolicyAction.BLOCK

    @property
    def requires_approval(self) -> bool:
        return self.action == AdvisoryPolicyAction.REQUIRE_APPROVAL

    def as_dict(self) -> dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "action": self.action.value,
            "score": self.score,
            "tags": list(self.tags),
            "reason": self.reason,
            "executable": self.executable,
            "blocked": self.blocked,
            "requires_approval": self.requires_approval,
        }


_CRITICAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "destructive_recursive_delete": (
        r"\brm\b.*\s-rf\b",
        r"\bremove-item\b.*\s-recurse\b",
        r"\brmdir\b.*\s/s\b",
        r"\brd\b.*\s/s\b",
    ),
    "destructive_git_history": (
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\b.*\s-f",
    ),
    "system_shutdown": (
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bformat\b",
        r"\bdiskpart\b",
        r"\bmkfs\b",
    ),
    "privilege_or_registry_change": (
        r"\breg\s+(delete|add)\b",
        r"\btakeown\b",
        r"\bicacls\b",
        r"\bbcdedit\b",
    ),
    "production_delete": (
        r"\bkubectl\s+delete\b",
        r"\bdocker\s+system\s+prune\b",
    ),
    "database_destructive": (
        r"\bdrop\s+database\b",
        r"\btruncate\s+table\b",
    ),
}

_HIGH_PATTERNS: dict[str, tuple[str, ...]] = {
    "network_to_shell": (
        r"\b(curl|wget|irm|iwr)\b.*\|",
        r"\biex\b",
    ),
    "package_publish": (
        r"\bnpm\s+publish\b",
        r"\btwine\s+upload\b",
    ),
    "dependency_install": (
        r"\b(pip|uv)\s+install\b",
        r"\bnpm\s+install\b",
    ),
    "filesystem_mutation": (
        r"\b(del|erase|move|copy|cp|mv)\b",
    ),
}

_SCRIPTED_FILE_MUTATION_MARKERS = (
    "unlink(",
    "rmtree(",
    "remove(",
    "writefile",
    "write_text(",
)

_SCRIPT_EXECUTABLES = {
    "python",
    "python.exe",
    "py",
    "py.exe",
    "node",
    "node.exe",
}

_DEVELOPER_EXECUTABLES = {
    "git",
    "git.exe",
    "pytest",
    "pytest.exe",
    "python",
    "python.exe",
    "py",
    "py.exe",
    "node",
    "node.exe",
}


def assess_shell_command_risk(command: str) -> PolicyRiskAssessment:
    """Return an advisory risk assessment for a shell command.

    This helper is intentionally not wired into ToolPolicyEngine. It is a
    standalone analysis primitive for future owner-gated policy integration.
    """

    normalized = command.strip()
    if not normalized:
        return PolicyRiskAssessment()

    lowered = normalized.lower()
    tags: list[str] = []
    score = 0
    critical_match = False

    for tag, patterns in _CRITICAL_PATTERNS.items():
        if _matches_any(patterns, lowered):
            tags.append(tag)
            score += 100
            critical_match = True

    for tag, patterns in _HIGH_PATTERNS.items():
        if _matches_any(patterns, lowered):
            tags.append(tag)
            score += 40

    executable = shell_command_executable(normalized)
    if executable in _SCRIPT_EXECUTABLES and any(marker in lowered for marker in _SCRIPTED_FILE_MUTATION_MARKERS):
        tags.append("scripted_filesystem_mutation")
        score += 40

    if not tags and executable in _DEVELOPER_EXECUTABLES:
        tags.append("developer_command")
        score += 5

    unique_tags = tuple(dict.fromkeys(tags))
    if critical_match:
        return PolicyRiskAssessment(
            risk_level=AdvisoryRiskLevel.CRITICAL,
            action=AdvisoryPolicyAction.BLOCK,
            score=score,
            tags=unique_tags,
            reason=f"Blocked shell command by advisory risk policy: {', '.join(unique_tags)}.",
            executable=executable,
        )

    if score >= 40:
        return PolicyRiskAssessment(
            risk_level=AdvisoryRiskLevel.HIGH,
            action=AdvisoryPolicyAction.REQUIRE_APPROVAL,
            score=score,
            tags=unique_tags,
            reason=f"Shell command should require approval due to risk tags: {', '.join(unique_tags)}.",
            executable=executable,
        )

    if score > 0:
        return PolicyRiskAssessment(
            risk_level=AdvisoryRiskLevel.MEDIUM,
            action=AdvisoryPolicyAction.REVIEW,
            score=score,
            tags=unique_tags,
            reason=f"Shell command risk reviewed: {', '.join(unique_tags)}.",
            executable=executable,
        )

    return PolicyRiskAssessment(executable=executable)


def assess_tool_argument_risk(tool_name: str, arguments: dict[str, Any] | None = None) -> PolicyRiskAssessment:
    if tool_name != "shell_exec":
        return PolicyRiskAssessment()
    command = str((arguments or {}).get("command") or "")
    return assess_shell_command_risk(command)


def merge_advisory_risk(
    base: AdvisoryRiskLevel | str,
    assessment: PolicyRiskAssessment,
) -> AdvisoryRiskLevel:
    base_level = AdvisoryRiskLevel(base)
    order = {
        AdvisoryRiskLevel.LOW: 0,
        AdvisoryRiskLevel.MEDIUM: 1,
        AdvisoryRiskLevel.HIGH: 2,
        AdvisoryRiskLevel.CRITICAL: 3,
    }
    return base_level if order[base_level] >= order[assessment.risk_level] else assessment.risk_level


def shell_command_executable(command: str) -> str:
    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return ""
    if not argv:
        return ""
    return Path(argv[0]).name.lower()


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)
