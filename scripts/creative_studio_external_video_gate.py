#!/usr/bin/env python3
"""Validate the Creative Studio external-video API-only delivery contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.core.creative_studio.adapters import external_video_api_status
from backend.app.core.creative_studio.adapters import external_video_api_error_reason
from backend.app.core.creative_studio.storyboard import Storyboard, Shot
from backend.app.core.creative_studio.workflow import run_external_video_workflow

REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_OUTPUT = REPORT_DIR / "creative-studio-external-video-gate.json"


@dataclass(frozen=True)
class CreativeVideoGateCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class CreativeVideoGateReport:
    status: str
    generated_at: str
    evidence_type: str
    dry_run: bool
    mutation_performed: bool
    network_mutation_performed: bool
    full_release_claimed: bool
    git_sha: str
    provider_status: dict[str, Any]
    checks: list[CreativeVideoGateCheck]
    known_limits: list[str]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _current_git_sha(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check(name: str, ok: bool, *, details: dict[str, Any] | None = None, error: str) -> CreativeVideoGateCheck:
    return CreativeVideoGateCheck(
        name=name,
        status="passed" if ok else "failed",
        details=details or {},
        error=None if ok else error,
    )


async def _workflow_execution_cap_check() -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    storyboard = Storyboard(brief="external video workflow", genre="都市")
    storyboard.shots = [
        Shot(shot_id=f"S{i:02d}", duration_seconds=4, video_prompt="slow push")
        for i in range(12)
    ]

    async def runner(**kwargs):
        calls.append(kwargs)
        return {
            "success": True,
            "output_path": "https://cdn.example/shot.mp4",
            "provider": "seedance",
            "error": None,
            "metadata": {"provider_api_call_attempted": True},
        }

    result = await run_external_video_workflow(
        storyboard,
        execute=True,
        human_review_approved=True,
        max_shots=99,
        shot_video_runner=runner,
    )
    return {
        "selected_shot_count": result.get("selected_shot_count"),
        "result_count": len(result.get("results", [])),
        "runner_call_count": len(calls),
    }


async def build_creative_video_gate_report(root: Path = ROOT) -> CreativeVideoGateReport:
    api_source = _read(root / "backend/app/api/creative_studio.py")
    adapters_source = _read(root / "backend/app/core/creative_studio/adapters.py")
    wiring_source = _read(root / "backend/app/core/creative_studio/wiring.py")
    workflow_source = _read(root / "backend/app/core/creative_studio/workflow.py")
    main_source = _read(root / "backend/app/main.py")
    tools_source = _read(root / "backend/app/core/tools.py")
    frontend_contract_source = _read(root / "frontend/src/panda/api/creativeStudioApiContracts.ts")
    frontend_client_source = _read(root / "frontend/src/panda/api/creativeStudioClient.ts")
    provider_status = external_video_api_status()
    workflow_cap = await _workflow_execution_cap_check()
    rejected_video_urls = [
        external_video_api_error_reason(api_url="http://localhost:8188/prompt", provider="external-video-api"),
        external_video_api_error_reason(api_url="https://127.0.0.1/prompt", provider="external-video-api"),
        external_video_api_error_reason(api_url="https://api.example/video", provider="comfyui"),
    ]

    checks = [
        _check(
            "provider_status_redacted",
            "api_key" not in provider_status and "api_url" not in provider_status,
            details={"keys": sorted(provider_status.keys())},
            error="provider status exposes raw api_key or api_url",
        ),
        _check(
            "provider_status_does_not_attempt_call",
            provider_status.get("provider_api_call_attempted") is False,
            details={"provider_api_call_attempted": provider_status.get("provider_api_call_attempted")},
            error="provider status attempted an external provider call",
        ),
        _check(
            "provider_url_must_be_external_https",
            "external_video_api_error_reason" in adapters_source
            and "external_https_url_error_reason" in adapters_source
            and all(rejected_video_urls),
            details={"rejected_reasons": rejected_video_urls},
            error="external video provider can be configured with local, non-HTTPS, or ComfyUI endpoints",
        ),
        _check(
            "human_review_required_by_api_contract",
            "human_review_approved: bool = False" in api_source
            and "human_review_approved=body.human_review_approved" in api_source,
            error="shot-video API does not expose/pass explicit human_review_approved",
        ),
        _check(
            "video_workflow_endpoint_is_local_opt_in",
            '"/video-workflow"' in api_source
            and "execute: bool = False" in api_source
            and "run_external_video_workflow" in api_source,
            error="Creative Studio does not expose a local opt-in video workflow endpoint",
        ),
        _check(
            "reviewed_execution_requires_control_scope",
            'enforce_scope(principal, "workflow:control")' in api_source
            and "_enforce_creative_video_execution_scope" in api_source,
            error="reviewed external video execution is not protected by a server-side control scope",
        ),
        _check(
            "adapter_blocks_without_human_review",
            "human_review_required_before_video_provider_call" in adapters_source
            and '"provider_api_call_attempted": False' in adapters_source,
            error="external video adapter does not fail closed before human review",
        ),
        _check(
            "adapter_does_not_send_local_output_path",
            '"output_path": request.output_path' not in adapters_source,
            error="external video adapter payload sends local output_path to provider",
        ),
        _check(
            "default_tool_registry_excludes_creative_tools",
            "register_creative_tools" not in tools_source,
            error="build_default_tool_registry imports or registers Creative Studio tools",
        ),
        _check(
            "main_app_does_not_mount_creative_studio",
            "creative_studio" not in main_source,
            error="main app mounts Creative Studio router despite RC exclusion",
        ),
        _check(
            "video_tool_is_high_risk",
            '"generate_shot_video"' in wiring_source and "risk_level=RiskLevel.HIGH" in wiring_source,
            error="generate_shot_video is not registered as a high-risk explicit tool",
        ),
        _check(
            "workflow_defaults_to_dry_run",
            "execute: bool = False" in workflow_source
            and '"workflow_status": "dry_run"' in workflow_source
            and '"provider_api_call_attempted": False' in workflow_source,
            error="external video workflow does not default to dry-run without provider calls",
        ),
        _check(
            "workflow_caps_max_shots",
            "_shot_limit(max_shots)" in workflow_source
            and "max_shots: int = Field(default=8, ge=0, le=8)" in api_source,
            error="external video workflow does not cap max_shots before execution",
        ),
        _check(
            "workflow_execution_caps_max_shots_behavior",
            workflow_cap["selected_shot_count"] == 8
            and workflow_cap["result_count"] == 8
            and workflow_cap["runner_call_count"] == 8,
            details=workflow_cap,
            error="external video workflow execution exceeded the 8-shot cap",
        ),
        _check(
            "workflow_requires_review_before_execution",
            "human_review_required_before_video_provider_call" in workflow_source
            and "if not human_review_approved" in workflow_source,
            error="external video workflow can execute without human review",
        ),
        _check(
            "frontend_contract_is_api_only",
            "react" not in frontend_contract_source.lower() and "axios" not in frontend_contract_source.lower(),
            error="Creative Studio frontend contract imports UI or transport dependencies",
        ),
        _check(
            "frontend_client_is_api_only",
            "createCreativeStudioFetchClient" in frontend_client_source
            and "getAuthHeaders" in frontend_client_source
            and "axios" not in frontend_client_source.lower()
            and "react" not in frontend_client_source.lower(),
            error="Creative Studio frontend client is missing auth headers or has UI/axios coupling",
        ),
        _check(
            "frontend_contract_requires_review",
            "human_review_approved: boolean" in frontend_contract_source
            and "requires_human_review: true" in frontend_contract_source,
            error="Creative Studio frontend contract does not require explicit human review",
        ),
        _check(
            "frontend_contract_exposes_video_workflow",
            "ApiCreativeStudioVideoWorkflowRequest" in frontend_contract_source
            and "videoWorkflow: '/api/v1/creative-studio/video-workflow'" in frontend_contract_source,
            error="Creative Studio frontend contract does not expose the video workflow endpoint",
        ),
    ]
    failed = [check for check in checks if check.status == "failed"]
    return CreativeVideoGateReport(
        status="passed" if not failed else "failed",
        generated_at=_utc_now(),
        evidence_type="creative_studio_external_video_api_only_gate",
        dry_run=True,
        mutation_performed=False,
        network_mutation_performed=False,
        full_release_claimed=False,
        git_sha=_current_git_sha(root),
        provider_status=provider_status,
        checks=checks,
        known_limits=[
            "Creative Studio remains excluded from the commercial RC default surface unless the owner explicitly approves promotion.",
            "This gate does not call any external video provider and does not validate real provider credentials.",
            "This gate validates a local opt-in workflow boundary; it does not promote Creative Studio into the global workflow router.",
            "Provider URLs must be external HTTPS endpoints; local ComfyUI-style endpoints are rejected before provider calls.",
        ],
        next_commands=[
            "python scripts/creative_studio_external_video_gate.py",
            "python -m pytest tests/test_creative_studio.py -q --no-cov",
            "cd frontend && npm run verify:creative-studio:contracts && npm run type-check",
        ],
    )


def write_report(report: CreativeVideoGateReport, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(build_creative_video_gate_report())
    write_report(report, args.output)
    print(f"Creative Studio external video gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
