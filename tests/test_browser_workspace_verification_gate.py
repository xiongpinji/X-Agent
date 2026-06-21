from __future__ import annotations

import json

from scripts.browser_workspace_verification_gate import build_browser_workspace_verification_gate_report, write_report


def test_browser_workspace_verification_gate_passes() -> None:
    report = build_browser_workspace_verification_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.dry_run is True
    assert report.network_mutation_performed is False
    assert checks["replay_steps_are_defined"].status == "passed"
    assert checks["network_mutation_is_disabled"].status == "passed"
    assert checks["ai_exploration_is_not_final_proof"].status == "passed"


def test_browser_workspace_verification_gate_json_contract(tmp_path) -> None:
    output = tmp_path / "browser-workspace-verification-gate.json"
    report = build_browser_workspace_verification_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "browser_workspace_verification_gate"
    assert payload["git_sha"]
    assert payload["replay_steps"]
    assert all(step["network_mutation_allowed"] is False for step in payload["replay_steps"])
    assert all("npm run build" not in step["command"] for step in payload["replay_steps"])
