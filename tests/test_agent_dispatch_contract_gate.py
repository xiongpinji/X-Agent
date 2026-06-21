from __future__ import annotations

import json

from backend.app.core.agent_dispatch_contracts import build_default_second_batch_dispatch_contract
from scripts.agent_dispatch_contract_gate import build_agent_dispatch_contract_gate_report, write_report


def test_default_second_batch_dispatch_contract_validates() -> None:
    contract = build_default_second_batch_dispatch_contract()
    validation = contract.validate()

    assert validation["valid"] is True
    assert validation["handoff_count"] == 2
    assert validation["fan_in_required"] is True
    assert validation["trace_required"] is True
    assert validation["audit_required"] is True


def test_agent_dispatch_contract_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "agent-dispatch-contract-gate.json"
    report = build_agent_dispatch_contract_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "agent_dispatch_contract_gate"
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(check["name"] == "fan_in_trace_and_audit_required" for check in payload["checks"])
