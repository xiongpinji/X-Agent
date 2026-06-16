from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_security_compliance_gate import (
    SecurityEvidenceSpec,
    build_security_compliance_gate,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "f1e89ffd6bbb3a35b175b9f0ff0ce41873bf77c8"
OTHER_SHA = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path) -> list[SecurityEvidenceSpec]:
    return [
        SecurityEvidenceSpec("security_scanner_bandit", report_dir / "bandit.json"),
        SecurityEvidenceSpec("dependency_audit", report_dir / "dependency.json"),
        SecurityEvidenceSpec("secret_scan", report_dir / "secrets.json"),
        SecurityEvidenceSpec("rbac_tenant_isolation", report_dir / "rbac.json"),
        SecurityEvidenceSpec("audit_log", report_dir / "audit-log.json"),
        SecurityEvidenceSpec("retention_compliance_signoff", report_dir / "retention.json"),
        SecurityEvidenceSpec("risk_acceptance_register", report_dir / "risk.json"),
    ]


def _base_payload(*, release_sha: str = HEAD) -> dict[str, object]:
    return {
        "status": "passed",
        "current_head_sha": release_sha,
        "release_sha": release_sha,
        "findings": [],
        "secret_leakage_detected": False,
    }


def _write_complete_evidence(report_dir: Path, *, release_sha: str = HEAD) -> None:
    for spec in _specs(report_dir):
        payload = _base_payload(release_sha=release_sha)
        if spec.name == "risk_acceptance_register":
            payload["risk_acceptance_recorded"] = True
            payload["accepted_risks"] = [{"id": "RISK-1", "decision": "accepted for release"}]
        _write_json(spec.path, payload)


def test_security_compliance_gate_blocks_when_all_evidence_missing(tmp_path: Path) -> None:
    report = build_security_compliance_gate(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "security_compliance_blocked"
    assert report.security_compliance_ready is False
    assert set(report.missing_or_blocked_evidence) == {spec.name for spec in _specs(tmp_path)}
    assert all(item.ready is False for item in report.required_evidence)


def test_security_compliance_gate_accepts_complete_temporary_evidence(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)

    report = build_security_compliance_gate(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "security_compliance_ready"
    assert report.security_compliance_ready is True
    assert report.current_head_sha == HEAD
    assert report.release_sha == HEAD
    assert report.missing_or_blocked_evidence == []
    assert {check.status for check in report.checks} == {"passed"}
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_security_compliance_gate_blocks_unresolved_critical_or_high(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    _write_json(
        tmp_path / "dependency.json",
        {
            **_base_payload(),
            "vulnerabilities": [
                {"id": "CVE-0001", "severity": "critical", "status": "open", "title": "blocked vuln"},
                {"id": "CVE-0002", "severity": "high", "status": "resolved"},
            ],
        },
    )

    report = build_security_compliance_gate(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "security_compliance_blocked"
    assert "dependency_audit" in report.missing_or_blocked_evidence
    finding_check = next(check for check in report.checks if check.name == "no_unresolved_high_or_critical_findings")
    assert finding_check.status == "failed"
    assert "dependency_audit" in finding_check.details["unresolved_blocking_findings"]


def test_security_compliance_gate_blocks_sha_mismatch(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    payload = _base_payload(release_sha=OTHER_SHA)
    _write_json(tmp_path / "bandit.json", payload)

    report = build_security_compliance_gate(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == "security_compliance_blocked"
    assert "security_scanner_bandit" in report.missing_or_blocked_evidence
    sha_check = next(check for check in report.checks if check.name == "evidence_bound_to_current_head_and_release_sha")
    assert sha_check.status == "failed"


def test_security_compliance_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    report = build_security_compliance_gate(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    output_json = tmp_path / "stage5-security-compliance-gate-20260615.json"
    output_md = tmp_path / "stage5-security-compliance-gate-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "security_compliance_ready"
    assert payload["current_head_sha"] == HEAD
    assert payload["release_sha"] == HEAD
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Security Compliance Gate" in markdown
    assert "security_compliance_ready" in markdown
    assert render_markdown_report(report) == markdown
