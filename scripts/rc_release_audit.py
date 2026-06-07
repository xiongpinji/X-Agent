#!/usr/bin/env python3
"""Audit the commercial RC candidate file set before staging."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "RC_STAGING_MANIFEST.md"
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "rc-release-audit.json"

EXCLUDED_PREFIXES = (".agents/", ".codex/", ".xagent_runtime/", "backend/app/core/creative_studio/")
EXCLUDED_EXACT = {
    "AGENTS.md",
    "COMPETITIVE_ANALYSIS_2026.md",
    "backend/app/api/creative_studio.py",
    "docs/01-项目规划/05-Creative-Studio短剧成片工作流.md",
    "tests/test_creative_studio.py",
}
EXCLUDED_REFERENCE_PATTERNS = {
    "creative_studio": (
        "backend.app.api.creative_studio",
        "backend.app.core.creative_studio",
        "/api/v1/creative-studio",
    ),
}
LOCAL_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("windows_user_profile", re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/:\s]+")),
    ("posix_user_home", re.compile(r"(?i)/(?:home|Users)/[A-Za-z0-9._-]+/")),
)
EXCLUDED_REFERENCE_SCAN_EXEMPT = {
    "scripts/rc_release_audit.py",
    "tests/test_rc_release_audit.py",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".env",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

SECRET_PATTERNS = (
    re.compile(r"(?i)\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{24,})"),
    re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b"),
)
PLACEHOLDER_TOKENS = (
    "...",
    "<",
    ">",
    "change",
    "example",
    "placeholder",
    "secure_password",
    "secure_key",
    "your",
)


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    pattern: str
    sample: str


@dataclass(frozen=True)
class ExcludedReferenceFinding:
    path: str
    line: int
    excluded_area: str
    sample: str


@dataclass(frozen=True)
class LocalPathFinding:
    path: str
    line: int
    pattern: str
    sample: str


@dataclass(frozen=True)
class FileHygieneFinding:
    path: str
    line: int
    kind: str
    sample: str


@dataclass(frozen=True)
class ManifestPathFinding:
    path: str
    reason: str


@dataclass(frozen=True)
class ReleaseAudit:
    status: str
    generated_at: str
    branch: str
    candidate_count: int
    manifest_count: int
    missing_from_manifest: list[str]
    manifest_extra: list[str]
    manifest_tracked_misclassified: list[str]
    manifest_new_misclassified: list[str]
    manifest_unsafe_paths: list[ManifestPathFinding]
    secret_findings: list[SecretFinding]
    excluded_reference_findings: list[ExcludedReferenceFinding]
    local_path_findings: list[LocalPathFinding]
    file_hygiene_findings: list[FileHygieneFinding]
    excluded_present: list[str]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["secret_findings"] = [asdict(finding) for finding in self.secret_findings]
        payload["excluded_reference_findings"] = [
            asdict(finding) for finding in self.excluded_reference_findings
        ]
        payload["local_path_findings"] = [asdict(finding) for finding in self.local_path_findings]
        payload["file_hygiene_findings"] = [asdict(finding) for finding in self.file_hygiene_findings]
        payload["manifest_unsafe_paths"] = [asdict(finding) for finding in self.manifest_unsafe_paths]
        return payload


def _git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def is_excluded(path: str) -> bool:
    return path in EXCLUDED_EXACT or any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def candidate_paths(manifest_text: str | None = None) -> tuple[list[str], list[str], bool]:
    tracked = set(_git_lines("diff", "--name-only")) | set(_git_lines("diff", "--cached", "--name-only"))
    untracked = set(_git_lines("ls-files", "--others", "--exclude-standard"))
    candidates = sorted(path for path in tracked | untracked if not is_excluded(path))
    excluded_present = sorted(path for path in tracked | untracked if is_excluded(path))
    manifest_fallback = False
    if not candidates and manifest_text is not None:
        candidates = [path for path in manifest_candidate_paths(manifest_text) if (ROOT / path).exists()]
        manifest_fallback = True
    return candidates, excluded_present, manifest_fallback


def repository_classification_paths() -> tuple[set[str], set[str]]:
    head_paths = set(_git_lines("ls-tree", "-r", "--name-only", "HEAD"))
    index_paths = set(_git_lines("ls-files", "--cached"))
    untracked_paths = set(_git_lines("ls-files", "--others", "--exclude-standard"))
    return head_paths, (index_paths - head_paths) | untracked_paths


def missing_from_manifest(paths: Iterable[str], manifest_text: str) -> list[str]:
    return [path for path in paths if path not in manifest_text]


def manifest_candidate_paths(manifest_text: str) -> list[str]:
    sections = manifest_candidate_sections(manifest_text)
    paths: list[str] = []
    for section_paths in sections.values():
        paths.extend(section_paths)
    return sorted(dict.fromkeys(paths))


def manifest_candidate_sections(manifest_text: str) -> dict[str, list[str]]:
    wanted = {"Tracked Modified Candidate Files", "New Candidate Files"}
    current_heading = ""
    in_block = False
    sections: dict[str, list[str]] = {heading: [] for heading in wanted}
    for raw_line in manifest_text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("## "):
            current_heading = line.removeprefix("## ").strip()
            continue
        if line.strip() == "```text" and current_heading in wanted:
            in_block = True
            continue
        if in_block and line.strip() == "```":
            in_block = False
            continue
        if in_block:
            candidate = line.strip()
            if candidate and not candidate.startswith("#"):
                sections[current_heading].append(candidate.replace("\\", "/"))
    return {
        heading: sorted(dict.fromkeys(paths))
        for heading, paths in sections.items()
    }


def manifest_classification_mismatches(
    manifest_text: str,
    *,
    tracked_paths: Iterable[str],
    untracked_paths: Iterable[str],
) -> tuple[list[str], list[str]]:
    sections = manifest_candidate_sections(manifest_text)
    tracked = set(tracked_paths)
    untracked = set(untracked_paths)
    tracked_block = sections["Tracked Modified Candidate Files"]
    new_block = sections["New Candidate Files"]
    tracked_misclassified = [path for path in tracked_block if path in untracked]
    new_misclassified = [path for path in new_block if path in tracked]
    return tracked_misclassified, new_misclassified


def manifest_extra_paths(manifest_paths: Iterable[str], candidate_paths_: Iterable[str]) -> list[str]:
    candidates = set(candidate_paths_)
    return [path for path in manifest_paths if path not in candidates]


def normalize_manifest_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def unsafe_manifest_path_reason(path: str) -> str | None:
    normalized = normalize_manifest_path(path)
    if not normalized:
        return "empty path"
    if normalized.startswith("/"):
        return "absolute path"
    if len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/":
        return "windows drive path"
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return "unsafe path segment"
    return None


def is_safe_manifest_path(path: str) -> bool:
    return unsafe_manifest_path_reason(path) is None


def manifest_unsafe_path_findings(paths: Iterable[str]) -> list[ManifestPathFinding]:
    findings: list[ManifestPathFinding] = []
    for path in paths:
        normalized = normalize_manifest_path(path)
        reason = unsafe_manifest_path_reason(normalized)
        if reason:
            findings.append(ManifestPathFinding(path=normalized, reason=reason))
    return findings


def _is_probable_placeholder(value: str) -> bool:
    if value.startswith("--"):
        return True
    if value.startswith("_"):
        return True
    lowered = value.lower()
    return any(token in lowered for token in PLACEHOLDER_TOKENS)


def _redact(value: str) -> str:
    if len(value) <= 12:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def scan_secret_findings(paths: Iterable[str], root: Path = ROOT) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    seen: set[tuple[str, int, str]] = set()
    for relative_path in paths:
        path = root / relative_path
        if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for pattern in SECRET_PATTERNS:
                for match in pattern.finditer(line):
                    sample = match.group(1) if match.groups() else match.group(0)
                    if _is_probable_placeholder(sample):
                        continue
                    key = (relative_path, line_number, sample)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        SecretFinding(
                            path=relative_path,
                            line=line_number,
                            pattern=pattern.pattern,
                            sample=_redact(sample),
                        )
                    )
    return findings


def scan_excluded_reference_findings(paths: Iterable[str], root: Path = ROOT) -> list[ExcludedReferenceFinding]:
    findings: list[ExcludedReferenceFinding] = []
    for relative_path in paths:
        if relative_path in EXCLUDED_REFERENCE_SCAN_EXEMPT:
            continue
        path = root / relative_path
        if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for area, patterns in EXCLUDED_REFERENCE_PATTERNS.items():
                if any(pattern in line for pattern in patterns):
                    findings.append(
                        ExcludedReferenceFinding(
                            path=relative_path,
                            line=line_number,
                            excluded_area=area,
                            sample=line.strip()[:160],
                        )
                    )
    return findings


def scan_local_path_findings(paths: Iterable[str], root: Path = ROOT) -> list[LocalPathFinding]:
    findings: list[LocalPathFinding] = []
    for relative_path in paths:
        if relative_path in EXCLUDED_REFERENCE_SCAN_EXEMPT:
            continue
        path = root / relative_path
        if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for pattern_name, pattern in LOCAL_PATH_PATTERNS:
                for match in pattern.finditer(line):
                    findings.append(
                        LocalPathFinding(
                            path=relative_path,
                            line=line_number,
                            pattern=pattern_name,
                            sample=_redact(match.group(0)),
                        )
                    )
    return findings


def scan_file_hygiene_findings(paths: Iterable[str], root: Path = ROOT) -> list[FileHygieneFinding]:
    findings: list[FileHygieneFinding] = []
    for relative_path in paths:
        path = root / relative_path
        if not path.exists():
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            findings.append(
                FileHygieneFinding(
                    path=relative_path,
                    line=0,
                    kind="nul_byte",
                    sample="<binary-nul>",
                )
            )
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = data.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            findings.append(
                FileHygieneFinding(
                    path=relative_path,
                    line=0,
                    kind="utf8_decode_error",
                    sample=f"byte offset {exc.start}",
                )
            )
            continue
        for line_number, line in enumerate(lines, start=1):
            if line.rstrip(" \t") != line:
                findings.append(
                    FileHygieneFinding(
                        path=relative_path,
                        line=line_number,
                        kind="trailing_whitespace",
                        sample=line.strip()[:160],
                    )
                )
                break
            if line.startswith(("<<<<<<< ", "=======", ">>>>>>> ")):
                findings.append(
                    FileHygieneFinding(
                        path=relative_path,
                        line=line_number,
                        kind="merge_conflict_marker",
                        sample=line.strip()[:160],
                    )
                )
                break
    return findings


def run_audit(manifest_path: Path = DEFAULT_MANIFEST) -> ReleaseAudit:
    tracked, untracked = repository_classification_paths()
    manifest_text = manifest_path.read_text(encoding="utf-8")
    candidates, excluded_present, manifest_fallback = candidate_paths(manifest_text)
    manifest_paths = manifest_candidate_paths(manifest_text)
    manifest_unsafe_paths = manifest_unsafe_path_findings(manifest_paths)
    missing = missing_from_manifest(candidates, manifest_text)
    extra = manifest_extra_paths(manifest_paths, candidates)
    if manifest_fallback:
        tracked_misclassified, new_misclassified = [], []
    else:
        tracked_misclassified, new_misclassified = manifest_classification_mismatches(
            manifest_text,
            tracked_paths=tracked,
            untracked_paths=untracked,
        )
    findings = scan_secret_findings(candidates)
    excluded_reference_findings = scan_excluded_reference_findings(candidates)
    local_path_findings = scan_local_path_findings(candidates)
    file_hygiene_findings = scan_file_hygiene_findings(candidates)
    status = (
        "passed"
        if not missing
        and not extra
        and not tracked_misclassified
        and not new_misclassified
        and not manifest_unsafe_paths
        and not findings
        and not excluded_reference_findings
        and not local_path_findings
        and not file_hygiene_findings
        else "failed"
    )
    branch = _git_lines("branch", "--show-current")
    return ReleaseAudit(
        status=status,
        generated_at=datetime.now(UTC).isoformat(),
        branch=branch[0] if branch else "",
        candidate_count=len(candidates),
        manifest_count=len(manifest_paths),
        missing_from_manifest=missing,
        manifest_extra=extra,
        manifest_tracked_misclassified=tracked_misclassified,
        manifest_new_misclassified=new_misclassified,
        manifest_unsafe_paths=manifest_unsafe_paths,
        secret_findings=findings,
        excluded_reference_findings=excluded_reference_findings,
        local_path_findings=local_path_findings,
        file_hygiene_findings=file_hygiene_findings,
        excluded_present=excluded_present,
    )


def write_report(audit: ReleaseAudit, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit X-Agent commercial RC candidate files")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    audit = run_audit(args.manifest)
    write_report(audit, args.output)
    print(f"RC release audit status: {audit.status}")
    print(f"Candidate files: {audit.candidate_count}")
    print(f"Report written to {args.output}")
    if audit.missing_from_manifest:
        print("Missing from manifest:")
        for path in audit.missing_from_manifest:
            print(f"- {path}")
    if audit.manifest_extra:
        print("Manifest entries not present in current candidate diff:")
        for path in audit.manifest_extra:
            print(f"- {path}")
    if audit.manifest_tracked_misclassified:
        print("Manifest tracked entries that are currently untracked:")
        for path in audit.manifest_tracked_misclassified:
            print(f"- {path}")
    if audit.manifest_new_misclassified:
        print("Manifest new entries that are currently tracked:")
        for path in audit.manifest_new_misclassified:
            print(f"- {path}")
    if audit.manifest_unsafe_paths:
        print("Manifest unsafe path entries:")
        for finding in audit.manifest_unsafe_paths:
            print(f"- {finding.path}: {finding.reason}")
    if audit.secret_findings:
        print("Secret-like findings:")
        for finding in audit.secret_findings:
            print(f"- {finding.path}:{finding.line} {finding.sample}")
    if audit.excluded_reference_findings:
        print("Excluded-area references:")
        for finding in audit.excluded_reference_findings:
            print(f"- {finding.path}:{finding.line} {finding.excluded_area}: {finding.sample}")
    if audit.local_path_findings:
        print("Local user/runtime path findings:")
        for finding in audit.local_path_findings:
            print(f"- {finding.path}:{finding.line} {finding.pattern}: {finding.sample}")
    if audit.file_hygiene_findings:
        print("Candidate file hygiene findings:")
        for finding in audit.file_hygiene_findings:
            location = f"{finding.path}:{finding.line}" if finding.line else finding.path
            print(f"- {location} {finding.kind}: {finding.sample}")
    return 0 if audit.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
