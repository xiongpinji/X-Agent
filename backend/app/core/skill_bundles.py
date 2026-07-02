from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.app.core.skill_market_models import SkillManifest
from backend.app.core.storage import atomic_write_json, dumps_json, try_parse_datetime_utc


def skill_manifest_sha256(manifest: SkillManifest) -> str:
    return hashlib.sha256(_manifest_bytes(manifest)).hexdigest()


def package_skill_bundle(
    *,
    manifest_path: Path,
    output: Path,
    source: str = "local",
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = _load_skill_manifest(manifest_path)
    manifest_sha = skill_manifest_sha256(manifest)
    scan = scan_skill_manifest(manifest)
    bundle_manifest = {
        "kind": "xagent_skill_market_bundle",
        "created_at": _utc_now(),
        "source": source,
        "skill_name": manifest.name,
        "version": manifest.version,
        "manifest_sha256": manifest_sha,
        "scan_result": scan,
        "files": [
            {
                "path": "skill-manifest.json",
                "size": len(_manifest_bytes(manifest)),
                "sha256": manifest_sha,
                "kind": "skill_manifest",
            }
        ],
    }
    result = {
        "ok": scan["ok"],
        "output": str(output),
        "dry_run": dry_run,
        "skill_name": manifest.name,
        "version": manifest.version,
        "manifest_sha256": manifest_sha,
        "scan_ok": scan["ok"],
        "error_keys": sorted(scan["errors"]),
        "warning_count": len(scan["warnings"]),
        "bundle_manifest": bundle_manifest,
    }
    if dry_run:
        return result
    _atomic_write_bundle(output, manifest, bundle_manifest)
    result["archive_sha256"] = _sha256_file(output)
    result["verification"] = verify_skill_bundle(output)
    return result


def verify_skill_bundle(bundle_path: Path) -> dict[str, Any]:
    return verify_skill_bundle_bytes(bundle_path.read_bytes(), archive=str(bundle_path))


def verify_skill_bundle_bytes(archive_bytes: bytes, *, archive: str = "<memory>") -> dict[str, Any]:
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive_file:
        names = set(archive_file.namelist())
        if "bundle-manifest.json" not in names:
            raise ValueError("skill bundle missing bundle-manifest.json")
        if "skill-manifest.json" not in names:
            raise ValueError("skill bundle missing skill-manifest.json")
        extra = names - {"bundle-manifest.json", "skill-manifest.json"}
        if extra:
            raise ValueError(f"skill bundle contains unexpected files: {sorted(extra)}")
        bundle_manifest = json.loads(archive_file.read("bundle-manifest.json"))
        if not isinstance(bundle_manifest, dict):
            raise ValueError("skill bundle manifest must be a JSON object")
        if bundle_manifest.get("kind") != "xagent_skill_market_bundle":
            raise ValueError("skill bundle manifest has invalid kind")
        _validate_created_at(bundle_manifest.get("created_at"))
        manifest_payload = json.loads(archive_file.read("skill-manifest.json"))
        manifest = SkillManifest.model_validate(manifest_payload)
        scan = scan_skill_manifest(manifest)
        manifest_sha = skill_manifest_sha256(manifest)
        expected_sha = bundle_manifest.get("manifest_sha256")
        if expected_sha != manifest_sha:
            raise ValueError(
                f"skill bundle manifest hash mismatch: expected {expected_sha}, got {manifest_sha}"
            )
        files = bundle_manifest.get("files")
        if not isinstance(files, list) or len(files) != 1:
            raise ValueError("skill bundle manifest must list exactly one skill manifest file")
        file_entry = files[0]
        if not isinstance(file_entry, dict) or file_entry.get("path") != "skill-manifest.json":
            raise ValueError("skill bundle file entry must reference skill-manifest.json")
        manifest_bytes = archive_file.read("skill-manifest.json")
        if file_entry.get("size") != len(manifest_bytes):
            raise ValueError("skill bundle skill-manifest.json size mismatch")
        if file_entry.get("sha256") != manifest_sha:
            raise ValueError("skill bundle skill-manifest.json sha256 mismatch")
        if bundle_manifest.get("scan_result") != scan:
            raise ValueError("skill bundle scan_result is stale or inconsistent")
        if bundle_manifest.get("skill_name") != manifest.name:
            raise ValueError("skill bundle skill_name mismatch")
        if bundle_manifest.get("version") != manifest.version:
            raise ValueError("skill bundle version mismatch")
        return {
            "ok": True,
            "archive": archive,
            "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
            "skill_name": manifest.name,
            "name_zh": manifest.name_zh,
            "version": manifest.version,
            "manifest_sha256": manifest_sha,
            "scan_ok": scan["ok"],
            "error_keys": sorted(scan["errors"]),
            "warning_count": len(scan["warnings"]),
            "manifest": manifest.model_dump(mode="json"),
            "bundle_manifest": bundle_manifest,
        }


def build_skill_catalog(
    *,
    bundles_dir: Path,
    output: Path,
    dry_run: bool = False,
    query: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for bundle_path in sorted(bundles_dir.glob("*.zip")):
        try:
            verification = verify_skill_bundle(bundle_path)
            bundle_status = "passed"
            error = None
        except (OSError, ValueError, zipfile.BadZipFile, ValidationError, json.JSONDecodeError) as exc:
            verification = {"archive": str(bundle_path)}
            bundle_status = "failed"
            error = str(exc)
        entries.append(
            skill_catalog_entry_from_verification(
                location_key="path",
                location=str(bundle_path),
                verification=verification,
                status=bundle_status,
                error=error,
            )
        )
    filters = normalize_skill_catalog_filters(query=query, status=status, risk_level=risk_level)
    filtered_entries = filter_skill_catalog_entries(entries, **filters)
    catalog = {
        "kind": "xagent_skill_bundle_catalog",
        "generated_at": _utc_now(),
        "bundles_dir": str(bundles_dir),
        "scanned_count": len(entries),
        "bundle_count": len(filtered_entries),
        "valid_count": sum(1 for item in filtered_entries if item["status"] == "passed"),
        "invalid_count": sum(1 for item in filtered_entries if item["status"] == "failed"),
        "filters": filters,
        "entries": filtered_entries,
    }
    result = {"ok": catalog["invalid_count"] == 0, "output": str(output), "dry_run": dry_run, "catalog": catalog}
    if not dry_run:
        atomic_write_json(output, catalog)
    return result


def scan_skill_manifest(manifest: SkillManifest) -> dict[str, Any]:
    errors: dict[str, str] = {}
    warnings: list[str] = []
    if not manifest.name.strip():
        errors["name"] = "Skill name is required."
    if not manifest.name_zh.strip():
        errors["name_zh"] = "Chinese skill name is required."
    if not manifest.version.strip():
        errors["version"] = "Skill version is required."
    if not manifest.description.strip() and not manifest.description_zh.strip():
        warnings.append("Skill bundle has no short description.")
    normalized_permissions = sorted({str(item).strip().lower() for item in manifest.permissions if str(item).strip()})
    risk_level = infer_skill_risk_level(normalized_permissions)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "risk_level": risk_level,
        "permissions": normalized_permissions,
        "capability_count": len(manifest.capabilities),
        "dependency_count": len(manifest.dependencies),
        "tag_count": len(manifest.tags),
    }


def infer_skill_risk_level(permissions: list[str]) -> str:
    permission_text = " ".join(permissions)
    if any(token in permission_text for token in ("admin", "secret", "credential", "system", "shell")):
        return "critical"
    if any(token in permission_text for token in ("write", "delete", "network", "execute")):
        return "high"
    if any(token in permission_text for token in ("read", "file", "browser")):
        return "medium"
    return "low"


def skill_catalog_entry_from_verification(
    *,
    location_key: str,
    location: str | None,
    verification: dict[str, Any],
    status: str,
    error: str | None,
) -> dict[str, Any]:
    manifest = verification.get("manifest") if isinstance(verification.get("manifest"), dict) else {}
    scan_result = verification.get("bundle_manifest", {}).get("scan_result", {})
    if not isinstance(scan_result, dict):
        scan_result = {}
    return {
        location_key: location,
        "status": status,
        "error": error,
        "archive_sha256": verification.get("archive_sha256"),
        "skill_name": verification.get("skill_name"),
        "name_zh": verification.get("name_zh") or manifest.get("name_zh"),
        "description": manifest.get("description"),
        "description_zh": manifest.get("description_zh"),
        "author": manifest.get("author"),
        "version": verification.get("version"),
        "risk_level": scan_result.get("risk_level"),
        "permissions": scan_result.get("permissions"),
        "capability_count": scan_result.get("capability_count"),
        "dependency_count": scan_result.get("dependency_count"),
        "manifest_sha256": verification.get("manifest_sha256"),
        "scan_ok": verification.get("scan_ok"),
        "error_keys": verification.get("error_keys"),
        "warning_count": verification.get("warning_count"),
    }


def normalize_skill_catalog_filters(
    *,
    query: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
) -> dict[str, str | None]:
    normalized_status = status.strip().lower() if status else None
    if normalized_status == "":
        normalized_status = None
    if normalized_status not in {None, "passed", "failed"}:
        raise ValueError("skill catalog status filter must be passed or failed")
    normalized_risk = risk_level.strip().lower() if risk_level else None
    if normalized_risk == "":
        normalized_risk = None
    if normalized_risk not in {None, "low", "medium", "high", "critical"}:
        raise ValueError("skill catalog risk_level filter must be low, medium, high, or critical")
    normalized_query = query.strip().lower() if query else None
    if normalized_query == "":
        normalized_query = None
    return {"query": normalized_query, "status": normalized_status, "risk_level": normalized_risk}


def filter_skill_catalog_entries(
    entries: list[dict[str, Any]],
    *,
    query: str | None = None,
    status: str | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    filtered = []
    for entry in entries:
        if status and entry.get("status") != status:
            continue
        if risk_level and entry.get("risk_level") != risk_level:
            continue
        if query and not _catalog_entry_matches_query(entry, query):
            continue
        filtered.append(entry)
    return filtered


def _catalog_entry_matches_query(entry: dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        str(entry.get(key) or "").lower()
        for key in (
            "path",
            "filename",
            "skill_name",
            "name_zh",
            "description",
            "description_zh",
            "author",
            "version",
            "risk_level",
            "error",
        )
    )
    return query in haystack


def _load_skill_manifest(path: Path) -> SkillManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"skill manifest is not valid JSON: {path}") from exc
    return SkillManifest.model_validate(payload)


def _manifest_bytes(manifest: SkillManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    return dumps_json(payload, indent=2, sort_keys=True).encode("utf-8")


def _atomic_write_bundle(output: Path, manifest: SkillManifest, bundle_manifest: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output.with_name(f".{output.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("bundle-manifest.json", dumps_json(bundle_manifest, indent=2, sort_keys=True))
            archive.writestr("skill-manifest.json", _manifest_bytes(manifest))
        os.replace(tmp_path, output)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _validate_created_at(value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("skill bundle manifest missing created_at")
    if try_parse_datetime_utc(value) is None:
        raise ValueError("skill bundle manifest created_at must be a valid ISO 8601 datetime")
    if not (value.endswith("+00:00") or value.endswith("Z")):
        raise ValueError("skill bundle manifest created_at must be UTC")
