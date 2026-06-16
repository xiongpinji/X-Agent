#!/usr/bin/env python3
"""Generate the final customer acceptance pack for Feishu Pilot V1.

The pack is read-only. It consumes existing evidence reports and the stable
commercial-pilot API aggregation contract. It does not refresh reports, call
external services, move tags, or send Feishu outbound messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.api.commercial_pilot import build_feishu_pilot_status
from scripts.commercial_pilot_core_entrypoints import REPORT_DIR, _utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELIVERY_PACK_DOC = ROOT / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md"
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-customer-acceptance-pack.json"
DEFAULT_MARKDOWN_OUTPUT = REPORT_DIR / "commercial-pilot-customer-acceptance-pack.md"

API_ENDPOINTS = (
    "GET /api/v1/commercial-pilot/feishu/status",
    "GET /api/v1/commercial-pilot/feishu/reports",
    "GET /api/v1/commercial-pilot/feishu/reports/{report_name}",
)

CODEX_REFERENCE_SOURCES = (
    "https://openai.com/codex/",
    "https://openai.com/index/codex-now-generally-available/",
    "https://openai.com/index/introducing-upgrades-to-codex/",
    "https://openai.com/index/introducing-the-codex-app/",
    "https://help.openai.com/en/articles/11096431",
    "https://help.openai.com/en/articles/11369540-getting-started-with-codex",
)


@dataclass(frozen=True)
class AcceptanceArtifactSpec:
    name: str
    path: Path
    category: str
    required: bool = True
    expected_statuses: frozenset[str] = frozenset()
    expected_evidence_type: str | None = None


@dataclass(frozen=True)
class AcceptanceArtifact:
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
class AcceptanceCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CodexAlignmentItem:
    capability: str
    codex_reference: str
    xagent_pilot_v1_status: str
    evidence: str
    delivery_decision: str


@dataclass(frozen=True)
class CustomerAcceptancePackReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str | None
    pilot_tag_name: str | None
    pilot_commit_sha: str | None
    rc_tag_name: str | None
    rc_commit_sha: str | None
    operational_status: str | None
    acceptance_gate_status: str | None
    handoff_index_status: str | None
    inbound_live_status: str | None
    outbound_owner_gate_status: str | None
    full_codex_parity_claimed: bool
    mutation_performed: bool
    outbound_message_sent: bool
    api_contract: dict[str, Any]
    codex_alignment_summary: dict[str, Any]
    codex_alignment: list[CodexAlignmentItem]
    artifacts: list[AcceptanceArtifact]
    checks: list[AcceptanceCheck]
    customer_acceptance_checklist: list[str]
    operator_commands: list[str]
    archive_files: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["codex_alignment"] = [asdict(item) for item in self.codex_alignment]
        payload["artifacts"] = [asdict(artifact) for artifact in self.artifacts]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


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


def _artifact_from_spec(spec: AcceptanceArtifactSpec) -> tuple[AcceptanceArtifact, dict[str, Any] | None]:
    sha256, size_bytes, read_error = _sha256_file(spec.path)
    if read_error:
        return (
            AcceptanceArtifact(
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
        AcceptanceArtifact(
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


def _artifact_specs(report_dir: Path, delivery_pack_doc_path: Path) -> tuple[AcceptanceArtifactSpec, ...]:
    return (
        AcceptanceArtifactSpec(
            "acceptance_gate_report",
            report_dir / "commercial-pilot-acceptance-gate.json",
            "runtime_report",
            expected_statuses=frozenset({"pilot_acceptance_ready"}),
            expected_evidence_type="commercial_pilot_acceptance_gate",
        ),
        AcceptanceArtifactSpec(
            "handoff_index_report",
            report_dir / "commercial-pilot-handoff-index.json",
            "runtime_report",
            expected_statuses=frozenset({"handoff_index_ready"}),
            expected_evidence_type="commercial_pilot_handoff_index",
        ),
        AcceptanceArtifactSpec(
            "final_gate_report",
            report_dir / "commercial-pilot-final-gate.json",
            "runtime_report",
            expected_statuses=frozenset({"final_gate_ready"}),
            expected_evidence_type="commercial_pilot_final_gate",
        ),
        AcceptanceArtifactSpec(
            "delivery_receipt_report",
            report_dir / "commercial-pilot-delivery-receipt.json",
            "runtime_report",
            expected_statuses=frozenset({"delivery_receipt_ready"}),
            expected_evidence_type="commercial_pilot_delivery_receipt",
        ),
        AcceptanceArtifactSpec("delivery_receipt_markdown", report_dir / "commercial-pilot-delivery-receipt.md", "customer_markdown"),
        AcceptanceArtifactSpec(
            "handoff_status_report",
            report_dir / "commercial-pilot-handoff-status.json",
            "runtime_report",
            expected_statuses=frozenset({"pilot_handoff_ready"}),
        ),
        AcceptanceArtifactSpec(
            "operator_status_report",
            report_dir / "commercial-pilot-ops-status.json",
            "runtime_report",
            expected_statuses=frozenset({"pilot_ops_ready"}),
        ),
        AcceptanceArtifactSpec(
            "delivery_manifest_report",
            report_dir / "commercial-pilot-delivery-manifest.json",
            "runtime_report",
            expected_statuses=frozenset({"delivery_manifest_ready"}),
            expected_evidence_type="commercial_pilot_delivery_manifest",
        ),
        AcceptanceArtifactSpec(
            "feishu_inbound_live_report",
            report_dir / "commercial-pilot-feishu-live.json",
            "runtime_report",
            expected_statuses=frozenset({"passed"}),
            expected_evidence_type="commercial_pilot_feishu_live",
        ),
        AcceptanceArtifactSpec(
            "channel_readiness_report",
            report_dir / "commercial-pilot-channel-readiness.json",
            "runtime_report",
            expected_statuses=frozenset({"ready", "ready_with_owner_gates"}),
        ),
        AcceptanceArtifactSpec(
            "rc_delivery_status_report",
            report_dir / "rc-delivery-status.json",
            "runtime_report",
            expected_statuses=frozenset({"commercial_rc_ready"}),
        ),
        AcceptanceArtifactSpec("delivery_pack_doc", delivery_pack_doc_path, "source_doc"),
    )


def _required_artifacts_check(artifacts: list[AcceptanceArtifact]) -> AcceptanceCheck:
    failed = [
        artifact.name
        for artifact in artifacts
        if artifact.required and artifact.status not in {"present", "passed"}
    ]
    if failed:
        hard_failed = [artifact.name for artifact in artifacts if artifact.required and artifact.status == "failed"]
        return AcceptanceCheck(
            name="required_customer_artifacts",
            status="failed" if hard_failed else "action_required",
            details={"missing_or_invalid": failed},
            error="one or more required customer acceptance artifacts are missing or invalid",
        )
    return AcceptanceCheck(
        name="required_customer_artifacts",
        status="passed",
        details={"count": sum(1 for artifact in artifacts if artifact.required)},
    )


def _digest_check(artifacts: list[AcceptanceArtifact]) -> AcceptanceCheck:
    missing = [
        artifact.name
        for artifact in artifacts
        if artifact.status != "optional_missing" and not artifact.sha256
    ]
    if missing:
        return AcceptanceCheck(
            name="customer_archive_digests",
            status="action_required",
            details={"missing_digests": missing},
            error="one or more customer artifacts do not have a SHA-256 digest",
        )
    return AcceptanceCheck(
        name="customer_archive_digests",
        status="passed",
        details={"count": sum(1 for artifact in artifacts if artifact.sha256)},
    )


def _status_check(name: str, actual: str | None, expected: str) -> AcceptanceCheck:
    passed = actual == expected
    return AcceptanceCheck(
        name=name,
        status="passed" if passed else "action_required",
        details={"actual": actual, "expected": expected},
        error=None if passed else f"{name} is not {expected}",
    )


def _inbound_live_check(live: dict[str, Any] | None) -> AcceptanceCheck:
    expected = {
        "status": "passed",
        "channel": "feishu",
        "evidence_type": "commercial_pilot_feishu_live",
        "event_type": "im.message.receive_v1",
        "tenant_key_present": True,
        "message_id_present": True,
        "chat_id_present": True,
        "content_present": True,
        "encrypted_callback": True,
        "mutation_performed": False,
        "outbound_message_sent": False,
    }
    mismatches = [key for key, value in expected.items() if live is None or live.get(key) != value]
    if live is None or not live.get("event_id"):
        mismatches.append("event_id")
    if live is None or live.get("signature_mode") not in {"lark_sha256", "legacy_hmac_sha256"}:
        mismatches.append("signature_mode")
    details = {
        "event_id": live.get("event_id") if live else None,
        "event_type": live.get("event_type") if live else None,
        "signature_mode": live.get("signature_mode") if live else None,
        "encrypted_callback": live.get("encrypted_callback") if live else None,
        "mismatches": mismatches,
    }
    if mismatches:
        unsafe = {"mutation_performed", "outbound_message_sent", "channel", "evidence_type"} & set(mismatches)
        return AcceptanceCheck(
            name="feishu_inbound_live_evidence",
            status="failed" if unsafe else "action_required",
            details=details,
            error="Feishu inbound live evidence is not accepted for customer handoff",
        )
    return AcceptanceCheck(name="feishu_inbound_live_evidence", status="passed", details=details)


def _parity_claim_check(payloads: dict[str, dict[str, Any] | None], api_status: dict[str, Any]) -> AcceptanceCheck:
    claimers = [
        name
        for name, payload in payloads.items()
        if isinstance(payload, dict) and payload.get("full_codex_parity_claimed") is True
    ]
    if api_status.get("full_codex_parity_claimed") is True:
        claimers.append("api_status")
    if claimers:
        return AcceptanceCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_reports": sorted(claimers)},
            error="one or more customer acceptance sources claim full Codex parity",
        )
    return AcceptanceCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _mutation_check(payloads: dict[str, dict[str, Any] | None], api_status: dict[str, Any]) -> AcceptanceCheck:
    watched = {
        "acceptance_gate_report",
        "handoff_index_report",
        "final_gate_report",
        "delivery_receipt_report",
        "feishu_inbound_live_report",
    }
    observed: dict[str, Any] = {
        "api_status.mutation_performed": api_status.get("mutation_performed"),
        "api_status.outbound_message_sent": api_status.get("outbound_message_sent"),
    }
    offenders = [
        key
        for key, value in observed.items()
        if value is not False
    ]
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
        return AcceptanceCheck(
            name="no_customer_handoff_mutation",
            status="failed",
            details={"observed": observed, "offenders": sorted(offenders)},
            error="customer acceptance evidence must not record final gate or inbound outbound mutation",
        )
    return AcceptanceCheck(name="no_customer_handoff_mutation", status="passed", details={"observed": observed})


def _api_contract_check(api_status: dict[str, Any]) -> AcceptanceCheck:
    passed = (
        api_status.get("status") == "pilot_operational_ready"
        and api_status.get("pilot_channel") == "feishu"
        and len(API_ENDPOINTS) == 3
    )
    return AcceptanceCheck(
        name="read_only_api_contract",
        status="passed" if passed else "action_required",
        details={
            "api_status": api_status.get("status"),
            "pilot_channel": api_status.get("pilot_channel"),
            "endpoints": list(API_ENDPOINTS),
            "read_only": True,
        },
        error=None if passed else "commercial pilot API aggregation is not ready",
    )


def _codex_alignment_items() -> list[CodexAlignmentItem]:
    return [
        CodexAlignmentItem(
            capability="commercial_feishu_pilot_handoff",
            codex_reference="Codex helps teams build and ship with agentic workflows.",
            xagent_pilot_v1_status="aligned_for_pilot_v1",
            evidence="Feishu inbound live evidence, acceptance gate, handoff index, and read-only API are ready.",
            delivery_decision="Deliverable for first domestic Feishu commercial pilot.",
        ),
        CodexAlignmentItem(
            capability="local_agent_execution_and_approvals",
            codex_reference="Codex CLI supports local code edits, shell execution, and approval modes.",
            xagent_pilot_v1_status="partial",
            evidence="X-Agent uses owner-gated scripts and read-only gates; this pack is not a Codex CLI replacement.",
            delivery_decision="Keep as enterprise backend/control-plane evidence, not terminal-agent parity.",
        ),
        CodexAlignmentItem(
            capability="parallel_cloud_tasks",
            codex_reference="Codex cloud can run multiple repository tasks in isolated cloud environments.",
            xagent_pilot_v1_status="partial",
            evidence="X-Agent has workflow and multi-agent foundations; Pilot V1 does not claim Codex cloud task UX.",
            delivery_decision="Track as post-pilot platform work.",
        ),
        CodexAlignmentItem(
            capability="ide_extension_and_app_surfaces",
            codex_reference="Codex is available through CLI, IDE extension, web, and app surfaces.",
            xagent_pilot_v1_status="not_targeted_for_pilot_v1",
            evidence="Feishu Pilot V1 is channel/backend delivery; UI work is tracked separately.",
            delivery_decision="Do not block Feishu Pilot V1 on IDE/app parity.",
        ),
        CodexAlignmentItem(
            capability="github_and_slack_integrations",
            codex_reference="Codex GA includes GitHub and Slack-oriented engineering workflows.",
            xagent_pilot_v1_status="partial",
            evidence="RC hosted CI and GitHub evidence are recorded; Slack is not targeted because V1 domestic channel is Feishu.",
            delivery_decision="Keep Feishu first; add other collaboration channels after domestic pilot acceptance.",
        ),
        CodexAlignmentItem(
            capability="skills_sdk_and_embedding_harness",
            codex_reference="Codex supports Skills and SDK-style embedding into engineering workflows.",
            xagent_pilot_v1_status="partial",
            evidence="X-Agent has skills/plugin foundations and delivery scripts, but no Codex SDK parity claim.",
            delivery_decision="Use X-Agent skills as product differentiation while keeping parity claim scoped.",
        ),
        CodexAlignmentItem(
            capability="enterprise_sandbox_admin_and_compliance",
            codex_reference="Codex emphasizes sandboxing, configurable network access, and admin visibility.",
            xagent_pilot_v1_status="partial",
            evidence="Pilot V1 has read-only evidence gates and owner-gated mutation boundaries.",
            delivery_decision="Commercial pilot can proceed; broader admin/compliance parity remains roadmap work.",
        ),
    ]


def _codex_alignment_check(items: list[CodexAlignmentItem]) -> AcceptanceCheck:
    allowed = {"aligned_for_pilot_v1", "partial", "not_targeted_for_pilot_v1"}
    invalid = [item.capability for item in items if item.xagent_pilot_v1_status not in allowed]
    full_claims = [
        item.capability
        for item in items
        if item.xagent_pilot_v1_status.lower() in {"full", "full_parity", "codex_parity"}
    ]
    if invalid or full_claims:
        return AcceptanceCheck(
            name="codex_alignment_scope_declared",
            status="failed",
            details={"invalid": invalid, "full_claims": full_claims},
            error="Codex alignment scope contains an unsupported or full-parity claim",
        )
    return AcceptanceCheck(
        name="codex_alignment_scope_declared",
        status="passed",
        details={
            "aligned_for_pilot_v1": sum(1 for item in items if item.xagent_pilot_v1_status == "aligned_for_pilot_v1"),
            "partial": sum(1 for item in items if item.xagent_pilot_v1_status == "partial"),
            "not_targeted_for_pilot_v1": sum(
                1 for item in items if item.xagent_pilot_v1_status == "not_targeted_for_pilot_v1"
            ),
            "full_codex_parity_claimed": False,
        },
    )


def _customer_acceptance_checklist() -> list[str]:
    return [
        "Confirm status is customer_acceptance_pack_ready.",
        "Confirm Feishu inbound live evidence status is passed.",
        "Confirm /api/v1/commercial-pilot/feishu/status returns pilot_operational_ready.",
        "Confirm acceptance gate status is pilot_acceptance_ready.",
        "Confirm handoff index status is handoff_index_ready.",
        "Confirm outbound owner gate is preview or separately owner-approved.",
        "Confirm full_codex_parity_claimed is false.",
        "Confirm mutation_performed and outbound_message_sent are false for Pilot V1 handoff evidence.",
        "Archive this JSON and Markdown pack with the delivery receipt and handoff index.",
    ]


def _checklist_check(checklist: list[str]) -> AcceptanceCheck:
    passed = len(checklist) >= 8
    return AcceptanceCheck(
        name="customer_acceptance_checklist",
        status="passed" if passed else "action_required",
        details={"count": len(checklist)},
        error=None if passed else "customer acceptance checklist is incomplete",
    )


def _operator_commands() -> list[str]:
    return [
        "python scripts\\commercial_pilot_final_gate.py",
        "python scripts\\commercial_pilot_delivery_receipt.py",
        "python scripts\\commercial_pilot_acceptance_gate.py",
        "python scripts\\commercial_pilot_handoff_index.py",
        "python scripts\\commercial_pilot_customer_acceptance_pack.py",
        "Invoke-RestMethod http://127.0.0.1:8000/api/v1/commercial-pilot/feishu/status",
        "Invoke-RestMethod http://127.0.0.1:8000/api/v1/commercial-pilot/feishu/reports",
        "Invoke-RestMethod http://127.0.0.1:8000/api/v1/commercial-pilot/feishu/reports/acceptance_gate",
    ]


def _archive_files(artifacts: list[AcceptanceArtifact]) -> list[str]:
    return [
        artifact.path
        for artifact in artifacts
        if artifact.required and artifact.status in {"present", "passed"}
    ]


def _overall_status(checks: list[AcceptanceCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "customer_acceptance_pack_blocked"
    if any(check.status == "action_required" for check in checks):
        return "customer_acceptance_pack_action_required"
    return "customer_acceptance_pack_ready"


def build_customer_acceptance_pack_report(
    *,
    report_dir: Path = REPORT_DIR,
    delivery_pack_doc_path: Path = DEFAULT_DELIVERY_PACK_DOC,
) -> CustomerAcceptancePackReport:
    artifacts: list[AcceptanceArtifact] = []
    payloads: dict[str, dict[str, Any] | None] = {}
    for spec in _artifact_specs(report_dir, delivery_pack_doc_path):
        artifact, payload = _artifact_from_spec(spec)
        artifacts.append(artifact)
        payloads[spec.name] = payload

    api_status = build_feishu_pilot_status(report_dir=report_dir)
    acceptance = payloads.get("acceptance_gate_report")
    handoff_index = payloads.get("handoff_index_report")
    live = payloads.get("feishu_inbound_live_report")
    ops = payloads.get("operator_status_report")
    codex_alignment = _codex_alignment_items()
    checklist = _customer_acceptance_checklist()

    checks = [
        _required_artifacts_check(artifacts),
        _digest_check(artifacts),
        _status_check("operational_status_ready", api_status.get("status"), "pilot_operational_ready"),
        _status_check(
            "acceptance_gate_ready",
            acceptance.get("status") if acceptance else None,
            "pilot_acceptance_ready",
        ),
        _status_check(
            "handoff_index_ready",
            handoff_index.get("status") if handoff_index else None,
            "handoff_index_ready",
        ),
        _inbound_live_check(live),
        _api_contract_check(api_status),
        _codex_alignment_check(codex_alignment),
        _checklist_check(checklist),
        _parity_claim_check(payloads, api_status),
        _mutation_check(payloads, api_status),
    ]
    status = _overall_status(checks)
    codex_alignment_counts = {
        "aligned_for_pilot_v1": sum(1 for item in codex_alignment if item.xagent_pilot_v1_status == "aligned_for_pilot_v1"),
        "partial": sum(1 for item in codex_alignment if item.xagent_pilot_v1_status == "partial"),
        "not_targeted_for_pilot_v1": sum(
            1 for item in codex_alignment if item.xagent_pilot_v1_status == "not_targeted_for_pilot_v1"
        ),
        "full_codex_parity_claimed": False,
        "official_sources": list(CODEX_REFERENCE_SOURCES),
    }

    return CustomerAcceptancePackReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_customer_acceptance_pack",
        pilot_channel=api_status.get("pilot_channel"),
        pilot_tag_name=api_status.get("pilot_tag_name"),
        pilot_commit_sha=api_status.get("pilot_commit_sha"),
        rc_tag_name=api_status.get("rc_tag_name"),
        rc_commit_sha=api_status.get("rc_commit_sha"),
        operational_status=api_status.get("status"),
        acceptance_gate_status=api_status.get("acceptance_gate_status"),
        handoff_index_status=api_status.get("handoff_index_status"),
        inbound_live_status=live.get("status") if live else None,
        outbound_owner_gate_status=ops.get("outbound_owner_gate_status") if ops else api_status.get("outbound_owner_gate_status"),
        full_codex_parity_claimed=False,
        mutation_performed=False,
        outbound_message_sent=False,
        api_contract={
            "read_only": True,
            "endpoints": list(API_ENDPOINTS),
            "status": api_status.get("status"),
            "known_limits": api_status.get("known_limits", []),
        },
        codex_alignment_summary=codex_alignment_counts,
        codex_alignment=codex_alignment,
        artifacts=artifacts,
        checks=checks,
        customer_acceptance_checklist=checklist,
        operator_commands=_operator_commands(),
        archive_files=_archive_files(artifacts),
        known_limits=[
            "This pack proves Feishu Pilot V1 customer-acceptance readiness only.",
            "It does not refresh reports, move tags, call GitHub, or send Feishu outbound messages.",
            "Outbound Feishu send remains optional and owner-gated for Pilot V1.",
            "Telegram is not required for the first domestic pilot.",
            "Full Codex parity is not claimed by this customer acceptance pack.",
        ],
    )


def render_markdown_pack(report: CustomerAcceptancePackReport) -> str:
    checks = "\n".join(f"- {check.name}: `{check.status}`" for check in report.checks)
    artifacts = "\n".join(
        f"- {artifact.name}: `{artifact.status}` / `{artifact.sha256 or '<missing-sha256>'}` / `{artifact.path}`"
        for artifact in report.artifacts
    )
    endpoints = "\n".join(f"- `{endpoint}`" for endpoint in report.api_contract["endpoints"])
    commands = "\n".join(f"- `{command}`" for command in report.operator_commands)
    checklist = "\n".join(f"- [ ] {item}" for item in report.customer_acceptance_checklist)
    limits = "\n".join(f"- {item}" for item in report.known_limits)
    codex_alignment = "\n".join(
        (
            f"- {item.capability}: `{item.xagent_pilot_v1_status}`. "
            f"{item.delivery_decision}"
        )
        for item in report.codex_alignment
    )
    sources = "\n".join(f"- {source}" for source in report.codex_alignment_summary["official_sources"])
    return (
        "# X-Agent Feishu Pilot V1 Customer Acceptance Pack\n\n"
        f"- Status: `{report.status}`\n"
        f"- Generated at: `{report.generated_at}`\n"
        f"- Pilot channel: `{report.pilot_channel}`\n"
        f"- Pilot tag: `{report.pilot_tag_name}`\n"
        f"- Pilot commit: `{report.pilot_commit_sha}`\n"
        f"- RC baseline: `{report.rc_tag_name}` / `{report.rc_commit_sha}`\n"
        f"- Operational status: `{report.operational_status}`\n"
        f"- Acceptance gate: `{report.acceptance_gate_status}`\n"
        f"- Handoff index: `{report.handoff_index_status}`\n"
        f"- Feishu inbound live: `{report.inbound_live_status}`\n"
        f"- Outbound owner gate: `{report.outbound_owner_gate_status}`\n"
        f"- Full Codex parity claimed: `{report.full_codex_parity_claimed}`\n"
        f"- Mutation performed: `{report.mutation_performed}`\n"
        f"- Outbound message sent: `{report.outbound_message_sent}`\n\n"
        "## Delivery Decision\n\n"
        "Feishu Pilot V1 is ready for first domestic commercial pilot customer acceptance when this pack status is "
        "`customer_acceptance_pack_ready`.\n\n"
        "## Read-Only API Contract\n\n"
        f"{endpoints}\n\n"
        "## Codex Alignment Boundary\n\n"
        f"{codex_alignment}\n\n"
        "## Codex Reference Sources\n\n"
        f"{sources}\n\n"
        "## Customer Acceptance Checklist\n\n"
        f"{checklist}\n\n"
        "## Operator Commands\n\n"
        f"{commands}\n\n"
        "## Archive Artifacts\n\n"
        f"{artifacts}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Known Limits\n\n"
        f"{limits}\n"
    )


def write_report(report: CustomerAcceptancePackReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_pack(report: CustomerAcceptancePackReport, output_path: Path = DEFAULT_MARKDOWN_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_pack(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--delivery-pack-doc", type=Path, default=DEFAULT_DELIVERY_PACK_DOC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_customer_acceptance_pack_report(
        report_dir=args.report_dir,
        delivery_pack_doc_path=args.delivery_pack_doc,
    )
    write_report(report, args.output)
    write_markdown_pack(report, args.markdown_output)
    print(f"Commercial pilot customer acceptance pack status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel or '<missing>'}")
    print(f"Pilot tag: {report.pilot_tag_name or '<missing>'}")
    print(f"Operational status: {report.operational_status or '<missing>'}")
    print(f"Acceptance gate: {report.acceptance_gate_status or '<missing>'}")
    print(f"Handoff index: {report.handoff_index_status or '<missing>'}")
    print(f"JSON pack written to {args.output}")
    print(f"Markdown pack written to {args.markdown_output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    print(f"Mutation performed: {report.mutation_performed}")
    print(f"Outbound message sent: {report.outbound_message_sent}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "customer_acceptance_pack_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
