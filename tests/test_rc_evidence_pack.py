from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts import rc_evidence_pack
from scripts.rc_evidence_pack import build_evidence_pack


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _owner_gate_runner_report(generated_at: str = "2026-06-05T10:00:00Z") -> dict[str, object]:
    return {
        "status": "planned",
        "generated_at": generated_at,
        "selected_gate": "all",
        "dry_run": True,
        "env_file": ".xagent_runtime/reports/rc-owner-env-template.env",
        "loaded_env_names": ["XAGENT_OLLAMA_MODEL"],
        "owner_gate_env_names": ["XAGENT_OLLAMA_MODEL"],
        "missing_env_groups": [["XAGENT_GITHUB_TOKEN", "GITHUB_TOKEN"]],
        "steps": [
            {
                "name": "owner_gate:all",
                "status": "planned",
                "returncode": None,
                "command": [
                    "python",
                    "scripts/rc_external_smoke.py",
                    "--provider",
                    "ollama",
                        "--github-execute-preflight",
                    "--github-actions-preflight",
                    "--require-configured",
                ],
            }
        ],
    }


def _windows_user_path(*parts: str) -> str:
    return "C:" + "\\Users\\" + "canqu" + "\\" + "\\".join(parts)


def _posix_user_path(prefix: str, *parts: str) -> str:
    return "/" + prefix + "/" + "canqu" + "/" + "/".join(parts)


def _write_pack_fixture(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path
    reports = root / ".xagent_runtime" / "reports"
    release = root / ".xagent_runtime" / "release"
    smoke = root / ".xagent_runtime" / "smoke"
    original_root = rc_evidence_pack.ROOT
    original_required_reports = rc_evidence_pack.REQUIRED_REPORTS
    source_zip = release / "x-agent-commercial-rc.zip"
    source_zip.parent.mkdir(parents=True)
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("README.md", "x-agent")
    source_sha = rc_evidence_pack._sha256_file(source_zip)
    sidecar = _write_text(source_zip.with_suffix(source_zip.suffix + ".sha256"), f"{source_sha}  {source_zip.name}\n")

    receipt_path = release / "x-agent-commercial-rc-receipt.json"
    artifact = {
        "path": str(source_zip),
        "sha256": source_sha,
        "file_count": 1,
    }
    final_gate = {
        "status": "ready_with_owner_gates",
        "can_stage_candidate_files": False,
        "can_tag_rc_now": False,
        "full_parity_claimed": False,
    }
    receipt = _write_json(
        receipt_path,
        {
            "status": "created",
            "generated_at": "2026-06-05T10:02:00Z",
            "artifact": artifact,
            "final_gate": final_gate,
            "sidecars": {"sha256": str(sidecar)},
            "checks": [
                {"name": "artifact_integrity_gate", "status": "passed"},
                {"name": "owner_env_template", "status": "passed"},
                {"name": "owner_gate_checklist", "status": "passed"},
            ],
            "approval_request": {
                "approval_required_before_staging": True,
                "final_gate_status": final_gate["status"],
                "can_stage_candidate_files": final_gate["can_stage_candidate_files"],
                "can_tag_rc_now": final_gate["can_tag_rc_now"],
                "full_parity_claimed": final_gate["full_parity_claimed"],
                "artifact_path": artifact["path"],
                "artifact_sha256": artifact["sha256"],
                "artifact_file_count": artifact["file_count"],
                "receipt_path": str(receipt_path),
                "sha256_sidecar": str(sidecar),
                "remaining_risks": [{"name": "provider", "status": "action_required", "missing": []}],
                "exact_staging_commands": ["git add scripts/rc_evidence_pack.py tests/test_rc_evidence_pack.py"],
                "no_broad_staging_command": True,
            },
        },
    )

    for path in original_required_reports:
        target = root / path.relative_to(original_root)
        if target.suffix == ".md":
            _write_text(target, "# owner checklist\n")
        elif target.suffix in {".env", ".ps1"}:
            _write_text(target, 'XAGENT_OPENAI_API_KEY="<set-in-owner-secret-store>"\n')
        else:
            archive_path = target.relative_to(root).as_posix()
            generated_at = (
                "2026-06-05T10:03:00Z"
                if archive_path in rc_evidence_pack.RECEIPT_VALIDATOR_REPORTS
                else "2026-06-05T10:00:00Z"
            )
            if archive_path == ".xagent_runtime/reports/rc-owner-gate-runner.json":
                _write_json(target, _owner_gate_runner_report(generated_at=generated_at))
                continue
            _write_json(
                target,
                {
                    "status": "passed",
                    "generated_at": generated_at,
                    "checks": [{"name": "ok", "status": "passed"}],
                },
            )
    _write_json(smoke / "rc-runtime-smoke.json", {"status": "passed", "generated_at": "2026-06-05T10:00:00Z"})
    monkeypatch.setattr(rc_evidence_pack, "ROOT", root)
    monkeypatch.setattr(rc_evidence_pack, "REPORT_DIR", reports)
    monkeypatch.setattr(rc_evidence_pack, "RELEASE_DIR", release)
    monkeypatch.setattr(rc_evidence_pack, "SMOKE_DIR", smoke)
    monkeypatch.setattr(
        rc_evidence_pack,
        "REQUIRED_REPORTS",
        tuple(root / path.relative_to(original_root) for path in original_required_reports),
    )
    return {"receipt": receipt, "source_zip": source_zip, "sidecar": sidecar}


def test_evidence_pack_creates_zip_with_manifest(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    output = tmp_path / ".xagent_runtime" / "release" / "evidence.zip"

    report = build_evidence_pack(receipt_path=paths["receipt"], output_path=output)

    assert report.status == "created"
    assert output.exists()
    assert report.pack_sha256 == rc_evidence_pack._sha256_file(output)
    assert any(item.archive_path.endswith("x-agent-commercial-rc-receipt.json") for item in report.files)
    assert any(item.archive_path.endswith("rc-refresh-release-chain.json") for item in report.files)
    assert any(item.archive_path.endswith("rc-owner-env-template.env") for item in report.files)
    assert any(check.name == "evidence_pack_freshness" and check.status == "passed" for check in report.checks)
    assert any(check.name == "evidence_secret_scan" and check.status == "passed" for check in report.checks)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        receipt_name = next(name for name in names if name.endswith("x-agent-commercial-rc-receipt.json"))
        receipt_text = archive.read(receipt_name).decode("utf-8")
    assert any(name.endswith("rc-owner-gate-checklist.md") for name in names)
    assert any(name.endswith("rc-refresh-release-chain.json") for name in names)
    assert any(name.endswith("x-agent-commercial-rc.zip") for name in names)
    assert "<redacted-local-path>" in receipt_text
    assert str(paths["source_zip"]) not in receipt_text
    assert str(paths["source_zip"]).replace("\\", "\\\\") not in receipt_text
    assert str(paths["receipt"]) not in receipt_text


def test_evidence_pack_dry_run_does_not_create_zip(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    output = tmp_path / ".xagent_runtime" / "release" / "evidence.zip"

    report = build_evidence_pack(receipt_path=paths["receipt"], output_path=output, dry_run=True)

    assert report.status == "planned"
    assert report.output_path is None
    assert not output.exists()


def test_evidence_pack_fails_when_receipt_missing(tmp_path: Path, monkeypatch) -> None:
    _write_pack_fixture(tmp_path, monkeypatch)

    report = build_evidence_pack(receipt_path=tmp_path / "missing.json")

    assert report.status == "failed"
    assert any(check.name == "release_receipt" and check.status == "failed" for check in report.checks)


def test_evidence_pack_fails_when_receipt_approval_request_missing(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    receipt.pop("approval_request")
    _write_json(paths["receipt"], receipt)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_receipt")
    assert check.status == "failed"
    assert "receipt missing approval_request summary" in str(check.error)


def test_evidence_pack_fails_when_receipt_approval_request_has_broad_staging(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    approval_request = receipt["approval_request"]
    assert isinstance(approval_request, dict)
    approval_request["exact_staging_commands"] = ["git add ."]
    approval_request["no_broad_staging_command"] = False
    _write_json(paths["receipt"], receipt)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_receipt")
    assert check.status == "failed"
    assert "receipt approval_request.no_broad_staging_command must be true" in str(check.error)


def test_evidence_pack_fails_when_receipt_approval_request_staging_commands_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    approval_request = receipt["approval_request"]
    assert isinstance(approval_request, dict)
    approval_request["exact_staging_commands"] = []
    _write_json(paths["receipt"], receipt)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "release_receipt")
    assert check.status == "failed"
    assert "receipt approval_request.exact_staging_commands must be a non-empty list of strings" in str(check.error)


def test_evidence_pack_fails_when_required_handoff_file_missing(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    (tmp_path / ".xagent_runtime" / "reports" / "rc-owner-env-template.env").unlink()

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "required_files")
    assert check.status == "failed"
    assert "rc-owner-env-template.env" in json.dumps(check.details)


def test_evidence_pack_fails_when_owner_runner_env_file_evidence_missing(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    runner = _owner_gate_runner_report()
    runner.pop("env_file")
    _write_json(tmp_path / ".xagent_runtime" / "reports" / "rc-owner-gate-runner.json", runner)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_runner_evidence")
    assert check.status == "failed"
    assert "owner gate runner env_file must be .xagent_runtime/reports/rc-owner-env-template.env" in str(check.error)


def test_evidence_pack_fails_when_owner_runner_missing_env_groups_invalid(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    runner = _owner_gate_runner_report()
    runner["missing_env_groups"] = ["XAGENT_GITHUB_TOKEN"]
    _write_json(tmp_path / ".xagent_runtime" / "reports" / "rc-owner-gate-runner.json", runner)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "owner_gate_runner_evidence")
    assert check.status == "failed"
    assert "owner gate runner missing_env_groups must be a list of env variable name groups" in str(check.error)


def test_evidence_pack_fails_when_receipt_is_older_than_source_report(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-source-bundle.json",
        {
            "status": "passed",
            "generated_at": "2026-06-05T10:03:00Z",
            "checks": [{"name": "ok", "status": "passed"}],
        },
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_pack_freshness")
    assert check.status == "failed"
    assert "older than packed JSON evidence reports" in str(check.error)
    assert any(item["path"].endswith("rc-source-bundle.json") for item in check.details["stale_reports"])


def test_evidence_pack_fails_when_receipt_timestamp_is_in_future(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    receipt["generated_at"] = "2999-01-01T00:00:00Z"
    _write_json(paths["receipt"], receipt)

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_pack_freshness")
    assert check.status == "failed"
    assert "receipt generated_at is in the future" in str(check.error)


def test_evidence_pack_allows_receipt_validator_report_older_than_receipt(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-final-gate.json",
        {
            "status": "passed",
            "generated_at": "2026-06-05T10:01:00Z",
            "checks": [{"name": "ok", "status": "passed"}],
        },
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "created"
    check = next(item for item in report.checks if item.name == "evidence_pack_freshness")
    assert check.status == "passed"
    assert any(item["path"].endswith("rc-final-gate.json") for item in check.details["receipt_validator_reports"])


def test_evidence_pack_does_not_pack_self_report(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    self_report = _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-evidence-pack.json",
        {
            "status": "created",
            "generated_at": "2026-06-05T10:03:00Z",
            "checks": [{"name": "ok", "status": "passed"}],
        },
    )
    output = tmp_path / ".xagent_runtime" / "release" / "evidence.zip"

    report = build_evidence_pack(receipt_path=paths["receipt"], output_path=output, extra_reports=[self_report])

    assert report.status == "created"
    check = next(item for item in report.checks if item.name == "evidence_pack_freshness")
    assert check.status == "passed"
    assert not any(item.archive_path.endswith("rc-evidence-pack.json") for item in report.files)
    assert not any(item["path"].endswith("rc-evidence-pack.json") for item in check.details["receipt_validator_reports"])
    with zipfile.ZipFile(output) as archive:
        assert not any(name.endswith("rc-evidence-pack.json") for name in archive.namelist())


def test_evidence_pack_fails_when_packed_report_has_no_generated_at(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-final-gate.json",
        {"status": "passed", "checks": [{"name": "ok", "status": "passed"}]},
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_pack_freshness")
    assert check.status == "failed"
    assert "missing valid generated_at" in str(check.error)
    assert any(
        item["path"].endswith("rc-final-gate.json")
        for item in check.details["missing_or_invalid_generated_at_reports"]
    )


def test_evidence_pack_fails_on_secret_like_handoff_text(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_text(
        tmp_path / ".xagent_runtime" / "reports" / "rc-owner-env-template.env",
        'XAGENT_OPENAI_API_KEY="sk-' + ("a" * 32) + '"\n',
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_secret_scan")
    assert check.status == "failed"
    assert "secret-like" in str(check.error)


def test_evidence_pack_allows_public_xagent_path_names(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "codex-hermes-gap-closure.json",
        {
            "status": "passed",
            "generated_at": "2026-06-05T10:00:00Z",
            "status_short": [
                "?? frontend/src/panda/assets/roles/xagent-reference-media-operator.png",
                "?? docs/superpowers/plans/2026-06-14-xagent-remaining-parallel-delivery.md",
            ],
        },
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "created"
    check = next(item for item in report.checks if item.name == "evidence_secret_scan")
    assert check.status == "passed"


def test_evidence_pack_still_fails_on_xagent_token_value(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    _write_text(
        tmp_path / ".xagent_runtime" / "reports" / "rc-owner-env-template.env",
        'XAGENT_INTERNAL_TOKEN="xagent_' + ("a" * 32) + '"\n',
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_secret_scan")
    assert check.status == "failed"
    assert "secret-like" in str(check.error)


def test_evidence_pack_redacts_local_user_runtime_paths_before_privacy_scan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    output = tmp_path / ".xagent_runtime" / "release" / "evidence.zip"
    raw_path = _windows_user_path(
        "AppData",
        "Local",
        "uv",
        "cache",
        "archive-v0",
        "example",
        "httpx",
    )
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "codex-hermes-gap-closure.json",
        {
            "status": "passed",
            "generated_at": "2026-06-05T10:00:00Z",
            "checks": [{"name": "gap_matrix", "status": "passed"}],
            "stdout_tail": [f"warning from dependency cache: {raw_path}"],
        },
    )

    report = build_evidence_pack(receipt_path=paths["receipt"], output_path=output)

    assert report.status == "created"
    check = next(item for item in report.checks if item.name == "evidence_local_path_privacy_scan")
    assert check.status == "passed"
    assert check.details["privacy_findings"] == []
    with zipfile.ZipFile(output) as archive:
        archived_text = archive.read(".xagent_runtime/reports/codex-hermes-gap-closure.json").decode("utf-8")
    assert "<redacted-local-path>" in archived_text
    assert raw_path not in archived_text
    assert raw_path.replace("\\", "\\\\") not in archived_text


def test_evidence_pack_fails_on_unredacted_runtime_marker(tmp_path: Path, monkeypatch) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    runner = _owner_gate_runner_report()
    runner["stdout_tail"] = ["fallback command still references hermes-agent runtime"]
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-owner-gate-runner.json",
        runner,
    )

    report = build_evidence_pack(receipt_path=paths["receipt"])

    assert report.status == "failed"
    check = next(item for item in report.checks if item.name == "evidence_local_path_privacy_scan")
    assert check.status == "failed"
    assert "local user/runtime path" in str(check.error)


def test_evidence_pack_redacts_general_user_runtime_paths_before_privacy_scan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    paths = _write_pack_fixture(tmp_path, monkeypatch)
    output = tmp_path / ".xagent_runtime" / "release" / "evidence.zip"
    raw_paths = [
        _windows_user_path(".codex", "bin", "python.exe"),
        _posix_user_path("home", ".agents", "tools", "python"),
        _posix_user_path("Users", "Library", "Application Support", "X-Agent", "runtime"),
    ]
    runner = _owner_gate_runner_report()
    runner["diagnostics"] = raw_paths
    _write_json(
        tmp_path / ".xagent_runtime" / "reports" / "rc-owner-gate-runner.json",
        runner,
    )

    report = build_evidence_pack(receipt_path=paths["receipt"], output_path=output)

    assert report.status == "created"
    check = next(item for item in report.checks if item.name == "evidence_local_path_privacy_scan")
    assert check.status == "passed"
    assert check.details["privacy_findings"] == []
    with zipfile.ZipFile(output) as archive:
        archived_text = archive.read(".xagent_runtime/reports/rc-owner-gate-runner.json").decode("utf-8")
    assert "<redacted-local-path>" in archived_text
    for raw_path in raw_paths:
        assert raw_path not in archived_text
        assert raw_path.replace("\\", "\\\\") not in archived_text
