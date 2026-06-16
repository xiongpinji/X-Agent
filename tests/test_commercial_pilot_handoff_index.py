from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_handoff_index import (
    HandoffIndexArtifactSpec,
    build_handoff_index_report,
    render_markdown_index,
    write_markdown_index,
    write_report,
)


PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, value: str = "handoff artifact\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _runtime_payload(
    status: str,
    *,
    evidence_type: str | None = None,
    parity: bool = False,
    mutation: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status,
        "full_codex_parity_claimed": parity,
    }
    if evidence_type:
        payload["evidence_type"] = evidence_type
    if status in {"pilot_acceptance_ready", "final_gate_ready", "delivery_receipt_ready", "passed"}:
        payload["mutation_performed"] = mutation
        payload["outbound_message_sent"] = mutation
    return payload


def _write_all_artifacts(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "acceptance": tmp_path / "reports" / "commercial-pilot-acceptance-gate.json",
        "final_gate": tmp_path / "reports" / "commercial-pilot-final-gate.json",
        "receipt": tmp_path / "reports" / "commercial-pilot-delivery-receipt.json",
        "receipt_md": tmp_path / "reports" / "commercial-pilot-delivery-receipt.md",
        "handoff": tmp_path / "reports" / "commercial-pilot-handoff-status.json",
        "ops": tmp_path / "reports" / "commercial-pilot-ops-status.json",
        "manifest": tmp_path / "reports" / "commercial-pilot-delivery-manifest.json",
        "live": tmp_path / "reports" / "commercial-pilot-feishu-live.json",
        "rc": tmp_path / "reports" / "rc-delivery-status.json",
        "doc": tmp_path / "docs" / "FEISHU_PILOT_V1_DELIVERY_PACK.md",
    }
    _write_json(
        paths["acceptance"],
        _runtime_payload("pilot_acceptance_ready", evidence_type="commercial_pilot_acceptance_gate")
        | {
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
        },
    )
    _write_json(paths["final_gate"], _runtime_payload("final_gate_ready", evidence_type="commercial_pilot_final_gate"))
    _write_json(
        paths["receipt"],
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt")
        | {
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
        },
    )
    _write_text(paths["receipt_md"], "# Receipt\n")
    _write_json(
        paths["handoff"],
        {
            "status": "pilot_handoff_ready",
            "pilot_tag_name": PILOT_TAG,
            "expected_pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "expected_rc_commit_sha": RC_SHA,
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(
        paths["ops"],
        {
            "status": "pilot_ops_ready",
            "pilot_channel": "feishu",
            "pilot_tag_name": PILOT_TAG,
            "pilot_commit_sha": PILOT_SHA,
            "rc_tag_name": RC_TAG,
            "rc_commit_sha": RC_SHA,
            "outbound_owner_gate_status": "preview",
            "full_codex_parity_claimed": False,
        },
    )
    _write_json(paths["manifest"], _runtime_payload("delivery_manifest_ready", evidence_type="commercial_pilot_delivery_manifest"))
    _write_json(paths["live"], _runtime_payload("passed", evidence_type="commercial_pilot_feishu_live"))
    _write_json(paths["rc"], {"status": "commercial_rc_ready", "full_codex_parity_claimed": False})
    _write_text(paths["doc"], "# Feishu Pilot V1\n")
    return paths


def _artifact_specs(paths: dict[str, Path]) -> tuple[HandoffIndexArtifactSpec, ...]:
    return (
        HandoffIndexArtifactSpec(
            "acceptance_gate_report",
            paths["acceptance"],
            "runtime_report",
            expected_statuses=frozenset({"pilot_acceptance_ready"}),
            expected_evidence_type="commercial_pilot_acceptance_gate",
        ),
        HandoffIndexArtifactSpec(
            "final_gate_report",
            paths["final_gate"],
            "runtime_report",
            expected_statuses=frozenset({"final_gate_ready"}),
            expected_evidence_type="commercial_pilot_final_gate",
        ),
        HandoffIndexArtifactSpec(
            "delivery_receipt_report",
            paths["receipt"],
            "runtime_report",
            expected_statuses=frozenset({"delivery_receipt_ready"}),
            expected_evidence_type="commercial_pilot_delivery_receipt",
        ),
        HandoffIndexArtifactSpec("delivery_receipt_markdown", paths["receipt_md"], "customer_markdown"),
        HandoffIndexArtifactSpec(
            "handoff_status_report",
            paths["handoff"],
            "runtime_report",
            expected_statuses=frozenset({"pilot_handoff_ready"}),
        ),
        HandoffIndexArtifactSpec(
            "operator_status_report",
            paths["ops"],
            "runtime_report",
            expected_statuses=frozenset({"pilot_ops_ready"}),
        ),
        HandoffIndexArtifactSpec(
            "delivery_manifest_report",
            paths["manifest"],
            "runtime_report",
            expected_statuses=frozenset({"delivery_manifest_ready"}),
            expected_evidence_type="commercial_pilot_delivery_manifest",
        ),
        HandoffIndexArtifactSpec(
            "feishu_inbound_live_report",
            paths["live"],
            "runtime_report",
            expected_statuses=frozenset({"passed"}),
            expected_evidence_type="commercial_pilot_feishu_live",
        ),
        HandoffIndexArtifactSpec(
            "rc_delivery_status_report",
            paths["rc"],
            "runtime_report",
            expected_statuses=frozenset({"commercial_rc_ready"}),
        ),
        HandoffIndexArtifactSpec("delivery_pack_doc", paths["doc"], "source_doc"),
    )


def test_handoff_index_ready_from_accepted_evidence(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)

    report = build_handoff_index_report(artifacts=_artifact_specs(paths))

    assert report.status == "handoff_index_ready"
    assert report.pilot_channel == "feishu"
    assert report.pilot_tag_name == PILOT_TAG
    assert report.pilot_commit_sha == PILOT_SHA
    assert report.acceptance_gate_status == "pilot_acceptance_ready"
    assert report.full_codex_parity_claimed is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert {check.status for check in report.checks} == {"passed"}
    assert all(artifact.sha256 for artifact in report.artifacts)
    assert "commercial-pilot-acceptance-gate.json" in " ".join(report.archive_files)


def test_handoff_index_action_required_when_required_artifact_missing(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    paths["acceptance"].unlink()

    report = build_handoff_index_report(artifacts=_artifact_specs(paths))

    assert report.status == "handoff_index_action_required"
    required = next(check for check in report.checks if check.name == "required_archive_artifacts")
    acceptance = next(artifact for artifact in report.artifacts if artifact.name == "acceptance_gate_report")
    assert required.status == "action_required"
    assert acceptance.status == "missing"


def test_handoff_index_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    _write_json(
        paths["receipt"],
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt", parity=True),
    )

    report = build_handoff_index_report(artifacts=_artifact_specs(paths))

    assert report.status == "handoff_index_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "delivery_receipt_report" in parity.details["claiming_reports"]


def test_handoff_index_blocks_mutation_in_archive_sources(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    _write_json(
        paths["final_gate"],
        _runtime_payload("final_gate_ready", evidence_type="commercial_pilot_final_gate", mutation=True),
    )

    report = build_handoff_index_report(artifacts=_artifact_specs(paths))

    assert report.status == "handoff_index_blocked"
    mutation = next(check for check in report.checks if check.name == "no_archive_mutation")
    assert mutation.status == "failed"
    assert "final_gate_report.mutation_performed" in mutation.details["offenders"]


def test_write_handoff_index_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    report = build_handoff_index_report(artifacts=_artifact_specs(paths))
    json_output = tmp_path / "commercial-pilot-handoff-index.json"
    markdown_output = tmp_path / "commercial-pilot-handoff-index.md"

    write_report(report, json_output)
    write_markdown_index(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "handoff_index_ready"
    assert payload["evidence_type"] == "commercial_pilot_handoff_index"
    assert "# X-Agent Feishu Pilot V1 Handoff Index" in markdown
    assert "Acceptance gate: `pilot_acceptance_ready`" in markdown
    assert PILOT_TAG in render_markdown_index(report)
