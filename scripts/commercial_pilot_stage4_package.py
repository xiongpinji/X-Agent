#!/usr/bin/env python3
"""Generate the Stage 4 controlled pilot handoff package.

The package binds the current PR head to the existing Feishu Pilot V1 evidence
bundle. It is deliberately read-only: no deploys, tags, releases, customer
messages, or outbound channel calls are performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, ROOT, _utc_now

DEFAULT_STAGE2_REMOTE_REPORT = REPORT_DIR / "stage2-remote-ci-final-20260615.json"
DEFAULT_STAGE3_STATIC_REPORT = REPORT_DIR / "stage3-static-remediation-result-20260615.json"
DEFAULT_STAGE3_REMOTE_REPORT = REPORT_DIR / "stage3-remote-ci-final-20260615.json"
DEFAULT_FINAL_GATE_REPORT = REPORT_DIR / "commercial-pilot-final-gate.json"
DEFAULT_DELIVERY_RECEIPT_REPORT = REPORT_DIR / "commercial-pilot-delivery-receipt.json"
DEFAULT_ACCEPTANCE_GATE_REPORT = REPORT_DIR / "commercial-pilot-acceptance-gate.json"
DEFAULT_HANDOFF_INDEX_REPORT = REPORT_DIR / "commercial-pilot-handoff-index.json"
DEFAULT_CUSTOMER_ACCEPTANCE_PACK_REPORT = REPORT_DIR / "commercial-pilot-customer-acceptance-pack.json"
DEFAULT_OUTPUT = REPORT_DIR / "stage4-pilot-handoff-package-20260615.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "stage4-pilot-handoff-package-20260615.md"


@dataclass(frozen=True)
class Stage4Check:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class Stage4SourceReport:
    name: str
    path: str
    status: str | None
    sha256: str | None
    size_bytes: int | None
    error: str | None = None


@dataclass(frozen=True)
class Stage4PilotPackage:
    package_status: str
    generated_at: str
    evidence_type: str
    claim_boundary: dict[str, Any]
    version_identity: dict[str, Any]
    remote_pr_gate: dict[str, Any]
    stage3_static_remediation_gate: str
    real_staging_rehearsal_gate: str
    historical_pilot_identity: dict[str, Any]
    pilot_evidence_bundle: dict[str, Any]
    source_reports: list[Stage4SourceReport]
    checks: list[Stage4Check]
    owner_acceptance_checklist: list[str]
    customer_acceptance_checklist: list[str]
    known_limits: list[str]
    next_commands: list[str]
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_reports"] = [asdict(source) for source in self.source_reports]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


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


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"report not found: {path}"
    except OSError as exc:
        return None, None, f"could not read report {path}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def _source_report(
    name: str,
    path: Path,
    payload: dict[str, Any] | None,
    read_error: str | None,
) -> Stage4SourceReport:
    sha256, size_bytes, digest_error = _sha256_file(path)
    return Stage4SourceReport(
        name=name,
        path=str(path),
        status=payload.get("status") or payload.get("report") if payload else None,
        sha256=sha256,
        size_bytes=size_bytes,
        error=read_error or digest_error,
    )


def _git_value(args: Sequence[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
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


def _remote_pr_gate(remote_report: dict[str, Any] | None) -> dict[str, Any]:
    checks = remote_report.get("github_actions_check_runs") if remote_report else None
    pr = remote_report.get("pull_request") if remote_report else None
    if not isinstance(checks, dict):
        checks = {}
    if not isinstance(pr, dict):
        pr = {}
    failed = checks.get("failed")
    in_progress = checks.get("in_progress")
    return {
        "status": "passed" if failed == 0 and in_progress == 0 else "not_met",
        "head_sha": remote_report.get("head_sha") if remote_report else None,
        "remote_branch_sha": remote_report.get("remote_branch_sha") if remote_report else None,
        "pull_request": {
            "number": pr.get("number"),
            "url": pr.get("url"),
            "state": pr.get("state"),
            "draft": pr.get("draft"),
            "mergeable_state": pr.get("mergeable_state"),
            "title": pr.get("title") or pr.get("title_after_correction"),
        },
        "check_runs": {
            "total_count": checks.get("total_count"),
            "completed_success": checks.get("completed_success"),
            "completed_skipped": checks.get("completed_skipped"),
            "failed": failed,
            "in_progress": in_progress,
            "skipped_checks": checks.get("skipped_checks", []),
        },
    }


def _historical_pilot_identity(*payloads: dict[str, Any] | None) -> dict[str, Any]:
    keys = (
        "pilot_channel",
        "pilot_tag_name",
        "pilot_commit_sha",
        "rc_tag_name",
        "rc_commit_sha",
        "outbound_owner_gate_status",
    )
    identity: dict[str, Any] = {}
    for key in keys:
        for payload in payloads:
            if isinstance(payload, dict) and payload.get(key) is not None:
                identity[key] = payload[key]
                break
        else:
            identity[key] = None
    identity["identity_class"] = "historical_feishu_pilot_v1"
    identity["current_head_is_historical_pilot_commit"] = False
    return identity


def _pilot_evidence_bundle(
    *,
    final_gate: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    acceptance: dict[str, Any] | None,
    handoff_index: dict[str, Any] | None,
    customer_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "final_gate_status": final_gate.get("status") if final_gate else None,
        "delivery_receipt_status": receipt.get("status") if receipt else None,
        "acceptance_gate_status": acceptance.get("status") if acceptance else None,
        "handoff_index_status": handoff_index.get("status") if handoff_index else None,
        "customer_acceptance_pack_status": customer_pack.get("status") if customer_pack else None,
        "pilot_channel": customer_pack.get("pilot_channel") if customer_pack else None,
        "outbound_owner_gate_status": (
            customer_pack.get("outbound_owner_gate_status") if customer_pack else None
        ),
    }


def _any_true(payloads: Sequence[dict[str, Any] | None], key: str) -> bool:
    return any(isinstance(payload, dict) and payload.get(key) is True for payload in payloads)


def _check(name: str, passed: bool, details: dict[str, Any], error: str) -> Stage4Check:
    return Stage4Check(
        name=name,
        status="passed" if passed else "failed",
        details=details,
        error=None if passed else error,
    )


def _owner_acceptance_checklist() -> list[str]:
    return [
        "Confirm the version identity points to the current PR head.",
        "Confirm the historical Feishu pilot tag and commit remain a separate identity.",
        "Confirm the remote PR gate is passed for the current head.",
        "Confirm static staging deployment contract remediation is recorded.",
        "Confirm real staging proof remains absent unless a later owner-approved run records it.",
        "Confirm parity, mutation, and outbound flags are false.",
        "Confirm no customer-facing artifact promotes this pilot package beyond the controlled pilot boundary.",
    ]


def _customer_acceptance_checklist() -> list[str]:
    return [
        "Confirm package_status is stage4_pilot_handoff_ready_with_staging_owner_blocked.",
        "Confirm current_head_sha matches the PR head under review.",
        "Confirm historical_pilot_identity contains the Feishu Pilot V1 tag and commit.",
        "Confirm final_gate_status is final_gate_ready.",
        "Confirm customer_acceptance_pack_status is customer_acceptance_pack_ready.",
        "Confirm real staging rehearsal remains not_met.",
        "Confirm full_codex_parity_claimed is false.",
        "Confirm mutation_performed and outbound_message_sent are false.",
    ]


def _known_limits() -> list[str]:
    return [
        "This package is limited to a controlled commercial pilot handoff.",
        "General availability and production launch are excluded from this package.",
        "End-to-end parity with Codex as a whole is excluded from this package.",
        "Real staging execution evidence is absent and recorded as not_met.",
        "No deploy, tag, release, or customer outbound message is performed by this package.",
        "Generated .xagent_runtime reports are local evidence and are not staged by default.",
    ]


def _next_commands(status: str) -> list[str]:
    if status == "stage4_pilot_handoff_ready_with_staging_owner_blocked":
        return [
            "python scripts\\commercial_pilot_final_gate.py",
            "python scripts\\commercial_pilot_delivery_receipt.py",
            "python scripts\\commercial_pilot_acceptance_gate.py",
            "python scripts\\commercial_pilot_handoff_index.py",
            "python scripts\\commercial_pilot_customer_acceptance_pack.py",
            "python scripts\\commercial_pilot_stage4_package.py",
        ]
    return [
        "Inspect stage4-pilot-handoff-package-20260615.json and fix the first failed check.",
        "Regenerate upstream pilot evidence before rerunning the Stage 4 package generator.",
    ]


def build_stage4_package(
    *,
    report_dir: Path = REPORT_DIR,
    branch: str | None = None,
    current_head_sha: str | None = None,
    remote_branch_sha: str | None = None,
    remote_branch: str = "origin/feat/commercial-delivery-v1",
    stage2_remote_report_path: Path | None = None,
    stage3_static_report_path: Path | None = None,
    stage3_remote_report_path: Path | None = None,
    final_gate_report_path: Path | None = None,
    delivery_receipt_report_path: Path | None = None,
    acceptance_gate_report_path: Path | None = None,
    handoff_index_report_path: Path | None = None,
    customer_acceptance_pack_report_path: Path | None = None,
) -> Stage4PilotPackage:
    stage2_path = stage2_remote_report_path or report_dir / DEFAULT_STAGE2_REMOTE_REPORT.name
    stage3_static_path = stage3_static_report_path or report_dir / DEFAULT_STAGE3_STATIC_REPORT.name
    stage3_remote_path = stage3_remote_report_path or report_dir / DEFAULT_STAGE3_REMOTE_REPORT.name
    final_gate_path = final_gate_report_path or report_dir / DEFAULT_FINAL_GATE_REPORT.name
    receipt_path = delivery_receipt_report_path or report_dir / DEFAULT_DELIVERY_RECEIPT_REPORT.name
    acceptance_path = acceptance_gate_report_path or report_dir / DEFAULT_ACCEPTANCE_GATE_REPORT.name
    handoff_index_path = handoff_index_report_path or report_dir / DEFAULT_HANDOFF_INDEX_REPORT.name
    customer_pack_path = customer_acceptance_pack_report_path or report_dir / DEFAULT_CUSTOMER_ACCEPTANCE_PACK_REPORT.name

    stage2_remote, stage2_error = _read_json(stage2_path)
    stage3_static, stage3_static_error = _read_json(stage3_static_path)
    stage3_remote, stage3_remote_error = _read_json(stage3_remote_path)
    final_gate, final_gate_error = _read_json(final_gate_path)
    receipt, receipt_error = _read_json(receipt_path)
    acceptance, acceptance_error = _read_json(acceptance_path)
    handoff_index, handoff_index_error = _read_json(handoff_index_path)
    customer_pack, customer_pack_error = _read_json(customer_pack_path)

    sources = [
        _source_report("stage2_remote_ci_final", stage2_path, stage2_remote, stage2_error),
        _source_report("stage3_static_remediation", stage3_static_path, stage3_static, stage3_static_error),
        _source_report("stage3_remote_ci_final", stage3_remote_path, stage3_remote, stage3_remote_error),
        _source_report("commercial_pilot_final_gate", final_gate_path, final_gate, final_gate_error),
        _source_report("commercial_pilot_delivery_receipt", receipt_path, receipt, receipt_error),
        _source_report("commercial_pilot_acceptance_gate", acceptance_path, acceptance, acceptance_error),
        _source_report("commercial_pilot_handoff_index", handoff_index_path, handoff_index, handoff_index_error),
        _source_report("commercial_pilot_customer_acceptance_pack", customer_pack_path, customer_pack, customer_pack_error),
    ]

    branch = branch or _git_value(["rev-parse", "--abbrev-ref", "HEAD"])
    current_head_sha = current_head_sha or _git_value(["rev-parse", "HEAD"])
    remote_branch_sha = remote_branch_sha or _git_value(["rev-parse", remote_branch])
    remote_gate = _remote_pr_gate(stage3_remote)
    historical_identity = _historical_pilot_identity(customer_pack, receipt, acceptance)
    if current_head_sha and historical_identity.get("pilot_commit_sha"):
        historical_identity["current_head_is_historical_pilot_commit"] = (
            current_head_sha == historical_identity.get("pilot_commit_sha")
        )
    evidence_bundle = _pilot_evidence_bundle(
        final_gate=final_gate,
        receipt=receipt,
        acceptance=acceptance,
        handoff_index=handoff_index,
        customer_pack=customer_pack,
    )

    payloads = [stage2_remote, stage3_static, stage3_remote, final_gate, receipt, acceptance, handoff_index, customer_pack]
    sources_available = all(source.error is None and source.sha256 for source in sources)
    current_head_bound = bool(current_head_sha) and remote_gate.get("head_sha") == current_head_sha
    remote_branch_bound = bool(current_head_sha) and remote_branch_sha == current_head_sha
    static_gate = stage3_static.get("static_remediation_gate") if stage3_static else None
    real_staging_gate = (
        stage3_remote.get("real_staging_rehearsal_gate")
        if stage3_remote
        else stage3_static.get("real_staging_rehearsal_gate")
        if stage3_static
        else None
    )
    expected_evidence = {
        "final_gate_status": "final_gate_ready",
        "delivery_receipt_status": "delivery_receipt_ready",
        "acceptance_gate_status": "pilot_acceptance_ready",
        "handoff_index_status": "handoff_index_ready",
        "customer_acceptance_pack_status": "customer_acceptance_pack_ready",
    }
    pilot_evidence_ready = all(evidence_bundle.get(key) == expected for key, expected in expected_evidence.items())
    no_parity = not _any_true(payloads, "full_codex_parity_claimed")
    no_mutation = not _any_true(payloads, "mutation_performed")
    no_outbound = not _any_true(payloads, "outbound_message_sent")
    identities_separate = (
        bool(current_head_sha)
        and bool(historical_identity.get("pilot_commit_sha"))
        and current_head_sha != historical_identity.get("pilot_commit_sha")
    )

    checks = [
        _check(
            "source_reports_available",
            sources_available,
            {"count": len(sources), "failed_sources": [source.name for source in sources if source.error]},
            "one or more source reports are missing or unreadable",
        ),
        _check(
            "current_head_bound_to_remote_pr_gate",
            current_head_bound,
            {"current_head_sha": current_head_sha, "remote_gate_head_sha": remote_gate.get("head_sha")},
            "current head does not match the remote PR gate head",
        ),
        _check(
            "remote_branch_bound_to_current_head",
            remote_branch_bound,
            {"current_head_sha": current_head_sha, "remote_branch_sha": remote_branch_sha},
            "remote branch does not match current head",
        ),
        _check(
            "remote_pr_gate_passed",
            remote_gate.get("status") == "passed",
            remote_gate,
            "remote PR gate is not passed",
        ),
        _check(
            "stage3_static_remediation_met",
            static_gate == "met",
            {"static_remediation_gate": static_gate},
            "Stage 3 static remediation gate is not met",
        ),
        _check(
            "real_staging_rehearsal_explicitly_not_met",
            real_staging_gate == "not_met",
            {"real_staging_rehearsal_gate": real_staging_gate},
            "real staging rehearsal gate must be recorded as not_met for this package",
        ),
        _check(
            "pilot_evidence_bundle_ready",
            pilot_evidence_ready,
            evidence_bundle,
            "one or more pilot evidence reports are not ready",
        ),
        _check(
            "current_head_and_historical_pilot_identity_are_separate",
            identities_separate,
            {
                "current_head_sha": current_head_sha,
                "historical_pilot_commit_sha": historical_identity.get("pilot_commit_sha"),
            },
            "current head and historical pilot identity are missing or conflated",
        ),
        _check(
            "no_codex_total_parity_claim",
            no_parity,
            {"full_codex_parity_claimed": False},
            "one or more source reports claim total Codex parity",
        ),
        _check(
            "no_mutation_performed",
            no_mutation,
            {"mutation_performed": False},
            "one or more source reports record mutation",
        ),
        _check(
            "no_outbound_message_sent",
            no_outbound,
            {"outbound_message_sent": False},
            "one or more source reports record outbound send",
        ),
    ]

    package_ready = all(check.status == "passed" for check in checks)
    package_status = (
        "stage4_pilot_handoff_ready_with_staging_owner_blocked"
        if package_ready
        else "stage4_pilot_handoff_blocked"
    )
    return Stage4PilotPackage(
        package_status=package_status,
        generated_at=_utc_now(),
        evidence_type="stage4_pilot_handoff_package",
        claim_boundary={
            "allowed": "controlled commercial pilot readiness with local and remote PR gates passing, plus static deployment contract remediation",
            "excluded_claim_slugs": [
                "ga",
                "production_launch",
                "complete_commercial_ga_delivery",
                "codex_total_parity",
                "real_staging_execution_proof",
            ],
        },
        version_identity={
            "branch": branch,
            "current_head_sha": current_head_sha,
            "remote_branch": remote_branch,
            "remote_branch_sha": remote_branch_sha,
            "pull_request": remote_gate.get("pull_request", {}),
        },
        remote_pr_gate=remote_gate,
        stage3_static_remediation_gate=static_gate or "missing",
        real_staging_rehearsal_gate=real_staging_gate or "missing",
        historical_pilot_identity=historical_identity,
        pilot_evidence_bundle=evidence_bundle,
        source_reports=sources,
        checks=checks,
        owner_acceptance_checklist=_owner_acceptance_checklist(),
        customer_acceptance_checklist=_customer_acceptance_checklist(),
        known_limits=_known_limits(),
        next_commands=_next_commands(package_status),
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
    )


def render_markdown_package(report: Stage4PilotPackage) -> str:
    checks = "\n".join(
        f"- {check.name}: `{check.status}`" + (f" - {check.error}" if check.error else "")
        for check in report.checks
    )
    sources = "\n".join(
        f"- {source.name}: `{source.status}` / `{source.sha256 or '<missing-sha256>'}`"
        for source in report.source_reports
    )
    owner_items = "\n".join(f"- [ ] {item}" for item in report.owner_acceptance_checklist)
    customer_items = "\n".join(f"- [ ] {item}" for item in report.customer_acceptance_checklist)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    commands = "\n".join(f"- `{command}`" for command in report.next_commands)
    version = report.version_identity
    pilot = report.historical_pilot_identity
    bundle = report.pilot_evidence_bundle
    return (
        "# Stage 4 Pilot Handoff Package\n\n"
        f"- Status: `{report.package_status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Branch: `{version.get('branch')}`\n"
        f"- Current head: `{version.get('current_head_sha')}`\n"
        f"- Remote branch: `{version.get('remote_branch')}` / `{version.get('remote_branch_sha')}`\n"
        f"- Pull request: `{version.get('pull_request', {}).get('url')}`\n"
        f"- Real staging rehearsal gate: `{report.real_staging_rehearsal_gate}`\n"
        f"- Static remediation gate: `{report.stage3_static_remediation_gate}`\n"
        f"- full_codex_parity_claimed: `{report.full_codex_parity_claimed}`\n"
        f"- mutation_performed: `{report.mutation_performed}`\n"
        f"- outbound_message_sent: `{report.outbound_message_sent}`\n\n"
        "## Historical Pilot Identity\n\n"
        f"- Pilot channel: `{pilot.get('pilot_channel')}`\n"
        f"- Pilot tag: `{pilot.get('pilot_tag_name')}`\n"
        f"- Pilot commit: `{pilot.get('pilot_commit_sha')}`\n"
        f"- RC baseline: `{pilot.get('rc_tag_name')}` / `{pilot.get('rc_commit_sha')}`\n"
        f"- Identity class: `{pilot.get('identity_class')}`\n\n"
        "## Pilot Evidence Bundle\n\n"
        f"- Final gate: `{bundle.get('final_gate_status')}`\n"
        f"- Delivery receipt: `{bundle.get('delivery_receipt_status')}`\n"
        f"- Acceptance gate: `{bundle.get('acceptance_gate_status')}`\n"
        f"- Handoff index: `{bundle.get('handoff_index_status')}`\n"
        f"- Customer pack: `{bundle.get('customer_acceptance_pack_status')}`\n"
        f"- Outbound owner gate: `{bundle.get('outbound_owner_gate_status')}`\n\n"
        "## Source Reports\n\n"
        f"{sources}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Owner Acceptance Checklist\n\n"
        f"{owner_items}\n\n"
        "## Customer Acceptance Checklist\n\n"
        f"{customer_items}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n\n"
        "## Next Commands\n\n"
        f"{commands}\n"
    )


def write_report(report: Stage4PilotPackage, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_package(
    report: Stage4PilotPackage,
    output_path: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_package(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--remote-branch", default="origin/feat/commercial-delivery-v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_stage4_package(report_dir=args.report_dir, remote_branch=args.remote_branch)
    write_report(report, args.output_json)
    write_markdown_package(report, args.output_md)
    print(f"Stage 4 pilot handoff package status: {report.package_status}")
    print(f"Current head: {report.version_identity.get('current_head_sha') or '<missing>'}")
    print(f"Remote PR gate: {report.remote_pr_gate.get('status')}")
    print(f"Real staging rehearsal gate: {report.real_staging_rehearsal_gate}")
    print(f"JSON package written to {args.output_json}")
    print(f"Markdown package written to {args.output_md}")
    print(f"full_codex_parity_claimed: {report.full_codex_parity_claimed}")
    print(f"mutation_performed: {report.mutation_performed}")
    print(f"outbound_message_sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.package_status == "stage4_pilot_handoff_ready_with_staging_owner_blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
