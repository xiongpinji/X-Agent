from __future__ import annotations

import json

from scripts.provider_preflight_api_gate import build_provider_preflight_api_gate_report, write_report


def test_provider_preflight_api_gate_passes_without_external_call() -> None:
    report = build_provider_preflight_api_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.evidence_type == "provider_preflight_api_gate"
    assert report.dry_run is True
    assert report.network_mutation_performed is False
    assert checks["endpoint_requires_audit_read"].status == "passed"
    assert checks["runtime_api_uses_core_not_scripts"].status == "passed"
    assert checks["provider_secrets_are_redacted"].status == "passed"
    assert checks["preflight_does_not_call_network"].status == "passed"
    assert checks["rejected_provider_urls_are_blocked"].status == "passed"


def test_provider_preflight_api_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "provider-preflight-api-gate.json"
    report = build_provider_preflight_api_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "provider_preflight_api_gate"
    assert payload["endpoint"] == "/api/v1/providers/preflight"
    assert payload["git_sha"]
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(check["name"] == "endpoint_requires_audit_read" for check in payload["checks"])
    assert any(item["provider"] == "deepseek" for item in payload["providers"])
