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
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from scripts.rc_release_audit import (
    is_excluded,
    is_safe_manifest_path,
    manifest_base_ref,
    normalize_manifest_path,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "RC_STAGING_MANIFEST.md"
DEFAULT_OUTPUT_DIR = ROOT / ".xagent_runtime" / "release"
DEFAULT_REPORT = ROOT / ".xagent_runtime" / "reports" / "rc-source-bundle.json"
DELETION_MANIFEST_PATH = ".xagent-release/deleted-paths.txt"


@dataclass(frozen=True)
class BundleFile:
    path: str
    size_bytes: int
    sha256: str
    deleted: bool = False


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
    deleted_files: list[str] = field(default_factory=list)
    undeleted_files: list[str] = field(default_factory=list)
    deletion_manifest_path: str | None = None
    base_ref: str = ""
    base_sha: str = ""
    head_sha: str = ""
    committed_missing_from_manifest: list[str] = field(default_factory=list)
    manifest_extra_committed: list[str] = field(default_factory=list)
    dirty_files: list[str] = field(default_factory=list)

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
            "Deleted Candidate Files",
        },
    )
    return sorted(dict.fromkeys(paths))


def manifest_deleted_paths(manifest_path: Path = DEFAULT_MANIFEST) -> list[str]:
    text = manifest_path.read_text(encoding="utf-8")
    return sorted(dict.fromkeys(_extract_code_blocks(text, {"Deleted Candidate Files"})))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_bundle_files(
    paths: Iterable[str],
    root: Path = ROOT,
    *,
    deleted_paths: Iterable[str] = (),
) -> tuple[list[BundleFile], list[str], list[str], list[str]]:
    files: list[BundleFile] = []
    missing: list[str] = []
    excluded: list[str] = []
    undeleted: list[str] = []
    deleted = {normalize_manifest_path(path) for path in deleted_paths}
    for relative_path in paths:
        normalized = normalize_manifest_path(relative_path)
        if not is_safe_manifest_path(normalized) or is_excluded(normalized) or normalized.startswith(".xagent_runtime/"):
            excluded.append(normalized)
            continue
        path = root / normalized
        if normalized in deleted:
            if path.exists():
                undeleted.append(normalized)
                continue
            files.append(
                BundleFile(
                    path=normalized,
                    size_bytes=0,
                    sha256=hashlib.sha256(b"").hexdigest(),
                    deleted=True,
                )
            )
            continue
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
    return files, missing, excluded, undeleted


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
        staged = set(_git_lines(root, "diff", "--cached", "--name-only"))
        untracked = set(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    except (OSError, subprocess.CalledProcessError):
        return set()
    return tracked | staged | untracked


def committed_candidate_paths(root: Path, *, base_ref: str) -> tuple[list[str], list[str], str, str]:
    base_lines = _git_lines(root, "merge-base", base_ref, "HEAD")
    head_lines = _git_lines(root, "rev-parse", "HEAD")
    if len(base_lines) != 1 or len(head_lines) != 1:
        raise RuntimeError(f"unable to resolve release base/head: {base_ref}")
    base_sha = base_lines[0]
    head_sha = head_lines[0]
    changed = sorted(
        dict.fromkeys(
            _git_lines(
                root,
                "diff",
                "--name-only",
                "--diff-filter=ACMRD",
                f"{base_sha}...HEAD",
            )
        )
    )
    included = [path for path in changed if not is_excluded(path)]
    excluded = [path for path in changed if is_excluded(path)]
    return included, excluded, base_sha, head_sha


def _default_bundle_path(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"x-agent-commercial-rc-{stamp}.zip"


def create_zip(
    files: list[BundleFile],
    output_path: Path,
    root: Path = ROOT,
    *,
    deleted_paths: Iterable[str] = (),
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            if item.deleted:
                continue
            archive.write(root / item.path, arcname=item.path)
        deleted = sorted(dict.fromkeys(deleted_paths))
        if deleted:
            archive.writestr(DELETION_MANIFEST_PATH, "".join(f"{path}\n" for path in deleted))


def build_bundle(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path | None = None,
    dry_run: bool = True,
    root: Path = ROOT,
    base_ref: str | None = None,
) -> BundleReport:
    paths = manifest_candidate_paths(manifest_path)
    effective_base_ref = base_ref or manifest_base_ref(manifest_path.read_text(encoding="utf-8"))
    deleted = manifest_deleted_paths(manifest_path)
    files, missing, excluded, undeleted = inspect_bundle_files(
        paths,
        root=root,
        deleted_paths=deleted,
    )
    changed = current_changed_paths(root)
    clean_tracked = sorted(item.path for item in files if not item.deleted and item.path not in changed)
    errors: list[str] = []
    if missing:
        errors.append("manifest candidate files are missing from the worktree")
    if excluded:
        errors.append("manifest includes excluded paths")
    if undeleted:
        errors.append("manifest deletion entries still exist in the worktree")
    if changed:
        errors.append("worktree must be clean before creating an immutable source bundle")
    base_sha = ""
    head_sha = ""
    committed_missing: list[str] = []
    manifest_extra: list[str] = []
    if (root / ".git").exists() and root.resolve() == ROOT.resolve():
        committed, committed_excluded, base_sha, head_sha = committed_candidate_paths(
            root,
            base_ref=effective_base_ref,
        )
        manifest_set = set(paths)
        committed_set = set(committed)
        committed_missing = sorted(committed_set.difference(manifest_set))
        manifest_extra = sorted(manifest_set.difference(committed_set))
        if committed_excluded:
            excluded.extend(path for path in committed_excluded if path not in excluded)
            errors.append("committed candidate delta includes excluded paths")
        if committed_missing:
            errors.append("manifest omits committed candidate paths")
        if manifest_extra:
            errors.append("manifest includes paths outside the committed candidate delta")
    destination = output_path if output_path is not None else _default_bundle_path()
    if not dry_run and not errors:
        create_zip(files, destination, root=root, deleted_paths=deleted)
    status = "failed" if errors else "planned" if dry_run else "created"
    return BundleReport(
        status=status,
        generated_at=_utc_now(),
        dry_run=dry_run,
        manifest_path=str(manifest_path),
        output_path=None if dry_run else str(destination),
        file_count=len(files),
        total_bytes=sum(item.size_bytes for item in files if not item.deleted),
        files=files,
        missing_files=missing,
        excluded_files=excluded,
        clean_tracked_files=clean_tracked,
        errors=errors,
        deleted_files=deleted,
        undeleted_files=undeleted,
        deletion_manifest_path=DELETION_MANIFEST_PATH if deleted else None,
        base_ref=effective_base_ref if base_sha else "",
        base_sha=base_sha,
        head_sha=head_sha,
        committed_missing_from_manifest=committed_missing,
        manifest_extra_committed=manifest_extra,
        dirty_files=sorted(changed),
    )


def write_report(report: BundleReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or create the X-Agent commercial RC source bundle")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=None, help="zip output path when not in dry-run mode")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--base-ref")
    parser.add_argument("--create", action="store_true", help="write the zip archive; default is dry-run only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_bundle(
        manifest_path=args.manifest,
        output_path=args.output,
        dry_run=not args.create,
        base_ref=args.base_ref,
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
