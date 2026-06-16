from __future__ import annotations

from pathlib import Path


SCRIPT = Path("scripts/run_feishu_pilot_final_handoff.ps1")


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_final_handoff_script_uses_powershell_safe_wrapper_contract() -> None:
    text = _script_text()

    assert text.startswith("param(")
    assert "Set-StrictMode -Version Latest" in text
    assert '$ErrorActionPreference = "Stop"' in text
    assert "Push-Location $Root" in text
    assert "Pop-Location" in text
    assert "${LASTEXITCODE}" in text


def test_final_handoff_script_runs_final_gate_before_receipt() -> None:
    text = _script_text()

    final_gate_index = text.index("commercial_pilot_final_gate.py")
    receipt_index = text.index("commercial_pilot_delivery_receipt.py")

    assert final_gate_index < receipt_index


def test_final_handoff_script_wires_receipt_to_refreshed_gate_outputs() -> None:
    text = _script_text()

    assert "--output $FinalGateOutput" in text
    assert "--ops-output $OpsOutput" in text
    assert "--manifest-output $ManifestOutput" in text
    assert "--final-gate-report $FinalGateOutput" in text
    assert "--ops-status-report $OpsOutput" in text
    assert "--delivery-manifest-report $ManifestOutput" in text
    assert "--markdown-output $ReceiptMarkdownOutput" in text


def test_final_handoff_script_does_not_include_mutating_follow_up_flags() -> None:
    text = _script_text().lower()

    assert "--execute" not in text
    assert "--owner-approved" not in text
    assert "git tag" not in text
    assert "git push" not in text
