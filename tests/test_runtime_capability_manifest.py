from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.runtime_capability_manifest import (
    assess_runtime_capability,
    build_runtime_capability_manifest,
)


def test_runtime_capability_manifest_marks_ready_capabilities_ready() -> None:
    manifest = build_runtime_capability_manifest(
        {
            "runtime": "x-agent-mainline",
            "capabilities": [
                {
                    "capability_id": "browser-readiness",
                    "name": "Browser task readiness",
                    "owner": "mainline-browser",
                    "integration_stage": "ready",
                    "evidence": [{"kind": "browser_task_readiness", "status": "ready"}],
                    "dependencies": ["browser-runtime"],
                }
            ],
        }
    )

    assert manifest["kind"] == "runtime_capability_manifest"
    assert manifest["ok"] is True
    assert manifest["status"] == "ready"
    assert manifest["summary"]["ready_count"] == 1
    assert manifest["next_actions"] == ["prepare_runtime_capability_review"]


def test_blocked_stage_blocks_manifest() -> None:
    manifest = build_runtime_capability_manifest(
        {
            "capabilities": [
                {
                    "id": "mcp-tools",
                    "name": "MCP tools",
                    "owner": "tooling",
                    "stage": "blocked",
                    "evidence": ["report"],
                }
            ]
        }
    )

    assert manifest["status"] == "blocked"
    assert manifest["capabilities"][0]["decision"] == "blocked"
    assert manifest["issues"][0]["code"] == "runtime_capability_stage_blocked"
    assert manifest["next_actions"] == ["resolve_blocked_runtime_capabilities", "refresh_runtime_capability_manifest"]


def test_missing_owner_or_evidence_needs_review() -> None:
    manifest = build_runtime_capability_manifest(
        {
            "capabilities": [
                {
                    "id": "channel-integrations",
                    "stage": "candidate",
                    "missing_evidence": ["live callback evidence"],
                }
            ]
        }
    )

    assert manifest["status"] == "needs_review"
    assert manifest["summary"]["owner_missing_count"] == 1
    assert manifest["summary"]["missing_evidence_count"] == 1
    assert "integration owner missing" in manifest["capabilities"][0]["reasons"]
    assert manifest["issues"][0]["code"] == "runtime_capability_required_evidence_missing"


def test_blocking_risk_flag_blocks_even_if_stage_ready() -> None:
    item = assess_runtime_capability(
        {
            "id": "shell-execution",
            "owner": "runtime",
            "stage": "ready",
            "evidence_count": 2,
            "risk_flags": ["security"],
        }
    )

    assert item.decision == "blocked"
    assert "risk flags present" in item.reasons


def test_non_blocking_risk_flag_needs_review() -> None:
    item = assess_runtime_capability(
        {
            "id": "open-source-adoption",
            "owner": "ecosystem",
            "stage": "ready",
            "evidence": ["adoption-matrix"],
            "risk_flags": ["license_review"],
        }
    )

    assert item.decision == "needs_review"
    assert item.risk_flags == ("license_review",)


def test_accepts_manifest_and_dataclass_like_capability() -> None:
    @dataclass
    class Capability:
        capability_id: str
        name: str
        owner: str
        integration_stage: str
        evidence_count: int

    manifest = build_runtime_capability_manifest(
        {
            "manifest": {
                "capabilities": [
                    Capability("eval-pack", "Eval evidence pack", "release", "integrated", 1)
                ]
            }
        }
    )

    assert manifest["status"] == "ready"
    assert manifest["capabilities"][0]["capability_id"] == "eval-pack"
    assert manifest["capabilities"][0]["evidence_count"] == 1


def test_empty_manifest_requests_capabilities() -> None:
    manifest = build_runtime_capability_manifest({})

    assert manifest["status"] == "empty"
    assert manifest["ok"] is False
    assert manifest["next_actions"] == ["provide_runtime_capabilities"]
