#!/usr/bin/env python3
"""Validate dependency and supply-chain gates for the commercial RC.

The gate stays deterministic and local where possible. It checks project
manifests, lockfiles, CI install discipline, and runs the frontend npm audit
that is already part of the commercial RC workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".xagent_runtime" / "reports"
DEFAULT_SOURCE_BUNDLE = REPORT_DIR / "rc-source-bundle.json"
DEFAULT_STAGING_PLAN = REPORT_DIR / "rc-staging-plan.json"
DEFAULT_CI_CONTRACT = REPORT_DIR / "rc-ci-contract.json"
DEFAULT_OUTPUT = ROOT / ".xagent_runtime" / "reports" / "rc-supply-chain-gate.json"
SECRET_KEY_OUTPUT_RE = re.compile(r"(?i)(\b[A-Z0-9_]*(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*).+")
SECRET_VALUE_OUTPUT_RE = re.compile(r"\b(?:sk|ghp|github_pat|xagent)[_-][A-Za-z0-9_=-]{24,}\b")
LOCAL_USER_PATH_OUTPUT_RE = re.compile(
    r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s\"']+(?:[\\/]+[^\\/\s\"']+)*"
    r"|(?<!\w)/(?:Users|home)/[^/\s\"']+(?:/[^/\s\"']+)*"
)
LOCAL_RUNTIME_MARKER_RE = re.compile(r"(?i)\bhermes-agent\b")
NPM_REGISTRY_PREFIX = "https://registry.npmjs.org/"
REQUIRED_PYPROJECT_DEV_TOOLS = ("aiosqlite", "pip-audit")


@dataclass(frozen=True)
class SupplyChainCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class SupplyChainGateReport:
    status: str
    generated_at: str
    checks: list[SupplyChainCheck]
    next_commands: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(check) for check in self.checks]
        return payload


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _load_report(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return _load_json(path), None
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return None, str(exc)


def _run_command(command: list[str], *, cwd: Path, timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )


def _tail(text: str, max_chars: int = 2000) -> str:
    sanitized = _sanitize_output_text(text)
    return sanitized[-max_chars:]


def _sanitize_output_text(text: str) -> str:
    text = SECRET_KEY_OUTPUT_RE.sub(r"\1<redacted-output>", text)
    text = SECRET_VALUE_OUTPUT_RE.sub("<redacted-secret>", text)
    text = LOCAL_USER_PATH_OUTPUT_RE.sub("<redacted-local-path>", text)
    return LOCAL_RUNTIME_MARKER_RE.sub("<redacted-local-runtime>", text)


def _npm_executable() -> str:
    for name in ("npm.cmd", "npm"):
        found = shutil.which(name)
        if found:
            return found
    return "npm"


def _dependency_name(specifier: object) -> str:
    match = re.match(r"^([A-Za-z0-9_.-]+)", str(specifier).strip())
    return match.group(1).lower().replace("_", "-") if match else ""


def check_python_manifest(root: Path = ROOT) -> SupplyChainCheck:
    path = root / "pyproject.toml"
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, tomllib.TOMLDecodeError) as exc:
        return SupplyChainCheck("python_manifest", "failed", error=str(exc))

    project = payload.get("project") or {}
    dependencies = project.get("dependencies") or []
    optional = project.get("optional-dependencies") or {}
    missing: list[str] = []
    if project.get("requires-python") != ">=3.11":
        missing.append("project.requires-python must be >=3.11")
    for package in (
        "bcrypt",
        "cryptography",
        "fastapi",
        "pydantic",
        "python-multipart",
        "scikit-learn",
        "sqlalchemy",
        "uvicorn",
        "redis",
        "celery",
    ):
        if not any(str(item).lower().startswith(package) for item in dependencies):
            missing.append(f"missing runtime dependency {package}")
    for extra in ("dev", "cli"):
        if extra not in optional:
            missing.append(f"missing optional dependency group {extra}")
    dev_dependencies = optional.get("dev")
    dev_dependency_names: set[str] = set()
    if not isinstance(dev_dependencies, list):
        missing.append("optional dependency group dev must be a list")
    else:
        dev_dependency_names = {_dependency_name(item) for item in dev_dependencies}
    missing_dev_tools = sorted(tool for tool in REQUIRED_PYPROJECT_DEV_TOOLS if tool not in dev_dependency_names)
    for tool in missing_dev_tools:
        missing.append(f"missing dev dependency {tool}")
    return SupplyChainCheck(
        name="python_manifest",
        status="passed" if not missing else "failed",
        details={
            "path": str(path),
            "runtime_dependency_count": len(dependencies),
            "optional_groups": sorted(optional.keys()),
            "requires_python": project.get("requires-python"),
            "required_dev_tools": sorted(REQUIRED_PYPROJECT_DEV_TOOLS),
            "missing_dev_tools": missing_dev_tools,
            "missing": missing,
        },
        error=None if not missing else "Python dependency manifest contract failed.",
    )


def _parse_pinned_requirements(text: str) -> tuple[dict[str, str], list[str]]:
    packages: dict[str, str] = {}
    unpinned: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[.*?\])?==([^;\s]+)", line)
        if match:
            packages[match.group(1).lower().replace("_", "-")] = match.group(2)
            continue
        unpinned.append(line)
    return packages, unpinned


def check_python_lockfile(root: Path = ROOT, *, timeout_seconds: float = 120.0) -> SupplyChainCheck:
    path = root / "requirements-lock.txt"
    try:
        packages, unpinned = _parse_pinned_requirements(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return SupplyChainCheck("python_lockfile", "failed", error=str(exc))

    required = {
        "asyncpg",
        "bcrypt",
        "celery",
        "cryptography",
        "fastapi",
        "httpx",
        "langfuse",
        "openai",
        "playwright",
        "psycopg",
        "psycopg-binary",
        "pydantic",
        "python-multipart",
        "qdrant-client",
        "redis",
        "scikit-learn",
        "sqlalchemy",
        "uvicorn",
    }
    missing = sorted(required.difference(packages))
    problems = []
    if missing:
        problems.append(f"missing locked runtime dependencies: {missing}")
    if unpinned:
        problems.append(f"requirements-lock.txt contains unpinned entries: {unpinned}")

    audit_details: dict[str, Any] = {"tool_available": False, "status": "missing"}
    pip_audit = shutil.which("pip-audit")
    if not pip_audit:
        audit_details["error"] = "pip-audit executable was not found on PATH."
        problems.append("pip-audit is required for commercial RC Python vulnerability evidence.")
    else:
        command = [pip_audit, "-r", str(path), "--format", "json", "--no-deps", "--disable-pip"]
        display_command = ["pip-audit", "-r", str(path.relative_to(root)), "--format", "json", "--no-deps", "--disable-pip"]
        audit_details = {"tool_available": True, "command": display_command}
        try:
            result = _run_command(command, cwd=root, timeout_seconds=timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as exc:
            audit_details.update({"status": "failed", "error": str(exc)})
            problems.append("pip-audit could not complete for Python dependency vulnerability evidence.")
        else:
            audit_details.update(
                {
                    "status": "passed" if result.returncode == 0 else "failed",
                    "exit_code": result.returncode,
                    "stdout_tail": _tail(result.stdout),
                    "stderr_tail": _tail(result.stderr),
                }
            )
            try:
                payload = json.loads(result.stdout or "{}")
            except json.JSONDecodeError as exc:
                audit_details["error"] = f"pip-audit did not emit JSON: {exc}"
                problems.append("pip-audit did not emit parseable JSON vulnerability evidence.")
            else:
                vulnerabilities = [
                    vuln
                    for dependency in payload.get("dependencies", [])
                    if isinstance(dependency, dict)
                    for vuln in dependency.get("vulns", [])
                ]
                audit_details["vulnerability_count"] = len(vulnerabilities)
                if vulnerabilities:
                    audit_details["status"] = "failed"
                    problems.append("pip-audit reported Python dependency vulnerabilities.")
                elif result.returncode != 0:
                    audit_details["error"] = "pip-audit exited non-zero without vulnerability JSON."
                    problems.append("pip-audit exited non-zero without vulnerability JSON.")

    return SupplyChainCheck(
        name="python_lockfile",
        status="passed" if not problems else "failed",
        details={
            "path": str(path),
            "locked_dependency_count": len(packages),
            "required_runtime_dependencies": sorted(required),
            "missing_runtime_dependencies": missing,
            "unpinned_entries": unpinned,
            "pip_audit": audit_details,
        },
        error="; ".join(problems) if problems else None,
    )


def check_frontend_lockfile(root: Path = ROOT) -> SupplyChainCheck:
    package_path = root / "frontend" / "package.json"
    lock_path = root / "frontend" / "package-lock.json"
    try:
        package = _load_json(package_path)
        lock = _load_json(lock_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        return SupplyChainCheck("frontend_lockfile", "failed", error=str(exc))

    root_package = (lock.get("packages") or {}).get("") or {}
    problems: list[str] = []
    if lock.get("lockfileVersion", 0) < 3:
        problems.append("package-lock.json must use lockfileVersion >= 3")
    for field_name in ("name", "version"):
        if package.get(field_name) != lock.get(field_name):
            problems.append(f"package-lock root {field_name} does not match package.json")
        if package.get(field_name) != root_package.get(field_name):
            problems.append(f"package-lock packages[''] {field_name} does not match package.json")
    package_deps = package.get("dependencies") or {}
    lock_deps = root_package.get("dependencies") or {}
    for dependency in sorted(package_deps):
        if dependency not in lock_deps:
            problems.append(f"dependency {dependency} missing from package-lock root package")
    packages = lock.get("packages")
    scanned_packages = 0
    missing_integrity: list[str] = []
    missing_resolved: list[str] = []
    missing_version: list[str] = []
    non_registry_resolved: list[dict[str, str]] = []
    if not isinstance(packages, dict) or not packages:
        problems.append("package-lock packages section is missing or empty")
        packages = {}
    for lock_entry_path, package_entry in packages.items():
        if lock_entry_path == "":
            continue
        if not isinstance(package_entry, dict):
            problems.append(f"package-lock entry is not an object: {lock_entry_path}")
            continue
        if not str(lock_entry_path).startswith("node_modules/"):
            continue
        scanned_packages += 1
        if not package_entry.get("version"):
            missing_version.append(str(lock_entry_path))
        if package_entry.get("link") is True:
            continue
        resolved = str(package_entry.get("resolved") or "")
        if not resolved:
            missing_resolved.append(str(lock_entry_path))
        elif not resolved.startswith(NPM_REGISTRY_PREFIX):
            non_registry_resolved.append({"path": str(lock_entry_path), "resolved": resolved})
        if not package_entry.get("integrity"):
            missing_integrity.append(str(lock_entry_path))
    if missing_version:
        problems.append("package-lock entries missing version")
    if missing_resolved:
        problems.append("package-lock entries missing resolved source")
    if missing_integrity:
        problems.append("package-lock entries missing integrity")
    if non_registry_resolved:
        problems.append("package-lock contains non-npm-registry resolved sources")
    return SupplyChainCheck(
        name="frontend_lockfile",
        status="passed" if not problems else "failed",
        details={
            "package_json": str(package_path),
            "package_lock": str(lock_path),
            "lockfile_version": lock.get("lockfileVersion"),
            "dependency_count": len(package_deps),
            "dev_dependency_count": len(package.get("devDependencies") or {}),
            "scanned_package_entries": scanned_packages,
            "missing_version": missing_version[:20],
            "missing_resolved": missing_resolved[:20],
            "missing_integrity": missing_integrity[:20],
            "non_registry_resolved": non_registry_resolved[:20],
            "problems": problems,
        },
        error=None if not problems else "Frontend package lockfile contract failed.",
    )


def check_npm_audit(root: Path = ROOT, *, timeout_seconds: float = 120.0) -> SupplyChainCheck:
    command = [_npm_executable(), "audit", "--audit-level=moderate", "--json"]
    try:
        result = _run_command(command, cwd=root / "frontend", timeout_seconds=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SupplyChainCheck("npm_audit", "failed", details={"command": command}, error=str(exc))

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return SupplyChainCheck(
            "npm_audit",
            "failed",
            details={"exit_code": result.returncode, "stdout_tail": _tail(result.stdout), "stderr_tail": _tail(result.stderr)},
            error=f"npm audit did not emit JSON: {exc}",
        )
    vulnerabilities = ((payload.get("metadata") or {}).get("vulnerabilities") or {})
    moderate_plus = sum(int(vulnerabilities.get(level, 0) or 0) for level in ("moderate", "high", "critical"))
    ok = result.returncode == 0 and moderate_plus == 0
    return SupplyChainCheck(
        name="npm_audit",
        status="passed" if ok else "failed",
        details={
            "command": command,
            "exit_code": result.returncode,
            "vulnerabilities": vulnerabilities,
            "stderr_tail": _tail(result.stderr),
        },
        error=None if ok else "npm audit reported moderate-or-higher vulnerabilities.",
    )


def check_ci_dependency_contract(root: Path = ROOT) -> SupplyChainCheck:
    path = root / ".github" / "workflows" / "commercial-rc.yml"
    try:
        text = _normalize_workflow_text(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return SupplyChainCheck("ci_dependency_contract", "failed", error=str(exc))
    required = [
        "cache-dependency-path: frontend/package-lock.json",
        "working-directory: frontend",
        "npm ci",
        "npm audit --audit-level=moderate",
        'python -m pip install -e ".[dev,cli]"',
        "python -m pip show pip-audit",
    ]
    missing = [token for token in required if token not in text]
    forbidden_patterns = {
        "npm install": re.compile(r"(?m)^\s*(?:run:\s*)?npm install(?:\s|$)"),
        "pip install -r requirements.txt": re.compile(r"(?m)^\s*(?:run:\s*)?pip install -r requirements\.txt(?:\s|$)"),
    }
    forbidden = [name for name, pattern in forbidden_patterns.items() if pattern.search(text)]
    return SupplyChainCheck(
        name="ci_dependency_contract",
        status="passed" if not missing and not forbidden else "failed",
        details={"workflow": str(path), "missing": missing, "forbidden": forbidden},
        error=None if not missing and not forbidden else "CI dependency contract failed.",
    )


def _bundle_paths(payload: dict[str, Any] | None) -> set[str]:
    paths: set[str] = set()
    for item in (payload or {}).get("files", []):
        if isinstance(item, dict) and item.get("path"):
            paths.add(str(item["path"]).replace("\\", "/"))
    return paths


def _bundle_hashes(payload: dict[str, Any] | None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in (payload or {}).get("files", []):
        if isinstance(item, dict) and item.get("path") and item.get("sha256"):
            hashes[str(item["path"]).replace("\\", "/")] = str(item["sha256"])
    return hashes


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def _strip_yaml_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index].rstrip()
    return line


def _normalize_workflow_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\\", "/")
    return "\n".join(_strip_yaml_comment(line) for line in normalized.splitlines())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_release_dependency_evidence(
    source_bundle_report: Path = DEFAULT_SOURCE_BUNDLE,
    staging_plan_report: Path = DEFAULT_STAGING_PLAN,
    ci_contract_report: Path = DEFAULT_CI_CONTRACT,
) -> SupplyChainCheck:
    source_payload, source_error = _load_report(source_bundle_report)
    staging_payload, staging_error = _load_report(staging_plan_report)
    ci_payload, ci_error = _load_report(ci_contract_report)
    problems: list[str] = []
    required_bundle_files = {
        ".github/workflows/commercial-rc.yml",
        "docs/RC_STAGING_MANIFEST.md",
        "frontend/package.json",
        "frontend/package-lock.json",
        "pyproject.toml",
        "requirements-lock.txt",
        "scripts/rc_supply_chain_gate.py",
        "tests/test_rc_supply_chain_gate.py",
    }

    if source_error:
        problems.append(f"source_bundle_report: {source_error}")
    if staging_error:
        problems.append(f"staging_plan_report: {staging_error}")
    if ci_error:
        problems.append(f"ci_contract_report: {ci_error}")

    source_count = (source_payload or {}).get("file_count")
    staging_count = (staging_payload or {}).get("file_count")
    if source_count is None or staging_count is None:
        problems.append("source_bundle and staging_plan file_count fields must both be present")
    elif source_count != staging_count:
        problems.append(f"source/staging file_count mismatch: source={source_count}, staging={staging_count}")

    ci_status = str((ci_payload or {}).get("status") or "")
    ci_findings = (ci_payload or {}).get("findings")
    if ci_payload is not None and ci_status != "passed":
        problems.append(f"ci_contract status must be passed, got {ci_status}")
    if isinstance(ci_findings, list) and ci_findings:
        problems.append("ci_contract findings must be empty")
    elif ci_findings not in (None, []) and not isinstance(ci_findings, list):
        problems.append("ci_contract findings must be a list")

    bundle_paths = _bundle_paths(source_payload)
    bundle_hashes = _bundle_hashes(source_payload)
    missing_required = sorted(required_bundle_files.difference(bundle_paths))
    if missing_required:
        problems.append(f"source bundle is missing dependency/CI files: {missing_required}")
    missing_hashes = sorted(path for path in required_bundle_files if path in bundle_paths and not _is_sha256(bundle_hashes.get(path, "")))
    if missing_hashes:
        problems.append(f"source bundle dependency/CI files are missing sha256: {missing_hashes}")
    stale_hashes: list[dict[str, str]] = []
    root = source_bundle_report.resolve().parents[2] if source_bundle_report.is_absolute() else ROOT
    for relative_path in sorted(required_bundle_files):
        recorded_sha = bundle_hashes.get(relative_path, "")
        if not _is_sha256(recorded_sha):
            continue
        current_path = root / relative_path
        if not current_path.is_file():
            continue
        current_sha = _sha256_file(current_path)
        if current_sha != recorded_sha:
            stale_hashes.append(
                {
                    "path": relative_path,
                    "bundle_sha256": recorded_sha,
                    "current_sha256": current_sha,
                }
            )
    if stale_hashes:
        problems.append("source bundle dependency/CI file sha256 does not match current worktree")

    staging_manifest_sha = str((staging_payload or {}).get("manifest_sha256") or "")
    bundle_manifest_sha = bundle_hashes.get("docs/RC_STAGING_MANIFEST.md", "")
    if not _is_sha256(staging_manifest_sha):
        problems.append("staging plan manifest_sha256 is missing or invalid")
    elif bundle_manifest_sha != staging_manifest_sha:
        problems.append(
            "source bundle docs/RC_STAGING_MANIFEST.md sha256 does not match staging plan manifest_sha256"
        )

    return SupplyChainCheck(
        name="release_dependency_evidence",
        status="passed" if not problems else "failed",
        details={
            "source_bundle_report": str(source_bundle_report),
            "staging_plan_report": str(staging_plan_report),
            "ci_contract_report": str(ci_contract_report),
            "file_counts": {
                "source_bundle": source_count,
                "staging_plan": staging_count,
            },
            "ci_contract_status": ci_status,
            "required_bundle_files": sorted(required_bundle_files),
            "missing_required_bundle_files": missing_required,
            "missing_required_bundle_hashes": missing_hashes,
            "stale_required_bundle_hashes": stale_hashes,
            "staging_manifest_sha256": staging_manifest_sha,
            "bundle_manifest_sha256": bundle_manifest_sha,
        },
        error="; ".join(problems) if problems else None,
    )


def run_supply_chain_gate(
    *,
    root: Path = ROOT,
    timeout_seconds: float = 120.0,
    source_bundle_report: Path = DEFAULT_SOURCE_BUNDLE,
    staging_plan_report: Path = DEFAULT_STAGING_PLAN,
    ci_contract_report: Path = DEFAULT_CI_CONTRACT,
) -> SupplyChainGateReport:
    checks = [
        check_python_manifest(root),
        check_python_lockfile(root, timeout_seconds=timeout_seconds),
        check_frontend_lockfile(root),
        check_npm_audit(root, timeout_seconds=timeout_seconds),
        check_ci_dependency_contract(root),
        check_release_dependency_evidence(source_bundle_report, staging_plan_report, ci_contract_report),
    ]
    failed = [check for check in checks if check.status != "passed"]
    return SupplyChainGateReport(
        status="failed" if failed else "passed",
        generated_at=_utc_now(),
        checks=checks,
        next_commands=[
            "Review .xagent_runtime/reports/rc-supply-chain-gate.json.",
            "Keep pip-audit installed through the dev extra so Python vulnerability audit evidence remains enforced.",
            "Regenerate frontend/package-lock.json with npm install only when package.json intentionally changes.",
            "Keep CI on npm ci and the editable Python install path.",
        ],
    )


def write_report(report: SupplyChainGateReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate X-Agent commercial RC supply-chain gates")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--source-bundle-report", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--staging-plan-report", type=Path, default=DEFAULT_STAGING_PLAN)
    parser.add_argument("--ci-contract-report", type=Path, default=DEFAULT_CI_CONTRACT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_supply_chain_gate(
        timeout_seconds=args.timeout,
        source_bundle_report=args.source_bundle_report,
        staging_plan_report=args.staging_plan_report,
        ci_contract_report=args.ci_contract_report,
    )
    write_report(report, args.output)
    print(f"RC supply-chain gate status: {report.status}")
    print(f"Report written to {args.output}")
    for check in report.checks:
        print(f"- {check.name}: {check.status}")
        if check.error:
            print(f"  error: {check.error}")
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
