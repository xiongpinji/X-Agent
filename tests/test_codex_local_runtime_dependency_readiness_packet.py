from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.codex_local_runtime_dependency_readiness_packet import (
    build_codex_local_runtime_dependency_readiness_packet,
    summarize_codex_local_runtime_dependency,
)


PACKET_POLICIES = {
    "runtime_policy": "runtime-policy",
    "dependency_policy": "dependency-policy",
    "lockfile_policy": "lockfile-policy",
    "environment_template_policy": "environment-template-policy",
    "runtime_dependency_manifest_ref": "runtime-dependency-manifest",
    "reproducibility_governance_ref": "reproducibility-governance",
}


def test_ready_local_runtime_dependency_has_toolchain_evidence() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet(
        {
            **PACKET_POLICIES,
            "runtimes": [
                {
                    "runtime_id": "runtime-1",
                    "status": "validated",
                    "runtime_ref": "runtime",
                    "python_runtime_refs": ["python-3.11"],
                    "node_runtime_refs": ["node-20"],
                    "package_manager_refs": ["uv", "npm"],
                    "lockfile_refs": ["uv-lock", "package-lock"],
                    "environment_template_refs": ["env-template"],
                    "install_verification_refs": ["install-check"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    assert packet["kind"] == "codex_local_runtime_dependency_readiness_packet"
    assert packet["ok"] is True
    assert packet["status"] == "ready"
    assert packet["summary"]["runtime_count"] == 1
    assert packet["summary"]["package_manager_ref_count"] == 2
    assert packet["next_actions"] == ["share_local_runtime_dependency_readiness_with_mainline"]


def test_missing_packet_policies_needs_review() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet(
        {
            "runtimes": [
                {
                    "runtime_id": "runtime-2",
                    "status": "validated",
                    "runtime_ref": "runtime",
                    "python_runtime_refs": ["python"],
                    "package_manager_refs": ["uv"],
                    "lockfile_refs": ["lock"],
                    "environment_template_refs": ["env"],
                    "install_verification_refs": ["install"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ]
        }
    )

    assert packet["status"] == "needs_review"
    assert packet["findings"][0]["code"] == "codex_local_runtime_dependency_packet_missing_evidence"
    assert packet["packet_missing_refs"] == [
        "runtime_policy_ref",
        "dependency_policy_ref",
        "lockfile_policy_ref",
        "environment_template_policy_ref",
        "runtime_dependency_manifest_ref",
        "reproducibility_governance_ref",
    ]


def test_missing_runtime_package_lock_env_install_and_validation_refs_needs_review() -> None:
    runtime = summarize_codex_local_runtime_dependency(
        {
            "runtime_id": "runtime-3",
            "status": "validated",
            "runtime_ref": "runtime",
        }
    )

    assert runtime.readiness_state == "needs_review"
    assert "runtime_version_refs" in runtime.missing_refs
    assert "package_manager_refs" in runtime.missing_refs
    assert "lockfile_refs" in runtime.missing_refs
    assert "environment_template_refs" in runtime.missing_refs
    assert "install_verification_refs" in runtime.missing_refs
    assert "validation_receipt_refs" in runtime.missing_refs


def test_failed_or_mismatched_runtime_requires_version_mismatch_refs_and_blocks() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet(
        {
            **PACKET_POLICIES,
            "runtimes": [
                {
                    "runtime_id": "runtime-4",
                    "status": "mismatched",
                    "runtime_ref": "runtime",
                    "python_runtime_refs": ["python"],
                    "package_manager_refs": ["uv"],
                    "lockfile_refs": ["lock"],
                    "environment_template_refs": ["env"],
                    "install_verification_refs": ["install"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                }
            ],
        }
    )

    runtime = packet["runtimes"][0]
    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_local_runtime_dependency_status_failed"
    assert "version_mismatch_refs" in runtime["missing_refs"]


def test_detected_dependency_conflict_blocks_candidate() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet(
        {
            **PACKET_POLICIES,
            "runtimes": [
                {
                    "runtime_id": "runtime-5",
                    "status": "validated",
                    "runtime_ref": "runtime",
                    "python_runtime_refs": ["python"],
                    "package_manager_refs": ["uv"],
                    "lockfile_refs": ["lock"],
                    "environment_template_refs": ["env"],
                    "install_verification_refs": ["install"],
                    "version_mismatch_refs": ["mismatch"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "version_mismatch_detected": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_local_runtime_dependency_version_mismatch"
    assert "local_runtime_dependency_version_mismatch_detected" in packet["runtimes"][0]["blockers"]


def test_live_dependency_install_or_package_manager_mutation_blocks_candidate() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet(
        {
            **PACKET_POLICIES,
            "runtimes": [
                {
                    "runtime_id": "runtime-6",
                    "status": "validated",
                    "runtime_ref": "runtime",
                    "node_runtime_refs": ["node"],
                    "package_manager_refs": ["npm"],
                    "lockfile_refs": ["lock"],
                    "environment_template_refs": ["env"],
                    "install_verification_refs": ["install"],
                    "version_mismatch_refs": ["mismatch"],
                    "validation_receipt_refs": ["validation"],
                    "artifact_refs": ["artifact"],
                    "dependency_install_attempted": True,
                }
            ],
        }
    )

    assert packet["status"] == "blocked"
    assert packet["findings"][0]["code"] == "codex_local_runtime_dependency_live_operation_blocked"
    assert "live_runtime_dependency_operation_attempted" in packet["runtimes"][0]["blockers"]


def test_empty_payload_requests_local_runtime_dependency_inventory() -> None:
    packet = build_codex_local_runtime_dependency_readiness_packet({})

    assert packet["status"] == "empty"
    assert packet["ok"] is False
    assert packet["next_actions"] == ["provide_codex_local_runtime_dependency_inventory"]


def test_dataclass_like_runtime_dependency_is_accepted_by_summarizer() -> None:
    @dataclass
    class RuntimeDependency:
        runtime_id: str
        status: str
        runtime_ref: str
        python_runtime_refs: list[str]
        node_runtime_refs: list[str]
        package_manager_refs: list[str]
        lockfile_refs: list[str]
        environment_template_refs: list[str]
        install_verification_refs: list[str]
        version_mismatch_refs: list[str]
        validation_receipt_refs: list[str]
        artifact_refs: list[str]

    runtime = summarize_codex_local_runtime_dependency(
        RuntimeDependency(
            "runtime-7",
            "passed",
            "runtime",
            ["python"],
            ["node"],
            ["uv", "npm"],
            ["uv-lock", "package-lock"],
            ["env"],
            ["install"],
            ["mismatch"],
            ["validation"],
            ["artifact"],
        )
    )

    assert runtime.runtime_id == "runtime-7"
    assert runtime.status == "passed"
    assert runtime.readiness_state == "ready"
