from __future__ import annotations

import re
from pathlib import Path


WORKFLOWS = {
    Path(".github/workflows/ci-cd.yml"): {
        "secrets.databaseUrl": "STAGING_DATABASE_URL",
        "secrets.redisUrl": "STAGING_REDIS_URL",
        "secrets.apiKey": "STAGING_API_KEY",
        "secrets.langfusePublicKey": "STAGING_LANGFUSE_PUBLIC_KEY",
        "secrets.langfuseSecretKey": "STAGING_LANGFUSE_SECRET_KEY",
    },
    Path(".github/workflows/deploy-production.yml"): {
        "secrets.databaseUrl": "PROD_DATABASE_URL",
        "secrets.redisUrl": "PROD_REDIS_URL",
        "secrets.apiKey": "PROD_API_KEY",
        "secrets.langfusePublicKey": "PROD_LANGFUSE_PUBLIC_KEY",
        "secrets.langfuseSecretKey": "PROD_LANGFUSE_SECRET_KEY",
    },
}
HELM_SECRET_TEMPLATE = Path("deployment/helm/templates/secret.yaml")
SECRETS_DOC = Path("docs/GITHUB_SECRETS.md")

FORBIDDEN_LEGACY_KEYS = {
    "secrets.secretKey",
    "secrets.dbPassword",
    "secrets.redisPassword",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _helm_upgrade_blocks(text: str) -> list[str]:
    return re.findall(r"helm upgrade --install xagent xagent/xagent \\\n(?:[^\n]*\n)+?            --timeout 10m", text)


def test_deployment_workflows_helm_deploy_uses_chart_secret_keys() -> None:
    for workflow, expected_helm_keys in WORKFLOWS.items():
        blocks = _helm_upgrade_blocks(_text(workflow))

        assert blocks, f"{workflow} must keep an explicit Helm deploy block"
        for block in blocks:
            assert "--set secrets.enabled=true" in block
            for helm_key, secret_name in expected_helm_keys.items():
                assert f"--set-string {helm_key}=" in block
                assert f"secrets.{secret_name}" in block


def test_deployment_workflows_reject_legacy_secret_values_keys() -> None:
    workflow_text = "\n".join(_text(path) for path in WORKFLOWS)

    for legacy_key in FORBIDDEN_LEGACY_KEYS:
        assert legacy_key not in workflow_text


def test_deployment_workflow_helm_keys_match_secret_template_consumers() -> None:
    workflow_text = "\n".join(_text(path) for path in WORKFLOWS)
    template = _text(HELM_SECRET_TEMPLATE)

    for helm_key in next(iter(WORKFLOWS.values())):
        assert f".Values.{helm_key}" in template
        assert helm_key in workflow_text


def test_github_secrets_doc_tracks_ci_helm_secret_contract() -> None:
    doc = _text(SECRETS_DOC)

    assert "secrets.enabled=true" in doc
    for expected_helm_keys in WORKFLOWS.values():
        for helm_key, secret_name in expected_helm_keys.items():
            assert helm_key in doc
            assert secret_name in doc
    for legacy_key in FORBIDDEN_LEGACY_KEYS:
        assert legacy_key in doc
