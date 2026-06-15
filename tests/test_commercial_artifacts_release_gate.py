from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_artifacts_release_gate import (
    build_artifacts_release_gate,
    render_markdown_report,
    write_markdown_report,
    write_report,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_file(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _write_complete_fixture(tmp_path: Path) -> dict[str, Path]:
    reports = tmp_path / ".xagent_runtime" / "reports"
    release = tmp_path / ".xagent_runtime" / "release"
    source = _write_file(release / "x-agent-commercial.zip", b"source-bundle")
    sbom = _write_file(release / "x-agent.spdx.json", b'{"sbom": true}\n')
    helm = _write_file(release / "x-agent-1.0.0.tgz", b"helm-package")

    _write_json(
        reports / "rc-source-bundle.json",
        {
            "status": "created",
            "output_path": str(source),
            "artifact_sha256": _sha256(source),
            "file_count": 3,
        },
    )
    _write_json(
        reports / "stage5-image-digests-20260615.json",
        {
            "status": "image_digests_ready",
            "image_digests": {
                "backend": "sha256:" + ("a" * 64),
                "frontend": "sha256:" + ("b" * 64),
            },
        },
    )
    _write_json(
        reports / "stage5-sbom-20260615.json",
        {"status": "sbom_ready", "sbom_path": str(sbom), "sha256": _sha256(sbom)},
    )
    _write_json(
        reports / "stage5-helm-package-20260615.json",
        {"status": "helm_package_ready", "helm_package_path": str(helm), "sha256": _sha256(helm)},
    )
    _write_json(
        reports / "stage5-artifact-checksums-20260615.json",
        {
            "status": "checksums_ready",
            "checksums": [
                {"path": str(source), "sha256": _sha256(source)},
                {"path": str(sbom), "sha256": _sha256(sbom)},
                {"path": str(helm), "sha256": _sha256(helm)},
            ],
        },
    )
    _write_json(
        release / "x-agent-commercial-rc-receipt.json",
        {
            "status": "created",
            "artifact": {"path": str(source), "sha256": _sha256(source), "file_count": 3},
            "checks": [{"name": "release_artifact_consistency", "status": "passed"}],
        },
    )
    return {"reports": reports, "release": release, "source": source, "sbom": sbom, "helm": helm}


def test_artifacts_release_gate_blocks_when_evidence_missing(tmp_path: Path) -> None:
    report = build_artifacts_release_gate(
        report_dir=tmp_path / ".xagent_runtime" / "reports",
        release_dir=tmp_path / ".xagent_runtime" / "release",
        root=tmp_path,
        current_head_sha="1" * 40,
    )

    assert report.status == "artifacts_release_blocked"
    assert report.artifacts_release_ready is False
    assert set(report.missing_or_mismatched) == {
        "source_bundle",
        "image_digests",
        "sbom",
        "helm_package",
        "checksums",
        "release_receipt",
    }


def test_artifacts_release_gate_accepts_complete_temporary_evidence(tmp_path: Path) -> None:
    paths = _write_complete_fixture(tmp_path)

    report = build_artifacts_release_gate(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="2" * 40,
    )

    assert report.status == "artifacts_release_ready"
    assert report.artifacts_release_ready is True
    assert report.release_sha == "2" * 40
    assert report.missing_or_mismatched == []
    assert all(item.ready for item in report.evidence)


def test_artifacts_release_gate_blocks_on_sha_mismatch(tmp_path: Path) -> None:
    paths = _write_complete_fixture(tmp_path)
    source_report = paths["reports"] / "rc-source-bundle.json"
    payload = json.loads(source_report.read_text(encoding="utf-8"))
    payload["artifact_sha256"] = "0" * 64
    _write_json(source_report, payload)

    report = build_artifacts_release_gate(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="3" * 40,
    )

    assert report.status == "artifacts_release_blocked"
    assert "source_bundle" in report.missing_or_mismatched
    source = next(item for item in report.evidence if item.name == "source_bundle")
    assert source.error is not None
    assert "sha256 mismatch" in source.error


def test_artifacts_release_gate_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_complete_fixture(tmp_path)
    report = build_artifacts_release_gate(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="4" * 40,
    )
    output_json = tmp_path / "reports" / "stage5-artifacts-release-gate-20260615.json"
    output_md = tmp_path / "reports" / "stage5-artifacts-release-gate-20260615.md"

    write_report(report, output_json)
    write_markdown_report(report, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "artifacts_release_ready"
    assert payload["release_sha"] == "4" * 40
    assert "Stage 5 Artifacts Release Gate" in markdown
    assert "artifacts_release_ready" in markdown
    assert render_markdown_report(report) == markdown
