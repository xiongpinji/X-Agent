#!/usr/bin/env python3
"""Preflight owner-gated staging commands without mutating git state.

This report is the last read-only check before an owner runs the explicit
``git add -- '<path>'`` commands from the owner staging packet. It validates
that commands and eligible paths still match, protected surfaces are absent,
and the git index is clean before staging begins.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.md"

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
class OwnerStagingPreflightCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStagingPreflight:
    status: str
    generated_at: str
    evidence_type: str
    owner_gated: bool
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
    stage_command_count: int
    stage_path_count: int
    manifest_stage_path_count: int
    cached_staged_path_count: int
    parsed_stage_paths: list[str]
    cached_staged_paths: list[str]
    protected_stage_paths: list[str]
    broad_stage_commands: list[str]
    checks: list[OwnerStagingPreflightCheck]
    next_actions: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
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


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().strip('"')


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
) -> OwnerStagingPreflightCheck:
    return OwnerStagingPreflightCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _is_protected(path: str) -> bool:
    normalized = _normalize_path(path)
    return normalized in PROTECTED_EXACT or any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def _stage_paths_from_packet(packet: dict[str, Any]) -> list[str]:
    values = packet.get("stage_paths")
    if not isinstance(values, list):
        return []
    return [_normalize_path(str(value)) for value in values if str(value).strip()]


def _stage_paths_from_staging_review(staging_review: dict[str, Any]) -> list[str]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    paths: list[str] = []
    for item in rows:
        if isinstance(item, dict) and item.get("status") == "eligible" and item.get("path"):
            paths.append(_normalize_path(str(item["path"])))
    return paths


def _stage_paths_from_manifest(manifest: dict[str, Any]) -> list[str]:
    values = manifest.get("stage_include_paths")
    if not isinstance(values, list):
        return []
    return [_normalize_path(str(value)) for value in values if str(value).strip()]


def _stage_commands(packet: dict[str, Any]) -> list[str]:
    values = packet.get("stage_commands")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _parse_stage_command(command: str) -> str | None:
    match = re.fullmatch(r"git add -- '((?:[^']|'')+)'", command.strip())
    if not match:
        return None
    return _normalize_path(match.group(1).replace("''", "'"))


def _broad_stage_commands(commands: Sequence[str]) -> list[str]:
    broad: list[str] = []
    for command in commands:
        normalized = " ".join(command.strip().split())
        if normalized in {"git add .", "git add -A", "git add --all", "git add -- ."}:
            broad.append(command)
        elif _parse_stage_command(command) is None:
            broad.append(command)
    return broad


def _git_cached_diff_lines() -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _cached_paths(lines: Sequence[str]) -> list[str]:
    return sorted({_normalize_path(line) for line in lines if line.strip()})


def build_owner_staging_preflight(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    cached_diff_lines: Sequence[str] | None = None,
) -> OwnerStagingPreflight:
    owner_packet, owner_packet_error = _read_json(owner_packet_path)
    staging_review, staging_review_error = _read_json(staging_review_path)
    manifest, manifest_error = _read_json(manifest_path)

    packet_stage_paths = _stage_paths_from_packet(owner_packet)
    staging_eligible_paths = _stage_paths_from_staging_review(staging_review)
    manifest_stage_paths = _stage_paths_from_manifest(manifest)
    commands = _stage_commands(owner_packet)
    parsed_paths = [_parse_stage_command(command) for command in commands]
    parsed_stage_paths = [path for path in parsed_paths if path is not None]
    broad_commands = _broad_stage_commands(commands)
    cached_paths = _cached_paths(cached_diff_lines if cached_diff_lines is not None else _git_cached_diff_lines())
    protected_paths = sorted({path for path in parsed_stage_paths + packet_stage_paths if _is_protected(path)})

    command_paths_match_packet = parsed_stage_paths == packet_stage_paths
    packet_paths_match_staging = packet_stage_paths == staging_eligible_paths
    packet_paths_known_to_manifest = set(packet_stage_paths).issubset(set(manifest_stage_paths))
    full_codex_parity_claimed = (
        owner_packet.get("full_codex_parity_claimed") is True
        or staging_review.get("full_codex_parity_claimed") is True
        or manifest.get("full_codex_parity_claimed") is True
    )
    owner_gated = owner_packet.get("owner_gated") is True and staging_review.get("owner_gated") is True

    checks = [
        _check(
            "owner_packet_readable",
            owner_packet_error is None,
            details={"owner_packet_path": _display_path(owner_packet_path)},
            error=owner_packet_error,
        ),
        _check(
            "staging_review_readable",
            staging_review_error is None,
            details={"staging_review_path": _display_path(staging_review_path)},
            error=staging_review_error,
        ),
        _check(
            "manifest_readable",
            manifest_error is None,
            details={"manifest_path": _display_path(manifest_path)},
            error=manifest_error,
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
            "owner_gate_present",
            owner_gated,
            details={"owner_packet_owner_gated": owner_packet.get("owner_gated"), "staging_review_owner_gated": staging_review.get("owner_gated")},
            error="owner gate is missing from packet or staging review",
        ),
        _check(
            "no_broad_stage_commands",
            not broad_commands,
            details={"broad_stage_commands": broad_commands},
            error="stage commands must be exact git add -- '<path>' commands",
        ),
        _check(
            "stage_commands_match_packet_paths",
            command_paths_match_packet,
            details={"parsed_stage_paths": parsed_stage_paths, "packet_stage_paths": packet_stage_paths},
            error="parsed stage command paths do not match owner packet stage_paths",
        ),
        _check(
            "packet_paths_match_staging_review",
            packet_paths_match_staging,
            details={"packet_stage_paths": packet_stage_paths, "staging_eligible_paths": staging_eligible_paths},
            error="owner packet stage_paths do not match staging review eligible paths",
        ),
        _check(
            "packet_paths_known_to_manifest",
            packet_paths_known_to_manifest,
            details={
                "packet_stage_paths": packet_stage_paths,
                "manifest_stage_path_count": len(manifest_stage_paths),
                "unknown_paths": sorted(set(packet_stage_paths).difference(manifest_stage_paths)),
            },
            error="owner packet contains paths outside the delivery manifest",
        ),
        _check(
            "no_protected_stage_paths",
            not protected_paths,
            details={"protected_stage_paths": protected_paths},
            error="stage commands include protected entrypoint, API, control-plane, agent-loop, or frontend paths",
        ),
        _check(
            "no_cached_staged_paths_before_owner_staging",
            not cached_paths,
            details={"cached_staged_paths": cached_paths},
            error="git index is not empty before owner-gated staging",
        ),
        _check(
            "no_blocked_stage_paths",
            int(staging_review.get("blocked_stage_count") or 0) == 0 and int(owner_packet.get("blocked_stage_count") or 0) == 0,
            details={
                "staging_review_blocked_stage_count": staging_review.get("blocked_stage_count"),
                "owner_packet_blocked_stage_count": owner_packet.get("blocked_stage_count"),
            },
            error="staging review or owner packet contains blocked paths",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="one or more staging reports claim full Codex parity",
        ),
        _check(
            "no_preflight_mutation",
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
    status = (
        "owner_staging_preflight_ready"
        if all(check.status == "passed" for check in checks)
        else "owner_staging_preflight_blocked"
    )
    return OwnerStagingPreflight(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_staging_preflight",
        owner_gated=True,
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
        stage_command_count=len(commands),
        stage_path_count=len(packet_stage_paths),
        manifest_stage_path_count=len(manifest_stage_paths),
        cached_staged_path_count=len(cached_paths),
        parsed_stage_paths=parsed_stage_paths,
        cached_staged_paths=cached_paths,
        protected_stage_paths=protected_paths,
        broad_stage_commands=broad_commands,
        checks=checks,
        next_actions=[
            "If this preflight is ready, the owner may run only the exact stage_commands from the owner staging packet.",
            "Regenerate manifest, staging review, owner packet, preflight, and task board after any handoff or worktree change.",
            "Run the owner packet verification commands after staging and before commit.",
        ],
        known_limits=[
            "This preflight is read-only except writing its evidence report.",
            "It does not run git add, commit, push, tests, agents, browser tasks, network calls, or secondary candidate code.",
            "It validates the current git index is empty before owner-gated staging begins.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_preflight(report: OwnerStagingPreflight) -> str:
    lines = [
        "# Commercial Delivery Owner Staging Preflight",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Owner gated: `{str(report.owner_gated).lower()}`",
        f"- Stage command count: `{report.stage_command_count}`",
        f"- Stage path count: `{report.stage_path_count}`",
        f"- Cached staged path count: `{report.cached_staged_path_count}`",
        f"- Full Codex parity claimed: `{str(report.full_codex_parity_claimed).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Parsed Stage Paths", ""])
    lines.extend(f"- `{path}`" for path in report.parsed_stage_paths)
    lines.append("")
    return "\n".join(lines)


def write_report(report: OwnerStagingPreflight, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_preflight(report: OwnerStagingPreflight, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_preflight(report), encoding="utf-8")


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
    report = build_owner_staging_preflight(
        owner_packet_path=args.owner_packet,
        staging_review_path=args.staging_review,
        manifest_path=args.manifest,
    )
    write_report(report, args.output)
    write_markdown_preflight(report, args.markdown_output)
    print(f"Commercial delivery owner staging preflight status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Stage commands: {report.stage_command_count}")
    print(f"Cached staged paths: {report.cached_staged_path_count}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "owner_staging_preflight_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
