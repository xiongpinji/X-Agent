from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_delivery_manifest import (
    ArtifactSpec,
    DEFAULT_ARTIFACTS,
    build_delivery_manifest_report,
    write_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, value: str = "delivery artifact\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _runtime_payload(
    status: str,
    *,
    evidence_type: str | None = None,
    parity: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "full_codex_parity_claimed": parity,
    }
    if evidence_type:
        payload["evidence_type"] = evidence_type
    return payload


def _write_default_artifacts(tmp_path: Path, *, include_outbound: bool = True) -> dict[str, Path]:
    paths = {
        "ops": tmp_path / "reports" / "commercial-pilot-ops-status.json",
        "handoff": tmp_path / "reports" / "commercial-pilot-handoff-status.json",
        "inbound": tmp_path / "reports" / "commercial-pilot-feishu-live.json",
        "channel": tmp_path / "reports" / "commercial-pilot-channel-readiness.json",
        "rc": tmp_path / "reports" / "rc-delivery-status.json",
        "outbound": tmp_path / "reports" / "commercial-pilot-feishu-outbound-live.json",
        "doc": tmp_path / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md",
        "script": tmp_path / "scripts" / "commercial_pilot_ops_status.py",
        "test": tmp_path / "tests" / "test_commercial_pilot_ops_status.py",
    }
    _write_json(paths["ops"], _runtime_payload("pilot_ops_ready", evidence_type="commercial_pilot_ops_status"))
    _write_json(paths["handoff"], _runtime_payload("pilot_handoff_ready"))
    _write_json(paths["inbound"], _runtime_payload("passed", evidence_type="commercial_pilot_feishu_live"))
    _write_json(paths["channel"], _runtime_payload("ready_with_owner_gates"))
    _write_json(paths["rc"], _runtime_payload("commercial_rc_ready"))
    if include_outbound:
        _write_json(
            paths["outbound"],
            _runtime_payload("owner_action_required", evidence_type="commercial_pilot_feishu_outbound_live"),
        )
    _write_text(paths["doc"], "# Feishu Pilot V1\n")
    _write_text(paths["script"], "print('ops')\n")
    _write_text(paths["test"], "def test_ops():\n    assert True\n")
    return paths


def _artifact_specs(paths: dict[str, Path]) -> tuple[ArtifactSpec, ...]:
    return (
        ArtifactSpec(
            "ops_status_report",
            paths["ops"],
            "runtime_report",
            expected_statuses=frozenset({"pilot_ops_ready"}),
        ),
        ArtifactSpec(
            "handoff_status_report",
            paths["handoff"],
            "runtime_report",
            expected_statuses=frozenset({"pilot_handoff_ready"}),
        ),
        ArtifactSpec(
            "feishu_inbound_live_report",
            paths["inbound"],
            "runtime_report",
            expected_statuses=frozenset({"passed"}),
            expected_evidence_type="commercial_pilot_feishu_live",
        ),
        ArtifactSpec(
            "channel_readiness_report",
            paths["channel"],
            "runtime_report",
            expected_statuses=frozenset({"ready", "ready_with_owner_gates"}),
        ),
        ArtifactSpec(
            "rc_delivery_status_report",
            paths["rc"],
            "runtime_report",
            expected_statuses=frozenset({"commercial_rc_ready"}),
        ),
        ArtifactSpec(
            "feishu_outbound_owner_gate_report",
            paths["outbound"],
            "runtime_report",
            required=False,
            expected_statuses=frozenset({"passed", "ready_to_execute", "owner_action_required"}),
            expected_evidence_type="commercial_pilot_feishu_outbound_live",
        ),
        ArtifactSpec("delivery_pack_doc", paths["doc"], "source_doc"),
        ArtifactSpec("ops_status_script", paths["script"], "source_script"),
        ArtifactSpec("ops_status_tests", paths["test"], "source_test"),
    )


def test_delivery_manifest_ready_with_optional_outbound_present(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path)

    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))

    assert report.status == "delivery_manifest_ready"
    assert report.full_codex_parity_claimed is False
    assert {check.status for check in report.checks} == {"passed"}
    outbound = next(artifact for artifact in report.artifacts if artifact.name == "feishu_outbound_owner_gate_report")
    assert outbound.required is False
    assert outbound.status == "present"
    assert outbound.sha256 is not None


def test_delivery_manifest_ready_when_optional_outbound_missing(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path, include_outbound=False)

    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))

    assert report.status == "delivery_manifest_ready"
    outbound = next(artifact for artifact in report.artifacts if artifact.name == "feishu_outbound_owner_gate_report")
    assert outbound.status == "optional_missing"
    assert outbound.error


def test_delivery_manifest_blocks_missing_required_artifact(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path)
    paths["ops"].unlink()

    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))

    assert report.status == "delivery_manifest_blocked"
    required = next(check for check in report.checks if check.name == "required_artifacts")
    assert required.status == "failed"
    assert "ops_status_report" in required.details["missing_or_failed"]


def test_delivery_manifest_blocks_non_ready_ops_status(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path)
    _write_json(paths["ops"], _runtime_payload("pilot_ops_action_required", evidence_type="commercial_pilot_ops_status"))

    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))

    assert report.status == "delivery_manifest_blocked"
    ops = next(check for check in report.checks if check.name == "ops_status_report")
    assert ops.status == "failed"


def test_delivery_manifest_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path)
    _write_json(paths["channel"], _runtime_payload("ready_with_owner_gates", parity=True))

    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))

    assert report.status == "delivery_manifest_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "channel_readiness_report" in parity.details["claiming_artifacts"]


def test_write_report_serializes_manifest(tmp_path: Path) -> None:
    paths = _write_default_artifacts(tmp_path)
    report = build_delivery_manifest_report(artifacts=_artifact_specs(paths))
    output = tmp_path / "reports" / "commercial-pilot-delivery-manifest.json"

    write_report(report, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "delivery_manifest_ready"
    assert payload["evidence_type"] == "commercial_pilot_delivery_manifest"
    assert payload["artifacts"][0]["name"] == "ops_status_report"
    assert payload["artifacts"][0]["sha256"]


def test_default_manifest_includes_final_handoff_wrapper_script() -> None:
    spec = next(artifact for artifact in DEFAULT_ARTIFACTS if artifact.name == "final_handoff_script")

    assert spec.path.name == "run_feishu_pilot_final_handoff.ps1"
    assert spec.category == "source_script"
    assert spec.required is True


def test_default_manifest_includes_final_handoff_wrapper_tests() -> None:
    spec = next(artifact for artifact in DEFAULT_ARTIFACTS if artifact.name == "final_handoff_tests")

    assert spec.path.name == "test_run_feishu_pilot_final_handoff.py"
    assert spec.category == "source_test"
    assert spec.required is True


def test_default_manifest_includes_acceptance_gate_artifacts() -> None:
    script = next(artifact for artifact in DEFAULT_ARTIFACTS if artifact.name == "acceptance_gate_script")
    tests = next(artifact for artifact in DEFAULT_ARTIFACTS if artifact.name == "acceptance_gate_tests")

    assert script.path.name == "commercial_pilot_acceptance_gate.py"
    assert script.category == "source_script"
    assert script.required is True
    assert tests.path.name == "test_commercial_pilot_acceptance_gate.py"
    assert tests.category == "source_test"
    assert tests.required is True
