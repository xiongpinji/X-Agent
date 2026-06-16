from __future__ import annotations

import argparse
import fnmatch
import json
import sys
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
DEFAULT_OUTPUT = DEFAULT_REPORTS_DIR / "report-count-alias-normalization.json"


def normalize_report_count_aliases(
    *,
    source_root: Path = SOURCE_ROOT,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    output: Path = DEFAULT_OUTPUT,
    dry_run: bool = False,
    include_globs: list[str] | None = None,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    reports_dir = _resolve_path(source_root, reports_dir).resolve()
    output = _resolve_path(source_root, output)
    include_globs = include_globs or []
    entries: list[dict[str, Any]] = []
    scanned = 0

    for path in sorted(_iter_json_reports(reports_dir, include_globs=include_globs), key=lambda item: item.name):
        if path.resolve() == output.resolve():
            continue
        scanned += 1
        payload = _load_json_object(path)
        if payload is None:
            continue
        aliases = _missing_count_aliases(payload)
        if not aliases:
            continue
        if not dry_run:
            for field, count_field in aliases.items():
                payload[count_field] = len(payload[field])
            atomic_write_json(path, payload)
        entries.append(
            {
                "path": _display_path(path, source_root),
                "added_count_aliases": sorted(aliases.values()),
                "added_count_aliases_count": len(aliases),
            }
        )

    summary = {
        "reports_scanned": scanned,
        "reports_updated": len(entries),
        "count_aliases_added": sum(item["added_count_aliases_count"] for item in entries),
    }
    payload = {
        "kind": "report_count_alias_normalization",
        "version": 1,
        "source_root": source_root.as_posix(),
        "reports_dir": _display_path(reports_dir, source_root),
        "include_globs": include_globs,
        "include_globs_count": len(include_globs),
        "dry_run": dry_run,
        "ok": True,
        "status": "planned" if dry_run else "passed",
        "summary": summary,
        "updated_reports": entries,
        "updated_reports_count": len(entries),
    }
    atomic_write_json(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill top-level *_count aliases for JSON report lists.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-glob",
        action="append",
        default=[],
        help="Only normalize JSON report names matching this glob. Can be repeated.",
    )
    args = parser.parse_args()

    payload = normalize_report_count_aliases(
        source_root=args.source_root,
        reports_dir=args.reports_dir,
        output=args.output,
        dry_run=args.dry_run,
        include_globs=args.include_glob,
    )
    print(dumps_json(payload, indent=2))
    return 0


def _missing_count_aliases(payload: dict[str, Any]) -> dict[str, str]:
    return {
        key: f"{key}_count"
        for key, value in payload.items()
        if isinstance(value, list) and f"{key}_count" not in payload
    }


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _iter_json_reports(reports_dir: Path, *, include_globs: list[str] | None = None) -> list[Path]:
    if not reports_dir.exists():
        return []
    include_globs = include_globs or []
    paths = [path for path in reports_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"]
    if not include_globs:
        return paths
    return [path for path in paths if any(fnmatch.fnmatchcase(path.name, pattern) for pattern in include_globs)]


def _resolve_path(source_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else source_root / path


def _display_path(path: Path, source_root: Path) -> str:
    try:
        return path.resolve().relative_to(source_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
