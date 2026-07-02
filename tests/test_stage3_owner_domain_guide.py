from __future__ import annotations

import json
from pathlib import Path

from scripts.stage3_owner_domain_guide import build_stage3_owner_domain_guide, main


def _external_smoke_report(path: Path, *, head_sha_verified: bool = True) -> Path:
    payload = {
        "status": "passed",
        "checks": [
            {
                "name": "hosted_github_actions_run",
                "status": "passed",
                "details": {
                    "head_sha": "dca6a063e9c21ee5e420d3346c28735b17a92fdf",
                    "expected_head_sha": "dca6a063e9c21ee5e420d3346c28735b17a92fdf",
                    "head_sha_verified": head_sha_verified,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_stage3_owner_domain_guide_ready_for_real_domain() -> None:
    report = build_stage3_owner_domain_guide(
        domain="xagent.example.com",
        expected_ip="111.228.49.160",
        release_sha="dca6a063e9c21ee5e420d3346c28735b17a92fdf",
    )

    assert report.status == "stage3_owner_domain_guide_ready"
    assert report.domain == "xagent.example.com"
    assert report.mutation_performed is False
    assert report.deploy_performed is False
    assert report.workflow_dispatch_performed is False
    assert report.raw_secret_values_recorded is False
    assert any("certbot --nginx -d xagent.example.com" in command for command in report.server_commands)
    assert any("stage3_https_preflight.py" in command for command in report.local_validation_commands)
    assert any("--require-stage3-rehearsal" in command for command in report.local_validation_commands)
    assert any("secret-manager references only" in ref for ref in report.evidence_refs_to_collect)


def test_stage3_owner_domain_guide_auto_detects_verified_release_sha(tmp_path: Path) -> None:
    report = build_stage3_owner_domain_guide(
        domain="xagent.example.com",
        external_smoke_report=_external_smoke_report(tmp_path / "external-smoke.json"),
    )

    assert report.status == "stage3_owner_domain_guide_ready"
    assert report.release_sha == "dca6a063e9c21ee5e420d3346c28735b17a92fdf"
    assert "hosted_github_actions_run.head_sha" in report.release_sha_source
    check = next(item for item in report.checks if item.name == "release_sha_source")
    assert check.status == "passed"
    assert any("dca6a063e9c21ee5e420d3346c28735b17a92fdf" in command for command in report.local_validation_commands)


def test_stage3_owner_domain_guide_marks_unverified_auto_sha_as_placeholder(tmp_path: Path) -> None:
    report = build_stage3_owner_domain_guide(
        domain="xagent.example.com",
        external_smoke_report=_external_smoke_report(tmp_path / "external-smoke.json", head_sha_verified=False),
    )

    assert report.status == "stage3_owner_domain_guide_ready"
    assert report.release_sha == "<OWNER_VERIFIED_HEAD_SHA>"
    assert report.release_sha_source.startswith("placeholder:")
    check = next(item for item in report.checks if item.name == "release_sha_source")
    assert check.status == "failed"


def test_stage3_owner_domain_guide_blocks_non_commercial_domain_shapes() -> None:
    for domain in (
        "https://111.228.49.160",
        "xagent.111.228.49.160.sslip.io",
        "localhost",
        "stage3",
        "http://xagent.example.com",
        "https://user:pass@xagent.example.com",
        "https://xagent.example.com/ready",
    ):
        report = build_stage3_owner_domain_guide(domain=domain)

        assert report.status == "stage3_owner_domain_guide_blocked"
        assert report.server_commands == []
        assert report.local_validation_commands == []
        domain_check = next(check for check in report.checks if check.name == "domain_shape")
        assert domain_check.status == "failed"


def test_stage3_owner_domain_guide_cli_writes_no_secret_report(tmp_path: Path) -> None:
    output_json = tmp_path / "guide.json"
    output_md = tmp_path / "guide.md"
    external_smoke = _external_smoke_report(tmp_path / "external-smoke.json")

    rc = main(
        [
            "--domain",
            "xagent.example.com",
            "--external-smoke-report",
            str(external_smoke),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "stage3_owner_domain_guide_ready"
    assert payload["release_sha"] == "dca6a063e9c21ee5e420d3346c28735b17a92fdf"
    assert payload["release_sha_source"].endswith("hosted_github_actions_run.head_sha")
    assert payload["mutation_performed"] is False
    assert payload["deploy_performed"] is False
    assert payload["workflow_dispatch_performed"] is False
    assert payload["raw_secret_values_recorded"] is False
    assert "Stage3 Owner Domain Guide" in markdown
    assert "sk-" not in markdown
    assert "password=" not in markdown.lower()
    assert "secret values" in markdown


def test_stage3_owner_domain_guide_cli_blocks_temporary_dns(tmp_path: Path) -> None:
    output_json = tmp_path / "guide.json"
    output_md = tmp_path / "guide.md"

    rc = main(
        [
            "--domain",
            "xagent.111.228.49.160.sslip.io",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
    )

    assert rc == 1
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert payload["status"] == "stage3_owner_domain_guide_blocked"
    assert payload["server_commands"] == []
    assert payload["local_validation_commands"] == []
    assert "temporary wildcard DNS" in markdown
