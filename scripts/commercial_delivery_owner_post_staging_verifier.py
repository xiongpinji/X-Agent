#!/usr/bin/env python3
"""Verify owner-gated staged paths after explicit staging commands.

This report is the read-only companion to the owner staging preflight. The
preflight expects an empty git index before staging; this verifier expects the
cached index to contain exactly the owner packet stage paths after the owner has
run the explicit ``git add -- '<path>'`` commands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_OWNER_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_STAGING_REVIEW = REPORT_DIR / "commercial-delivery-staging-review.json"
DEFAULT_MANIFEST = REPORT_DIR / "original-kernel-delivery-manifest.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.md"

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
class OwnerPostStagingCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerPostStagingVerification:
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
    expected_stage_path_count: int
    cached_staged_path_count: int
    stage_path_digest: str | None
    stage_command_digest: str | None
    expected_stage_path_set_digest: str | None
    cached_staged_path_set_digest: str | None
    cached_staged_paths: list[str]
    missing_cached_paths: list[str]
    unexpected_cached_paths: list[str]
    protected_cached_paths: list[str]
    summary: dict[str, Any]
    checks: list[OwnerPostStagingCheck]
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
) -> OwnerPostStagingCheck:
    return OwnerPostStagingCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _failed_check_names(checks: list[OwnerPostStagingCheck]) -> list[str]:
    return [check.name for check in checks if check.status != "passed"]


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


def _stage_commands_from_packet(packet: dict[str, Any]) -> list[str]:
    values = packet.get("stage_commands")
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _stage_paths_from_staging_review(staging_review: dict[str, Any]) -> list[str]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    paths: list[str] = []
    for item in rows:
        if isinstance(item, dict) and item.get("status") == "eligible" and item.get("path"):
            paths.append(_normalize_path(str(item["path"])))
    return paths


def _stage_paths_by_status(staging_review: dict[str, Any], status: str) -> list[str]:
    rows = staging_review.get("paths")
    if not isinstance(rows, list):
        return []
    paths: list[str] = []
    for item in rows:
        if isinstance(item, dict) and item.get("status") == status and item.get("path"):
            paths.append(_normalize_path(str(item["path"])))
    return paths


def _stage_paths_from_manifest(manifest: dict[str, Any]) -> list[str]:
    values = manifest.get("stage_include_paths")
    if not isinstance(values, list):
        return []
    return [_normalize_path(str(value)) for value in values if str(value).strip()]


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


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _path_set_digest(paths: list[str]) -> str | None:
    return _digest_values(sorted(set(paths))) if paths else None


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value) if isinstance(value, str) and value else None


def _int_field(payload: dict[str, Any], field: str) -> int:
    try:
        return int(payload.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def _post_commit_noop_accounted_for(
    *,
    owner_packet: dict[str, Any],
    staging_review: dict[str, Any],
    manifest: dict[str, Any],
    packet_stage_paths: list[str],
    packet_stage_commands: list[str],
    cached_paths: list[str],
) -> bool:
    packet_summary = owner_packet.get("summary")
    packet_summary = packet_summary if isinstance(packet_summary, dict) else {}
    manifest_stage_paths = _stage_paths_from_manifest(manifest)
    unchanged_paths = _stage_paths_by_status(staging_review, "unchanged")
    manifest_stage_count = _int_field(manifest, "stage_include_count") or len(manifest_stage_paths)
    staging_stage_count = _int_field(staging_review, "stage_include_count")
    return (
        packet_summary.get("post_commit_noop_accounted_for") is True
        and _status(owner_packet) == "owner_staging_packet_ready"
        and _status(staging_review) == "staging_review_ready"
        and _status(manifest) == "original_kernel_delivery_manifest_ready"
        and owner_packet.get("owner_gated") is True
        and staging_review.get("owner_gated") is True
        and not packet_stage_paths
        and not packet_stage_commands
        and not cached_paths
        and _int_field(owner_packet, "blocked_stage_count") == 0
        and _int_field(staging_review, "blocked_stage_count") == 0
        and _int_field(owner_packet, "eligible_stage_count") == 0
        and _int_field(staging_review, "eligible_stage_count") == 0
        and manifest_stage_count > 0
        and staging_stage_count == manifest_stage_count
        and len(unchanged_paths) == manifest_stage_count
    )


def build_owner_post_staging_verification(
    *,
    owner_packet_path: Path = DEFAULT_OWNER_PACKET,
    staging_review_path: Path = DEFAULT_STAGING_REVIEW,
    manifest_path: Path = DEFAULT_MANIFEST,
    cached_diff_lines: Sequence[str] | None = None,
) -> OwnerPostStagingVerification:
    owner_packet, owner_packet_error = _read_json(owner_packet_path)
    staging_review, staging_review_error = _read_json(staging_review_path)
    manifest, manifest_error = _read_json(manifest_path)

    packet_stage_paths = _stage_paths_from_packet(owner_packet)
    packet_stage_commands = _stage_commands_from_packet(owner_packet)
    staging_eligible_paths = _stage_paths_from_staging_review(staging_review)
    manifest_stage_paths = _stage_paths_from_manifest(manifest)
    cached_paths = _cached_paths(cached_diff_lines if cached_diff_lines is not None else _git_cached_diff_lines())
    post_commit_noop_accounted_for = _post_commit_noop_accounted_for(
        owner_packet=owner_packet,
        staging_review=staging_review,
        manifest=manifest,
        packet_stage_paths=packet_stage_paths,
        packet_stage_commands=packet_stage_commands,
        cached_paths=cached_paths,
    )
    stage_path_digest = _digest_values(packet_stage_paths) if packet_stage_paths or post_commit_noop_accounted_for else None
    stage_command_digest = _digest_values(packet_stage_commands) if packet_stage_commands or post_commit_noop_accounted_for else None
    packet_stage_path_digest = _digest_field(owner_packet, "stage_path_digest")
    packet_stage_command_digest = _digest_field(owner_packet, "stage_command_digest")
    packet_summary = owner_packet.get("summary")
    packet_summary = packet_summary if isinstance(packet_summary, dict) else {}
    expected_stage_path_set_digest = (
        _digest_values([]) if post_commit_noop_accounted_for else _path_set_digest(packet_stage_paths)
    )
    cached_staged_path_set_digest = _digest_values([]) if post_commit_noop_accounted_for else _path_set_digest(cached_paths)

    missing_cached_paths = sorted(set(packet_stage_paths).difference(cached_paths))
    unexpected_cached_paths = sorted(set(cached_paths).difference(packet_stage_paths))
    protected_cached_paths = sorted(path for path in cached_paths if _is_protected(path))
    full_codex_parity_claimed = (
        owner_packet.get("full_codex_parity_claimed") is True
        or staging_review.get("full_codex_parity_claimed") is True
        or manifest.get("full_codex_parity_claimed") is True
    )
    owner_gated = owner_packet.get("owner_gated") is True and staging_review.get("owner_gated") is True
    exact_match = cached_paths == sorted(packet_stage_paths)

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
            details={
                "owner_packet_owner_gated": owner_packet.get("owner_gated"),
                "staging_review_owner_gated": staging_review.get("owner_gated"),
            },
            error="owner gate is missing from packet or staging review",
        ),
        _check(
            "packet_paths_match_staging_review",
            packet_stage_paths == staging_eligible_paths,
            details={"packet_stage_paths": packet_stage_paths, "staging_eligible_paths": staging_eligible_paths},
            error="owner packet stage_paths do not match staging review eligible paths",
        ),
        _check(
            "packet_paths_known_to_manifest",
            set(packet_stage_paths).issubset(set(manifest_stage_paths)),
            details={
                "packet_stage_paths": packet_stage_paths,
                "manifest_stage_path_count": len(manifest_stage_paths),
                "unknown_paths": sorted(set(packet_stage_paths).difference(manifest_stage_paths)),
            },
            error="owner packet contains paths outside the delivery manifest",
        ),
        _check(
            "packet_stage_path_digest_matches_stage_paths",
            (post_commit_noop_accounted_for and packet_stage_path_digest == stage_path_digest)
            or (stage_path_digest is not None and packet_stage_path_digest == stage_path_digest),
            details={
                "computed_stage_path_digest": stage_path_digest,
                "packet_stage_path_digest": packet_stage_path_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner packet stage_path_digest does not match its ordered stage_paths",
        ),
        _check(
            "packet_stage_command_digest_matches_stage_commands",
            (post_commit_noop_accounted_for and packet_stage_command_digest == stage_command_digest)
            or (stage_command_digest is not None and packet_stage_command_digest == stage_command_digest),
            details={
                "computed_stage_command_digest": stage_command_digest,
                "packet_stage_command_digest": packet_stage_command_digest,
                "stage_command_count": len(packet_stage_commands),
                "stage_path_count": len(packet_stage_paths),
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="owner packet stage_command_digest does not match its ordered stage_commands",
        ),
        _check(
            "cached_paths_present_after_owner_staging",
            bool(cached_paths) or post_commit_noop_accounted_for,
            details={
                "cached_staged_path_count": len(cached_paths),
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="git index is empty; owner staging commands have not been applied",
        ),
        _check(
            "cached_paths_match_owner_packet",
            exact_match,
            details={
                "expected_stage_path_count": len(packet_stage_paths),
                "cached_staged_path_count": len(cached_paths),
                "missing_cached_paths": missing_cached_paths,
                "unexpected_cached_paths": unexpected_cached_paths,
            },
            error="cached staged paths do not exactly match the owner staging packet",
        ),
        _check(
            "cached_path_set_digest_matches_expected_paths",
            expected_stage_path_set_digest is not None
            and cached_staged_path_set_digest == expected_stage_path_set_digest,
            details={
                "expected_stage_path_set_digest": expected_stage_path_set_digest,
                "cached_staged_path_set_digest": cached_staged_path_set_digest,
                "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            },
            error="cached staged path set digest does not match the owner staging packet",
        ),
        _check(
            "no_protected_cached_paths",
            not protected_cached_paths,
            details={"protected_cached_paths": protected_cached_paths},
            error="cached staged paths include protected entrypoint, API, control-plane, agent-loop, or frontend paths",
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
            "no_post_staging_verifier_mutation",
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
    ready = all(check.status == "passed" for check in checks)
    status = "owner_post_staging_verification_ready" if ready else "owner_post_staging_verification_blocked"
    blocking_reasons = _failed_check_names(checks)
    return OwnerPostStagingVerification(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_post_staging_verification",
        owner_gated=True,
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
        expected_stage_path_count=len(packet_stage_paths),
        cached_staged_path_count=len(cached_paths),
        stage_path_digest=stage_path_digest,
        stage_command_digest=stage_command_digest,
        expected_stage_path_set_digest=expected_stage_path_set_digest,
        cached_staged_path_set_digest=cached_staged_path_set_digest,
        cached_staged_paths=cached_paths,
        missing_cached_paths=missing_cached_paths,
        unexpected_cached_paths=unexpected_cached_paths,
        protected_cached_paths=protected_cached_paths,
        summary={
            "blocking_reasons": blocking_reasons,
            "owner_action_required": not ready,
            "post_commit_noop_accounted_for": post_commit_noop_accounted_for,
            "secondary_pending_count": packet_summary.get("secondary_pending_count"),
            "secondary_handoff_next_count": packet_summary.get("secondary_handoff_next_count"),
            "secondary_handoff_next_queue": packet_summary.get("secondary_handoff_next_queue"),
            "secondary_handoff_completed_count": packet_summary.get("secondary_handoff_completed_count"),
            "secondary_handoff_latest_completed_candidate": packet_summary.get(
                "secondary_handoff_latest_completed_candidate"
            ),
            "expected_stage_path_count": len(packet_stage_paths),
            "cached_staged_path_count": len(cached_paths),
            "stage_path_digest": stage_path_digest,
            "stage_command_digest": stage_command_digest,
            "expected_stage_path_set_digest": expected_stage_path_set_digest,
            "cached_staged_path_set_digest": cached_staged_path_set_digest,
        },
        checks=checks,
        next_actions=[
            "Run this verifier after the owner applies the exact stage_commands from the owner staging packet.",
            "If ready, run the owner packet verification commands before commit.",
            "If blocked, reset only the incorrect staged paths after owner review; do not use broad reset commands without approval.",
        ],
        known_limits=[
            "This verifier is read-only except writing its evidence report.",
            "It does not run git add, reset, commit, push, tests, agents, browser tasks, network calls, or secondary candidate code.",
            "It validates only the cached path set, not staged file content.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_verification(report: OwnerPostStagingVerification) -> str:
    lines = [
        "# Commercial Delivery Owner Post-Staging Verification",
        "",
        f"- Status: `{report.status}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Owner gated: `{str(report.owner_gated).lower()}`",
        f"- Expected stage path count: `{report.expected_stage_path_count}`",
        f"- Cached staged path count: `{report.cached_staged_path_count}`",
        f"- Stage path digest: `{report.stage_path_digest or '<missing>'}`",
        f"- Stage command digest: `{report.stage_command_digest or '<missing>'}`",
        f"- Expected stage path set digest: `{report.expected_stage_path_set_digest or '<missing>'}`",
        f"- Cached staged path set digest: `{report.cached_staged_path_set_digest or '<missing>'}`",
        f"- Owner action required: `{str(report.summary.get('owner_action_required')).lower()}`",
        f"- Blocking reasons: `{', '.join(report.summary.get('blocking_reasons') or [])}`",
        f"- Secondary handoff next queue: `{', '.join(report.summary.get('secondary_handoff_next_queue') or [])}`",
        f"- Secondary handoff completed count: `{report.summary.get('secondary_handoff_completed_count')}`",
        f"- Secondary latest completed candidate: `{report.summary.get('secondary_handoff_latest_completed_candidate')}`",
        f"- Full Codex parity claimed: `{str(report.full_codex_parity_claimed).lower()}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Cached Staged Paths", ""])
    lines.extend(f"- `{path}`" for path in report.cached_staged_paths)
    lines.append("")
    return "\n".join(lines)


def write_report(report: OwnerPostStagingVerification, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_verification(report: OwnerPostStagingVerification, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_verification(report), encoding="utf-8")


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
    report = build_owner_post_staging_verification(
        owner_packet_path=args.owner_packet,
        staging_review_path=args.staging_review,
        manifest_path=args.manifest,
    )
    write_report(report, args.output)
    write_markdown_verification(report, args.markdown_output)
    print(f"Commercial delivery owner post-staging verification status: {report.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Expected stage paths: {report.expected_stage_path_count}")
    print(f"Cached staged paths: {report.cached_staged_path_count}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "owner_post_staging_verification_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
