from __future__ import annotations

import json

import pytest

from scripts.creative_studio_external_video_gate import (
    build_creative_video_gate_report,
    write_report,
)


@pytest.mark.asyncio
async def test_creative_video_gate_passes_without_external_call(monkeypatch):
    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_API_URL", raising=False)
    monkeypatch.delenv("XAGENT_CREATIVE_VIDEO_API_KEY", raising=False)

    report = await build_creative_video_gate_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "passed"
    assert report.dry_run is True
    assert report.mutation_performed is False
    assert report.network_mutation_performed is False
    assert report.full_release_claimed is False
    assert report.provider_status["provider_api_call_attempted"] is False
    assert checks["provider_status_redacted"].status == "passed"
    assert checks["adapter_blocks_without_human_review"].status == "passed"
    assert checks["video_workflow_endpoint_is_local_opt_in"].status == "passed"
    assert checks["workflow_defaults_to_dry_run"].status == "passed"
    assert checks["workflow_execution_caps_max_shots_behavior"].status == "passed"
    assert checks["workflow_requires_review_before_execution"].status == "passed"
    assert checks["default_tool_registry_excludes_creative_tools"].status == "passed"
    assert checks["main_app_does_not_mount_creative_studio"].status == "passed"
    assert checks["frontend_client_is_api_only"].status == "passed"


@pytest.mark.asyncio
async def test_creative_video_gate_report_json_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_URL", "https://video.example/generate")
    monkeypatch.setenv("XAGENT_CREATIVE_VIDEO_API_KEY", "secret-video-key")

    output = tmp_path / "creative-video-gate.json"
    report = await build_creative_video_gate_report()
    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["evidence_type"] == "creative_studio_external_video_api_only_gate"
    assert payload["provider_status"]["configured"] is True
    assert payload["provider_status"]["api_key_fingerprint"]
    assert "secret-video-key" not in json.dumps(payload)
    assert "https://video.example/generate" not in json.dumps(payload)
    assert any(check["name"] == "frontend_contract_requires_review" for check in payload["checks"])
    assert any(check["name"] == "frontend_contract_exposes_video_workflow" for check in payload["checks"])
