from __future__ import annotations

import json

from scripts.provider_health_failover_gate import build_provider_health_failover_gate_report, write_report


def test_provider_health_failover_gate_redacts_secrets(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_API_KEY", "secret-protocol-llm-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_BASE_URL", "https://llm.gateway.example/v1")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "secret-deepseek-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_API_KEY", "secret-protocol-search-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_BASE_URL", "https://search.gateway.example/v1/query")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", "https://api.xagent-protocol.invalid/v1/video/generate")

    report = build_provider_health_failover_gate_report()
    payload = json.dumps(report.to_dict(), ensure_ascii=False)
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert "secret-protocol-llm-key" not in payload
    assert "secret-protocol-search-key" not in payload
    assert "secret-deepseek-key" not in payload
    assert "secret-video-key" not in payload
    assert checks["provider_matrix_is_api_only"].status == "passed"
    assert checks["provider_secrets_are_redacted"].status == "passed"
    assert checks["mock_fallback_is_available"].status == "passed"
    assert checks["creative_video_provider_is_covered"].status == "passed"


def test_provider_health_failover_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "provider-health-failover-gate.json"
    report = build_provider_health_failover_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "provider_health_failover_gate"
    assert payload["dry_run"] is True
    assert payload["git_sha"]
    assert payload["network_mutation_performed"] is False
    assert any(item["provider"] == "mock" and item["configured"] is True for item in payload["provider_matrix"])
    assert any(item["provider"] == "protocol-llm" for item in payload["provider_matrix"])
    assert any(item["provider"] == "protocol-search" for item in payload["provider_matrix"])
    assert any(item["capability"] == "creative-video" for item in payload["provider_matrix"])
