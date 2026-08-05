"""Generate a simplified CycloneDX 1.5 SBOM for the X-Agent repository.

Sources (no third-party Python dependencies, stdlib only):

* Python backend  -- parsed from ``requirements-lock.txt`` (the locked,
  authoritative backend dependency set). Optionally, ``--python-source
  installed`` uses ``<python> -m pip list --format=json`` from a live
  interpreter instead.
* Node.js packages -- parsed from each discovered ``package-lock.json``
  (the resolved dependency tree; no node_modules required). Directories
  with a ``package.json`` but no lockfile are recorded under
  ``metadata.properties`` as ``sbom:skipped`` so the gap is explicit
  instead of silent.

Usage:
    python scripts/generate_sbom.py [--output sbom.json]
                                    [--python-source lockfile|installed]
                                    [--python PATH]

Exit code is always 0 on successful generation; data gaps are reported
in the SBOM metadata, not hidden.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories that hold first-party Node packages worth tracking.
# (package.json discovered dynamically; node_modules / build output excluded.)
NODE_SCAN_DIRS = ["frontend", "desktop/frontend", "mobile", "extension"]

_SKIP_DIR_NAMES = {"node_modules", "venv", ".git", "archive", "dist", "build"}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_lockfile(lock_path: Path) -> list[dict]:
    """Parse requirements-lock.txt into CycloneDX components."""
    components: list[dict] = []
    pin_re = re.compile(r"^([A-Za-z0-9_.\-]+)==([A-Za-z0-9_.!+\-]+)\s*$")
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = pin_re.match(stripped)
        if not m:
            continue
        name, version = m.group(1), m.group(2)
        norm = name.lower().replace("_", "-")
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:pypi/{norm}@{version}",
                "name": norm,
                "version": version,
                "purl": f"pkg:pypi/{norm}@{version}",
                "scope": "required",
                "properties": [{"name": "sbom:source", "value": "requirements-lock.txt"}],
            }
        )
    return components


def _installed_python_packages(python: str) -> list[dict]:
    """List packages from a live interpreter via pip list."""
    out = subprocess.run(
        [python, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
        capture_output=True,
        text=True,
        check=True,
    )
    components = []
    for pkg in json.loads(out.stdout):
        norm = pkg["name"].lower().replace("_", "-")
        version = pkg["version"]
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:pypi/{norm}@{version}",
                "name": norm,
                "version": version,
                "purl": f"pkg:pypi/{norm}@{version}",
                "scope": "required",
                "properties": [{"name": "sbom:source", "value": "pip list (installed env)"}],
            }
        )
    return components


def _parse_package_lock(lock_path: Path, project_dir: Path) -> tuple[list[dict], int]:
    """Parse a package-lock.json v2/v3 into CycloneDX components.

    Returns (components, total_entries).
    """
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = data.get("packages", {})
    components: list[dict] = []
    for path_key, info in packages.items():
        if not path_key:  # root project entry
            continue
        if "node_modules/" not in path_key:
            continue
        name = path_key.split("node_modules/")[-1]
        version = str(info.get("version", "0.0.0"))
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:npm/{name}@{version}",
                "name": name,
                "version": version,
                "purl": f"pkg:npm/{name}@{version}",
                "scope": "required" if not info.get("dev") else "optional",
                "properties": [
                    {
                        "name": "sbom:source",
                        "value": str(lock_path.relative_to(REPO_ROOT)),
                    },
                    {"name": "sbom:project", "value": str(project_dir.relative_to(REPO_ROOT))},
                ],
            }
        )
    return components, len(packages)


def build_sbom(python_source: str, python: str) -> dict:
    components: list[dict] = []
    properties: list[dict] = []

    # --- Python ---
    if python_source == "lockfile":
        lock_path = REPO_ROOT / "requirements-lock.txt"
        if lock_path.is_file():
            py_components = _parse_lockfile(lock_path)
            properties.append(
                {"name": "sbom:python-source", "value": "requirements-lock.txt"}
            )
        else:
            py_components = []
            properties.append(
                {
                    "name": "sbom:skipped",
                    "value": "python: requirements-lock.txt not found",
                }
            )
    else:
        try:
            py_components = _installed_python_packages(python)
            properties.append(
                {"name": "sbom:python-source", "value": f"pip list via {python}"}
            )
        except Exception as exc:  # noqa: BLE001 - gap must be explicit, not silent
            py_components = []
            properties.append(
                {"name": "sbom:skipped", "value": f"python: pip list failed: {exc}"}
            )
    components.extend(py_components)

    # --- Node ---
    for rel in NODE_SCAN_DIRS:
        project_dir = REPO_ROOT / rel
        if not (project_dir / "package.json").is_file():
            continue
        lock = project_dir / "package-lock.json"
        if not lock.is_file():
            properties.append(
                {
                    "name": "sbom:skipped",
                    "value": f"{rel}: package.json present but no package-lock.json",
                }
            )
            continue
        try:
            node_components, _ = _parse_package_lock(lock, project_dir)
            components.extend(node_components)
        except Exception as exc:  # noqa: BLE001
            properties.append(
                {"name": "sbom:skipped", "value": f"{rel}: lockfile parse failed: {exc}"}
            )

    # De-duplicate by bom-ref, keeping first occurrence.
    seen: set[str] = set()
    unique: list[dict] = []
    for c in components:
        if c["bom-ref"] in seen:
            continue
        seen.add(c["bom-ref"])
        unique.append(c)
    unique.sort(key=lambda c: (c["purl"].split(":")[0], c["name"], c["version"]))

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _now_iso(),
            "tools": [{"vendor": "X-Agent", "name": "generate_sbom.py", "version": "1.0.0"}],
            "component": {
                "type": "application",
                "bom-ref": "pkg:generic/x-agent@0.2.0-alpha",
                "name": "x-agent",
                "version": "0.2.0-alpha",
            },
            "properties": properties,
        },
        "components": unique,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="sbom.json", help="Output path (default: sbom.json)")
    parser.add_argument(
        "--python-source",
        choices=["lockfile", "installed"],
        default="lockfile",
        help="Python dependency source (default: lockfile)",
    )
    parser.add_argument("--python", default=sys.executable, help="Interpreter for --python-source installed")
    args = parser.parse_args(argv)

    sbom = build_sbom(args.python_source, args.python)
    out_path = Path(args.output)
    out_path.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    skipped = [p["value"] for p in sbom["metadata"]["properties"] if p["name"] == "sbom:skipped"]
    print(f"SBOM written to {out_path} ({len(sbom['components'])} components)")
    for note in skipped:
        print(f"  SKIPPED: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
