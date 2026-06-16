from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs" / "specs" / "xagent-cloud-task-environment.md"


def _contract_payload() -> dict[str, object]:
    markdown = SPEC_PATH.read_text(encoding="utf-8")
    match = re.search(r"```json\n(?P<payload>.*?)\n```", markdown, re.DOTALL)
    assert match, "cloud task environment spec must include one JSON contract block"
    payload = json.loads(match.group("payload"))
    assert isinstance(payload, dict)
    return payload


def test_cloud_task_environment_contract_identity_and_status() -> None:
    payload = _contract_payload()
    checkout = payload["checkout_identity"]

    assert payload["status"] == "cloud_task_environment_contract_ready"
    assert payload["schema_version"] == "2026-06-08"
    assert payload["full_codex_parity_claimed"] is False
    assert payload["mutation_performed_by_contract"] is False
    assert checkout["required"] == ["provider", "repository", "workspace_id"]
    assert checkout["one_of_required"] == ["branch", "commit_sha"]
    assert checkout["detached_head_supported"] is True
    assert checkout["dirty_local_changes_supported"] is False
    assert checkout["worktree_mode"] == "metadata_only_until_adapter"


def test_cloud_task_environment_phases_preserve_secret_boundaries() -> None:
    payload = _contract_payload()
    phases = {phase["name"]: phase for phase in payload["environment_phases"]}

    assert list(phases) == [
        "checkout",
        "setup",
        "maintenance",
        "agent",
        "package_evidence",
        "publish_or_pr",
    ]
    assert phases["setup"]["secrets_available"] is True
    assert phases["maintenance"]["secrets_available"] is True
    assert phases["agent"]["secrets_available"] is False
    assert phases["package_evidence"]["secrets_available"] is False
    assert phases["publish_or_pr"]["owner_approval_required"] is True
    assert phases["publish_or_pr"]["secrets_available"] == "owner_approved_only"
    assert "approval_id" in phases["publish_or_pr"]["evidence"]


def test_cloud_task_environment_network_policy_is_default_deny_for_agent() -> None:
    payload = _contract_payload()
    network = payload["network_policy"]
    phases = {phase["name"]: phase for phase in payload["environment_phases"]}

    assert phases["setup"]["network"] == "dependency_allowlist"
    assert phases["maintenance"]["network"] == "dependency_allowlist"
    assert phases["agent"]["network"] == "off_by_default"
    assert network["setup_default"] == "dependency_allowlist"
    assert network["agent_default"] == "off"
    assert network["allowed_http_methods_default"] == ["GET", "HEAD", "OPTIONS"]
    assert network["domain_allowlist_presets"] == ["none", "common_dependencies"]
    assert network["unrestricted_network_requires_owner_approval"] is True
    assert {"POST", "PUT", "PATCH", "DELETE"}.issubset(set(network["blocked_without_approval"]))


def test_cloud_task_environment_task_loop_and_artifact_diff_are_evidence_first() -> None:
    payload = _contract_payload()
    task_loop = payload["task_loop"]
    artifact_diff = payload["artifact_diff"]
    evidence_export = payload["evidence_export"]

    assert task_loop["uses_agents_md"] is True
    assert task_loop["validation_commands_required"] is True
    assert {"queued", "running", "completed", "failed", "blocked"}.issubset(
        set(task_loop["status_vocabulary"])
    )
    assert {
        "task.created",
        "environment.checkout",
        "environment.setup",
        "agent.command",
        "agent.validation",
        "artifact.diff",
        "task.completed",
    }.issubset(set(task_loop["events_required"]))
    assert artifact_diff["required"] is True
    assert artifact_diff["binary_artifacts_manifest_required"] is True
    assert artifact_diff["diff_before_publish_required"] is True
    assert evidence_export["required"] is True
    assert evidence_export["format"] == "json"
    assert evidence_export["report_status"] == "cloud_task_environment_contract_ready"
    assert "full_codex_parity_claimed" in evidence_export["fields"]


def test_cloud_task_environment_adapter_boundary_is_not_live_execution() -> None:
    payload = _contract_payload()
    adapter = payload["adapter_boundary"]
    secret_policy = payload["secret_policy"]

    assert adapter["hosted_container_adapter"] == "not_implemented"
    assert adapter["real_checkout_mutation"] is False
    assert adapter["real_network_mutation"] is False
    assert adapter["real_pr_mutation"] is False
    assert adapter["owner_gate_required_before_execution"] is True
    assert secret_policy["raw_secret_payloads_allowed"] is False
    assert secret_policy["agent_phase_secrets_available"] is False
    assert secret_policy["secret_evidence_redacted"] is True
