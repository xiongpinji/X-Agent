#!/usr/bin/env python3
"""Scan customer-facing docs for unsupported commercial readiness claims.

The Stage 5 claim boundary allows controlled commercial pilot/RC wording only.
This script reads candidate docs and writes local JSON/Markdown reports. It
does not edit scanned files, deploy, release, tag, or send outbound messages.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from re import Pattern
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "stage5-claim-safe-docs-gate-20260615.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "stage5-claim-safe-docs-gate-20260615.md"

DEFAULT_SCAN_PATHS = (
    "README.md",
    "DEPLOYMENT.md",
    "RELEASE_NOTES_v1.0.0.md",
    "README_DELIVERABLES.md",
    "docs/PRODUCTION_DEPLOYMENT_RUNBOOK.md",
    "docs/COMMERCIAL_DEPLOYMENT_RUNBOOK.md",
    "docs/RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md",
)

CLAIM_BOUNDARY = {
    "allowed": "controlled commercial pilot readiness",
    "disallowed": [
        "GA ready",
        "general availability ready",
        "production ready",
        "full commercial delivery complete",
        "full Codex parity",
        "staging proven",
        "production deploy/tag/release complete",
        "customer delivery complete",
    ],
}

ALLOW_CONTEXT_TOKENS = (
    "not",
    "does not claim",
    "do not claim",
    "must not",
    "forbidden",
    "blocked",
    "draft",
    "pilot",
    "rc",
    "owner-gated",
    "owner gated",
    "not ga",
    "forbidden claims",
    "explicitly disallowed",
    "disallowed current claims",
    "不能声明",
    "不得声明",
    "不允许",
    "未",
    "不是",
)


@dataclass(frozen=True)
class BlockedPhraseSpec:
    phrase: str
    pattern: Pattern[str]


@dataclass(frozen=True)
class ClaimMatch:
    file: str
    line: int
    phrase: str
    text: str
    context: str
    allow_reason: str | None = None


@dataclass(frozen=True)
class ScannedFile:
    path: str
    line_count: int
    bytes: int


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class ClaimScanReport:
    status: str
    claim_safe_docs_ready: bool
    generated_at: str
    current_head_sha: str | None
    scanned_files: list[ScannedFile]
    skipped_files: list[SkippedFile]
    violations: list[ClaimMatch]
    allowed_matches: list[ClaimMatch]
    blocked_phrase_count: int
    mutation_performed: bool
    outbound_message_sent: bool
    claim_boundary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scanned_files"] = [asdict(item) for item in self.scanned_files]
        payload["skipped_files"] = [asdict(item) for item in self.skipped_files]
        payload["violations"] = [asdict(item) for item in self.violations]
        payload["allowed_matches"] = [asdict(item) for item in self.allowed_matches]
        return payload


def _blocked_phrase_specs() -> tuple[BlockedPhraseSpec, ...]:
    def spec(phrase: str, pattern: str) -> BlockedPhraseSpec:
        return BlockedPhraseSpec(phrase=phrase, pattern=re.compile(pattern, re.IGNORECASE))

    return (
        spec("GA ready", r"\bGA\s+ready\b"),
        spec("general availability ready", r"\bgeneral\s+availability\s+ready\b"),
        spec("production ready", r"\bproduction\s+ready\b"),
        spec("production-ready", r"\bproduction-ready\b"),
        spec("prod-ready", r"\bprod-ready\b"),
        spec(
            "full commercial delivery complete",
            r"\bfull\s+commercial\s+delivery\s+complete\b",
        ),
        spec("commercial delivery complete", r"\bcommercial\s+delivery\s+complete\b"),
        spec("delivery complete", r"\bdelivery\s+complete\b"),
        spec("release ready", r"\brelease\s+ready\b"),
        spec("full Codex parity", r"\bfull\s+codex\s+parity\b"),
        spec("full parity", r"\bfull\s+parity\b"),
        spec("full competitor parity", r"\bfull\s+competitor\s+parity\b"),
        spec("staging proven", r"\bstaging\s+proven\b"),
        spec("production deploy complete", r"\bproduction\s+deploy\s+complete\b"),
        spec("production release complete", r"\bproduction\s+release\s+complete\b"),
        spec("customer delivery complete", r"\bcustomer\s+delivery\s+complete\b"),
        spec(
            "unqualified Status: Production-Ready",
            r"\bstatus\s*:\s*production-ready\b",
        ),
        spec("SDK production-ready", r"\bsdk\b.{0,80}\bproduction[-\s]+ready\b"),
        spec("Helm production-ready", r"\bhelm\b.{0,80}\bproduction[-\s]+ready\b"),
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _git_head_sha(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _context_window(lines: Sequence[str], index: int) -> str:
    start = max(0, index - 3)
    end = min(len(lines), index + 2)
    return " ".join(line.strip() for line in lines[start:end] if line.strip())


def _allow_reason(context: str) -> str | None:
    normalized = context.casefold()
    for token in ALLOW_CONTEXT_TOKENS:
        if token.casefold() in normalized:
            return f"boundary context token: {token}"
    return None


def _scan_text(path_label: str, text: str) -> tuple[list[ClaimMatch], list[ClaimMatch]]:
    violations: list[ClaimMatch] = []
    allowed: list[ClaimMatch] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        context = _context_window(lines, index)
        allow_reason = _allow_reason(context)
        matched_spans: list[tuple[int, int]] = []
        for phrase_spec in _blocked_phrase_specs():
            for regex_match in phrase_spec.pattern.finditer(line):
                span = regex_match.span()
                if any(span[0] >= existing[0] and span[1] <= existing[1] for existing in matched_spans):
                    continue
                matched_spans.append(span)
                match = ClaimMatch(
                    file=path_label,
                    line=index + 1,
                    phrase=phrase_spec.phrase,
                    text=line.strip(),
                    context=context,
                    allow_reason=allow_reason,
                )
                if allow_reason:
                    allowed.append(match)
                else:
                    violations.append(match)
    return violations, allowed


def build_claim_scan_report(
    *,
    root: Path = ROOT,
    scan_paths: Sequence[str | Path] = DEFAULT_SCAN_PATHS,
    current_head_sha: str | None = None,
) -> ClaimScanReport:
    scanned_files: list[ScannedFile] = []
    skipped_files: list[SkippedFile] = []
    violations: list[ClaimMatch] = []
    allowed_matches: list[ClaimMatch] = []

    for scan_path in scan_paths:
        relative = Path(scan_path)
        path = relative if relative.is_absolute() else root / relative
        path_label = _display_path(path, root)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            skipped_files.append(SkippedFile(path=Path(scan_path).as_posix(), reason="missing"))
            continue
        except OSError as exc:
            skipped_files.append(SkippedFile(path=path_label, reason=f"read_error: {exc}"))
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            skipped_files.append(SkippedFile(path=path_label, reason=f"decode_error: {exc}"))
            continue

        scanned_files.append(
            ScannedFile(path=path_label, line_count=len(text.splitlines()), bytes=len(raw))
        )
        file_violations, file_allowed = _scan_text(path_label, text)
        violations.extend(file_violations)
        allowed_matches.extend(file_allowed)

    status = "claim_safe_docs_blocked" if violations else "claim_safe_docs_ready"
    return ClaimScanReport(
        status=status,
        claim_safe_docs_ready=not violations,
        generated_at=_utc_now(),
        current_head_sha=current_head_sha if current_head_sha is not None else _git_head_sha(root),
        scanned_files=scanned_files,
        skipped_files=skipped_files,
        violations=violations,
        allowed_matches=allowed_matches,
        blocked_phrase_count=len(violations) + len(allowed_matches),
        mutation_performed=False,
        outbound_message_sent=False,
        claim_boundary=CLAIM_BOUNDARY,
    )


def render_markdown(report: ClaimScanReport) -> str:
    lines = [
        "# Stage 5 Claim-Safe Docs Gate - 2026-06-15",
        "",
        f"- Status: `{report.status}`",
        f"- Claim-safe docs ready: `{report.claim_safe_docs_ready}`",
        f"- Current HEAD: `{report.current_head_sha}`",
        f"- Scanned files: `{len(report.scanned_files)}`",
        f"- Skipped files: `{len(report.skipped_files)}`",
        f"- Blocked phrase matches: `{report.blocked_phrase_count}`",
        f"- Violations: `{len(report.violations)}`",
        f"- Allowed boundary matches: `{len(report.allowed_matches)}`",
        f"- Mutation performed: `{report.mutation_performed}`",
        f"- Outbound message sent: `{report.outbound_message_sent}`",
        "",
        "## Claim Boundary",
        "",
        f"Allowed wording: `{report.claim_boundary['allowed']}`.",
        "",
        "Disallowed current claims: "
        + ", ".join(f"`{claim}`" for claim in report.claim_boundary["disallowed"]),
        "",
        "## Violations",
        "",
    ]
    if report.violations:
        lines.extend(
            f"- `{match.file}:{match.line}` `{match.phrase}` - {match.text}"
            for match in report.violations
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Allowed Boundary Matches", ""])
    if report.allowed_matches:
        lines.extend(
            f"- `{match.file}:{match.line}` `{match.phrase}` - {match.allow_reason}"
            for match in report.allowed_matches
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Skipped Files", ""])
    if report.skipped_files:
        lines.extend(f"- `{item.path}` - {item.reason}" for item in report.skipped_files)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_reports(report: ClaimScanReport, output: Path, markdown_output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument(
        "--scan-file",
        action="append",
        dest="scan_files",
        help="Relative or absolute file to scan. May be supplied multiple times.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    scan_paths = args.scan_files if args.scan_files else DEFAULT_SCAN_PATHS
    report = build_claim_scan_report(root=args.root, scan_paths=scan_paths)
    write_reports(report, args.output, args.markdown_output)
    print(f"Status: {report.status}")
    print(f"Report: {args.output}")
    print(f"Markdown: {args.markdown_output}")
    print(f"Violations: {len(report.violations)}")
    return 1 if report.violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
