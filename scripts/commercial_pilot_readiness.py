#!/usr/bin/env python3
"""Summarize post-RC commercial pilot readiness.

This script is intentionally separate from the commercial RC gates. The RC
delivery report proves the selected release candidate; this report tracks the
next productization milestone without overwriting RC evidence or claiming full
Codex parity.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-readiness.json"
DEFAULT_RC_DELIVERY_REPORT = REPORT_DIR / "rc-delivery-status.json"
DEFAULT_CONTROL_PLANE_DOC = ROOT / "docs" / "specs" / "xagent-control-plane-protocol.md"
DEFAULT_PILOT_DOC = ROOT / "docs" / "COMMERCIAL_PILOT_READINESS.md"
DEFAULT_CODEX_ALIGNMENT_PLAN = (
    ROOT / "docs" / "superpowers" / "plans" / "2026-06-08-codex-aligned-commercial-delivery.md"
)

READY_STATUSES = {"passed", "ready", "commercial_rc_ready", "pilot_ready", "ready_for_rc_tag"}
PENDING_STATUSES = {
    "action_required",
    "pending",
    "pilot_pending",
    "owner_finalize_pending",
    "tag_action_required",
    "ready_with_owner_gates",
}
FAILED_STATUSES = {"failed", "error", "blocked", "pilot_blocked"}


@dataclass(frozen=True)
class PilotCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class PilotReadinessReport:
    status: str
    generated_at: str
    rc_tag: str | None
    rc_commit: str | None
    pilot_channel: str
    rc_delivery_report_path: str
    full_codex_parity_claimed: bool
    checks: list[PilotCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"report not found: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read report {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"report is not a JSON object: {path}"
    return payload, None


def _doc_check(*, name: str, path: Path, required_terms: list[str]) -> PilotCheck:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PilotCheck(name=name, status="action_required", details={"path": str(path)}, error="document is missing")
    except OSError as exc:
        return PilotCheck(
            name=name,
            status="failed",
            details={"path": str(path)},
            error=f"could not read document: {exc}",
        )
    missing_terms = [term for term in required_terms if term not in text]
    if missing_terms:
        return PilotCheck(
            name=name,
            status="action_required",
            details={"path": str(path), "missing_terms": missing_terms},
            error="document exists but does not contain required commercial pilot terms",
        )
    return PilotCheck(
        name=name,
        status="passed",
        details={"path": str(path), "required_terms": required_terms},
    )


def _rc_delivery_check(path: Path, expected_rc_tag: str | None, expected_rc_commit: str | None) -> PilotCheck:
    payload, error = _read_json(path)
    if error or payload is None:
        return PilotCheck(
            name="rc_delivery_status",
            status="failed",
            details={"path": str(path)},
            error=error or "RC delivery report is missing",
        )

    status = str(payload.get("status", ""))
    report_tag = payload.get("tag_name")
    report_commit = payload.get("expected_commit_sha")
    details = {
        "path": str(path),
        "status": status,
        "tag_name": report_tag,
        "expected_commit_sha": report_commit,
    }
    if status != "commercial_rc_ready":
        return PilotCheck(
            name="rc_delivery_status",
            status="failed" if status in FAILED_STATUSES else "action_required",
            details=details,
            error="RC delivery report is not commercial_rc_ready",
        )
    if expected_rc_tag and report_tag != expected_rc_tag:
        return PilotCheck(
            name="rc_delivery_status",
            status="failed",
            details=details | {"expected_rc_tag": expected_rc_tag},
            error="RC delivery tag does not match expected pilot baseline",
        )
    if expected_rc_commit and report_commit != expected_rc_commit:
        return PilotCheck(
            name="rc_delivery_status",
            status="failed",
            details=details | {"expected_rc_commit": expected_rc_commit},
            error="RC delivery commit does not match expected pilot baseline",
        )
    return PilotCheck(name="rc_delivery_status", status="passed", details=details)


def _status_from_evidence_payload(payload: dict[str, Any]) -> tuple[str, str | None]:
    status = str(payload.get("status", "")).strip()
    if status in READY_STATUSES:
        return "passed", None
    if status in FAILED_STATUSES:
        return "failed", f"evidence status is {status}"
    if status in PENDING_STATUSES:
        return "action_required", f"evidence status is {status}"

    checks = payload.get("checks")
    if isinstance(checks, list) and checks:
        statuses = [str(item.get("status", "")) for item in checks if isinstance(item, dict)]
        if statuses and all(item in READY_STATUSES for item in statuses):
            return "passed", None
        if any(item in FAILED_STATUSES for item in statuses):
            return "failed", f"one or more nested checks failed: {statuses}"
        return "action_required", f"nested checks are not all passed: {statuses}"

    return "action_required", "evidence status is missing or not recognized"


def _evidence_check(*, name: str, path: Path | None, command_hint: str) -> PilotCheck:
    if path is None:
        return PilotCheck(
            name=name,
            status="action_required",
            details={"command_hint": command_hint},
            error="pilot evidence report was not provided",
        )
    payload, error = _read_json(path)
    if error or payload is None:
        return PilotCheck(
            name=name,
            status="action_required",
            details={"path": str(path), "command_hint": command_hint},
            error=error or "pilot evidence report could not be read",
        )
    status, status_error = _status_from_evidence_payload(payload)
    return PilotCheck(
        name=name,
        status=status,
        details={
            "path": str(path),
            "source_status": payload.get("status"),
            "command_hint": command_hint,
        },
        error=status_error,
    )


def _overall_status(checks: list[PilotCheck]) -> str:
    statuses = [check.status for check in checks]
    if any(status == "failed" for status in statuses):
        return "pilot_blocked"
    if all(status == "passed" for status in statuses):
        return "pilot_ready"
    return "pilot_pending"


def _next_commands(checks: list[PilotCheck], output_path: Path) -> list[str]:
    commands: list[str] = []
    pending = {check.name for check in checks if check.status != "passed"}
    if "rc_delivery_status" in pending:
        commands.append("Rerun scripts\\rc_delivery_status.py for the selected RC tag and commit.")
    if "core_entrypoints" in pending:
        commands.append(
            "python scripts\\commercial_pilot_core_entrypoints.py"
        )
    if "workbench_thread_loop" in pending:
        commands.append("python scripts\\commercial_pilot_workbench_thread.py")
    if "pilot_channel_loop" in pending:
        commands.append("python scripts\\commercial_pilot_channel_loop.py")
    if "skill_governance" in pending:
        commands.append(
            "python scripts\\commercial_pilot_skill_governance.py"
        )
    if "approval_audit" in pending:
        commands.append("python scripts\\commercial_pilot_approval_audit.py")
    commands.append(f"Review {output_path} before making any commercial pilot claim.")
    return commands


def build_pilot_readiness_report(
    *,
    rc_delivery_report_path: Path = DEFAULT_RC_DELIVERY_REPORT,
    output_path: Path = DEFAULT_OUTPUT,
    rc_tag: str | None = None,
    rc_commit: str | None = None,
    pilot_channel: str = "feishu",
    control_plane_doc_path: Path = DEFAULT_CONTROL_PLANE_DOC,
    commercial_pilot_doc_path: Path = DEFAULT_PILOT_DOC,
    codex_alignment_plan_path: Path = DEFAULT_CODEX_ALIGNMENT_PLAN,
    core_entrypoints_report_path: Path | None = None,
    workbench_thread_report_path: Path | None = None,
    pilot_channel_report_path: Path | None = None,
    skill_governance_report_path: Path | None = None,
    approval_audit_report_path: Path | None = None,
) -> PilotReadinessReport:
    checks = [
        _rc_delivery_check(rc_delivery_report_path, rc_tag, rc_commit),
        _doc_check(
            name="control_plane_protocol",
            path=control_plane_doc_path,
            required_terms=["thread/start", "approval/list", "mcp/tool/call", "runtime/rc/status"],
        ),
        _doc_check(
            name="commercial_pilot_readiness_doc",
            path=commercial_pilot_doc_path,
            required_terms=["30-Minute Setup Path", "Rollback", "Known Limits", "Pilot Evidence Template"],
        ),
        _doc_check(
            name="codex_alignment_plan",
            path=codex_alignment_plan_path,
            required_terms=["Definition Of Done", "Workstreams", "full Codex parity"],
        ),
        _evidence_check(
            name="core_entrypoints",
            path=core_entrypoints_report_path,
            command_hint="tests/test_first_release_entrypoints.py tests/test_security.py",
        ),
        _evidence_check(
            name="workbench_thread_loop",
            path=workbench_thread_report_path,
            command_hint="Workbench thread-loop smoke report",
        ),
        _evidence_check(
            name="pilot_channel_loop",
            path=pilot_channel_report_path,
            command_hint=f"{pilot_channel} channel loop evidence report",
        ),
        _evidence_check(
            name="skill_governance",
            path=skill_governance_report_path,
            command_hint="Skill Curator governance tests/report",
        ),
        _evidence_check(
            name="approval_audit",
            path=approval_audit_report_path,
            command_hint="Unified approval/audit pilot smoke report",
        ),
    ]
    rc_payload, _ = _read_json(rc_delivery_report_path)
    resolved_rc_tag = rc_tag or (str(rc_payload.get("tag_name")) if rc_payload and rc_payload.get("tag_name") else None)
    resolved_rc_commit = rc_commit or (
        str(rc_payload.get("expected_commit_sha")) if rc_payload and rc_payload.get("expected_commit_sha") else None
    )
    known_limits = [
        "Commercial pilot readiness is separate from commercial RC readiness.",
        "Full Codex parity is not claimed by this report.",
        "Pilot evidence reports must be generated separately from RC evidence.",
        "External provider and channel checks remain owner-gated when real credentials are required.",
    ]
    return PilotReadinessReport(
        status=_overall_status(checks),
        generated_at=_utc_now(),
        rc_tag=resolved_rc_tag,
        rc_commit=resolved_rc_commit,
        pilot_channel=pilot_channel,
        rc_delivery_report_path=str(rc_delivery_report_path),
        full_codex_parity_claimed=False,
        checks=checks,
        next_commands=_next_commands(checks, output_path),
        known_limits=known_limits,
    )


def write_report(report: PilotReadinessReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rc-delivery-report", type=Path, default=DEFAULT_RC_DELIVERY_REPORT)
    parser.add_argument("--rc-tag", default=None)
    parser.add_argument("--rc-commit", default=None)
    parser.add_argument("--pilot-channel", default="feishu")
    parser.add_argument("--control-plane-doc", type=Path, default=DEFAULT_CONTROL_PLANE_DOC)
    parser.add_argument("--commercial-pilot-doc", type=Path, default=DEFAULT_PILOT_DOC)
    parser.add_argument("--codex-alignment-plan", type=Path, default=DEFAULT_CODEX_ALIGNMENT_PLAN)
    parser.add_argument("--core-entrypoints-report", type=Path, default=None)
    parser.add_argument("--workbench-thread-report", type=Path, default=None)
    parser.add_argument("--pilot-channel-report", type=Path, default=None)
    parser.add_argument("--skill-governance-report", type=Path, default=None)
    parser.add_argument("--approval-audit-report", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_pilot_readiness_report(
        rc_delivery_report_path=args.rc_delivery_report,
        output_path=args.output,
        rc_tag=args.rc_tag,
        rc_commit=args.rc_commit,
        pilot_channel=args.pilot_channel,
        control_plane_doc_path=args.control_plane_doc,
        commercial_pilot_doc_path=args.commercial_pilot_doc,
        codex_alignment_plan_path=args.codex_alignment_plan,
        core_entrypoints_report_path=args.core_entrypoints_report,
        workbench_thread_report_path=args.workbench_thread_report,
        pilot_channel_report_path=args.pilot_channel_report,
        skill_governance_report_path=args.skill_governance_report,
        approval_audit_report_path=args.approval_audit_report,
    )
    write_report(report, args.output)
    print(f"Commercial pilot readiness status: {report.status}")
    print(f"RC tag: {report.rc_tag or '<unresolved>'}")
    print(f"RC commit: {report.rc_commit or '<unresolved>'}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "pilot_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
