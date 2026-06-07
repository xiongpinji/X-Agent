#!/usr/bin/env python3
"""Create a source-control-safe commercial RC source bundle.

The bundle is built from ``docs/RC_STAGING_MANIFEST.md`` candidate file lists,
not from the full dirty worktree. It refuses excluded/local/runtime artifacts
and defaults to dry-run so release owners can inspect the planned payload before
writing an archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from scripts.rc_release_audit import is_excluded, is_safe_manifest_path, normalize_manifest_path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "RC_STAGING_MANIFEST.md"
DEFAULT_OUTPUT_DIR = ROOT / ".xagent_runtime" / "release"
DEFAULT_REPORT = ROOT / ".xagent_runtime" / "reports" / "rc-source-bundle.json"


@dataclass(frozen=True)
class BundleFile:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class BundleReport:
    status: str
    generated_at: str
    dry_run: bool
    manifest_path: str
    output_path: str | None
    file_count: int
    total_bytes: int
    files: list[BundleFile]
    missing_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    clean_tracked_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["files"] = [asdict(item) for item in self.files]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_code_blocks(markdown: str, headings: Iterable[str]) -> list[str]:
    wanted = set(headings)
    current_heading = ""
    in_block = False
    captured: list[str] = []
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            continue
        if line.strip() == "```text" and current_heading in wanted:
            in_block = True
            lines = []
            continue
        if in_block and line.strip() == "```":
            in_block = False
            captured.extend(lines)
            lines = []
            continue
        if in_block:
            lines.append(line.strip())
    return [line for line in captured if line and not line.startswith("#")]


def manifest_candidate_paths(manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    text = manifest_path.read_text(encoding="utf-8")
    paths = _extract_code_blocks(
        text,
        {
            "Tracked Modified Candidate Files",
            "New Candidate Files",
        },
    )
    return sorted(dict.fromkeys(paths))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_bundle_files(paths: Iterable[str], root: Path = ROOT) -> tuple[list[BundleFile], list[str], list[str]]:
    files: list[BundleFile] = []
    missing: list[str] = []
    excluded: list[str] = []
    for relative_path in paths:
        normalized = normalize_manifest_path(relative_path)
        if not is_safe_manifest_path(normalized) or is_excluded(normalized) or normalized.startswith(".xagent_runtime/"):
            excluded.append(normalized)
            continue
        path = root / normalized
        if not path.exists() or not path.is_file():
            missing.append(normalized)
            continue
        files.append(
            BundleFile(
                path=normalized,
                size_bytes=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return files, missing, excluded


def _git_lines(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def current_changed_paths(root: Path = ROOT) -> set[str]:
    try:
        tracked = set(_git_lines(root, "diff", "--name-only"))
        untracked = set(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    except (OSError, subprocess.CalledProcessError):
        return set()
    return tracked | untracked


def _default_bundle_path(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"x-agent-commercial-rc-{stamp}.zip"


def create_zip(files: list[BundleFile], output_path: Path, root: Path = ROOT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            archive.write(root / item.path, arcname=item.path)


def build_bundle(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path | None = None,
    dry_run: bool = True,
    root: Path = ROOT,
) -> BundleReport:
    paths = manifest_candidate_paths(manifest_path)
    files, missing, excluded = inspect_bundle_files(paths, root=root)
    changed = current_changed_paths(root)
    clean_tracked = sorted(item.path for item in files if item.path not in changed)
    errors: list[str] = []
    if missing:
        errors.append("manifest candidate files are missing from the worktree")
    if excluded:
        errors.append("manifest includes excluded paths")
    destination = output_path if output_path is not None else _default_bundle_path()
    if not dry_run and not errors:
        create_zip(files, destination, root=root)
    status = "failed" if errors else "planned" if dry_run else "created"
    return BundleReport(
        status=status,
        generated_at=_utc_now(),
        dry_run=dry_run,
        manifest_path=str(manifest_path),
        output_path=None if dry_run else str(destination),
        file_count=len(files),
        total_bytes=sum(item.size_bytes for item in files),
        files=files,
        missing_files=missing,
        excluded_files=excluded,
        clean_tracked_files=clean_tracked,
        errors=errors,
    )


def write_report(report: BundleReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or create the X-Agent commercial RC source bundle")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=None, help="zip output path when not in dry-run mode")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--create", action="store_true", help="write the zip archive; default is dry-run only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_bundle(
        manifest_path=args.manifest,
        output_path=args.output,
        dry_run=not args.create,
    )
    write_report(report, args.report)
    print(f"RC source bundle status: {report.status}")
    print(f"Candidate files: {report.file_count}")
    if report.output_path:
        print(f"Bundle written to {report.output_path}")
    print(f"Report written to {args.report}")
    if report.errors:
        for error in report.errors:
            print(f"Error: {error}")
    return 0 if report.status in {"planned", "created"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
