from __future__ import annotations

import json
import subprocess
from pathlib import Path

import scripts.rc_supply_chain_gate as gate
from scripts.rc_supply_chain_gate import (
    SupplyChainCheck,
    check_ci_dependency_contract,
    check_frontend_lockfile,
    check_python_lockfile,
    check_python_manifest,
    check_npm_audit,
    check_release_dependency_evidence,
    run_supply_chain_gate,
)

MANIFEST_SHA = "c" * 64
REQUIRED_BUNDLE_SHA = "a" * 64


def _required_bundle_file_entries(*, manifest_sha: str = MANIFEST_SHA) -> list[dict[str, object]]:
    return [
        {"path": ".github/workflows/commercial-rc.yml", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "docs/RC_STAGING_MANIFEST.md", "sha256": manifest_sha},
        {"path": "frontend/package.json", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "frontend/package-lock.json", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "pyproject.toml", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "requirements-lock.txt", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "scripts/rc_supply_chain_gate.py", "sha256": REQUIRED_BUNDLE_SHA},
        {"path": "tests/test_rc_supply_chain_gate.py", "sha256": REQUIRED_BUNDLE_SHA},
    ]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_python_manifest_accepts_project_contract() -> None:
    check = check_python_manifest()

    assert check.status == "passed"
    assert check.details["requires_python"] == ">=3.11"
    assert check.details["missing_dev_tools"] == []


def test_python_manifest_requires_pip_audit_in_dev_extra(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
requires-python = ">=3.11"
dependencies = [
    "bcrypt>=4.1.2,<5.0.0",
    "cryptography>=46.0.0,<49.0.0",
    "fastapi>=0.115.0",
    "pydantic>=2.7.0",
    "uvicorn>=0.30.0",
    "redis>=5.0.0",
    "celery>=5.3.0",
    "python-multipart>=0.0.28",
    "scikit-learn>=1.5.0",
    "sqlalchemy>=2.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.2.0"]
cli = ["typer>=0.12.0"]
""",
        encoding="utf-8",
    )

    check = check_python_manifest(tmp_path)

    assert check.status == "failed"
    assert check.details["missing_dev_tools"] == ["aiosqlite", "pip-audit"]
    assert "missing dev dependency aiosqlite" in check.details["missing"]
    assert "missing dev dependency pip-audit" in check.details["missing"]


def test_python_lockfile_accepts_pinned_runtime_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(gate.shutil, "which", lambda name: "pip-audit" if name == "pip-audit" else None)
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, cwd, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"dependencies": [{"name": "fastapi", "version": "0.115.0", "vulns": []}]}),
            stderr="No known vulnerabilities found",
        ),
    )

    check = check_python_lockfile()

    assert check.status == "passed"
    assert check.details["locked_dependency_count"] >= 1
    assert check.details["missing_runtime_dependencies"] == []
    assert check.details["pip_audit"]["status"] == "passed"
    assert check.details["pip_audit"]["vulnerability_count"] == 0


def test_python_lockfile_rejects_missing_pip_audit_tool(monkeypatch) -> None:
    monkeypatch.setattr(gate.shutil, "which", lambda name: None)

    check = check_python_lockfile()

    assert check.status == "failed"
    assert check.details["pip_audit"]["status"] == "missing"
    assert "pip-audit is required" in str(check.error)


def test_python_lockfile_rejects_missing_file(tmp_path: Path) -> None:
    check = check_python_lockfile(tmp_path)

    assert check.status == "failed"
    assert "requirements-lock.txt" in str(check.error)


def test_python_lockfile_rejects_missing_core_dependency(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(gate.shutil, "which", lambda name: None)
    (tmp_path / "requirements-lock.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")

    check = check_python_lockfile(tmp_path)

    assert check.status == "failed"
    assert "missing locked runtime dependencies" in str(check.error)
    assert "redis" in str(check.error)


def test_python_lockfile_runs_pip_audit_when_available_and_fails(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "requirements-lock.txt").write_text(
        "\n".join(
            [
                "asyncpg==0.29.0",
                "bcrypt==4.1.2",
                "celery==5.3.0",
                "cryptography==46.0.0",
                "fastapi==0.115.0",
                "httpx==0.27.0",
                "langfuse==2.60.0",
                "openai==1.100.0",
                "playwright==1.48.0",
                "psycopg[binary]==3.2.0",
                "psycopg-binary==3.2.0",
                "pydantic==2.7.0",
                "python-multipart==0.0.28",
                "qdrant-client==1.11.0",
                "redis==5.0.0",
                "scikit-learn==1.5.0",
                "sqlalchemy==2.0.0",
                "uvicorn[standard]==0.30.0",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate.shutil, "which", lambda name: "pip-audit" if name == "pip-audit" else None)
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, cwd, timeout_seconds: subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps({"dependencies": [{"name": "fastapi", "version": "0.115.0", "vulns": [{"id": "PYSEC-1"}]}]}),
            stderr="",
        ),
    )

    check = check_python_lockfile(tmp_path)

    assert check.status == "failed"
    assert check.details["pip_audit"]["tool_available"] is True
    assert check.details["pip_audit"]["command"][0] == "pip-audit"
    assert all("hermes-agent" not in item.lower() for item in check.details["pip_audit"]["command"])
    assert check.details["pip_audit"]["vulnerability_count"] == 1


def test_python_lockfile_treats_pip_audit_tool_error_as_failure(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "requirements-lock.txt").write_text(
        "\n".join(
            [
                "asyncpg==0.29.0",
                "bcrypt==4.1.2",
                "celery==5.3.0",
                "cryptography==46.0.0",
                "fastapi==0.115.0",
                "httpx==0.27.0",
                "langfuse==2.60.0",
                "openai==1.100.0",
                "playwright==1.48.0",
                "psycopg[binary]==3.2.0",
                "psycopg-binary==3.2.0",
                "pydantic==2.7.0",
                "python-multipart==0.0.28",
                "qdrant-client==1.11.0",
                "redis==5.0.0",
                "scikit-learn==1.5.0",
                "sqlalchemy==2.0.0",
                "uvicorn[standard]==0.30.0",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate.shutil, "which", lambda name: "pip-audit" if name == "pip-audit" else None)
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, cwd, timeout_seconds: subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="network unavailable",
        ),
    )

    check = check_python_lockfile(tmp_path)

    assert check.status == "failed"
    assert check.details["pip_audit"]["status"] == "failed"
    assert "exited non-zero" in check.details["pip_audit"]["error"]
    assert "pip-audit exited non-zero" in str(check.error)


def test_frontend_lockfile_matches_package_manifest() -> None:
    check = check_frontend_lockfile()

    assert check.status == "passed"
    assert check.details["dependency_count"] >= 1
    assert str(check.details["package_json"]).endswith("frontend\\package.json") or str(
        check.details["package_json"]
    ).endswith("frontend/package.json")
    assert check.details["scanned_package_entries"] >= 1
    assert check.details["missing_integrity"] == []
    assert check.details["non_registry_resolved"] == []


def _write_frontend_manifest(root: Path, package_entry: dict[str, object]) -> None:
    frontend = root / "frontend"
    frontend.mkdir(parents=True)
    _write_json(
        frontend / "package.json",
        {
            "name": "x-agent-frontend",
            "version": "1.0.0",
            "dependencies": {"@vitejs/plugin-react": "^latest"},
            "devDependencies": {},
        },
    )
    _write_json(
        frontend / "package-lock.json",
        {
            "name": "x-agent-frontend",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "packages": {
                "": {
                    "name": "x-agent-frontend",
                    "version": "1.0.0",
                    "dependencies": {"@vitejs/plugin-react": "^latest"},
                },
                "node_modules/@vitejs/plugin-react": package_entry,
            },
        },
    )


def test_frontend_lockfile_rejects_missing_integrity(tmp_path: Path) -> None:
    _write_frontend_manifest(
        tmp_path,
        {
            "version": "latest",
            "resolved": "https://registry.npmjs.org/@vitejs/plugin-react/-/plugin-react-1.0.0.tgz",
        },
    )

    check = check_frontend_lockfile(tmp_path)

    assert check.status == "failed"
    assert "package-lock entries missing integrity" in check.details["problems"]
    assert "node_modules/@vitejs/plugin-react" in check.details["missing_integrity"]


def test_frontend_lockfile_rejects_non_registry_resolved_source(tmp_path: Path) -> None:
    _write_frontend_manifest(
        tmp_path,
        {
            "version": "latest",
            "resolved": "file:../local-plugin.tgz",
            "integrity": "sha512-fixture",
        },
    )

    check = check_frontend_lockfile(tmp_path)

    assert check.status == "failed"
    assert "package-lock contains non-npm-registry resolved sources" in check.details["problems"]
    assert check.details["non_registry_resolved"][0]["resolved"] == "file:../local-plugin.tgz"


def test_frontend_lockfile_rejects_missing_resolved_source(tmp_path: Path) -> None:
    _write_frontend_manifest(
        tmp_path,
        {
            "version": "latest",
            "integrity": "sha512-fixture",
        },
    )

    check = check_frontend_lockfile(tmp_path)

    assert check.status == "failed"
    assert "package-lock entries missing resolved source" in check.details["problems"]
    assert "node_modules/@vitejs/plugin-react" in check.details["missing_resolved"]


def test_ci_dependency_contract_rejects_npm_install(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "commercial-rc.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """
cache-dependency-path: frontend/package-lock.json
working-directory: frontend
npm ci
npm audit --audit-level=moderate
python -m pip install -e ".[dev,cli]"
python -m pip show pip-audit
npm install
""",
        encoding="utf-8",
    )

    check = check_ci_dependency_contract(tmp_path)

    assert check.status == "failed"
    assert "npm install" in check.details["forbidden"]


def test_ci_dependency_contract_ignores_required_tokens_in_comments(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "commercial-rc.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """
cache-dependency-path: frontend/package-lock.json
working-directory: frontend
npm ci
npm audit --audit-level=moderate
# python -m pip install -e ".[dev,cli]"
python -m pip show pip-audit
""",
        encoding="utf-8",
    )

    check = check_ci_dependency_contract(tmp_path)

    assert check.status == "failed"
    assert 'python -m pip install -e ".[dev,cli]"' in check.details["missing"]


def test_ci_dependency_contract_ignores_forbidden_tokens_in_comments(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "commercial-rc.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """
cache-dependency-path: frontend/package-lock.json
working-directory: frontend
npm ci
npm audit --audit-level=moderate
python -m pip install -e ".[dev,cli]"
python -m pip show pip-audit
# npm install
""",
        encoding="utf-8",
    )

    check = check_ci_dependency_contract(tmp_path)

    assert check.status == "passed"
    assert check.details["forbidden"] == []


def test_ci_dependency_contract_requires_pip_audit_tool_check(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "commercial-rc.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        """
cache-dependency-path: frontend/package-lock.json
working-directory: frontend
npm ci
npm audit --audit-level=moderate
python -m pip install -e ".[dev,cli]"
""",
        encoding="utf-8",
    )

    check = check_ci_dependency_contract(tmp_path)

    assert check.status == "failed"
    assert "python -m pip show pip-audit" in check.details["missing"]


def test_npm_audit_accepts_zero_moderate_plus(monkeypatch) -> None:
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, cwd, timeout_seconds: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"metadata": {"vulnerabilities": {"info": 0, "low": 1, "moderate": 0, "high": 0, "critical": 0}}}),
            stderr="",
        ),
    )

    check = check_npm_audit()

    assert check.status == "passed"


def test_npm_executable_prefers_cmd_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(gate.shutil, "which", lambda name: "C:/node/npm.cmd" if name == "npm.cmd" else "C:/node/npm")

    assert gate._npm_executable().endswith("npm.cmd")


def test_npm_audit_fails_moderate_plus(monkeypatch) -> None:
    monkeypatch.setattr(
        gate,
        "_run_command",
        lambda command, cwd, timeout_seconds: subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps({"metadata": {"vulnerabilities": {"moderate": 1, "high": 0, "critical": 0}}}),
            stderr="",
        ),
    )

    check = check_npm_audit()

    assert check.status == "failed"


def test_supply_chain_gate_aggregates_checks(monkeypatch) -> None:
    monkeypatch.setattr(gate, "check_python_manifest", lambda root: SupplyChainCheck("python_manifest", "passed"))
    monkeypatch.setattr(gate, "check_python_lockfile", lambda root, timeout_seconds: SupplyChainCheck("python_lockfile", "passed"))
    monkeypatch.setattr(gate, "check_frontend_lockfile", lambda root: SupplyChainCheck("frontend_lockfile", "passed"))
    monkeypatch.setattr(gate, "check_npm_audit", lambda root, timeout_seconds: SupplyChainCheck("npm_audit", "passed"))
    monkeypatch.setattr(gate, "check_ci_dependency_contract", lambda root: SupplyChainCheck("ci_dependency_contract", "passed"))
    monkeypatch.setattr(
        gate,
        "check_release_dependency_evidence",
        lambda source_bundle_report, staging_plan_report, ci_contract_report: SupplyChainCheck("release_dependency_evidence", "passed"),
    )

    report = run_supply_chain_gate()

    assert report.status == "passed"
    assert [check.name for check in report.checks] == [
        "python_manifest",
        "python_lockfile",
        "frontend_lockfile",
        "npm_audit",
        "ci_dependency_contract",
        "release_dependency_evidence",
    ]


def test_release_dependency_evidence_passes_when_bundle_and_ci_match(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 8,
            "files": _required_bundle_file_entries(),
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 8, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "passed"


def test_release_dependency_evidence_fails_when_dependency_files_missing_from_bundle(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 1,
            "files": [{"path": "frontend/package.json"}],
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 1, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert "frontend/package-lock.json" in str(check.error)
    assert "commercial-rc.yml" in str(check.error)
    assert "pyproject.toml" in str(check.error)


def test_release_dependency_evidence_requires_pyproject_in_source_bundle(tmp_path: Path) -> None:
    files = [item for item in _required_bundle_file_entries() if item["path"] != "pyproject.toml"]
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 8,
            "files": files,
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 8, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert check.details["missing_required_bundle_files"] == ["pyproject.toml"]


def test_release_dependency_evidence_fails_on_count_or_ci_drift(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 8,
            "files": _required_bundle_file_entries(),
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 4, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "failed", "findings": [{"id": "frontend_install"}]})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert "file_count mismatch" in str(check.error)
    assert "ci_contract status must be passed" in str(check.error)


def test_release_dependency_evidence_fails_when_manifest_hash_drifts(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 8,
            "files": _required_bundle_file_entries(manifest_sha="d" * 64),
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 8, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert "manifest_sha256" in str(check.error)


def test_release_dependency_evidence_fails_when_required_dependency_sha_missing(tmp_path: Path) -> None:
    files = _required_bundle_file_entries()
    for item in files:
        if item["path"] == "frontend/package-lock.json":
            item.pop("sha256")
    source = _write_json(
        tmp_path / "source.json",
        {
            "status": "created",
            "file_count": 8,
            "files": files,
        },
    )
    staging = _write_json(tmp_path / "staging.json", {"status": "planned", "file_count": 8, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(tmp_path / "ci.json", {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert "missing sha256" in str(check.error)
    assert "frontend/package-lock.json" in check.details["missing_required_bundle_hashes"]


def test_release_dependency_evidence_fails_when_required_dependency_sha_is_stale(tmp_path: Path) -> None:
    worktree = tmp_path / "repo"
    source_path = worktree / ".xagent_runtime" / "reports" / "rc-source-bundle.json"
    staging_path = worktree / ".xagent_runtime" / "reports" / "rc-staging-plan.json"
    ci_path = worktree / ".xagent_runtime" / "reports" / "rc-ci-contract.json"
    package_lock = worktree / "frontend" / "package-lock.json"
    package_lock.parent.mkdir(parents=True)
    package_lock.write_text("current lockfile", encoding="utf-8")
    source = _write_json(
        source_path,
        {
            "status": "created",
            "file_count": 8,
            "files": _required_bundle_file_entries(),
        },
    )
    staging = _write_json(staging_path, {"status": "planned", "file_count": 8, "manifest_sha256": MANIFEST_SHA})
    ci = _write_json(ci_path, {"status": "passed", "findings": []})

    check = check_release_dependency_evidence(source, staging, ci)

    assert check.status == "failed"
    assert "does not match current worktree" in str(check.error)
    assert check.details["stale_required_bundle_hashes"][0]["path"] == "frontend/package-lock.json"


def test_supply_chain_tail_redacts_secret_like_output() -> None:
    text = "NPM_TOKEN: github_pat_" + ("a" * 32) + "\nraw xagent-" + ("b" * 32)

    tail = gate._tail(text)

    assert "NPM_TOKEN: <redacted-output>" in tail
    assert "raw <redacted-secret>" in tail
    assert "github_pat_" not in tail
    assert "xagent-" not in tail


def test_supply_chain_tail_redacts_local_runtime_paths() -> None:
    windows_path = (
        "C:"
        + "\\Users\\"
        + "canqu"
        + "\\AppData\\Local\\hermes\\"
        + "hermes"
        + "-agent\\venv\\Lib\\site-packages\\pip_audit\\_cli.py"
    )
    posix_path = "/home/" + "canqu" + "/.cache/pip/http/cache.py"
    runtime_marker = "hermes" + "-agent"
    text = (
        f'File "{windows_path}"\n'
        f'File "{posix_path}"\n'
        f"runtime marker {runtime_marker}\n"
    )

    tail = gate._tail(text)

    assert "C:" + "\\Users\\" + "canqu" not in tail
    assert "/home/" + "canqu" not in tail
    assert runtime_marker not in tail
    assert "<redacted-local-path>" in tail
    assert "<redacted-local-runtime>" in tail
