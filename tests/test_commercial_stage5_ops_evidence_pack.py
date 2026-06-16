from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_stage5_ops_evidence_pack import (
    OpsEvidenceSource,
    build_ops_evidence_pack,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "a2b9b7fabc694b9f7d2a254019dacac64d89a20f"
OTHER_SHA = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"
REQUIRED_NAMES = {
    "slo_sla",
    "alert_routing",
    "backup_restore_rehearsal",
    "incident_process",
    "support_escalation",
    "cost_capacity_guardrails",
    "on_call_ownership",
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sources(report_dir: Path) -> list[OpsEvidenceSource]:
    return [
        OpsEvidenceSource("slo_sla", report_dir / "slo.json"),
        OpsEvidenceSource("alert_routing", report_dir / "alerts.json"),
        OpsEvidenceSource("backup_restore_rehearsal", report_dir / "backup.json"),
        OpsEvidenceSource("incident_process", report_dir / "incident.json"),
        OpsEvidenceSource("support_escalation", report_dir / "support.json"),
        OpsEvidenceSource("cost_capacity_guardrails", report_dir / "cost-capacity.json"),
        OpsEvidenceSource("on_call_ownership", report_dir / "on-call.json"),
    ]


def _ready_payload(name: str, *, release_sha: str = HEAD, status: str = "ready") -> dict[str, object]:
    return {
        "status": status,
        "release_sha": release_sha,
        "current_head_sha": release_sha,
        "summary": f"{name} evidence fixture",
        "evidence_refs": [f"docs/{name}.md"],
        "ga_ready": False,
        "production_ready": False,
        "full_commercial_delivery_complete": False,
        "full_codex_parity_claimed": False,
    }


def _write_all_ready(report_dir: Path, *, release_sha: str = HEAD) -> None:
    for source in _sources(report_dir):
        _write_json(source.path, _ready_payload(source.name, release_sha=release_sha))


def test_ops_evidence_pack_blocks_when_all_evidence_missing(tmp_path: Path) -> None:
    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_evidence_blocked"
    assert report.controlled_commercial_pilot_ops_ready is False
    assert report.release_sha == HEAD
    assert set(report.missing_or_blocked_evidence) == REQUIRED_NAMES
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_ops_evidence_pack_accepts_complete_ready_fixture(tmp_path: Path) -> None:
    _write_all_ready(tmp_path)

    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "controlled_commercial_pilot_ops_ready"
    assert report.controlled_commercial_pilot_ops_ready is True
    assert report.current_head_sha == HEAD
    assert report.release_sha == HEAD
    assert report.missing_or_blocked_evidence == []
    assert all(item.ready for item in report.evidence)
    assert {check.status for check in report.checks} == {"passed"}
    assert report.claim_boundary["allowed"] == "controlled commercial pilot readiness only"


def test_ops_evidence_pack_blocks_when_one_required_file_missing(tmp_path: Path) -> None:
    _write_all_ready(tmp_path)
    (tmp_path / "support.json").unlink()

    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_evidence_blocked"
    assert report.missing_or_blocked_evidence == ["support_escalation"]
    support = next(item for item in report.evidence if item.name == "support_escalation")
    assert any("missing evidence file" in error for error in support.errors)


def test_ops_evidence_pack_blocks_mismatched_release_sha(tmp_path: Path) -> None:
    _write_all_ready(tmp_path, release_sha=OTHER_SHA)

    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_evidence_blocked"
    assert set(report.missing_or_blocked_evidence) == REQUIRED_NAMES
    sha_check = next(check for check in report.checks if check.name == "evidence_bound_to_release_sha")
    assert sha_check.status == "failed"


def test_ops_evidence_pack_blocks_forbidden_claims(tmp_path: Path) -> None:
    _write_all_ready(tmp_path)
    _write_json(
        tmp_path / "slo.json",
        _ready_payload("slo_sla") | {"production_ready": True},
    )

    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_evidence_blocked"
    assert report.missing_or_blocked_evidence == ["slo_sla"]
    slo = next(item for item in report.evidence if item.name == "slo_sla")
    assert any("forbidden readiness claim" in error for error in slo.errors)


def test_ops_evidence_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_all_ready(tmp_path)
    report = build_ops_evidence_pack(
        report_dir=tmp_path,
        sources=_sources(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )
    output_json = tmp_path / "stage5-ops-support-evidence-pack-20260615.json"
    output_md = tmp_path / "stage5-ops-support-evidence-pack-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "controlled_commercial_pilot_ops_ready"
    assert payload["release_sha"] == HEAD
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Ops / Support Evidence Pack" in markdown
    assert "controlled commercial pilot readiness only" in markdown
    assert render_markdown_report(report) == markdown
