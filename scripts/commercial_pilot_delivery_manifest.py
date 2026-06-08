#!/usr/bin/env python3
"""Build the Feishu Pilot V1 delivery manifest.

The manifest is a read-only handoff artifact. It records the required runtime
evidence reports, source scripts, tests, and customer documentation with
SHA-256 digests so the operator can verify exactly what was delivered without
committing generated `.xagent_runtime` reports.
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
DEFAULT_OUTPUT = REPORT_DIR / "commercial-pilot-delivery-manifest.json"


@dataclass(frozen=True)
class ManifestArtifact:
    name: str
    path: str
    category: str
    required: bool
    status: str
    sha256: str | None = None
    size_bytes: int | None = None
    report_status: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ManifestCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class DeliveryManifestReport:
    status: str
    generated_at: str
    evidence_type: str
    pilot_channel: str
    full_codex_parity_claimed: bool
    artifacts: list[ManifestArtifact]
    checks: list[ManifestCheck]
    next_commands: list[str]
    known_limits: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = [asdict(artifact) for artifact in self.artifacts]
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    category: str
    required: bool = True
    expected_statuses: frozenset[str] = frozenset()
    expected_evidence_type: str | None = None


DEFAULT_ARTIFACTS = (
    ArtifactSpec(
        "ops_status_report",
        REPORT_DIR / "commercial-pilot-ops-status.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ops_ready"}),
    ),
    ArtifactSpec(
        "handoff_status_report",
        REPORT_DIR / "commercial-pilot-handoff-status.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_handoff_ready"}),
    ),
    ArtifactSpec(
        "feishu_inbound_live_report",
        REPORT_DIR / "commercial-pilot-feishu-live.json",
        "runtime_report",
        expected_statuses=frozenset({"passed"}),
        expected_evidence_type="commercial_pilot_feishu_live",
    ),
    ArtifactSpec(
        "channel_readiness_report",
        REPORT_DIR / "commercial-pilot-channel-readiness.json",
        "runtime_report",
        expected_statuses=frozenset({"ready", "ready_with_owner_gates"}),
    ),
    ArtifactSpec(
        "pilot_readiness_report",
        REPORT_DIR / "commercial-pilot-readiness.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ready"}),
    ),
    ArtifactSpec(
        "refresh_chain_report",
        REPORT_DIR / "commercial-pilot-refresh-chain.json",
        "runtime_report",
        expected_statuses=frozenset({"pilot_ready"}),
    ),
    ArtifactSpec(
        "rc_delivery_status_report",
        REPORT_DIR / "rc-delivery-status.json",
        "runtime_report",
        expected_statuses=frozenset({"commercial_rc_ready"}),
    ),
    ArtifactSpec(
        "feishu_outbound_owner_gate_report",
        REPORT_DIR / "commercial-pilot-feishu-outbound-live.json",
        "runtime_report",
        required=False,
        expected_statuses=frozenset({"passed", "ready_to_execute", "owner_action_required"}),
        expected_evidence_type="commercial_pilot_feishu_outbound_live",
    ),
    ArtifactSpec("delivery_pack_doc", ROOT / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md", "source_doc"),
    ArtifactSpec(
        "acceptance_gate_script",
        ROOT / "scripts" / "commercial_pilot_acceptance_gate.py",
        "source_script",
    ),
    ArtifactSpec(
        "delivery_manifest_script",
        ROOT / "scripts" / "commercial_pilot_delivery_manifest.py",
        "source_script",
    ),
    ArtifactSpec(
        "delivery_receipt_script",
        ROOT / "scripts" / "commercial_pilot_delivery_receipt.py",
        "source_script",
    ),
    ArtifactSpec(
        "final_gate_script",
        ROOT / "scripts" / "commercial_pilot_final_gate.py",
        "source_script",
    ),
    ArtifactSpec(
        "final_handoff_script",
        ROOT / "scripts" / "run_feishu_pilot_final_handoff.ps1",
        "source_script",
    ),
    ArtifactSpec("ops_status_script", ROOT / "scripts" / "commercial_pilot_ops_status.py", "source_script"),
    ArtifactSpec("handoff_status_script", ROOT / "scripts" / "commercial_pilot_handoff_status.py", "source_script"),
    ArtifactSpec(
        "channel_readiness_script",
        ROOT / "scripts" / "commercial_pilot_channel_readiness.py",
        "source_script",
    ),
    ArtifactSpec("refresh_chain_script", ROOT / "scripts" / "commercial_pilot_refresh_chain.py", "source_script"),
    ArtifactSpec(
        "feishu_outbound_smoke_script",
        ROOT / "scripts" / "commercial_pilot_feishu_outbound_smoke.py",
        "source_script",
    ),
    ArtifactSpec(
        "acceptance_gate_tests",
        ROOT / "tests" / "test_commercial_pilot_acceptance_gate.py",
        "source_test",
    ),
    ArtifactSpec("ops_status_tests", ROOT / "tests" / "test_commercial_pilot_ops_status.py", "source_test"),
    ArtifactSpec(
        "delivery_manifest_tests",
        ROOT / "tests" / "test_commercial_pilot_delivery_manifest.py",
        "source_test",
    ),
    ArtifactSpec(
        "delivery_receipt_tests",
        ROOT / "tests" / "test_commercial_pilot_delivery_receipt.py",
        "source_test",
    ),
    ArtifactSpec(
        "final_gate_tests",
        ROOT / "tests" / "test_commercial_pilot_final_gate.py",
        "source_test",
    ),
    ArtifactSpec(
        "final_handoff_tests",
        ROOT / "tests" / "test_run_feishu_pilot_final_handoff.py",
        "source_test",
    ),
    ArtifactSpec(
        "handoff_status_tests",
        ROOT / "tests" / "test_commercial_pilot_handoff_status.py",
        "source_test",
    ),
    ArtifactSpec(
        "channel_readiness_tests",
        ROOT / "tests" / "test_commercial_pilot_channel_readiness.py",
        "source_test",
    ),
    ArtifactSpec(
        "feishu_outbound_smoke_tests",
        ROOT / "tests" / "test_commercial_pilot_feishu_outbound_smoke.py",
        "source_test",
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


def _artifact_from_spec(spec: ArtifactSpec) -> ManifestArtifact:
    sha256, size_bytes, read_error = _sha256_file(spec.path)
    if read_error:
        return ManifestArtifact(
            name=spec.name,
            path=_display_path(spec.path),
            category=spec.category,
            required=spec.required,
            status="missing" if spec.required else "optional_missing",
            error=read_error,
        )

    details: dict[str, Any] = {}
    report_status: str | None = None
    error: str | None = None
    status = "present"

    if spec.category == "runtime_report":
        payload, json_error = _read_json(spec.path)
        if json_error or payload is None:
            status = "failed" if spec.required else "preview"
            error = json_error or "runtime report is not readable"
        else:
            report_status = payload.get("status") if isinstance(payload.get("status"), str) else None
            details = {
                "report_status": report_status,
                "evidence_type": payload.get("evidence_type"),
                "full_codex_parity_claimed": payload.get("full_codex_parity_claimed"),
            }
            if payload.get("full_codex_parity_claimed") is True:
                status = "failed"
                error = "runtime report claims full Codex parity"
            elif spec.expected_statuses and report_status not in spec.expected_statuses:
                status = "failed" if spec.required else "preview"
                error = f"runtime report status {report_status!r} is not accepted"
            elif spec.expected_evidence_type and payload.get("evidence_type") != spec.expected_evidence_type:
                status = "failed" if spec.required else "preview"
                error = "runtime report evidence_type is not accepted"
            else:
                status = "passed" if spec.required else "present"

    return ManifestArtifact(
        name=spec.name,
        path=_display_path(spec.path),
        category=spec.category,
        required=spec.required,
        status=status,
        sha256=sha256,
        size_bytes=size_bytes,
        report_status=report_status,
        details=details,
        error=error,
    )


def _required_artifacts_check(artifacts: list[ManifestArtifact]) -> ManifestCheck:
    missing_or_failed = [
        artifact.name
        for artifact in artifacts
        if artifact.required and artifact.status not in {"present", "passed"}
    ]
    if missing_or_failed:
        return ManifestCheck(
            name="required_artifacts",
            status="failed",
            details={"missing_or_failed": missing_or_failed},
            error="one or more required delivery artifacts are missing or invalid",
        )
    return ManifestCheck(
        name="required_artifacts",
        status="passed",
        details={"count": sum(1 for artifact in artifacts if artifact.required)},
    )


def _ops_status_check(artifacts: list[ManifestArtifact]) -> ManifestCheck:
    ops = next((artifact for artifact in artifacts if artifact.name == "ops_status_report"), None)
    if not ops:
        return ManifestCheck(name="ops_status_report", status="failed", error="ops status artifact is not listed")
    if ops.status != "passed" or ops.report_status != "pilot_ops_ready":
        return ManifestCheck(
            name="ops_status_report",
            status="failed",
            details={"artifact_status": ops.status, "report_status": ops.report_status},
            error="operator status report is not pilot_ops_ready",
        )
    return ManifestCheck(
        name="ops_status_report",
        status="passed",
        details={"artifact_status": ops.status, "report_status": ops.report_status},
    )


def _parity_claim_check(artifacts: list[ManifestArtifact]) -> ManifestCheck:
    claimers = [
        artifact.name
        for artifact in artifacts
        if artifact.details.get("full_codex_parity_claimed") is True
    ]
    if claimers:
        return ManifestCheck(
            name="no_full_codex_parity_claim",
            status="failed",
            details={"claiming_artifacts": claimers},
            error="one or more delivery reports claim full Codex parity",
        )
    return ManifestCheck(
        name="no_full_codex_parity_claim",
        status="passed",
        details={"full_codex_parity_claimed": False},
    )


def _digest_uniqueness_check(artifacts: list[ManifestArtifact]) -> ManifestCheck:
    digested = [artifact for artifact in artifacts if artifact.sha256]
    if len(digested) != len([artifact for artifact in artifacts if artifact.status != "optional_missing"]):
        missing = [artifact.name for artifact in artifacts if artifact.status != "optional_missing" and not artifact.sha256]
        return ManifestCheck(
            name="artifact_digests",
            status="failed",
            details={"missing_digests": missing},
            error="one or more present artifacts do not have a SHA-256 digest",
        )
    return ManifestCheck(name="artifact_digests", status="passed", details={"count": len(digested)})


def _overall_status(checks: list[ManifestCheck]) -> str:
    if any(check.status == "failed" for check in checks):
        return "delivery_manifest_blocked"
    return "delivery_manifest_ready"


def _next_commands(status: str) -> list[str]:
    if status == "delivery_manifest_ready":
        return [
            "Share .xagent_runtime\\reports\\commercial-pilot-delivery-manifest.json with the pilot handoff evidence.",
            "Regenerate this manifest after refreshing any runtime evidence report or delivery script.",
        ]
    return [
        "Fix failed manifest checks before using this package for customer handoff.",
        "Regenerate commercial-pilot-ops-status.json first if the operator status is stale or blocked.",
    ]


def build_delivery_manifest_report(
    *,
    artifacts: tuple[ArtifactSpec, ...] = DEFAULT_ARTIFACTS,
    pilot_channel: str = "feishu",
) -> DeliveryManifestReport:
    artifact_reports = [_artifact_from_spec(spec) for spec in artifacts]
    checks = [
        _required_artifacts_check(artifact_reports),
        _ops_status_check(artifact_reports),
        _parity_claim_check(artifact_reports),
        _digest_uniqueness_check(artifact_reports),
    ]
    status = _overall_status(checks)
    return DeliveryManifestReport(
        status=status,
        generated_at=_utc_now(),
        evidence_type="commercial_pilot_delivery_manifest",
        pilot_channel=pilot_channel,
        full_codex_parity_claimed=False,
        artifacts=artifact_reports,
        checks=checks,
        next_commands=_next_commands(status),
        known_limits=[
            "This manifest is a read-only inventory over current delivery artifacts.",
            "Generated runtime reports under .xagent_runtime are not staged by default.",
            "Optional outbound Feishu evidence is included when present but is not required for Pilot V1 readiness.",
            "Full Codex parity is not claimed by this manifest.",
        ],
    )


def write_report(report: DeliveryManifestReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pilot-channel", default="feishu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_delivery_manifest_report(pilot_channel=args.pilot_channel)
    write_report(report, args.output)
    print(f"Commercial pilot delivery manifest status: {report.status}")
    print(f"Pilot channel: {report.pilot_channel}")
    print(f"Artifacts: {len(report.artifacts)}")
    print(f"Report written to {args.output}")
    print(f"Full Codex parity claimed: {report.full_codex_parity_claimed}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "delivery_manifest_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
