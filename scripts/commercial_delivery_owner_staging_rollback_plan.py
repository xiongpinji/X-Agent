#!/usr/bin/env python3
"""Build a read-only rollback plan for owner-approved staging.

The plan converts the owner staging packet and post-staging evidence into
explicit ``git reset -- '<path>'`` commands that would unstage only the owner
packet paths. It never runs git reset, stages files, commits, pushes, calls
network services, executes tests, or runs agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_delivery_task_board import _display_path
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

DEFAULT_OWNER_STAGING_PACKET = REPORT_DIR / "commercial-delivery-owner-staging-packet.json"
DEFAULT_OWNER_STAGING_PREFLIGHT = REPORT_DIR / "commercial-delivery-owner-staging-preflight.json"
DEFAULT_OWNER_POST_STAGING_VERIFIER = REPORT_DIR / "commercial-delivery-owner-post-staging-verifier.json"
DEFAULT_OWNER_POST_STAGE_COMMIT_GATE = REPORT_DIR / "commercial-delivery-owner-post-stage-commit-gate.json"
DEFAULT_OWNER_COMMIT_PACKET = REPORT_DIR / "commercial-delivery-owner-commit-packet.json"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-delivery-owner-staging-rollback-plan.md"


@dataclass(frozen=True)
class OwnerStagingRollbackPlanCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class OwnerStagingRollbackPlan:
    status: str
    generated_at: str
    evidence_type: str
    owner_gated: bool
    mutation_performed: bool
    git_stage_performed: bool
    git_reset_performed: bool
    git_commit_performed: bool
    git_push_performed: bool
    network_mutation_performed: bool
    agent_execution_enabled: bool
    full_codex_parity_claimed: bool
    rollback_available: bool
    rollback_required: bool
    reset_command_count: int
    stage_path_digest: str | None
    reset_path_digest: str | None
    owner_packet_stage_path_digest: str | None
    rollback_commands: list[str]
    reports: dict[str, str]
    report_statuses: dict[str, str | None]
    summary: dict[str, Any]
    checks: list[OwnerStagingRollbackPlanCheck]
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


def _status(payload: dict[str, Any]) -> str | None:
    value = payload.get("status")
    return str(value) if value is not None else None


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("summary")
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).replace("\\", "/").strip() for item in value if str(item).strip()]


def _quote_path(path: str) -> str:
    return "'" + path.replace("'", "''") + "'"


def _reset_commands(paths: list[str]) -> list[str]:
    return [f"git reset -- {_quote_path(path)}" for path in paths]


def _digest_values(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _digest_path_set(values: list[str]) -> str | None:
    if not values:
        return None
    return _digest_values(sorted(set(values)))


def _digest_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return str(value) if isinstance(value, str) and value else None


def _check(
    name: str,
    passed: bool,
    *,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> OwnerStagingRollbackPlanCheck:
    return OwnerStagingRollbackPlanCheck(
        name=name,
        status="passed" if passed else "failed",
        details=details or {},
        error=None if passed else error,
    )


def _claims_parity(payloads: list[dict[str, Any]]) -> bool:
    return any(payload.get("full_codex_parity_claimed") is True for payload in payloads)


def _preflight_ready_or_post_staging_accounted_for(
    preflight: dict[str, Any],
    post_staging: dict[str, Any],
    stage_paths: list[str],
) -> bool:
    if _status(preflight) == "owner_staging_preflight_ready":
        return True
    if _status(preflight) != "owner_staging_preflight_blocked":
        return False
    cached_paths = _list(post_staging.get("cached_staged_paths"))
    return (
        _status(post_staging) == "owner_post_staging_verification_ready"
        and bool(stage_paths)
        and bool(cached_paths)
        and set(cached_paths) == set(stage_paths)
        and not _list(post_staging.get("unexpected_cached_paths"))
        and not _list(post_staging.get("protected_cached_paths"))
    )


def build_owner_staging_rollback_plan(
    *,
    owner_staging_packet_path: Path = DEFAULT_OWNER_STAGING_PACKET,
    owner_staging_preflight_path: Path = DEFAULT_OWNER_STAGING_PREFLIGHT,
    owner_post_staging_verifier_path: Path = DEFAULT_OWNER_POST_STAGING_VERIFIER,
    owner_post_stage_commit_gate_path: Path = DEFAULT_OWNER_POST_STAGE_COMMIT_GATE,
    owner_commit_packet_path: Path = DEFAULT_OWNER_COMMIT_PACKET,
) -> OwnerStagingRollbackPlan:
    report_paths = {
        "owner_staging_packet": owner_staging_packet_path,
        "owner_staging_preflight": owner_staging_preflight_path,
        "owner_post_staging_verifier": owner_post_staging_verifier_path,
        "owner_post_stage_commit_gate": owner_post_stage_commit_gate_path,
        "owner_commit_packet": owner_commit_packet_path,
    }
    reports: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for name, path in report_paths.items():
        payload, error = _read_json(path)
        reports[name] = payload
        if error:
            errors[name] = error

    staging_packet = reports["owner_staging_packet"]
    preflight = reports["owner_staging_preflight"]
    post_staging = reports["owner_post_staging_verifier"]
    commit_gate = reports["owner_post_stage_commit_gate"]
    commit_packet = reports["owner_commit_packet"]
    stage_paths = _list(staging_packet.get("stage_paths"))
    cached_paths = _list(post_staging.get("cached_staged_paths"))
    cached_path_count = int(post_staging.get("cached_staged_path_count") or 0)
    reset_paths = cached_paths if cached_paths else stage_paths
    stage_path_digest = _digest_values(stage_paths) if stage_paths else None
    reset_path_digest = _digest_values(reset_paths) if reset_paths else None
    reset_path_set_digest = _digest_path_set(reset_paths)
    owner_packet_stage_path_digest = _digest_field(staging_packet, "stage_path_digest")
    verifier_cached_path_set_digest = _digest_field(post_staging, "cached_staged_path_set_digest")
    unexpected_cached_paths = _list(post_staging.get("unexpected_cached_paths"))
    protected_cached_paths = _list(post_staging.get("protected_cached_paths"))
    rollback_required = (
        cached_path_count > 0
        and (
            _status(post_staging) != "owner_post_staging_verification_ready"
            or _status(commit_gate) != "owner_post_stage_commit_gate_ready"
            or _status(commit_packet) != "owner_commit_packet_ready"
        )
    )
    full_codex_parity_claimed = _claims_parity(list(reports.values()))
    owner_gated = staging_packet.get("owner_gated") is True and preflight.get("owner_gated") is True
    preflight_accounted_for = _preflight_ready_or_post_staging_accounted_for(
        preflight,
        post_staging,
        stage_paths,
    )

    commands = _reset_commands(reset_paths)
    checks = [
        _check(
            "reports_readable",
            not errors,
            details={"errors": errors},
            error="one or more rollback plan inputs are missing or unreadable",
        ),
        _check(
            "owner_staging_packet_ready",
            _status(staging_packet) == "owner_staging_packet_ready",
            details={"status": _status(staging_packet)},
            error="owner staging packet is not ready",
        ),
        _check(
            "owner_staging_preflight_accounted_for",
            preflight_accounted_for,
            details={
                "status": _status(preflight),
                "cached_staged_path_count": preflight.get("cached_staged_path_count"),
                "owner_post_staging_verifier_status": _status(post_staging),
                "post_staging_cached_staged_path_count": cached_path_count,
                "post_staging_cached_paths_match_owner_packet": bool(stage_paths)
                and set(cached_paths) == set(stage_paths),
            },
            error="owner staging preflight is not ready or accounted for by post-staging evidence",
        ),
        _check(
            "rollback_paths_known",
            bool(stage_paths) and set(reset_paths) == set(stage_paths),
            details={
                "stage_path_count": len(stage_paths),
                "reset_path_count": len(reset_paths),
                "missing_reset_paths": sorted(set(stage_paths).difference(reset_paths)),
                "unexpected_reset_paths": sorted(set(reset_paths).difference(stage_paths)),
            },
            error="rollback reset paths are missing or do not exactly match the owner staging packet",
        ),
        _check(
            "rollback_path_digest_matches_owner_packet",
            owner_packet_stage_path_digest is not None
            and stage_path_digest is not None
            and reset_path_digest is not None
            and stage_path_digest == owner_packet_stage_path_digest
            and (
                not cached_paths
                or reset_path_digest == owner_packet_stage_path_digest
                or (
                    reset_path_set_digest is not None
                    and verifier_cached_path_set_digest is not None
                    and reset_path_set_digest == verifier_cached_path_set_digest
                )
            ),
            details={
                "stage_path_digest": stage_path_digest,
                "reset_path_digest": reset_path_digest,
                "reset_path_set_digest": reset_path_set_digest,
                "owner_packet_stage_path_digest": owner_packet_stage_path_digest,
                "verifier_cached_staged_path_set_digest": verifier_cached_path_set_digest,
            },
            error="rollback path digest does not match owner staging packet path digest",
        ),
        _check(
            "no_unexpected_cached_paths",
            not unexpected_cached_paths,
            details={"unexpected_cached_paths": unexpected_cached_paths},
            error="cached index contains paths outside the owner staging packet",
        ),
        _check(
            "no_protected_cached_paths",
            not protected_cached_paths,
            details={"protected_cached_paths": protected_cached_paths},
            error="cached index contains protected entrypoint or UI paths",
        ),
        _check(
            "commit_not_already_allowed_when_rollback_required",
            not rollback_required or commit_packet.get("commit_allowed") is not True,
            details={
                "rollback_required": rollback_required,
                "owner_commit_packet_status": _status(commit_packet),
                "commit_allowed": commit_packet.get("commit_allowed"),
            },
            error="rollback is marked required while commit packet already allows commit",
        ),
        _check(
            "no_full_codex_parity_claim",
            not full_codex_parity_claimed,
            details={"full_codex_parity_claimed": full_codex_parity_claimed},
            error="rollback plan inputs claim full Codex parity",
        ),
        _check(
            "no_rollback_plan_mutation",
            True,
            details={
                "mutation_performed": False,
                "git_stage_performed": False,
                "git_reset_performed": False,
                "git_commit_performed": False,
                "git_push_performed": False,
                "network_mutation_performed": False,
                "agent_execution_enabled": False,
            },
        ),
    ]
    ready = all(check.status == "passed" for check in checks)
    status = "owner_staging_rollback_plan_ready" if ready else "owner_staging_rollback_plan_blocked"

    return OwnerStagingRollbackPlan(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_delivery_owner_staging_rollback_plan",
        owner_gated=owner_gated,
        mutation_performed=False,
        git_stage_performed=False,
        git_reset_performed=False,
        git_commit_performed=False,
        git_push_performed=False,
        network_mutation_performed=False,
        agent_execution_enabled=False,
        full_codex_parity_claimed=full_codex_parity_claimed,
        rollback_available=ready and bool(commands),
        rollback_required=rollback_required,
        reset_command_count=len(commands),
        stage_path_digest=stage_path_digest,
        reset_path_digest=reset_path_digest,
        owner_packet_stage_path_digest=owner_packet_stage_path_digest,
        rollback_commands=commands,
        reports={name: _display_path(path) for name, path in report_paths.items()},
        report_statuses={name: _status(payload) for name, payload in reports.items()},
        summary={
            "stage_path_count": len(stage_paths),
            "cached_staged_path_count": cached_path_count,
            "reset_path_count": len(reset_paths),
            "stage_path_digest": stage_path_digest,
            "reset_path_digest": reset_path_digest,
            "reset_path_set_digest": reset_path_set_digest,
            "owner_packet_stage_path_digest": owner_packet_stage_path_digest,
            "verifier_cached_staged_path_set_digest": verifier_cached_path_set_digest,
            "owner_post_staging_verifier_status": _status(post_staging),
            "owner_post_stage_commit_gate_status": _status(commit_gate),
            "owner_commit_packet_status": _status(commit_packet),
            "commit_allowed": commit_packet.get("commit_allowed"),
            "preflight_cached_staged_path_count": preflight.get("cached_staged_path_count"),
            "owner_staging_preflight_accounted_for": preflight_accounted_for,
        },
        checks=checks,
        next_actions=[
            "Use this plan only if owner-approved staging has occurred and post-stage gates fail.",
            "Run only the explicit rollback_commands; never use broad git reset commands.",
            "After rollback, rerun owner staging preflight and the commercial delivery refresh chain.",
            "Do not commit after rollback until post-stage verifier, commit gate, and commit packet are regenerated.",
        ],
        known_limits=[
            "This plan is read-only except writing local evidence files.",
            "It does not run git reset, stage, commit, push, call network services, run tests, or execute agents.",
            "It only plans reset commands for explicit owner staging packet paths.",
            "It does not claim full Codex parity.",
        ],
    )


def render_markdown_plan(plan: OwnerStagingRollbackPlan) -> str:
    lines = [
        "# Commercial Delivery Owner Staging Rollback Plan",
        "",
        f"- Status: `{plan.status}`",
        f"- Generated at: `{plan.generated_at}`",
        f"- Rollback available: `{str(plan.rollback_available).lower()}`",
        f"- Rollback required: `{str(plan.rollback_required).lower()}`",
        f"- Reset command count: `{plan.reset_command_count}`",
        f"- Stage path digest: `{plan.stage_path_digest or '<missing>'}`",
        f"- Reset path digest: `{plan.reset_path_digest or '<missing>'}`",
        "",
        "## Checks",
        "",
    ]
    for check in plan.checks:
        lines.append(f"- `{check.name}`: `{check.status}`")
        if check.error:
            lines.append(f"  - Error: {check.error}")
    lines.extend(["", "## Rollback Commands", ""])
    if plan.rollback_commands:
        lines.extend(f"- `{command}`" for command in plan.rollback_commands)
    else:
        lines.append("- No rollback commands are available.")
    lines.extend(["", "## Next Actions", ""])
    lines.extend(f"- {action}" for action in plan.next_actions)
    lines.append("")
    return "\n".join(lines)


def write_report(plan: OwnerStagingRollbackPlan, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_plan(plan: OwnerStagingRollbackPlan, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_plan(plan), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-staging-packet", type=Path, default=DEFAULT_OWNER_STAGING_PACKET)
    parser.add_argument("--owner-staging-preflight", type=Path, default=DEFAULT_OWNER_STAGING_PREFLIGHT)
    parser.add_argument("--owner-post-staging-verifier", type=Path, default=DEFAULT_OWNER_POST_STAGING_VERIFIER)
    parser.add_argument("--owner-post-stage-commit-gate", type=Path, default=DEFAULT_OWNER_POST_STAGE_COMMIT_GATE)
    parser.add_argument("--owner-commit-packet", type=Path, default=DEFAULT_OWNER_COMMIT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = build_owner_staging_rollback_plan(
        owner_staging_packet_path=args.owner_staging_packet,
        owner_staging_preflight_path=args.owner_staging_preflight,
        owner_post_staging_verifier_path=args.owner_post_staging_verifier,
        owner_post_stage_commit_gate_path=args.owner_post_stage_commit_gate,
        owner_commit_packet_path=args.owner_commit_packet,
    )
    write_report(plan, args.output)
    write_markdown_plan(plan, args.markdown_output)
    print(f"Commercial delivery owner staging rollback plan status: {plan.status}")
    print(f"Report written to {args.output}")
    print(f"Markdown written to {args.markdown_output}")
    print(f"Rollback available: {plan.rollback_available}")
    print(f"Rollback required: {plan.rollback_required}")
    print(f"Reset command count: {plan.reset_command_count}")
    for check in plan.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if plan.status == "owner_staging_rollback_plan_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
