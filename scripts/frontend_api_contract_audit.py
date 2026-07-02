"""Audit frontend API references against mounted FastAPI routes.

The audit intentionally uses ``backend.app.main:app.routes`` as the backend
source of truth. Deferred first-version frontend surfaces can stay in the repo,
but they must be excluded explicitly with a reason so they do not masquerade as
commercially shipped paths.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi.routing import APIRoute

from backend.app.main import app


API_REF_RE = re.compile(r"""['"`](/api/[^'"`\s]+)""")
TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]+\}")
ENCODE_COMPONENT_RE = re.compile(r"\$\{encodeURIComponent\([^}]+\)\}")
UUIDISH_RE = re.compile(r"\b[0-9a-fA-F]{8,}(?:-[0-9a-fA-F]{4,})*\b")
NUMERIC_SEGMENT_RE = re.compile(r"(?<=/)\d+(?=/|$)")

DEFAULT_EXCLUDED_PARTS = {
    "__tests__",
    "marketplace",
    "templates",
}
DEFAULT_EXCLUDED_FILES = {
    Path("frontend/src/components/AnalyticsDashboard.tsx"),
    Path("frontend/src/components/Forum.tsx"),
    Path("frontend/src/utils/pushNotificationManager.ts"),
    Path("frontend/src/components/streaming/RealtimeVisualization.tsx"),
}


@dataclass(frozen=True)
class FrontendApiRef:
    file: str
    path: str


def _normalize_frontend_path(path: str) -> str:
    path = path.split("?", 1)[0].split("#", 1)[0]
    path = ENCODE_COMPONENT_RE.sub("{param}", path)
    path = TEMPLATE_EXPR_RE.sub("{param}", path)
    path = UUIDISH_RE.sub("{param}", path)
    path = NUMERIC_SEGMENT_RE.sub("{param}", path)
    return path.rstrip("/") or path


def _normalize_fastapi_path(path: str) -> str:
    path = re.sub(r"\{[^}]+\}", "{param}", path)
    return path.rstrip("/") or path


def mounted_api_routes() -> set[str]:
    routes: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            routes.add(_normalize_fastapi_path(route.path))
    return routes


def _is_excluded_frontend_file(path: Path, root: Path) -> bool:
    rel = path.as_posix()
    parts = set(path.parts)
    if parts.intersection(DEFAULT_EXCLUDED_PARTS):
        return True
    try:
        repo_rel = path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        repo_rel = rel
    if Path(repo_rel) in DEFAULT_EXCLUDED_FILES:
        return True
    try:
        root_rel = path.relative_to(root).as_posix()
    except ValueError:
        root_rel = rel
    return any(str(excluded).endswith(root_rel) for excluded in DEFAULT_EXCLUDED_FILES)


def frontend_api_refs(frontend_root: Path) -> list[FrontendApiRef]:
    refs: set[FrontendApiRef] = set()
    for path in frontend_root.rglob("*"):
        if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if _is_excluded_frontend_file(path, frontend_root):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in API_REF_RE.finditer(text):
            refs.add(FrontendApiRef(file=path.as_posix(), path=_normalize_frontend_path(match.group(1))))
    return sorted(refs, key=lambda item: (item.path, item.file))


def allowlist_entries(path: Path) -> set[str]:
    if not path.exists():
        return set()
    entries: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- `/api/"):
            entries.add(line.split("`", 2)[1].rstrip("/"))
    return entries


def audit_frontend_api_contract(frontend_root: Path, allowlist_path: Path) -> dict[str, object]:
    mounted = mounted_api_routes()
    refs = frontend_api_refs(frontend_root)
    allowlist = allowlist_entries(allowlist_path)
    missing = [
        {"file": ref.file, "path": ref.path}
        for ref in refs
        if ref.path not in mounted and ref.path not in allowlist
    ]
    return {
        "ok": not missing,
        "mounted_count": len(mounted),
        "frontend_ref_count": len(refs),
        "allowlist_count": len(allowlist),
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-root", default="frontend/src")
    parser.add_argument("--allowlist", default="docs/API_CONTRACT_ALLOWLIST.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit_frontend_api_contract(
        frontend_root=Path(args.frontend_root),
        allowlist_path=Path(args.allowlist),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(
            "OK frontend API contract clean "
            f"refs={result['frontend_ref_count']} mounted={result['mounted_count']} "
            f"allowlist={result['allowlist_count']}"
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
