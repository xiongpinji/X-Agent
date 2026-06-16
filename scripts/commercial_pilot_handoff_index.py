#!/usr/bin/env python3
"""Generate a customer-archivable Feishu Pilot V1 handoff index.

The index consumes existing evidence reports only. It does not refresh reports,
call external services, move tags, or send Feishu outbound messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-handoff-index.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-pilot-handoff-index.md"


@dataclass(frozen=True)
class HandoffIndexArtifactSpec:
    name: str
    path: Path
    category: str
    required: bool = True
    expected_statuses: frozenset[str] = frozenset()
    expected_evidence_type: str | None = None


@dataclass(frozen=True)
class HandoffIndexArtifact:
    name: str
    path: str
    category: str
    required: bool
    status: str
    sha256: str | None = None
    size_bytes: int | None = None
    report_status: str | None = None
    evidence_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class HandoffIndexCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class HandoffIndexReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str | None
    pilot_tag_name: str | None
    pilot_commit_sha: str | None
    rc_tag_name: str | None
    rc_commit_sha: str | None
    acceptance_gate_status: str | None
    final_gate_status: str | None
    delivery_receipt_status: str | None
    handoff_status: str | None
    ops_status: str | None
    delivery_manifest_status: str | None
    inbound_live_status: str | None
    outbound_owner_gate_status: str | None
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    artifacts: list[HandoffIndexArtifact]
    checks: list[HandoffIndexCheck]
    customer_summary: list[str]
    archive_files: list[str]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = [asdict(artifact) for artifact in self.artifacts]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


DEFAULT_ARTIFACTS = (
    HandoffIndexArtifactSpec(
        "acceptance_gate_report",
        REPORT_DIR / "commercial-pilot-acceptance-gate.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_acceptance_ready"}),
        expected_evidence_type="commercial_pilot_acceptance_gate",
    ),
    HandoffIndexArtifactSpec(
        "final_gate_report",
        REPORT_DIR / "commercial-pilot-final-gate.json",
        "runtime_report",
        expected_statuses=frozenset({"final_gate_ready"}),
        expected_evidence_type="commercial_pilot_final_gate",
    ),
    HandoffIndexArtifactSpec(
        "delivery_receipt_report",
        REPORT_DIR / "commercial-pilot-delivery-receipt.json",
        "runtime_report",
        expected_statuses=frozenset({"delivery_receipt_ready"}),
        expected_evidence_type="commercial_pilot_delivery_receipt",
    ),
    HandoffIndexArtifactSpec(
        "delivery_receipt_markdown",
        REPORT_DIR / "commercial-pilot-delivery-receipt.md",
        "customer_markdown",
    ),
    HandoffIndexArtifactSpec(
        "handoff_status_report",
        REPORT_DIR / "commercial-pilot-handoff-status.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_handoff_ready"}),
    ),
    HandoffIndexArtifactSpec(
        "operator_status_report",
        REPORT_DIR / "commercial-pilot-ops-status.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ops_ready"}),
    ),
    HandoffIndexArtifactSpec(
        "delivery_manifest_report",
        REPORT_DIR / "commercial-pilot-delivery-manifest.json",
        "runtime_report",
        expected_statuses=frozenset({"delivery_manifest_ready"}),
        expected_evidence_type="commercial_pilot_delivery_manifest",
    ),
    HandoffIndexArtifactSpec(
        "feishu_inbound_live_report",
        REPORT_DIR / "commercial-pilot-feishu-live.json",
        "runtime_report",
        expected_statuses=frozenset({"passed"}),
        expected_evidence_type="commercial_pilot_feishu_live",
    ),
    HandoffIndexArtifactSpec(
        "rc_delivery_status_report",
        REPORT_DIR / "rc-delivery-status.json",
        "runtime_report",
        expected_statuses=frozenset({"commercial_rc_ready"}),
    ),
    HandoffIndexArtifactSpec(
        "channel_readiness_report",
        REPORT_DIR / "commercial-pilot-channel-readiness.json",
        "runtime_report",
        expected_statuses=frozenset({"ready", "ready_with_owner_gates"}),
    ),
    HandoffIndexArtifactSpec(
        "pilot_readiness_report",
        REPORT_DIR / "commercial-pilot-readiness.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ready"}),
    ),
    HandoffIndexArtifactSpec(
        "refresh_chain_report",
        REPORT_DIR / "commercial-pilot-refresh-chain.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ready"}),
    ),
    HandoffIndexArtifactSpec(
        "feishu_outbound_owner_gate_report",
        REPORT_DIR / "commercial-pilot-feishu-outbound-live.json",
        "runtime_report",
        required=False,
        expected_statuses=frozenset({"passed", "ready_to_execute", "owner_action_required"}),
        expected_evidence_type="commercial_pilot_feishu_outbound_live",
    ),
    HandoffIndexArtifactSpec(
        "delivery_pack_doc",
        ROOT / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md",
        "source_doc",
    ),
)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"artifact not found: {_display_path(path)}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"could not read JSON artifact {_display_path(path)}: {exc}"
    if not isinstance(payload, dict):
        return None, f"JSON artifact is not an object: {_display_path(path)}"
    return payload, None


def _sha256_file(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None, f"artifact not found: {_display_path(path)}"
    except OSError as exc:
        return None, None, f"could not read artifact {_display_path(path)}: {exc}"
    return hashlib.sha256(data).hexdigest(), len(data), None


def _artifact_from_spec(spec: HandoffIndexArtifactSpec) -> tuple[HandoffIndexArtifact, dict[str, Any] | None]:
    sha256, size_bytes, read_error = _sha256_file(spec.path)
    if read_error:
        return (
            HandoffIndexArtifact(
                name=spec.name,
                path=_display_path(spec.path),
                category=spec.category,
                required=spec.required,
                status="missing" if spec.required else "optional_missing",
                error=read_error,
            ),
            None,
        )

    payload: dict[str, Any] | None = None
    details: dict[str, Any] = {}
    report_status: str | None = None
    evidence_type: str | None = None
    status = "present"
    error: str | None = None

    if spec.category == "runtime_report":
        payload, json_error = _read_json(spec.path)
        if json_error or payload is None:
            status = "failed" if spec.required else "preview"
            error = json_error or "runtime report is not readable"
        else:
            report_status = payload.get("status") if isinstance(payload.get("status"), str) else None
            evidence_type = payload.get("evidence_type") if isinstance(payload.get("evidence_type"), str) else None
            details = {
                "report_status": report_status,
                "evidence_type": evidence_type,
                "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
                "mutation_performed": payload.get("mutation_performed"),
                "outbound_message_sent": payload.get("outbound_message_sent"),
            }
            if payload.get("full_codex_parity_claimed") is True:
                status = "failed"
                error = "runtime report claims full Codex parity"
            elif spec.expected_statuses and report_status not in spec.expected_statuses:
                status = "action_required" if spec.required else "preview"
                error = f"runtime report status {report_status!r} is not accepted"
            elif spec.expected_evidence_type and evidence_type != spec.expected_evidence_type:
                status = "failed" if spec.required else "preview"
                error = "runtime report evidence_type is not accepted"
            else:
                status = "passed" if spec.required else "present"

    return (
        HandoffIndexArtifact(
            name=spec.name,
            path=_display_path(spec.path),
            category=spec.category,
            required=spec.required,
            status=status,
            sha256=sha256,
            size_bytes=size_bytes,
            report_status=report_status,
            evidence_type=evidence_type,
            details=details,
            error=error,
        ),
        payload,
    )


def _required_artifacts_check(artifacts: list[HandoffIndexArtifact]) -> HandoffIndexCheck:
    failed = [
        artifact.name
        for artifact in artifacts
        if artifact.required and artifact.status not in {"present", "passed"}
    ]
    if failed:
        hard_failed = [
            artifact.name
            for artifact in artifacts
            if artifact.required and artifact.status == "failed"
        ]
        return HandoffIndexCheck(
            name="required_archive_artifacts",
            status="failed" if hard_failed else "action_required",
            details={"missing_or_failed": failed},
            error="one or more required handoff archive artifacts are missing or invalid",
        )
    return HandoffIndexCheck(
        name="required_archive_artifacts",
        status="passed",
        details={"count": sum(1 for artifact in artifacts if artifact.required)},
    )


def _digest_check(artifacts: list[HandoffIndexArtifact]) -> HandoffIndexCheck:
    missing = [
        artifact.name
        for artifact in artifacts
        if artifact.status != "optional_missing" and not artifact.sha256
    ]
    if missing:
        return HandoffIndexCheck(
            name="archive_digests",
            status="action_required",
            details={"missing_digests": missing},
            error="one or more archive artifacts do not have a SHA-256 digest",
        )
    return HandoffIndexCheck(
        name="archive_digests",
        status="passed",
        details={"count": sum(1 for artifact in artifacts if artifact.sha256)},
    )


def _acceptance_gate_ready_check(payload: dict[str, Any] | None) -> HandoffIndexCheck:
    status = payload.get("status") if payload else None
    passed = status == "pilot_acceptance_ready"
    return HandoffIndexCheck(
        name="acceptance_gate_ready",
        status="passed" if passed else "action_required",
        details={"actual": status, "expected": "pilot_acceptance_ready"},
        error=None if passed else "acceptance gate is not pilot_acceptance_ready",
    )


def _parity_claim_check(payloads: dict[str, dict[str, Any] | None]) -> HandoffIndexCheck:
    claimers = [
        name
        for name, payload in payloads.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return HandoffIndexCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_reports": claimers},
            error="one or more handoff index reports claim full Codex parity",
        )
    return HandoffIndexCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _mutation_check(payloads: dict[str, dict[str, Any] | None]) -> HandoffIndexCheck:
    watched = {
        "acceptance_gate_report",
        "final_gate_report",
        "delivery_receipt_report",
        "feishu_inbound_live_report",
    }
    observed: dict[str, Any] = {}
    offenders: list[str] = []
    for name in watched:
        payload = payloads.get(name)
        if not isinstance(payload, dict):
            continue
        mutation = payload.get("mutation_performed")
        outbound = payload.get("outbound_message_sent")
        observed[f"{name}.mutation_performed"] = mutation
        observed[f"{name}.outbound_message_sent"] = outbound
        if mutation is not False:
            offenders.append(f"{name}.mutation_performed")
        if outbound is not False:
            offenders.append(f"{name}.outbound_message_sent")
    if offenders:
        return HandoffIndexCheck(
            name="no_archive_mutation",
            status="failed",
            details={"observed": observed, "offenders": sorted(offenders)},
            error="handoff archive source reports must not record final gate or inbound outbound mutation",
        )
    return HandoffIndexCheck(name="no_archive_mutation", status="passed", details={"observed": observed})


def _overall_status(checks: list[HandoffIndexCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "handoff_index_blocked"
    if any(check.status == "action_required" for check in checks):
        return "handoff_index_action_required"
    return "handoff_index_ready"


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _customer_summary(
    *,
    acceptance: dict[str, Any] | None,
    receipt: dict[str, Any] | None,
    ops: dict[str, Any] | None,
    artifact_count: int,
) -> list[str]:
    pilot_channel = _first_value(
        acceptance.get("pilot_channel") if acceptance else None,
        ops.get("pilot_channel") if ops else None,
    )
    pilot_tag = _first_value(
        acceptance.get("pilot_tag_name") if acceptance else None,
        receipt.get("pilot_tag_name") if receipt else None,
    )
    pilot_commit = _first_value(
        acceptance.get("pilot_commit_sha") if acceptance else None,
        receipt.get("pilot_commit_sha") if receipt else None,
    )
    rc_tag = _first_value(
        acceptance.get("rc_tag_name") if acceptance else None,
        receipt.get("rc_tag_name") if receipt else None,
    )
    rc_commit = _first_value(
        acceptance.get("rc_commit_sha") if acceptance else None,
        receipt.get("rc_commit_sha") if receipt else None,
    )
    return [
        f"Pilot channel: {pilot_channel}",
        f"Pilot tag: {pilot_tag}",
        f"Pilot commit: {pilot_commit}",
        f"RC baseline: {rc_tag} / {rc_commit}",
        f"Acceptance gate: {acceptance.get('status') if acceptance else '<missing>'}",
        f"Outbound owner gate: {ops.get('outbound_owner_gate_status') if ops else '<missing>'}",
        f"Indexed artifacts: {artifact_count}",
    ]


def _archive_files(artifacts: list[HandoffIndexArtifact]) -> list[str]:
    return [
        artifact.path
        for artifact in artifacts
        if artifact.required and artifact.status in {"present", "passed"}
    ]


def _next_commands(status: str) -> list[str]:
    if status == "handoff_index_ready":
        return [
            "Archive commercial-pilot-handoff-index.json and commercial-pilot-handoff-index.md with the customer handoff.",
            "Regenerate this index after rerunning commercial_pilot_acceptance_gate.py.",
        ]
    if status == "handoff_index_action_required":
        return [
            "Inspect commercial-pilot-handoff-index.json and fix the first action_required check.",
            "Rerun python scripts\\commercial_pilot_acceptance_gate.py before regenerating the handoff index.",
        ]
    return [
        "Do not archive this handoff package until failed checks are resolved.",
        "Inspect full_codex_parity_claimed, mutation_performed, and outbound_message_sent fields first.",
    ]


def build_handoff_index_report(
    *,
    artifacts: tuple[HandoffIndexArtifactSpec, ...] = DEFAULT_ARTIFACTS,
) -> HandoffIndexReport:
    artifact_reports: list[HandoffIndexArtifact] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    for spec in artifacts:
        artifact, payload = _artifact_from_spec(spec)
        artifact_reports.append(artifact)
        payloads[spec.name] = payload

    acceptance = payloads.get("acceptance_gate_report")
    receipt = payloads.get("delivery_receipt_report")
    handoff = payloads.get("handoff_status_report")
    ops = payloads.get("operator_status_report")
    manifest = payloads.get("delivery_manifest_report")
    live = payloads.get("feishu_inbound_live_report")
    final_gate = payloads.get("final_gate_report")

    checks = [
        _required_artifacts_check(artifact_reports),
        _digest_check(artifact_reports),
        _acceptance_gate_ready_check(acceptance),
        _parity_claim_check(payloads),
        _mutation_check(payloads),
    ]
    status = _overall_status(checks)
    archive_files = _archive_files(artifact_reports)
    return HandoffIndexReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_handoff_index",
        pilot_channel=_first_value(
            acceptance.get("pilot_channel") if acceptance else None,
            receipt.get("pilot_channel") if receipt else None,
            ops.get("pilot_channel") if ops else None,
        ),
        pilot_tag_name=_first_value(
            acceptance.get("pilot_tag_name") if acceptance else None,
            receipt.get("pilot_tag_name") if receipt else None,
            ops.get("pilot_tag_name") if ops else None,
            handoff.get("pilot_tag_name") if handoff else None,
        ),
        pilot_commit_sha=_first_value(
            acceptance.get("pilot_commit_sha") if acceptance else None,
            receipt.get("pilot_commit_sha") if receipt else None,
            ops.get("pilot_commit_sha") if ops else None,
            handoff.get("expected_pilot_commit_sha") if handoff else None,
        ),
        rc_tag_name=_first_value(
            acceptance.get("rc_tag_name") if acceptance else None,
            receipt.get("rc_tag_name") if receipt else None,
            ops.get("rc_tag_name") if ops else None,
            handoff.get("rc_tag_name") if handoff else None,
        ),
        rc_commit_sha=_first_value(
            acceptance.get("rc_commit_sha") if acceptance else None,
            receipt.get("rc_commit_sha") if receipt else None,
            ops.get("rc_commit_sha") if ops else None,
            handoff.get("expected_rc_commit_sha") if handoff else None,
        ),
        acceptance_gate_status=acceptance.get("status") if acceptance else None,
        final_gate_status=final_gate.get("status") if final_gate else None,
        delivery_receipt_status=receipt.get("status") if receipt else None,
        handoff_status=handoff.get("status") if handoff else None,
        ops_status=ops.get("status") if ops else None,
        delivery_manifest_status=manifest.get("status") if manifest else None,
        inbound_live_status=live.get("status") if live else None,
        outbound_owner_gate_status=ops.get("outbound_owner_gate_status") if ops else None,
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
        artifacts=artifact_reports,
        checks=checks,
        customer_summary=_customer_summary(
            acceptance=acceptance,
            receipt=receipt,
            ops=ops,
            artifact_count=len(artifact_reports),
        ),
        archive_files=archive_files,
        next_commands=_next_commands(status),
        known_limits=[
            "This handoff index is read-only and consumes existing evidence reports only.",
            "It does not refresh reports, move tags, call GitHub, or send Feishu outbound messages.",
            "Optional outbound Feishu evidence is included when present but is not required for Pilot V1.",
            "Full Codex parity is not claimed by this handoff index.",
        ],
    )


def render_markdown_index(report: HandoffIndexReport) -> str:
    summary = "\n".join(f"- {item}" for item in report.customer_summary)
    artifacts = "\n".join(
        f"- {artifact.name}: `{artifact.status}` / `{artifact.sha256 or '<missing-sha256>'}` / `{artifact.path}`"
        for artifact in report.artifacts
    )
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    return (
        "# X-Agent Feishu Pilot V1 Handoff Index\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Pilot channel: `{report.pilot_channel}`\n"
        f"- Pilot tag: `{report.pilot_tag_name}`\n"
        f"- Pilot commit: `{report.pilot_commit_sha}`\n"
        f"- RC baseline: `{report.rc_tag_name}` / `{report.rc_commit_sha}`\n"
        f"- Acceptance gate: `{report.acceptance_gate_status}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n\n"
        "## Customer Summary\n\n"
        f"{summary}\n\n"
        "## Archive Artifacts\n\n"
        f"{artifacts}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: HandoffIndexReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_index(report: HandoffIndexReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_index(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_handoff_index_report()
    write_report(report, args.output)
    write_markdown_index(report, args.markdown_output)
    print(f"Commercial pilot handoff index status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel or '<missing>'}")
    print(f"Pilot tag: {report.pilot_tag_name or '<missing>'}")
    print(f"JSON index written to {args.output}")
    print(f"Markdown index written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "handoff_index_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
