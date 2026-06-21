from __future__ import annotations

import json

from scripts.second_batch_quality_gate import build_second_batch_quality_gate_report, write_report


def test_second_batch_quality_gate_passes_with_existing_reports() -> None:
    report = build_second_batch_quality_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.evidence_type == "second_batch_quality_gate"
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.full_release_claimed is False
    assert checks["capability_reports_present"].status == "passed"
    assert checks["capability_reports_passed"].status == "passed"
    assert checks["capability_reports_do_not_mutate"].status == "passed"
    assert checks["required_capability_surfaces_covered"].status == "passed"


def test_second_batch_quality_gate_report_json_contract(tmp_path) -> None:
    output = tmp_path / "second-batch-quality-gate.json"
    report = build_second_batch_quality_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "second_batch_quality_gate"
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert len(payload["capability_reports"]) >= 2
    assert any(item["evidence_type"] == "llm_governance_api_gate" for item in payload["capability_reports"])
    assert any(item["evidence_type"] == "rag_governance_api_gate" for item in payload["capability_reports"])
    assert any(item["evidence_type"] == "agent_dispatch_contract_gate" for item in payload["capability_reports"])
    assert any(item["evidence_type"] == "browser_workspace_verification_gate" for item in payload["capability_reports"])
    assert any(item["evidence_type"] == "provider_health_failover_gate" for item in payload["capability_reports"])
    assert any(
        item["evidence_type"] == "creative_studio_external_video_api_only_gate"
        for item in payload["capability_reports"]
    )
