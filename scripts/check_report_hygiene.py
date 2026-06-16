from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _ensure_source_root() -> Path:
    source_root = Path(__file__).resolve().parents[1]
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)
    return source_root


SOURCE_ROOT = _ensure_source_root()

from backend.app.core.storage import atomic_write_json, dumps_json  # noqa: E402

DEFAULT_REPORTS_DIR = Path(".xagent_runtime") / "reports"
DEFAULT_OUTPUT = DEFAULT_REPORTS_DIR / "report-hygiene.json"
SECRET_LIKE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?:sk|pk)-(?:proj-)?[A-Za-z0-9][A-Za-z0-9_-]{10,}")
TEXT_SUFFIXES = frozenset({".json", ".md", ".txt", ".env", ".example", ".yaml", ".yml", ".log", ".out", ".ps1"})
PACKAGE_SUFFIXES = frozenset({".zip"})
MAX_ZIP_TEXT_MEMBER_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Classification:
    category: str
    reason: str
    counts_as_issue: bool = False


def check_report_hygiene(
    *,
    source_root: Path = SOURCE_ROOT,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    include_globs: list[str] | None = None,
    exclude_paths: list[Path] | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    reports_dir = _resolve_path(source_root, reports_dir).resolve()
    include_globs = include_globs or []
    exclude_resolved = {_resolve_path(source_root, path).resolve() for path in (exclude_paths or [])}
    entries = []
    for path in sorted(_iter_report_artifacts(reports_dir, include_globs=include_globs), key=lambda item: item.name):
        if path.resolve() in exclude_resolved:
            continue
        classification = _classify_report_artifact(path)
        payload_status = _payload_status(path) if path.suffix.lower() == ".json" else {}
        secret_like_scan = _secret_like_token_scan(path)
        entry = {
            "path": _redact_secret_like_text(_display_path(path, source_root)),
            "name": _redact_secret_like_text(path.name),
            "artifact_suffix": path.suffix.lower(),
            "category": classification.category,
            "reason": classification.reason,
            "counts_as_issue": classification.counts_as_issue,
            **payload_status,
            **secret_like_scan,
        }
        if _entry_has_structural_issue(entry):
            entry["counts_as_issue"] = True
        entries.append(entry)

    issue_entries = [item for item in entries if item.get("counts_as_issue") is True]
    secret_entries = [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "secret_like_tokens_count": item.get("secret_like_tokens_count", 0),
            "secret_like_archive_members_count": item.get("secret_like_archive_members_count", 0),
        }
        for item in entries
        if int(item.get("secret_like_tokens_count") or 0) > 0
    ]
    missing_status_entries = [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "payload_kind": item.get("payload_kind"),
            "payload_ok": item.get("payload_ok"),
            "payload_status": item.get("payload_status"),
        }
        for item in entries
        if item.get("category") == "json_report" and item.get("missing_status_or_ok") is True
    ]
    missing_count_alias_entries = [
        {
            "name": item.get("name"),
            "path": item.get("path"),
            "missing_count_aliases": item.get("missing_count_aliases", []),
        }
        for item in entries
        if item.get("missing_count_aliases")
    ]
    counts = _counts_by_category(entries)
    ok = not issue_entries
    return {
        "kind": "report_hygiene",
        "version": 1,
        "source_root": source_root.as_posix(),
        "reports_dir": _display_path(reports_dir, source_root),
        "include_globs": include_globs,
        "include_globs_count": len(include_globs),
        "ok": ok,
        "status": "passed" if ok else "failed",
        "summary": {
            "artifacts": len(entries),
            "issues": len(issue_entries),
            "json_reports": counts.get("json_report", 0),
            "text_artifacts": counts.get("text_artifact", 0),
            "package_artifacts": counts.get("package_artifact", 0),
            "unknown_artifacts": counts.get("unknown", 0),
            "load_errors": counts.get("load_error", 0),
            "missing_status_or_ok": len(missing_status_entries),
            "missing_count_alias": len(missing_count_alias_entries),
            "secret_like_token_artifacts": len(secret_entries),
            "secret_like_tokens": sum(int(item.get("secret_like_tokens_count") or 0) for item in secret_entries),
        },
        "issue_artifacts": issue_entries,
        "issue_artifacts_count": len(issue_entries),
        "missing_status_or_ok_artifacts": missing_status_entries,
        "missing_status_or_ok_artifacts_count": len(missing_status_entries),
        "missing_count_alias_artifacts": missing_count_alias_entries,
        "missing_count_alias_artifacts_count": len(missing_count_alias_entries),
        "secret_like_token_artifacts": secret_entries,
        "secret_like_token_artifacts_count": len(secret_entries),
        "artifacts": entries,
        "artifacts_count": len(entries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check report artifacts for structural hygiene issues.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-glob",
        action="append",
        default=[],
        help="Only scan report artifact names matching this glob. Can be repeated.",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    output = _resolve_path(source_root, args.output)
    payload = check_report_hygiene(
        source_root=source_root,
        reports_dir=args.reports_dir,
        include_globs=args.include_glob,
        exclude_paths=[output],
    )
    atomic_write_json(output, payload)
    print(dumps_json(payload))
    return 0 if payload["ok"] is True else 1


def _iter_report_artifacts(reports_dir: Path, *, include_globs: list[str] | None = None) -> list[Path]:
    if not reports_dir.exists():
        return []
    include_globs = include_globs or []
    paths = [path for path in reports_dir.iterdir() if path.is_file()]
    if not include_globs:
        return paths
    return [path for path in paths if any(fnmatch.fnmatchcase(path.name, pattern) for pattern in include_globs)]


def _classify_report_artifact(path: Path) -> Classification:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return Classification("json_report", "json_report_payload")
    if suffix in TEXT_SUFFIXES:
        return Classification("text_artifact", "text_or_operator_artifact")
    if suffix in PACKAGE_SUFFIXES:
        return Classification("package_artifact", "packaged_report_artifact")
    return Classification("unknown", "unclassified_report_artifact", counts_as_issue=True)


def _payload_status(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "payload_load_error": str(exc),
            "category": "load_error",
            "counts_as_issue": True,
        }
    if not isinstance(payload, dict):
        return {
            "payload_kind": None,
            "payload_ok": None,
            "payload_status": None,
            "missing_status_or_ok": True,
            "missing_count_aliases": [],
        }
    return {
        "payload_kind": payload.get("kind"),
        "payload_ok": payload.get("ok"),
        "payload_status": payload.get("status"),
        "missing_status_or_ok": payload.get("status") is None and payload.get("ok") is None,
        "missing_count_aliases": _missing_count_aliases(payload),
    }


def _entry_has_structural_issue(entry: dict[str, Any]) -> bool:
    return bool(
        entry.get("payload_load_error")
        or entry.get("missing_status_or_ok")
        or entry.get("missing_count_aliases")
        or int(entry.get("secret_like_tokens_count") or 0) > 0
    )


def _counts_by_category(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in entries:
        category = str(item.get("category") or "unknown")
        counts[category] = counts.get(category, 0) + 1
    return counts


def _missing_count_aliases(payload: dict[str, Any]) -> list[str]:
    return sorted(
        f"{key}_count"
        for key, value in payload.items()
        if isinstance(value, list) and f"{key}_count" not in payload
    )


def _secret_like_token_scan(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return {"secret_like_tokens_count": 0, "secret_like_archive_members_count": 0}
        return {
            "secret_like_tokens_count": len(SECRET_LIKE_TOKEN_RE.findall(content)),
            "secret_like_archive_members_count": 0,
        }
    if suffix == ".zip":
        return _secret_like_zip_token_scan(path)
    return {"secret_like_tokens_count": 0, "secret_like_archive_members_count": 0}


def _secret_like_zip_token_scan(path: Path) -> dict[str, Any]:
    tokens_count = 0
    members_count = 0
    try:
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir() or member.file_size > MAX_ZIP_TEXT_MEMBER_BYTES:
                    continue
                if Path(member.filename).suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    content = archive.read(member).decode("utf-8")
                except (KeyError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile):
                    continue
                member_tokens_count = len(SECRET_LIKE_TOKEN_RE.findall(content))
                if member_tokens_count:
                    tokens_count += member_tokens_count
                    members_count += 1
    except (OSError, zipfile.BadZipFile):
        return {"secret_like_tokens_count": 0, "secret_like_archive_members_count": 0}
    return {
        "secret_like_tokens_count": tokens_count,
        "secret_like_archive_members_count": members_count,
    }


def _resolve_path(source_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else source_root / path


def _display_path(path: Path, source_root: Path) -> str:
    try:
        return path.resolve().relative_to(source_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _redact_secret_like_text(value: str) -> str:
    return SECRET_LIKE_TOKEN_RE.sub("<redacted-secret-like-token>", value)


if __name__ == "__main__":
    raise SystemExit(main())
