#!/usr/bin/env python3
"""Generate an exact, reviewable git staging plan for the commercial RC.

The script never stages files. It reads ``docs/RC_STAGING_MANIFEST.md``,
validates each candidate path, and writes copyable ``git add -- <paths>``
commands in small chunks so the release owner can stage exact files after
review without using ``git add .``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from scripts.rc_release_audit import is_excluded
from scripts.rc_source_bundle import DEFAULT_MANIFEST, ROOT, is_safe_manifest_path, manifest_candidate_paths, normalize_manifest_path

DEFAULT_REPORT = ROOT / ".xagent_runtime" / "reports" / "rc-staging-plan.json"


@dataclass(frozen=True)
class StagingCommand:
    index: int
    file_count: int
    command: str
    paths: list[str]


@dataclass(frozen=True)
class StagingPlanReport:
    status: str
    generated_at: str
    manifest_path: str
    manifest_sha256: str
    file_count: int
    command_count: int
    commands: list[StagingCommand]
    missing_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["commands"] = [asdict(item) for item in self.commands]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _quote_path(path: str) -> str:
    escaped = path.replace('"', '\\"')
    return f'"{escaped}"'


def validate_stage_paths(paths: Iterable[str], root: Path = ROOT) -> tuple[list[str], list[str], list[str]]:
    valid: list[str] = []
    missing: list[str] = []
    excluded: list[str] = []
    for item in paths:
        normalized = normalize_manifest_path(item)
        if not is_safe_manifest_path(normalized) or is_excluded(normalized) or normalized.startswith(".xagent_runtime/"):
            excluded.append(normalized)
            continue
        path = root / normalized
        if not path.exists() or not path.is_file():
            missing.append(normalized)
            continue
        valid.append(normalized)
    return sorted(dict.fromkeys(valid)), sorted(dict.fromkeys(missing)), sorted(dict.fromkeys(excluded))


def chunk_paths(paths: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    return [paths[index : index + chunk_size] for index in range(0, len(paths), chunk_size)]


def build_staging_commands(paths: list[str], *, chunk_size: int = 20) -> list[StagingCommand]:
    commands: list[StagingCommand] = []
    for index, chunk in enumerate(chunk_paths(paths, chunk_size), start=1):
        command = "git add -- " + " ".join(_quote_path(path) for path in chunk)
        commands.append(
            StagingCommand(
                index=index,
                file_count=len(chunk),
                command=command,
                paths=chunk,
            )
        )
    return commands


def build_staging_plan(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    root: Path = ROOT,
    chunk_size: int = 20,
) -> StagingPlanReport:
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    candidates = manifest_candidate_paths(manifest_path)
    valid, missing, excluded = validate_stage_paths(candidates, root=root)
    commands = build_staging_commands(valid, chunk_size=chunk_size)
    errors: list[str] = []
    if missing:
        errors.append("manifest candidate files are missing from the worktree")
    if excluded:
        errors.append("manifest includes excluded paths")
    status = "failed" if errors else "planned"
    return StagingPlanReport(
        status=status,
        generated_at=_utc_now(),
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_sha256,
        file_count=len(valid),
        command_count=len(commands),
        commands=commands,
        missing_files=missing,
        excluded_files=excluded,
        errors=errors,
        next_commands=[
            "Review docs/RC_STAGING_MANIFEST.md and the generated command list.",
            "Run the generated git add -- commands only after owner review.",
            "Run git diff --cached --stat before commit.",
        ],
    )


def write_report(report: StagingPlanReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a non-mutating X-Agent commercial RC staging plan")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chunk-size", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_staging_plan(
        manifest_path=args.manifest,
        chunk_size=args.chunk_size,
    )
    write_report(report, args.report)
    print(f"RC staging plan status: {report.status}")
    print(f"Candidate files: {report.file_count}")
    print(f"Staging commands: {report.command_count}")
    print(f"Report written to {args.report}")
    if report.errors:
        for error in report.errors:
            print(f"Error: {error}")
    return 0 if report.status == "planned" else 1


if __name__ == "__main__":
    raise SystemExit(main())
