#!/usr/bin/env python3
"""Build an owner-gated commercial staging review.

This script turns the original-kernel delivery manifest into an auditable
staging preview. It does not run `git add`, create commits, push branches, or
mutate the repository. The output is intended for owner review before any
explicit path-by-path staging operation.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-staging-review.md"
PROTECTED_PREFIXES = (
    "frontend/",
    "backend/app/api/",
    "backend/app/control_plane/",
    "backend/app/agents/",
)
PROTECTED_EXACT = {
    "backend/app/main.py",
    "backend/app/core/__init__.py",
}


@dataclass(frozen=True)
class StagingReviewPath:
    path: str
    status: str
    exists: bool
    dirty: bool
    category: str
    reason: str | None = None


@dataclass(frozen=True)
class StagingReviewCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CommercialDeliveryStagingReview:
    status: str
    generated_at: str
    evidence_type: str
    manifest_status: str | None
    owner_gated: bool
    mutation_performed: bool
    git_stage_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    full_codex_parity_claimed: bool
    stage_include_count: int
    eligible_stage_count: int
    blocked_stage_count: int
    unchanged_stage_count: int
    paths: list[StagingReviewPath]
    checks: list[StagingReviewCheck]
    owner_review_commands: list[str]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["paths"] = [asdict(path) for path in self.paths]
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
        return payload


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"manifest not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read manifest {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"manifest is not a JSON object: {_display_path(path)}"
    return payload, None


def _git_status_lines() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _git_dirty_paths(lines: Sequence[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        if not line.strip() or line.startswith("##"):
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        paths.add(path.replace("\\", "/").strip('"'))
    return paths


def _is_protected(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in PROTECTED_EXACT or any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _category(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("backend/app/core/"):
        return "backend_core"
    if normalized.startswith("scripts/"):
        return "script"
    if normalized.startswith("tests/"):
        return "test"
    if normalized.startswith("docs/"):
        return "doc"
    return "other"


def _stage_paths_from_manifest(manifest: dict[str, Any]) -> list[str]:
    values = manifest.get("stage_include_paths")
    if not isinstance(values, list):
        return []
    return [str(value).replace("\\", "/") for value in values if str(value)]


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> StagingReviewCheck:
    return StagingReviewCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _review_path(path: str, dirty_paths: set[str]) -> StagingReviewPath:
    exists = (ROOT / path).exists()
    dirty = path in dirty_paths
    if _is_protected(path):
        return StagingReviewPath(
            path=path,
            status="blocked",
            exists=exists,
            dirty=dirty,
            category=_category(path),
            reason="protected entrypoint, API, control-plane, agent-loop, or frontend path",
        )
    if not exists:
        return StagingReviewPath(
            path=path,
            status="blocked",
            exists=False,
            dirty=dirty,
            category=_category(path),
            reason="stage include path does not exist",
        )
    if not dirty:
        return StagingReviewPath(
            path=path,
            status="unchanged",
            exists=True,
            dirty=False,
            category=_category(path),
            reason="path is present in manifest but not dirty in current git status",
        )
    return StagingReviewPath(
        path=path,
        status="eligible",
        exists=True,
        dirty=True,
        category=_category(path),
    )


def _owner_review_commands(paths: Sequence[StagingReviewPath]) -> list[str]:
    eligible = [item.path for item in paths if item.status == "eligible"]
    if not eligible:
        return ["No eligible paths are ready for owner-gated staging."]
    commands = [
        "Review .xagent_runtime\\reports\\commercial-delivery-staging-review.json before staging.",
        "Stage only explicit paths after owner approval; never run git add .",
    ]
    commands.extend(f"git add -- {path}" for path in eligible)
    return commands


def build_staging_review(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    git_status_lines: Sequence[str] | None = None,
) -> CommercialDeliveryStagingReview:
    manifest, read_error = _read_json(manifest_path)
    stage_paths = _stage_paths_from_manifest(manifest)
    dirty_paths = _git_dirty_paths(git_status_lines if git_status_lines is not None else _git_status_lines())
    path_reviews = [_review_path(path, dirty_paths) for path in stage_paths]
    blocked = [item for item in path_reviews if item.status == "blocked"]
    eligible = [item for item in path_reviews if item.status == "eligible"]
    unchanged = [item for item in path_reviews if item.status == "unchanged"]
    manifest_status = manifest.get("status")
    protected_flags = {
        key: manifest.get(key)
        for key in (
            "entrypoints_modified",
            "api_router_modified",
            "control_plane_modified",
            "frontend_modified",
            "agent_loop_modified",
            "backend_core_init_modified",
        )
    }
    protected_drift = any(value is True for value in protected_flags.values())
    checks = [
        _check(
            "manifest_readable",
            read_error is None,
            details={"manifest_path": _display_path(manifest_path)},
            error=read_error,
        ),
        _check(
            "manifest_ready",
            manifest_status == "original_kernel_delivery_manifest_ready",
            details={"manifest_status": manifest_status},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "stage_include_count_matches",
            len(stage_paths) == int(manifest.get("stage_include_count") or -1),
            details={"stage_include_count": manifest.get("stage_include_count"), "path_count": len(stage_paths)},
            error="manifest stage_include_count does not match stage_include_paths length",
        ),
        _check(
            "no_protected_stage_paths",
            not any(_is_protected(path) for path in stage_paths),
            details={"protected_stage_paths": [path for path in stage_paths if _is_protected(path)]},
            error="stage include paths contain protected mainline entrypoint/UI/API surfaces",
        ),
        _check(
            "no_manifest_entrypoint_or_ui_drift",
            not protected_drift,
            details=protected_flags,
            error="manifest reports drift in protected mainline entrypoint/UI/API surfaces",
        ),
        _check(
            "no_stage_mutation",
            True,
            details={
                "owner_gated": True,
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
            },
        ),
    ]
    status = (
        "staging_review_blocked"
        if read_error or any(check.status == "failed" for check in checks) or blocked
        else "staging_review_ready"
    )
    return CommercialDeliveryStagingReview(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_staging_review",
        manifest_status=str(manifest_status) if manifest_status is not None else None,
        owner_gated=True,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        full_codex_parity_claimed=manifest.get("full_codex_parity_claimed") is True,
        stage_include_count=len(stage_paths),
        eligible_stage_count=len(eligible),
        blocked_stage_count=len(blocked),
        unchanged_stage_count=len(unchanged),
        paths=path_reviews,
        checks=checks,
        owner_review_commands=_owner_review_commands(path_reviews),
        next_actions=[
            "Review eligible paths and commands with the owner before staging.",
            "Regenerate this report after any secondary handoff update or manifest refresh.",
            "Keep unrelated UI/API/frontend dirty paths outside this staging package.",
        ],
        known_limits=[
            "This report is a staging preview only.",
            "It does not run git add, commit, push, tests, agents, or network calls.",
            "Unchanged manifest paths may still belong to already-clean or previously staged work; inspect before staging.",
        ],
    )


def render_markdown_review(report: CommercialDeliveryStagingReview) -> str:
    lines = [
        "# Commercial Delivery Staging Review",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Manifest status: `{report.manifest_status}`",
        f"- Owner gated: `{str(report.owner_gated).lower()}`",
        f"- Stage include count: `{report.stage_include_count}`",
        f"- Eligible stage count: `{report.eligible_stage_count}`",
        f"- Blocked stage count: `{report.blocked_stage_count}`",
        f"- Unchanged stage count: `{report.unchanged_stage_count}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Owner Review Commands", ""])
    lines.extend(f"- `{command}`" for command in report.owner_review_commands)
    lines.extend(["", "## Path Summary", ""])
    for item in report.paths:
        suffix = f" - {item.reason}" if item.reason else ""
        lines.append(f"- `{item.status}` `{item.path}` ({item.category}){suffix}")
    lines.append("")
    return "\n".join(lines)


def write_report(report: CommercialDeliveryStagingReview, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_review(report: CommercialDeliveryStagingReview, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_review(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_staging_review(manifest_path=args.manifest)
    write_report(report, args.output)
    write_markdown_review(report, args.markdown_output)
    print(f"Commercial delivery staging review status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Eligible stage paths: {report.eligible_stage_count}")
    print(f"Blocked stage paths: {report.blocked_stage_count}")
    print(f"Unchanged stage paths: {report.unchanged_stage_count}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "staging_review_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
