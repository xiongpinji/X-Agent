from __future__ import annotations

import json
from pathlib import Path

from scripts.commercial_pilot_customer_acceptance_pack import (
    API_ENDPOINTS,
    AcceptanceArtifactSpec,
    build_customer_acceptance_pack_report,
    render_markdown_pack,
    write_markdown_pack,
    write_report,
)


PILOT_SHA = "765d44b69da061caba6585a4cee0105bbf3310a7"
RC_SHA = "592141f35520df62578a00cbb805eeaa7371a940"
PILOT_TAG = "x-agent-commercial-pilot-feishu-20260608"
RC_TAG = "x-agent-commercial-rc-20260608-6"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, value: str = "customer artifact\n") -> None:
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
    if status in {
        "pilot_acceptance_ready",
        "handoff_index_ready",
        "final_gate_ready",
        "delivery_receipt_ready",
        "passed",
    }:
        payload["mutation_performed"] = mutation
        payload["outbound_message_sent"] = mutation
    return payload


def _write_all_artifacts(tmp_path: Path) -> dict[str, Path]:
    report_dir = tmp_path / "reports"
    paths = {
        "report_dir": report_dir,
        "acceptance": report_dir / "commercial-pilot-acceptance-gate.json",
        "handoff_index": report_dir / "commercial-pilot-handoff-index.json",
        "final_gate": report_dir / "commercial-pilot-final-gate.json",
        "receipt": report_dir / "commercial-pilot-delivery-receipt.json",
        "receipt_md": report_dir / "commercial-pilot-delivery-receipt.md",
        "handoff": report_dir / "commercial-pilot-handoff-status.json",
        "ops": report_dir / "commercial-pilot-ops-status.json",
        "manifest": report_dir / "commercial-pilot-delivery-manifest.json",
        "live": report_dir / "commercial-pilot-feishu-live.json",
        "channel": report_dir / "commercial-pilot-channel-readiness.json",
        "rc": report_dir / "rc-delivery-status.json",
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
    _write_json(
        paths["handoff_index"],
        _runtime_payload("handoff_index_ready", evidence_type="commercial_pilot_handoff_index"),
    )
    _write_json(
        paths["final_gate"],
        _runtime_payload("final_gate_ready", evidence_type="commercial_pilot_final_gate"),
    )
    _write_json(
        paths["receipt"],
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt"),
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
    _write_json(
        paths["manifest"],
        _runtime_payload("delivery_manifest_ready", evidence_type="commercial_pilot_delivery_manifest"),
    )
    _write_json(
        paths["live"],
        _runtime_payload("passed", evidence_type="commercial_pilot_feishu_live")
        | {
            "channel": "feishu",
            "event_id": "200a6a4679c9192722309edf45478364",
            "event_type": "im.message.receive_v1",
            "tenant_key_present": True,
            "message_id_present": True,
            "chat_id_present": True,
            "content_present": True,
            "signature_mode": "lark_sha256",
            "encrypted_callback": True,
        },
    )
    _write_json(paths["channel"], {"status": "ready_with_owner_gates", "full_codex_parity_claimed": False})
    _write_json(paths["rc"], {"status": "commercial_rc_ready", "full_codex_parity_claimed": False})
    _write_text(paths["doc"], "# Feishu Pilot V1\n")
    return paths


def test_customer_acceptance_pack_ready_from_accepted_evidence(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)

    report = build_customer_acceptance_pack_report(
        report_dir=paths["report_dir"],
        delivery_pack_doc_path=paths["doc"],
    )

    assert report.status == "customer_acceptance_pack_ready"
    assert report.pilot_channel == "feishu"
    assert report.pilot_tag_name == PILOT_TAG
    assert report.operational_status == "pilot_operational_ready"
    assert report.acceptance_gate_status == "pilot_acceptance_ready"
    assert report.handoff_index_status == "handoff_index_ready"
    assert report.inbound_live_status == "passed"
    assert report.api_contract["read_only"] is True
    assert report.api_contract["endpoints"] == list(API_ENDPOINTS)
    assert report.codex_alignment_summary["aligned_for_pilot_v1"] == 1
    assert report.codex_alignment_summary["partial"] >= 1
    assert report.codex_alignment_summary["full_codex_parity_claimed"] is False
    assert report.full_codex_parity_claimed is False
    assert report.mutation_performed is False
    assert report.outbound_message_sent is False
    assert {check.status for check in report.checks} == {"passed"}
    assert "commercial-pilot-acceptance-gate.json" in " ".join(report.archive_files)


def test_customer_acceptance_pack_action_required_when_handoff_index_missing(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    paths["handoff_index"].unlink()

    report = build_customer_acceptance_pack_report(
        report_dir=paths["report_dir"],
        delivery_pack_doc_path=paths["doc"],
    )

    assert report.status == "customer_acceptance_pack_action_required"
    required = next(check for check in report.checks if check.name == "required_customer_artifacts")
    operational = next(check for check in report.checks if check.name == "operational_status_ready")
    artifact = next(artifact for artifact in report.artifacts if artifact.name == "handoff_index_report")
    assert required.status == "action_required"
    assert operational.status == "action_required"
    assert artifact.status == "missing"


def test_customer_acceptance_pack_blocks_full_codex_parity_claim(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    _write_json(
        paths["receipt"],
        _runtime_payload("delivery_receipt_ready", evidence_type="commercial_pilot_delivery_receipt", parity=True),
    )

    report = build_customer_acceptance_pack_report(
        report_dir=paths["report_dir"],
        delivery_pack_doc_path=paths["doc"],
    )

    assert report.status == "customer_acceptance_pack_blocked"
    parity = next(check for check in report.checks if check.name == "no_full_codex_parity_claim")
    assert parity.status == "failed"
    assert "delivery_receipt_report" in parity.details["claiming_reports"]


def test_customer_acceptance_pack_blocks_mutation_in_handoff_sources(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    _write_json(
        paths["live"],
        _runtime_payload("passed", evidence_type="commercial_pilot_feishu_live", mutation=True)
        | {
            "channel": "feishu",
            "event_id": "200a6a4679c9192722309edf45478364",
            "event_type": "im.message.receive_v1",
            "tenant_key_present": True,
            "message_id_present": True,
            "chat_id_present": True,
            "content_present": True,
            "signature_mode": "lark_sha256",
            "encrypted_callback": True,
        },
    )

    report = build_customer_acceptance_pack_report(
        report_dir=paths["report_dir"],
        delivery_pack_doc_path=paths["doc"],
    )

    assert report.status == "customer_acceptance_pack_blocked"
    mutation = next(check for check in report.checks if check.name == "no_customer_handoff_mutation")
    assert mutation.status == "failed"
    assert "feishu_inbound_live_report.mutation_performed" in mutation.details["offenders"]


def test_write_customer_acceptance_pack_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_all_artifacts(tmp_path)
    report = build_customer_acceptance_pack_report(
        report_dir=paths["report_dir"],
        delivery_pack_doc_path=paths["doc"],
    )
    json_output = tmp_path / "commercial-pilot-customer-acceptance-pack.json"
    markdown_output = tmp_path / "commercial-pilot-customer-acceptance-pack.md"

    write_report(report, json_output)
    write_markdown_pack(report, markdown_output)

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = markdown_output.read_text(encoding="utf-8")
    assert payload["status"] == "customer_acceptance_pack_ready"
    assert payload["evidence_type"] == "commercial_pilot_customer_acceptance_pack"
    assert "# X-Agent Feishu Pilot V1 Customer Acceptance Pack" in markdown
    assert "Feishu Pilot V1 is ready for first domestic commercial pilot customer acceptance" in markdown
    assert "full_codex_parity_claimed" in json.dumps(payload)
    assert "ide_extension_and_app_surfaces" in render_markdown_pack(report)


def test_artifact_spec_type_is_importable_for_contract_extensions() -> None:
    spec = AcceptanceArtifactSpec("example", Path("example.json"), "runtime_report", required=False)

    assert spec.name == "example"
    assert spec.required is False
