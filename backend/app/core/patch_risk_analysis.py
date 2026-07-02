from __future__ import annotations

import posixpath
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_DIRECTORIES = {"secrets", "credentials", ".ssh"}
SENSITIVE_NAME_TOKENS = {"secret", "credential", "token", "apikey", "api_key"}
RELEASE_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}
CONFIG_FILENAMES = {
    ".env.example",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
}
CONFIG_EXTENSIONS = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".conf"}
GENERATED_DIRECTORIES = {"dist", "build", "coverage", ".xagent_runtime"}
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class PatchPathClassification:
    path: str
    layer: str
    risk: str
    sandbox_profile: str
    approval_required: bool
    allowed_by_default: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "layer": self.layer,
            "risk": self.risk,
            "sandbox_profile": self.sandbox_profile,
            "approval_required": self.approval_required,
            "allowed_by_default": self.allowed_by_default,
            "reasons": list(self.reasons),
        }


def normalize_patch_path(path: str) -> str:
    normalized = str(path).strip().replace("\\", "/")
    normalized = normalized.lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = posixpath.normpath(normalized)
    return "" if normalized == "." else normalized


def is_sensitive_patch_path(path: str) -> bool:
    normalized = normalize_patch_path(path).lower()
    if not normalized:
        return False
    name = PurePosixPath(normalized).name
    parts = set(PurePosixPath(normalized).parts)
    if name in SENSITIVE_FILENAMES:
        return True
    if parts.intersection(SENSITIVE_DIRECTORIES):
        return True
    return any(token in name for token in SENSITIVE_NAME_TOKENS)


def classify_patch_path(path: str) -> PatchPathClassification:
    normalized = normalize_patch_path(path)
    lower = normalized.lower()
    name = PurePosixPath(lower).name
    parts = set(PurePosixPath(lower).parts)

    if _escapes_repo_boundary(normalized):
        return PatchPathClassification(
            path=normalized,
            layer="workspace_boundary",
            risk="critical",
            sandbox_profile="manual_review",
            approval_required=True,
            allowed_by_default=False,
            reasons=("path_escapes_repository",),
        )
    if is_sensitive_patch_path(normalized):
        return PatchPathClassification(
            path=normalized,
            layer="secret",
            risk="critical",
            sandbox_profile="manual_review",
            approval_required=True,
            allowed_by_default=False,
            reasons=("sensitive_path",),
        )
    if _is_release_surface(lower, name):
        return PatchPathClassification(
            path=normalized,
            layer="release",
            risk="high",
            sandbox_profile="release_review",
            approval_required=True,
            allowed_by_default=False,
            reasons=("release_surface",),
        )
    if _is_configuration_path(lower, name):
        return PatchPathClassification(
            path=normalized,
            layer="configuration",
            risk="medium",
            sandbox_profile="restricted_patch",
            approval_required=False,
            allowed_by_default=True,
            reasons=("configuration_path",),
        )
    if _is_test_path(lower, parts, name):
        return PatchPathClassification(
            path=normalized,
            layer="test",
            risk="medium",
            sandbox_profile="restricted_patch",
            approval_required=False,
            allowed_by_default=True,
            reasons=("test_path",),
        )
    if parts.intersection(GENERATED_DIRECTORIES):
        return PatchPathClassification(
            path=normalized,
            layer="generated",
            risk="medium",
            sandbox_profile="restricted_patch",
            approval_required=False,
            allowed_by_default=False,
            reasons=("generated_path",),
        )
    return PatchPathClassification(
        path=normalized,
        layer="implementation",
        risk="low",
        sandbox_profile="scoped_patch",
        approval_required=False,
        allowed_by_default=True,
        reasons=("source_path",),
    )


def analyze_patch_paths(paths: Sequence[str]) -> dict[str, Any]:
    normalized_paths = _dedupe_normalized_paths(paths)
    classifications = [classify_patch_path(path) for path in normalized_paths]
    approval_required = [item for item in classifications if item.approval_required]
    issues = _build_issues(classifications)
    max_risk = _max_risk(item.risk for item in classifications)

    return {
        "kind": "patch_risk_analysis",
        "version": 1,
        "ok": not approval_required,
        "status": "review_required" if approval_required else "passed",
        "summary": {
            "total": len(classifications),
            "approval_required": len(approval_required),
            "max_risk": max_risk,
            "layers": _count_layers(classifications),
        },
        "targets": [item.as_dict() for item in classifications],
        "sensitive_targets": _paths_by_layer(classifications, "secret"),
        "release_surface_targets": _paths_by_layer(classifications, "release"),
        "configuration_targets": _paths_by_layer(classifications, "configuration"),
        "generated_targets": _paths_by_layer(classifications, "generated"),
        "issues": issues,
    }


def _dedupe_normalized_paths(paths: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = normalize_patch_path(str(path))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _escapes_repo_boundary(path: str) -> bool:
    return bool(path) and (path == ".." or path.startswith("../") or ":/" in path)


def _is_release_surface(lower: str, name: str) -> bool:
    return (
        name in RELEASE_FILENAMES
        or lower.startswith(".github/workflows/")
        or lower.startswith("deploy/kubernetes/")
        or lower.startswith("deploy/helm/")
    )


def _is_configuration_path(lower: str, name: str) -> bool:
    suffix = PurePosixPath(lower).suffix
    return name in CONFIG_FILENAMES or suffix in CONFIG_EXTENSIONS


def _is_test_path(lower: str, parts: set[str], name: str) -> bool:
    return (
        "tests" in parts
        or lower.startswith("test/")
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".test.ts")
        or name.endswith(".spec.tsx")
        or name.endswith(".test.tsx")
    )


def _paths_by_layer(classifications: Sequence[PatchPathClassification], layer: str) -> list[str]:
    return [item.path for item in classifications if item.layer == layer]


def _count_layers(classifications: Sequence[PatchPathClassification]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in classifications:
        counts[item.layer] = counts.get(item.layer, 0) + 1
    return counts


def _max_risk(risks: Sequence[str]) -> str:
    max_name = "low"
    for risk in risks:
        if RISK_RANK.get(risk, 0) > RISK_RANK[max_name]:
            max_name = risk
    return max_name


def _build_issues(classifications: Sequence[PatchPathClassification]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in classifications:
        if item.layer == "secret":
            issues.append(
                {
                    "code": "patch_sensitive_file_requires_review",
                    "severity": "critical",
                    "path": item.path,
                    "message": "Sensitive patch target requires manual review.",
                }
            )
        elif item.layer == "workspace_boundary":
            issues.append(
                {
                    "code": "patch_target_escapes_repository",
                    "severity": "critical",
                    "path": item.path,
                    "message": "Patch target must stay inside the repository boundary.",
                }
            )
        elif item.layer == "release":
            issues.append(
                {
                    "code": "patch_release_surface_requires_review",
                    "severity": "high",
                    "path": item.path,
                    "message": "Release or deployment surface patch target requires review.",
                }
            )
    return issues
