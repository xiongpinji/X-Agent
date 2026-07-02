from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from backend.app.core.skill_bundles import (
    build_skill_catalog,
    package_skill_bundle,
    skill_manifest_sha256,
    verify_skill_bundle,
)
from backend.app.core.skill_market_models import SkillManifest
from backend.app.core.storage import dumps_json


def _manifest(**overrides: object) -> SkillManifest:
    payload = {
        "name": "Bundle Echo",
        "name_zh": "回声技能包",
        "version": "1.0.0",
        "author": "x-agent",
        "description": "Offline skill bundle fixture.",
        "description_zh": "离线技能包测试夹具。",
        "keywords": ["bundle", "echo"],
        "tags": ["development"],
        "capabilities": ["echo_text"],
        "dependencies": {},
        "permissions": ["file:read"],
        "entry_point": "skills.echo:run",
    }
    payload.update(overrides)
    return SkillManifest.model_validate(payload)


def _write_manifest(path: Path, manifest: SkillManifest) -> None:
    path.write_text(dumps_json(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")


def test_skill_bundle_package_verify_and_catalog(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "skill-manifest.json"
    bundle_path = tmp_path / "bundles" / "bundle.echo.zip"
    catalog_path = tmp_path / "catalog.json"
    _write_manifest(manifest_path, manifest)

    packaged = package_skill_bundle(
        manifest_path=manifest_path,
        output=bundle_path,
        source="local-test",
    )
    verified = verify_skill_bundle(bundle_path)
    catalog = build_skill_catalog(
        bundles_dir=bundle_path.parent,
        output=catalog_path,
    )

    assert packaged["ok"] is True
    assert packaged["verification"]["ok"] is True
    assert bundle_path.is_file()
    assert list(bundle_path.parent.glob(".bundle.echo.zip.*.tmp")) == []
    assert verified["skill_name"] == "Bundle Echo"
    assert verified["manifest_sha256"] == skill_manifest_sha256(manifest)
    assert catalog["ok"] is True
    assert catalog["catalog"]["scanned_count"] == 1
    assert catalog["catalog"]["valid_count"] == 1
    assert catalog["catalog"]["entries"][0]["skill_name"] == "Bundle Echo"
    assert catalog["catalog"]["entries"][0]["risk_level"] == "medium"
    assert catalog["catalog"]["entries"][0]["manifest_sha256"] == verified["manifest_sha256"]
    assert json.loads(catalog_path.read_text(encoding="utf-8"))["bundle_count"] == 1
    assert list(catalog_path.parent.glob(".catalog.json.*.tmp")) == []


def test_skill_bundle_dry_run_does_not_write_archive(tmp_path: Path) -> None:
    manifest_path = tmp_path / "skill-manifest.json"
    bundle_path = tmp_path / "bundle.echo.zip"
    _write_manifest(manifest_path, _manifest())

    result = package_skill_bundle(manifest_path=manifest_path, output=bundle_path, dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["bundle_manifest"]["kind"] == "xagent_skill_market_bundle"
    assert not bundle_path.exists()


def test_skill_bundle_verify_rejects_tampered_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "skill-manifest.json"
    bundle_path = tmp_path / "bundle.echo.zip"
    tampered_path = tmp_path / "bundle.tampered.zip"
    _write_manifest(manifest_path, manifest)
    package_skill_bundle(manifest_path=manifest_path, output=bundle_path)

    with zipfile.ZipFile(bundle_path) as source, zipfile.ZipFile(tampered_path, "w") as target:
        target.writestr("bundle-manifest.json", source.read("bundle-manifest.json"))
        tampered = manifest.model_copy(update={"version": "9.9.9"})
        target.writestr("skill-manifest.json", dumps_json(tampered.model_dump(mode="json"), indent=2))

    with pytest.raises(ValueError, match="hash mismatch"):
        verify_skill_bundle(tampered_path)


def test_skill_bundle_catalog_records_invalid_bundle(tmp_path: Path) -> None:
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    bad_bundle = bundles_dir / "bad.zip"
    bad_bundle.write_text("not a zip", encoding="utf-8")

    catalog = build_skill_catalog(
        bundles_dir=bundles_dir,
        output=tmp_path / "catalog.json",
    )

    assert catalog["ok"] is False
    assert catalog["catalog"]["valid_count"] == 0
    assert catalog["catalog"]["invalid_count"] == 1
    assert catalog["catalog"]["entries"][0]["status"] == "failed"


def test_skill_bundle_catalog_filters_entries(tmp_path: Path) -> None:
    bundles_dir = tmp_path / "bundles"
    catalog_path = tmp_path / "catalog.json"
    low_manifest_path = tmp_path / "low-skill-manifest.json"
    high_manifest_path = tmp_path / "high-skill-manifest.json"
    low_bundle_path = bundles_dir / "bundle.low.zip"
    high_bundle_path = bundles_dir / "bundle.high.zip"
    bad_bundle_path = bundles_dir / "broken.zip"
    _write_manifest(low_manifest_path, _manifest(name="Low Bundle", permissions=[]))
    _write_manifest(
        high_manifest_path,
        _manifest(name="High Bundle", name_zh="高风险技能包", permissions=["network:write"]),
    )
    package_skill_bundle(manifest_path=low_manifest_path, output=low_bundle_path)
    package_skill_bundle(manifest_path=high_manifest_path, output=high_bundle_path)
    bad_bundle_path.write_text("not a zip", encoding="utf-8")

    catalog = build_skill_catalog(
        bundles_dir=bundles_dir,
        output=catalog_path,
        query="high",
        status="passed",
        risk_level="high",
    )

    assert catalog["ok"] is True
    assert catalog["catalog"]["scanned_count"] == 3
    assert catalog["catalog"]["bundle_count"] == 1
    assert catalog["catalog"]["filters"] == {
        "query": "high",
        "status": "passed",
        "risk_level": "high",
    }
    assert catalog["catalog"]["entries"][0]["skill_name"] == "High Bundle"
