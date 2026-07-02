from __future__ import annotations

import json

from scripts.second_batch_capability_manifest_gate import (
    build_second_batch_capability_manifest_gate_report,
    write_report,
)


def test_second_batch_capability_manifest_gate_passes() -> None:
    report = build_second_batch_capability_manifest_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.evidence_type == "second_batch_capability_manifest_gate"
    assert report.dry_run is True
    assert report.network_mutation_performed is False
    assert checks["route_is_mounted"].status == "passed"
    assert checks["endpoint_requires_audit_read"].status == "passed"
    assert checks["manifest_is_api_first_without_local_models"].status == "passed"
    assert checks["required_evidence_types_are_declared"].status == "passed"


def test_second_batch_capability_manifest_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "second-batch-capability-manifest-gate.json"
    report = build_second_batch_capability_manifest_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "second_batch_capability_manifest_gate"
    assert payload["git_sha"]
    assert payload["dry_run"] is True
    assert payload["network_mutation_performed"] is False
    assert any(check["name"] == "runtime_surfaces_are_declared" for check in payload["checks"])
