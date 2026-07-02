from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_stage5_security_evidence_pack import (
    BLOCKED_STATUS,
    READY_STATUS,
    EvidenceSpec,
    build_stage5_security_evidence_pack,
    render_markdown_report,
    write_markdown_report,
    write_report,
)

HEAD = "a2b9b7fabc694b9f7d2a254019dacac64d89a20f"
OTHER_SHA = "62f567982fc33b6f8d72c4f3a8d8e192698d0c92"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _specs(report_dir: Path) -> list[EvidenceSpec]:
    return [
        EvidenceSpec("security_scanner_bandit", report_dir / "bandit.json"),
        EvidenceSpec("dependency_audit", report_dir / "dependency.json"),
        EvidenceSpec("secret_scan", report_dir / "secrets.json"),
        EvidenceSpec("rbac_tenant_isolation", report_dir / "rbac.json"),
        EvidenceSpec("audit_log", report_dir / "audit-log.json"),
        EvidenceSpec("retention_compliance_signoff", report_dir / "retention.json"),
        EvidenceSpec("risk_acceptance_register", report_dir / "risk.json"),
    ]


def _base_payload(*, release_sha: str = HEAD) -> dict[str, object]:
    return {
        "status": "passed",
        "generated_at": "2026-06-15T00:00:00Z",
        "current_head_sha": release_sha,
        "release_sha": release_sha,
        "findings": [],
        "secret_leakage_detected": False,
        "summary": {"result": "clean"},
    }


def _write_complete_evidence(report_dir: Path, *, release_sha: str = HEAD) -> None:
    for spec in _specs(report_dir):
        payload = _base_payload(release_sha=release_sha)
        if spec.name == "risk_acceptance_register":
            payload["risk_acceptance_recorded"] = True
            payload["accepted_risks"] = [{"id": "RISK-1", "decision": "accepted for pilot"}]
        _write_json(spec.path, payload)


def test_stage5_security_evidence_pack_blocks_when_all_evidence_missing(tmp_path: Path) -> None:
    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == BLOCKED_STATUS
    assert report.security_evidence_ready is False
    assert set(report.missing_or_blocked_evidence) == {spec.name for spec in _specs(tmp_path)}
    assert all(item.ready is False for item in report.required_evidence)


def test_stage5_security_evidence_pack_accepts_complete_local_evidence(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)

    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == READY_STATUS
    assert report.readiness_scope == "controlled_commercial_pilot_readiness"
    assert report.security_evidence_ready is True
    assert report.missing_or_blocked_evidence == []
    assert {check.status for check in report.checks} == {"passed"}
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert report.deploy_tag_release_performed is False


def test_stage5_security_evidence_pack_blocks_unresolved_high_or_critical(tmp_path: Path) -> None:
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

    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == BLOCKED_STATUS
    assert "dependency_audit" in report.missing_or_blocked_evidence
    finding_check = next(check for check in report.checks if check.name == "no_unresolved_high_or_critical_findings")
    assert finding_check.status == "failed"
    assert finding_check.details["blocking_evidence_sources"] == ["dependency_audit"]


def test_stage5_security_evidence_pack_blocks_sha_mismatch(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    _write_json(tmp_path / "bandit.json", _base_payload(release_sha=OTHER_SHA))

    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )

    assert report.status == BLOCKED_STATUS
    assert "security_scanner_bandit" in report.missing_or_blocked_evidence
    sha_check = next(check for check in report.checks if check.name == "evidence_bound_to_current_head_and_release_sha")
    assert sha_check.status == "failed"


def test_stage5_security_evidence_pack_redacts_secret_values_in_outputs(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    secret_value = "gh" + "p_1234567890abcdefghijklmnopqrstuvwxyz"
    _write_json(
        tmp_path / "secrets.json",
        {
            **_base_payload(),
            "summary": {
                "token": secret_value,
                "message": f"found token={secret_value}",
                "safe": "scanner completed",
            },
            "secret_leakage_detected": False,
        },
    )
    output_json = tmp_path / "pack.json"
    output_md = tmp_path / "pack.md"

    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    write_report(report, output_json)
    write_markdown_report(report, output_md)

    encoded = output_json.read_text(encoding="utf-8") + output_md.read_text(encoding="utf-8")
    assert report.status == READY_STATUS
    assert secret_value not in encoded
    assert "<redacted" in encoded
    assert "scanner completed" in encoded


def test_stage5_security_evidence_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_complete_evidence(tmp_path)
    report = build_stage5_security_evidence_pack(
        report_dir=tmp_path,
        required_specs=_specs(tmp_path),
        current_head_sha=HEAD,
        release_sha=HEAD,
    )
    output_json = tmp_path / "stage5-security-evidence-pack-20260615.json"
    output_md = tmp_path / "stage5-security-evidence-pack-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == READY_STATUS
    assert payload["readiness_scope"] == "controlled_commercial_pilot_readiness"
    assert payload["mutation_performed"] is False
    assert payload["outbound_message_sent"] is False
    assert payload["deploy_tag_release_performed"] is False
    assert "# Stage 5 Security Evidence Pack" in markdown
    assert READY_STATUS in markdown
    assert render_markdown_report(report) == markdown
