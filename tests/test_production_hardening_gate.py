from __future__ import annotations

import json
from pathlib import Path

from scripts.production_hardening_gate import (
    build_production_hardening_report,
    main,
    write_report,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _rules(report) -> dict[str, str]:
    return {rule.name: rule.status for rule in report.rules}


def test_blocks_latest_images_in_production_deploy_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "docker-compose.monitoring.yml",
        """
        services:
          prometheus:
            image: prom/prometheus:latest
        """,
    )

    report = build_production_hardening_report(root=tmp_path)

    assert report.status == "blocked"
    assert _rules(report)["no_latest_images"] == "blocked"
    finding = next(item for item in report.findings if item.rule == "no_latest_images")
    assert finding.path == "deployment/docker-compose.monitoring.yml"
    assert "prom/prometheus:latest" in finding.evidence
    assert report.read_only is True
    assert report.mutation_performed is False


def test_blocks_placeholder_values_in_production_secret_manifest(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "k8s" / "secret.yaml",
        """
        apiVersion: v1
        kind: Secret
        stringData:
          DB_PASSWORD: "change-me-in-production"
        """,
    )

    report = build_production_hardening_report(root=tmp_path)

    assert report.status == "blocked"
    assert _rules(report)["no_placeholder_production_secrets"] == "blocked"
    finding = next(
        item for item in report.findings if item.rule == "no_placeholder_production_secrets"
    )
    assert finding.path == "deployment/k8s/secret.yaml"
    assert "DB_PASSWORD:" in finding.evidence
    assert "<redacted>" in finding.evidence
    assert "change-me-in-production" not in finding.evidence
    assert report.secret_written is False


def test_blocks_when_no_production_config_is_scanned(tmp_path: Path) -> None:
    report = build_production_hardening_report(root=tmp_path)

    assert report.status == "blocked"
    assert report.production_hardened is False
    assert report.scanned_paths == []
    assert report.blocking_reasons == ["no_production_config_scanned"]
    assert _rules(report)["no_production_config_scanned"] == "blocked"
    finding = next(item for item in report.findings if item.rule == "no_production_config_scanned")
    assert finding.evidence == "scanned_paths: <none>"


def test_secret_placeholder_evidence_redacts_raw_values_in_report_json(tmp_path: Path) -> None:
    raw_value = "REAL_SECRET_VALUE_DO_NOT_LEAK_12345"
    _write(
        tmp_path / "deployment" / "k8s" / "secret.yaml",
        f"""
        apiVersion: v1
        kind: Secret
        stringData:
          API_TOKEN: "{raw_value}" # placeholder {raw_value}
        """,
    )
    output = tmp_path / "reports" / "production-hardening-gate.json"

    report = build_production_hardening_report(root=tmp_path, output_path=output)
    finding = next(
        item for item in report.findings if item.rule == "no_placeholder_production_secrets"
    )

    assert raw_value not in finding.evidence
    assert "API_TOKEN:" in finding.evidence
    assert "<redacted>" in finding.evidence
    assert "# placeholder" not in finding.evidence

    write_report(report, output)
    payload_text = output.read_text(encoding="utf-8")
    assert raw_value not in payload_text
    payload = json.loads(payload_text)
    assert payload["findings"][0]["evidence"] == finding.evidence


def test_blocks_require_api_key_false_defaults(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "helm" / "values.yaml",
        """
        env:
          XAGENT_REQUIRE_API_KEY: "false"
        """,
    )
    _write(
        tmp_path / "docker-compose.yml",
        """
        services:
          api:
            environment:
              XAGENT_REQUIRE_API_KEY: ${XAGENT_REQUIRE_API_KEY:-false}
        """,
    )

    report = build_production_hardening_report(root=tmp_path)

    findings = [item for item in report.findings if item.rule == "require_api_key_default_true"]
    assert report.status == "blocked"
    assert _rules(report)["require_api_key_default_true"] == "blocked"
    assert len(findings) == 2
    assert {finding.path for finding in findings} == {
        "deployment/helm/values.yaml",
        "docker-compose.yml",
    }


def test_blocks_trust_all_certificates_enabled_or_default_enabled(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "production" / "config.yaml",
        """
        neo4j:
          trust: TRUST_ALL_CERTIFICATES
        tls:
          TRUST_ALL_CERTIFICATES: "true"
          fallback: ${TRUST_ALL_CERTIFICATES:-true}
        """,
    )

    report = build_production_hardening_report(root=tmp_path)

    findings = [item for item in report.findings if item.rule == "no_trust_all_certificates"]
    assert report.status == "blocked"
    assert _rules(report)["no_trust_all_certificates"] == "blocked"
    assert len(findings) == 3
    assert all(finding.path == "deployment/production/config.yaml" for finding in findings)


def test_ready_when_production_scan_has_no_blockers(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "k8s" / "xagent-api-deployment.yaml",
        """
        apiVersion: apps/v1
        kind: Deployment
        spec:
          template:
            spec:
              containers:
                - name: api
                  image: xagent:1.2.3
                  env:
                    - name: XAGENT_REQUIRE_API_KEY
                      value: "true"
        """,
    )

    report = build_production_hardening_report(root=tmp_path)

    assert report.status == "ready"
    assert report.production_hardened is True
    assert report.blocking_reasons == []
    assert report.findings == []
    assert {rule.status for rule in report.rules} == {"ready"}


def test_cli_writes_report_and_requires_allow_blocked_for_zero_exit(tmp_path: Path) -> None:
    _write(
        tmp_path / "deployment" / "k8s" / "qdrant-deployment.yaml",
        """
        spec:
          template:
            spec:
              containers:
                - image: qdrant/qdrant:latest
        """,
    )
    output = tmp_path / "reports" / "production-hardening-gate.json"

    blocked_exit = main(["--root", str(tmp_path), "--output", str(output)])

    assert blocked_exit == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked"
    assert payload["findings"][0]["rule"] == "no_latest_images"

    allowed_exit = main(
        ["--root", str(tmp_path), "--output", str(output), "--allow-blocked"]
    )

    assert allowed_exit == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "blocked"
