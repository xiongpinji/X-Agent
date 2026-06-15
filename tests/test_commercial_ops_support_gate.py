from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_ops_support_gate import (
    OpsSupportEvidenceSpec,
    build_ops_support_gate_report,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "f1e89ffd6bbb3a35b175b9f0ff0ce41873bf77c8"
OTHER_SHA = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path) -> list[OpsSupportEvidenceSpec]:
    return [
        OpsSupportEvidenceSpec("slo_sla", report_dir / "slo.json"),
        OpsSupportEvidenceSpec("alert_routing", report_dir / "alerts.json"),
        OpsSupportEvidenceSpec("backup_restore_rehearsal", report_dir / "backup.json"),
        OpsSupportEvidenceSpec("incident_process", report_dir / "incident.json"),
        OpsSupportEvidenceSpec("support_escalation", report_dir / "support.json"),
        OpsSupportEvidenceSpec("cost_capacity_guardrails", report_dir / "cost-capacity.json"),
        OpsSupportEvidenceSpec("on_call_ownership", report_dir / "on-call.json"),
    ]


def _write_all_evidence(report_dir: Path, *, release_sha: str = HEAD, status: str = "ready") -> None:
    for spec in _specs(report_dir):
        _write_json(
            spec.path,
            {
                "status": status,
                "current_head_sha": release_sha,
                "release_sha": release_sha,
                "evidence_refs": [f"{spec.name}.md"],
                "mutation_performed": False,
                "outbound_message_sent": False,
                "deploy_tag_release_performed": False,
            },
        )


def test_ops_support_gate_blocks_when_all_evidence_missing(tmp_path: Path) -> None:
    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_blocked"
    assert report.ops_support_ready is False
    assert report.release_sha == HEAD
    assert set(report.missing_or_blocked_evidence) == {
        "slo_sla",
        "alert_routing",
        "backup_restore_rehearsal",
        "incident_process",
        "support_escalation",
        "cost_capacity_guardrails",
        "on_call_ownership",
    }
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_ops_support_gate_accepts_complete_temporary_evidence(tmp_path: Path) -> None:
    _write_all_evidence(tmp_path)

    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_ready"
    assert report.ops_support_ready is True
    assert report.current_head_sha == HEAD
    assert report.release_sha == HEAD
    assert report.missing_or_blocked_evidence == []
    assert all(evidence.ready for evidence in report.required_evidence)
    assert {check.status for check in report.checks} == {"passed"}


def test_ops_support_gate_blocks_when_any_required_evidence_blocked(tmp_path: Path) -> None:
    _write_all_evidence(tmp_path)
    _write_json(
        tmp_path / "incident.json",
        {
            "status": "blocked",
            "current_head_sha": HEAD,
            "release_sha": HEAD,
        },
    )

    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_blocked"
    assert report.ops_support_ready is False
    assert "incident_process" in report.missing_or_blocked_evidence
    incident = next(item for item in report.required_evidence if item.name == "incident_process")
    assert incident.error is not None
    assert "expected status" in incident.error


def test_ops_support_gate_blocks_sha_mismatch(tmp_path: Path) -> None:
    _write_all_evidence(tmp_path, release_sha=OTHER_SHA)

    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )

    assert report.status == "ops_support_blocked"
    assert set(report.missing_or_blocked_evidence) == {
        "slo_sla",
        "alert_routing",
        "backup_restore_rehearsal",
        "incident_process",
        "support_escalation",
        "cost_capacity_guardrails",
        "on_call_ownership",
    }
    sha_check = next(check for check in report.checks if check.name == "required_evidence_bound_to_current_head")
    assert sha_check.status == "failed"


def test_ops_support_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_all_evidence(tmp_path)
    report = build_ops_support_gate_report(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        root=tmp_path,
    )
    output_json = tmp_path / "stage5-ops-support-gate-20260615.json"
    output_md = tmp_path / "stage5-ops-support-gate-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "ops_support_ready"
    assert payload["current_head_sha"] == HEAD
    assert payload["release_sha"] == HEAD
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Ops / Support Gate" in markdown
    assert "ops_support_ready" in markdown
    assert render_markdown_report(report) == markdown
