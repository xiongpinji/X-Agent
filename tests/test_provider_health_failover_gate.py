from __future__ import annotations

import json

from scripts.provider_health_failover_gate import build_provider_health_failover_gate_report, write_report


def test_provider_health_failover_gate_redacts_secrets(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_API_KEY", "secret-protocol-llm-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_BASE_URL", "https://llm-gateway.x-agent.dev/v1")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "secret-deepseek-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_API_KEY", "secret-protocol-search-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_BASE_URL", "https://search-gateway.x-agent.dev/v1/query")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", "https://video-gateway.x-agent.dev/v1/generate")

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
    assert all(
        item["preflight"]["network_call_attempted"] is False
        for item in report.to_dict()["provider_matrix"]
    )
    assert {
        item["provider"]: item["preflight"]["status"]
        for item in report.to_dict()["provider_matrix"]
        if item["provider"] in {"protocol-llm", "deepseek", "protocol-search", "external-video-api"}
    } == {
        "protocol-llm": "ready_to_call",
        "deepseek": "ready_to_call",
        "protocol-search": "ready_to_call",
        "external-video-api": "ready_to_call",
    }


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
    assert all("secret_value" not in item["preflight"] for item in payload["provider_matrix"])


def test_provider_preflight_rejects_blocked_protocol_and_local_video_urls(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_API_KEY", "secret-protocol-llm-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("XAGENT_DEEPSEEK_API_KEY", "secret-deepseek-key")
    monkeypatch.setenv("XAGENT_DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_API_KEY", "secret-protocol-search-key")
    monkeypatch.setenv("XAGENT_PROTOCOL_SEARCH_BASE_URL", "https://api.tavily.com/search")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", "https://video-gateway.example/v1/generate")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_PROVIDER", "comfyui")

    report = build_provider_health_failover_gate_report()
    preflight = {item["provider"]: item["preflight"] for item in report.to_dict()["provider_matrix"]}

    assert report.status == "passed"
    assert preflight["protocol-llm"]["status"] == "rejected_config"
    assert preflight["deepseek"]["status"] == "rejected_config"
    assert preflight["protocol-search"]["status"] == "rejected_config"
    assert preflight["comfyui"]["status"] == "rejected_config"
    assert preflight["comfyui"]["configuration_error"] == "provider must not be local"
