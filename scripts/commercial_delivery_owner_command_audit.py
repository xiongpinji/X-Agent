#!/usr/bin/env python3
"""Audit owner staging commands without executing them.

This report validates that the owner staging packet contains only exact
``git add -- '<path>'`` commands for the expected stage paths. It does not
stage files, create commits, push, run tests, execute agents, or call network
services.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now
from scripts.commercial_delivery_task_board import _display_path

DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-command-audit.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-command-audit.md"

COMMAND_RE = re.compile(r"^git add -- '([^']*(?:''[^']*)*)'$")
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
class OwnerCommandAuditCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerCommandAudit:
    status: str
    generated_at: str
    evidence_type: str
    owner_gated: bool
    post_commit_noop_accounted_for: bool
    mutation_performed: bool
    git_stage_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    agent_execution_enabled: bool
    full_codex_parity_claimed: bool
    owner_packet_status: str | None
    staging_review_status: str | None
    manifest_status: str | None
    command_count: int
    expected_path_count: int
    command_paths: list[str]
    expected_paths: list[str]
    command_path_digest: str | None
    expected_path_digest: str | None
    owner_packet_stage_path_digest: str | None
    command_digest: str | None
    owner_packet_stage_command_digest: str | None
    broad_commands: list[str]
    malformed_commands: list[str]
    missing_command_paths: list[str]
    unexpected_command_paths: list[str]
    duplicate_command_paths: list[str]
    protected_command_paths: list[str]
    summary: dict[str, Any]
    checks: list[OwnerCommandAuditCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        for name, value in asdict(self).items():
            if isinstance(value, list):
                payload[f"{name}_count"] = len(value)
        return payload


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, f"report not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"could not read report {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"report is not a JSON object: {_display_path(path)}"
    return payload, None


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerCommandAuditCheck:
    return OwnerCommandAuditCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip('"')


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _commands(packet: dict[str, Any]) -> list[str]:
    values = packet.get("stage_commands")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _packet_paths(packet: dict[str, Any]) -> list[str]:
    values = packet.get("stage_paths")
    if not isinstance(values, list):
        return []
    return [_normalize_path(str(value)) for value in values if str(value).strip()]


def _staging_paths(staging_review: dict[str, Any]) -> list[str]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    paths: list[str] = []
    for row in rows:
        if isinstance(row, dict) and row.get("status") == "eligible" and row.get("path"):
            paths.append(_normalize_path(str(row["path"])))
    return paths


def _staging_paths_by_status(staging_review: dict[str, Any], status: str) -> list[str]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    paths: list[str] = []
    for row in rows:
        if isinstance(row, dict) and row.get("status") == status and row.get("path"):
            paths.append(_normalize_path(str(row["path"])))
    return paths


def _manifest_paths(manifest: dict[str, Any]) -> list[str]:
    values = manifest.get("stage_include_paths")
    if not isinstance(values, list):
        return []
    return [_normalize_path(str(value)) for value in values if str(value).strip()]


def _command_path(command: str) -> str | None:
    match = COMMAND_RE.match(command.strip())
    if not match:
        return None
    return _normalize_path(match.group(1).replace("''", "'"))


def _is_broad_command(command: str) -> bool:
    normalized = command.strip().lower()
    return normalized in {"git add .", "git add -a", "git add --all", "git add *"} or normalized.startswith(
        "git add -- ."
    )


def _is_protected(path: str) -> bool:
    normalized = _normalize_path(path)
    return normalized in PROTECTED_EXACT or any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _duplicates(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for path in paths:
        if path in seen:
            duplicates.add(path)
        seen.add(path)
    return sorted(duplicates)


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value) if isinstance(value, str) and value else None


def _int_field(payload: dict[str, Any], field: str) -> int:
    try:
        return int(payload.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def _packet_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _post_commit_noop_accounted_for(
    *,
    owner_packet: dict[str, Any],
    staging_review: dict[str, Any],
    manifest: dict[str, Any],
    commands: list[str],
    packet_paths: list[str],
) -> bool:
    summary = _packet_summary(owner_packet)
    manifest_stage_paths = _manifest_paths(manifest)
    unchanged_paths = _staging_paths_by_status(staging_review, "unchanged")
    manifest_stage_count = _int_field(manifest, "stage_include_count") or len(manifest_stage_paths)
    staging_stage_count = _int_field(staging_review, "stage_include_count")
    return (
        summary.get("post_commit_noop_accounted_for") is True
        and _status(owner_packet) == "owner_staging_packet_ready"
        and _status(staging_review) == "staging_review_ready"
        and _status(manifest) == "original_kernel_delivery_manifest_ready"
        and owner_packet.get("owner_gated") is True
        and staging_review.get("owner_gated") is True
        and not commands
        and not packet_paths
        and _int_field(owner_packet, "blocked_stage_count") == 0
        and _int_field(staging_review, "blocked_stage_count") == 0
        and _int_field(owner_packet, "eligible_stage_count") == 0
        and _int_field(staging_review, "eligible_stage_count") == 0
        and manifest_stage_count > 0
        and staging_stage_count == manifest_stage_count
        and len(unchanged_paths) == manifest_stage_count
    )


def build_owner_command_audit(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> OwnerCommandAudit:
    owner_packet, owner_packet_error = _read_json(owner_packet_path)
    staging_review, staging_review_error = _read_json(staging_review_path)
    manifest, manifest_error = _read_json(manifest_path)

    commands = _commands(owner_packet)
    command_paths = [_command_path(command) for command in commands]
    parsed_command_paths = [path for path in command_paths if path]
    malformed_commands = [command for command, path in zip(commands, command_paths) if path is None]
    broad_commands = [command for command in commands if _is_broad_command(command)]
    packet_paths = _packet_paths(owner_packet)
    post_commit_noop_accounted_for = _post_commit_noop_accounted_for(
        owner_packet=owner_packet,
        staging_review=staging_review,
        manifest=manifest,
        commands=commands,
        packet_paths=packet_paths,
    )
    fallback_paths = _staging_paths(staging_review) or _manifest_paths(manifest)
    digest_expected_paths = [] if post_commit_noop_accounted_for else packet_paths or fallback_paths
    expected_paths = sorted(set(digest_expected_paths))
    missing_command_paths = sorted(set(expected_paths).difference(parsed_command_paths))
    unexpected_command_paths = sorted(set(parsed_command_paths).difference(expected_paths))
    duplicate_command_paths = _duplicates(parsed_command_paths)
    protected_command_paths = sorted(path for path in parsed_command_paths if _is_protected(path))
    sorted_command_paths = sorted(parsed_command_paths)
    command_path_digest = _digest_values(parsed_command_paths) if parsed_command_paths or post_commit_noop_accounted_for else None
    expected_path_digest = _digest_values(digest_expected_paths) if digest_expected_paths or post_commit_noop_accounted_for else None
    owner_packet_stage_path_digest = _digest_field(owner_packet, "stage_path_digest")
    command_digest = _digest_values(commands) if commands or post_commit_noop_accounted_for else None
    owner_packet_stage_command_digest = _digest_field(owner_packet, "stage_command_digest")
    full_codex_parity_claimed = (
        owner_packet.get("full_codex_parity_claimed") is True
        or staging_review.get("full_codex_parity_claimed") is True
        or manifest.get("full_codex_parity_claimed") is True
    )
    owner_gated = owner_packet.get("owner_gated") is True and staging_review.get("owner_gated") is True

    checks = [
        _check(
            "reports_readable",
            owner_packet_error is None and staging_review_error is None and manifest_error is None,
            details={
                "owner_packet_error": owner_packet_error,
                "staging_review_error": staging_review_error,
                "manifest_error": manifest_error,
            },
            error="one or more required reports are missing or unreadable",
        ),
        _check(
            "owner_packet_ready",
            _status(owner_packet) == "owner_staging_packet_ready",
            details={"owner_packet_status": _status(owner_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "staging_review_ready",
            _status(staging_review) == "staging_review_ready",
            details={"staging_review_status": _status(staging_review)},
            error="commercial delivery staging review is not ready",
        ),
        _check(
            "manifest_ready",
            _status(manifest) == "original_kernel_delivery_manifest_ready",
            details={"manifest_status": _status(manifest)},
            error="original-kernel delivery manifest is not ready",
        ),
        _check(
            "commands_present",
            bool(commands) or post_commit_noop_accounted_for,
            details={
                "command_count": len(commands),
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner staging packet has no stage commands",
        ),
        _check(
            "no_broad_stage_commands",
            not broad_commands,
            details={"broad_commands": broad_commands},
            error="owner staging packet contains broad git add commands",
        ),
        _check(
            "commands_are_strict_git_add_path_commands",
            not malformed_commands,
            details={"malformed_commands": malformed_commands},
            error="owner staging packet contains malformed stage commands",
        ),
        _check(
            "command_paths_match_expected_paths",
            not missing_command_paths and not unexpected_command_paths,
            details={
                "missing_command_paths": missing_command_paths,
                "unexpected_command_paths": unexpected_command_paths,
            },
            error="owner staging command paths do not exactly match expected stage paths",
        ),
        _check(
            "stage_path_digest_matches_owner_packet",
            owner_packet_stage_path_digest is not None
            and expected_path_digest is not None
            and command_path_digest == owner_packet_stage_path_digest
            and expected_path_digest == owner_packet_stage_path_digest,
            details={
                "command_path_digest": command_path_digest,
                "expected_path_digest": expected_path_digest,
                "owner_packet_stage_path_digest": owner_packet_stage_path_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner staging path digest does not match parsed command and expected path sets",
        ),
        _check(
            "stage_command_digest_matches_owner_packet",
            owner_packet_stage_command_digest is not None
            and command_digest is not None
            and command_digest == owner_packet_stage_command_digest,
            details={
                "command_digest": command_digest,
                "owner_packet_stage_command_digest": owner_packet_stage_command_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner staging command digest does not match owner packet stage commands",
        ),
        _check(
            "no_duplicate_command_paths",
            not duplicate_command_paths,
            details={"duplicate_command_paths": duplicate_command_paths},
            error="owner staging packet contains duplicate path commands",
        ),
        _check(
            "no_protected_command_paths",
            not protected_command_paths,
            details={"protected_command_paths": protected_command_paths},
            error="owner staging packet contains protected paths",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="delivery reports claim full Codex parity",
        ),
        _check(
            "no_command_audit_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
            },
        ),
    ]

    status = "owner_command_audit_ready" if all(check.status == "passed" for check in checks) else "owner_command_audit_blocked"
    return OwnerCommandAudit(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_command_audit",
        owner_gated=owner_gated,
        post_commit_noop_accounted_for=post_commit_noop_accounted_for,
        mutation_performed=False,
        git_stage_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        owner_packet_status=_status(owner_packet),
        staging_review_status=_status(staging_review),
        manifest_status=_status(manifest),
        command_count=len(commands),
        expected_path_count=len(expected_paths),
        command_paths=sorted_command_paths,
        expected_paths=expected_paths,
        command_path_digest=command_path_digest,
        expected_path_digest=expected_path_digest,
        owner_packet_stage_path_digest=owner_packet_stage_path_digest,
        command_digest=command_digest,
        owner_packet_stage_command_digest=owner_packet_stage_command_digest,
        broad_commands=broad_commands,
        malformed_commands=malformed_commands,
        missing_command_paths=missing_command_paths,
        unexpected_command_paths=unexpected_command_paths,
        duplicate_command_paths=duplicate_command_paths,
        protected_command_paths=protected_command_paths,
        summary={
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "manifest_stage_include_count": _int_field(manifest, "stage_include_count"),
            "staging_review_stage_include_count": _int_field(staging_review, "stage_include_count"),
            "staging_review_eligible_stage_count": _int_field(staging_review, "eligible_stage_count"),
            "staging_review_blocked_stage_count": _int_field(staging_review, "blocked_stage_count"),
            "staging_review_unchanged_stage_count": len(_staging_paths_by_status(staging_review, "unchanged")),
            "owner_packet_eligible_stage_count": _int_field(owner_packet, "eligible_stage_count"),
            "owner_packet_blocked_stage_count": _int_field(owner_packet, "blocked_stage_count"),
        },
        checks=checks,
        next_actions=[
            "Run this audit before owner-approved staging and after any owner packet regeneration.",
            "If ready, owner may review the exact stage commands in the owner staging packet.",
            "If blocked, regenerate or fix the owner staging packet; do not execute broad git add commands.",
        ],
        known_limits=[
            "This audit is read-only and never executes staging commands.",
            "It validates command shape and path equality, not the owner's manual copy/paste action.",
            "Run the post-staging verifier after owner-approved staging.",
        ],
    )


def render_markdown_audit(report: OwnerCommandAudit) -> str:
    lines = [
        "# Commercial Delivery Owner Command Audit",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Owner gated: `{str(report.owner_gated).lower()}`",
        f"- Command count: `{report.command_count}`",
        f"- Expected path count: `{report.expected_path_count}`",
        f"- Command path digest: `{report.command_path_digest or '<missing>'}`",
        f"- Expected path digest: `{report.expected_path_digest or '<missing>'}`",
        f"- Command digest: `{report.command_digest or '<missing>'}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Command Paths", ""])
    lines.extend(f"- `{path}`" for path in report.command_paths)
    return "\n".join(lines)


def write_report(report: OwnerCommandAudit, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown_audit(report: OwnerCommandAudit, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_audit(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-packet", type=Path, default=DEFAULT_OWNER_PACKET)
    parser.add_argument("--staging-review", type=Path, default=DEFAULT_STAGING_REVIEW)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_owner_command_audit(
        owner_packet_path=args.owner_packet,
        staging_review_path=args.staging_review,
        manifest_path=args.manifest,
    )
    write_report(report, args.output)
    write_markdown_audit(report, args.markdown_output)
    print(f"Commercial delivery owner command audit status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Commands: {report.command_count}")
    print(f"Expected paths: {report.expected_path_count}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "owner_command_audit_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
