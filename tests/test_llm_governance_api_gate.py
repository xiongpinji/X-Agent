from __future__ import annotations

import json

import pytest

from scripts.llm_governance_api_gate import build_llm_governance_gate_report, write_report


@pytest.mark.asyncio
async def test_llm_governance_gate_passes_without_external_call(monkeypatch):
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")
    monkeypatch.delenv("XAGENT_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAGENT_DEEPSEEK_API_KEY", raising=False)

    report = await build_llm_governance_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.dry_run is True
    assert report.network_mutation_performed is False
    assert checks["provider_surface_is_api_only"].status == "passed"
    assert checks["local_provider_rejected_before_network"].status == "passed"
    assert checks["auto_completion_rejected_until_costed"].status == "passed"
    assert checks["deepseek_base_url_must_be_official_external_https"].status == "passed"
    assert checks["budget_guard_rejects_before_provider_call"].status == "passed"
    assert checks["mock_completion_records_success"].status == "passed"


@pytest.mark.asyncio
async def test_llm_governance_gate_report_json_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "mock")

    output = tmp_path / "llm-governance-gate.json"
    report = await build_llm_governance_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "llm_governance_api_gate"
    assert payload["git_sha"]
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(check["name"] == "auto_completion_rejected_until_costed" for check in payload["checks"])
    assert any(check["name"] == "deepseek_base_url_must_be_official_external_https" for check in payload["checks"])
