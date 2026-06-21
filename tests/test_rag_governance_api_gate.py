from __future__ import annotations

import json

import pytest

from scripts.rag_governance_api_gate import build_rag_governance_gate_report, write_report


@pytest.mark.asyncio
async def test_rag_governance_gate_passes_without_external_call() -> None:
    report = await build_rag_governance_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.dry_run is True
    assert report.network_mutation_performed is False
    assert checks["provider_surface_is_api_only"].status == "passed"
    assert checks["local_provider_rejected_before_retrieval"].status == "passed"
    assert checks["budget_guard_rejects_before_provider_use"].status == "passed"
    assert checks["tenant_scope_is_enforced"].status == "passed"
    assert checks["mock_results_are_tenant_scoped"].status == "passed"


@pytest.mark.asyncio
async def test_rag_governance_gate_report_json_contract(tmp_path) -> None:
    output = tmp_path / "rag-governance-gate.json"
    report = await build_rag_governance_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "rag_governance_api_gate"
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(check["name"] == "tenant_scope_is_enforced" for check in payload["checks"])
    assert any(check["name"] == "mock_results_are_tenant_scoped" for check in payload["checks"])
