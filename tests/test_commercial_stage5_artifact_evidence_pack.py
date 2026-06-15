from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.commercial_stage5_artifact_evidence_pack import (
    build_artifact_evidence_pack,
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


def _with_sha(payload: dict[str, object], *, release_sha: str) -> dict[str, object]:
    return {
        **payload,
        "current_head_sha": release_sha,
        "release_sha": release_sha,
    }


def _write_ready_fixture(tmp_path: Path, *, release_sha: str = "2" * 40) -> dict[str, Path]:
    reports = tmp_path / ".xagent_runtime" / "reports"
    release = tmp_path / ".xagent_runtime" / "release"
    source = _write_file(release / "x-agent-commercial.zip", b"source-bundle")
    sbom = _write_file(release / "x-agent.spdx.json", b'{"sbom": true}\n')
    helm = _write_file(release / "x-agent-1.0.0.tgz", b"helm-package")

    _write_json(
        reports / "rc-source-bundle.json",
        _with_sha(
            {"status": "created", "output_path": str(source), "artifact_sha256": _sha256(source)},
            release_sha=release_sha,
        ),
    )
    _write_json(
        reports / "stage5-image-digests-20260615.json",
        _with_sha(
            {
                "status": "image_digests_ready",
                "image_digests": {
                    "backend": "sha256:" + ("a" * 64),
                    "frontend": "sha256:" + ("b" * 64),
                },
            },
            release_sha=release_sha,
        ),
    )
    _write_json(
        reports / "stage5-sbom-20260615.json",
        _with_sha({"status": "sbom_ready", "sbom_path": str(sbom), "sha256": _sha256(sbom)}, release_sha=release_sha),
    )
    _write_json(
        reports / "stage5-helm-package-20260615.json",
        _with_sha(
            {"status": "helm_package_ready", "helm_package_path": str(helm), "sha256": _sha256(helm)},
            release_sha=release_sha,
        ),
    )
    _write_json(
        reports / "stage5-artifact-checksums-20260615.json",
        _with_sha(
            {
                "status": "checksums_ready",
                "checksums": [
                    {"path": str(source), "sha256": _sha256(source)},
                    {"path": str(sbom), "sha256": _sha256(sbom)},
                    {"path": str(helm), "sha256": _sha256(helm)},
                ],
            },
            release_sha=release_sha,
        ),
    )
    return {"reports": reports, "release": release, "source": source, "sbom": sbom, "helm": helm}


def test_artifact_evidence_pack_blocks_when_required_evidence_is_missing(tmp_path: Path) -> None:
    pack = build_artifact_evidence_pack(
        report_dir=tmp_path / ".xagent_runtime" / "reports",
        release_dir=tmp_path / ".xagent_runtime" / "release",
        root=tmp_path,
        current_head_sha="1" * 40,
    )

    assert pack.status == "artifact_evidence_pack_blocked"
    assert pack.controlled_commercial_pilot_ready is False
    assert pack.production_ready is False
    assert pack.ga_ready is False
    assert pack.deploy_performed is False
    assert pack.tag_performed is False
    assert pack.release_performed is False
    assert set(pack.missing_or_mismatched) == {
        "source_bundle",
        "image_digests",
        "sbom",
        "helm_package",
        "checksums",
    }


def test_artifact_evidence_pack_accepts_ready_fixture_bound_to_release_sha(tmp_path: Path) -> None:
    release_sha = "2" * 40
    paths = _write_ready_fixture(tmp_path, release_sha=release_sha)

    pack = build_artifact_evidence_pack(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha=release_sha,
    )

    assert pack.status == "artifact_evidence_pack_ready"
    assert pack.controlled_commercial_pilot_ready is True
    assert pack.release_sha == release_sha
    assert pack.missing_or_mismatched == []
    assert all(item.ready for item in pack.evidence)
    assert pack.deploy_performed is False
    assert pack.tag_performed is False
    assert pack.release_performed is False


def test_artifact_evidence_pack_blocks_on_source_sha_mismatch(tmp_path: Path) -> None:
    paths = _write_ready_fixture(tmp_path, release_sha="3" * 40)
    source_report = paths["reports"] / "rc-source-bundle.json"
    payload = json.loads(source_report.read_text(encoding="utf-8"))
    payload["artifact_sha256"] = "0" * 64
    _write_json(source_report, payload)

    pack = build_artifact_evidence_pack(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="3" * 40,
    )

    assert pack.status == "artifact_evidence_pack_blocked"
    assert "source_bundle" in pack.missing_or_mismatched
    source = next(item for item in pack.evidence if item.name == "source_bundle")
    assert source.error is not None
    assert "sha256 mismatch" in source.error


def test_artifact_evidence_pack_blocks_on_checksum_mismatch(tmp_path: Path) -> None:
    paths = _write_ready_fixture(tmp_path, release_sha="4" * 40)
    checksum_report = paths["reports"] / "stage5-artifact-checksums-20260615.json"
    payload = json.loads(checksum_report.read_text(encoding="utf-8"))
    payload["checksums"][0]["sha256"] = "f" * 64
    _write_json(checksum_report, payload)

    pack = build_artifact_evidence_pack(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="4" * 40,
    )

    assert pack.status == "artifact_evidence_pack_blocked"
    assert "checksums" in pack.missing_or_mismatched
    checksums = next(item for item in pack.evidence if item.name == "checksums")
    assert checksums.error is not None
    assert "checksum mismatch" in checksums.error


def test_artifact_evidence_pack_blocks_when_evidence_sha_is_stale(tmp_path: Path) -> None:
    current_sha = "5" * 40
    paths = _write_ready_fixture(tmp_path, release_sha="6" * 40)

    pack = build_artifact_evidence_pack(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha=current_sha,
        release_sha=current_sha,
    )

    assert pack.status == "artifact_evidence_pack_blocked"
    assert set(pack.missing_or_mismatched) == {
        "source_bundle",
        "image_digests",
        "sbom",
        "helm_package",
        "checksums",
    }
    sha_check = next(check for check in pack.checks if check.name == "artifact_evidence_bound_to_release_sha")
    assert sha_check.status == "failed"


def test_artifact_evidence_pack_writes_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_ready_fixture(tmp_path, release_sha="5" * 40)
    pack = build_artifact_evidence_pack(
        report_dir=paths["reports"],
        release_dir=paths["release"],
        root=tmp_path,
        current_head_sha="5" * 40,
    )
    output_json = tmp_path / "reports" / "stage5-artifact-evidence-pack-20260615.json"
    output_md = tmp_path / "reports" / "stage5-artifact-evidence-pack-20260615.md"

    write_report(pack, output_json)
    write_markdown_report(pack, output_md)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "artifact_evidence_pack_ready"
    assert payload["release_sha"] == "5" * 40
    assert payload["deploy_performed"] is False
    assert payload["tag_performed"] is False
    assert payload["release_performed"] is False
    assert "Stage 5 Artifact Evidence Pack" in markdown
    assert "artifact_evidence_pack_ready" in markdown
    assert render_markdown_report(pack) == markdown
