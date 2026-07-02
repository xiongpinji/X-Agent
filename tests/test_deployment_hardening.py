"""Tests for the deployment & secret hardening gate.

Exercises scripts/security_deployment_gate.py (the durable enforcement
behind the deploy/secret defenses) against synthetic fixtures, and asserts
the real in-repo deployment manifests do not regress on weak default
passwords, :latest images, production --reload, or publicly exposed
databases.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GATE_PATH = REPO_ROOT / "scripts" / "security_deployment_gate.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("security_deployment_gate", GATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["security_deployment_gate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    if not GATE_PATH.exists():
        pytest.skip("security_deployment_gate.py not present")
    return _load_gate()


def _rules(findings):
    return {f.rule for f in findings}


# --- weak / default passwords ----------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "      POSTGRES_PASSWORD: xagent",
        "      - GF_SECURITY_ADMIN_PASSWORD=admin",
        "      MINIO_SECRET_KEY: minioadmin",
        "      - ELASTICSEARCH_PASSWORD=changeme",
        "      NEO4J_PASSWORD: neo4j",
    ],
)
def test_flags_weak_default_passwords(gate, line):
    findings = gate.scan_text(f"services:\n  db:\n    environment:\n{line}\n", filename="docker-compose.yml")
    assert "weak-default-password" in _rules(findings), line


def test_env_substituted_password_passes(gate):
    text = (
        "services:\n  db:\n    environment:\n"
        "      POSTGRES_PASSWORD: ${DB_PASSWORD:?Set DB_PASSWORD in .env}\n"
    )
    findings = gate.scan_text(text, filename="docker-compose.yml")
    assert "weak-default-password" not in _rules(findings)


def test_strong_inline_password_not_flagged_as_weak(gate):
    # A non-dictionary value is not in the weak set (it may still be a secret,
    # but it is not a *default/weak* password by this rule).
    text = "    environment:\n      POSTGRES_PASSWORD: S0me-L0ng-Rand0m-Value-9f2\n"
    findings = gate.scan_text(text, filename="docker-compose.yml")
    assert "weak-default-password" not in _rules(findings)


# --- :latest images ---------------------------------------------------------


def test_flags_latest_image(gate):
    findings = gate.scan_text("    image: grafana/grafana:latest\n", filename="docker-compose.yml")
    assert "mutable-latest-image" in _rules(findings)


def test_pinned_image_passes(gate):
    findings = gate.scan_text("    image: grafana/grafana:11.2.0\n", filename="docker-compose.yml")
    assert "mutable-latest-image" not in _rules(findings)


# --- production --reload -----------------------------------------------------


def test_flags_hardcoded_reload(gate):
    findings = gate.scan_text(
        "    command: uvicorn backend.app.main:app --host 0.0.0.0 --reload\n",
        filename="docker-compose.yml",
    )
    assert "uvicorn-reload" in _rules(findings)


def test_env_gated_reload_passes(gate):
    findings = gate.scan_text(
        '    command: sh -c "uvicorn backend.app.main:app --port 8000 ${UVICORN_RELOAD:-}"\n',
        filename="docker-compose.yml",
    )
    assert "uvicorn-reload" not in _rules(findings)


# --- public DB ports ---------------------------------------------------------


def test_flags_public_db_port(gate):
    findings = gate.scan_text('    ports:\n      - "0.0.0.0:5432:5432"\n', filename="docker-compose.yml")
    assert "public-db-port" in _rules(findings)


def test_localhost_db_port_passes(gate):
    findings = gate.scan_text('    ports:\n      - "127.0.0.1:5432:5432"\n', filename="docker-compose.yml")
    assert "public-db-port" not in _rules(findings)


# --- committed real secrets --------------------------------------------------


@pytest.mark.parametrize(
    "secret",
    [
        "OPENAI_API_KEY: " + "sk-proj-" + "abc123XYZdefinitely0000real9876543210",
        "AWS_KEY: " + "AKIA" + "IOSFODNN7EXAMPLE",
        "GH: " + "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789",
    ],
)
def test_flags_committed_real_secret(gate, secret):
    # Use a config-style line; planted markers like 'definitely' are NOT in the
    # value here so detection must rely on the provider-key shape.
    findings = gate.scan_text(f"env:\n  {secret}\n", filename="deployment/x.yaml")
    assert "hardcoded-secret" in _rules(findings)


def test_private_key_block_flagged(gate):
    findings = gate.scan_text(
        "key: |\n  -----BEGIN RSA PRIVATE KEY-----\n  MIIB...\n",
        filename="deployment/x.yaml",
    )
    assert "hardcoded-secret" in _rules(findings)


# --- .env.example value rule -------------------------------------------------


def test_env_example_usable_secret_flagged(gate):
    findings = gate.scan_text("DB_PASSWORD=hunter2supersecret\n", filename=".env.example")
    assert "env-example-value" in _rules(findings)


def test_env_example_empty_value_passes(gate):
    findings = gate.scan_text("DB_PASSWORD=\nJWT_SECRET=\n", filename=".env.example")
    assert "env-example-value" not in _rules(findings)


# --- main() exit code --------------------------------------------------------


def test_main_returns_nonzero_on_high_finding(gate, tmp_path):
    bad = tmp_path / "docker-compose.yml"
    bad.write_text("services:\n  db:\n    image: x:latest\n", encoding="utf-8")
    assert gate.main([str(bad)]) == 1


def test_main_returns_zero_when_clean(gate, tmp_path):
    good = tmp_path / "docker-compose.yml"
    good.write_text("services:\n  db:\n    image: postgres:16-alpine\n", encoding="utf-8")
    assert gate.main([str(good)]) == 0


# --- live repository regression guards --------------------------------------


def test_repo_deployment_configs_have_no_high_findings(gate):
    """The whole in-repo deployment surface must be free of HIGH risks."""
    findings = gate.scan_repo(REPO_ROOT)
    high = [f for f in findings if f.severity == "HIGH"]
    assert not high, "Deployment hardening regressions:\n" + "\n".join(str(f) for f in high)


def test_no_planted_secret_file_with_real_key(gate):
    """The neutralized _secret_test.tmp must not contain a usable key."""
    planted = REPO_ROOT / "_secret_test.tmp"
    if not planted.exists():
        return
    text = planted.read_text(encoding="utf-8", errors="replace")
    findings = gate.scan_text(text, filename="_secret_test.tmp")
    assert not any(f.rule == "hardcoded-secret" for f in findings)
