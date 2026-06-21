from __future__ import annotations

import json

from scripts.provider_health_failover_gate import build_provider_health_failover_gate_report, write_report


def test_provider_health_failover_gate_redacts_secrets(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_OPENAI_API_KEY", "secret-openai-key")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "secret-deepseek-key")

    report = build_provider_health_failover_gate_report()
    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert "secret-openai-key" not in payload
    assert "secret-deepseek-key" not in payload
    assert checks["provider_matrix_is_api_only"].status == "passed"
    assert checks["provider_secrets_are_redacted"].status == "passed"
    assert checks["mock_fallback_is_available"].status == "passed"


def test_provider_health_failover_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "provider-health-failover-gate.json"
    report = build_provider_health_failover_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "provider_health_failover_gate"
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(item["provider"] == "mock" and item["configured"] is True for item in payload["provider_matrix"])
