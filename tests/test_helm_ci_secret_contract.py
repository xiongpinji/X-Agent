from __future__ import annotations

import re
from pathlib import Path


WORKFLOWS = {
    Path(".github/workflows/deploy.yml"): {
        "secrets.databaseUrl": "STAGING_DATABASE_URL",
        "secrets.redisUrl": "STAGING_REDIS_URL",
        "secrets.apiKey": "STAGING_API_KEY",
        "secrets.jwtSecret": "STAGING_JWT_SECRET",
        "secrets.encryptionKey": "STAGING_ENCRYPTION_KEY",
        "secrets.auditHmacSecret": "STAGING_AUDIT_HMAC_SECRET",
        "secrets.langfusePublicKey": "STAGING_LANGFUSE_PUBLIC_KEY",
        "secrets.langfuseSecretKey": "STAGING_LANGFUSE_SECRET_KEY",
        "secrets.sentryDsn": "STAGING_SENTRY_DSN",
        "secrets.workflowEventRabbitmqUrl": "STAGING_WORKFLOW_EVENT_RABBITMQ_URL",
    },
    Path(".github/workflows/ci-cd.yml"): {
        "secrets.databaseUrl": "STAGING_DATABASE_URL",
        "secrets.redisUrl": "STAGING_REDIS_URL",
        "secrets.apiKey": "STAGING_API_KEY",
        "secrets.jwtSecret": "STAGING_JWT_SECRET",
        "secrets.encryptionKey": "STAGING_ENCRYPTION_KEY",
        "secrets.auditHmacSecret": "STAGING_AUDIT_HMAC_SECRET",
        "secrets.langfusePublicKey": "STAGING_LANGFUSE_PUBLIC_KEY",
        "secrets.langfuseSecretKey": "STAGING_LANGFUSE_SECRET_KEY",
        "secrets.sentryDsn": "STAGING_SENTRY_DSN",
        "secrets.workflowEventRabbitmqUrl": "STAGING_WORKFLOW_EVENT_RABBITMQ_URL",
    },
    Path(".github/workflows/deploy-production.yml"): {
        "secrets.databaseUrl": "PROD_DATABASE_URL",
        "secrets.redisUrl": "PROD_REDIS_URL",
        "secrets.apiKey": "PROD_API_KEY",
        "secrets.jwtSecret": "PROD_JWT_SECRET",
        "secrets.encryptionKey": "PROD_ENCRYPTION_KEY",
        "secrets.auditHmacSecret": "PROD_AUDIT_HMAC_SECRET",
        "secrets.langfusePublicKey": "PROD_LANGFUSE_PUBLIC_KEY",
        "secrets.langfuseSecretKey": "PROD_LANGFUSE_SECRET_KEY",
        "secrets.sentryDsn": "PROD_SENTRY_DSN",
        "secrets.workflowEventRabbitmqUrl": "PROD_WORKFLOW_EVENT_RABBITMQ_URL",
    },
}
HELM_SECRET_TEMPLATE = Path("deployment/helm/templates/secret.yaml")
HELM_DEPLOYMENT_TEMPLATE = Path("deployment/helm/templates/deployment.yaml")
HELM_VALUES = Path("deployment/helm/values.yaml")
HELM_STAGING_VALUES = Path("deployment/helm/values-staging.yaml")
HELM_PRODUCTION_VALUES = Path("deployment/helm/values-production.yaml")
HELM_README = Path("deployment/helm/README.md")
SECRETS_DOC = Path("docs/GITHUB_SECRETS.md")

FORBIDDEN_LEGACY_KEYS = {
    "secrets.secretKey",
    "secrets.dbPassword",
    "secrets.redisPassword",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _helm_upgrade_blocks(text: str) -> list[str]:
    return re.findall(r"helm upgrade --install xagent xagent/xagent \\\n(?:[^\n]*\n)+?\s+--timeout 10m", text)


def test_deployment_workflows_helm_deploy_uses_chart_secret_keys() -> None:
    for workflow, expected_helm_keys in WORKFLOWS.items():
        blocks = _helm_upgrade_blocks(_text(workflow))
        workflow_text = _text(workflow)

        assert blocks, f"{workflow} must keep an explicit Helm deploy block"
        for block in blocks:
            assert "--set secrets.enabled=true" in block
            assert "--set secrets.create=false" in block
            assert "--set-string secrets.existingSecretName=xagent-secrets" in block
            for helm_key in expected_helm_keys:
                assert f"--set-string {helm_key}=" not in block
        for secret_name in expected_helm_keys.values():
            assert f"secrets.{secret_name}" in workflow_text


def test_deployment_workflows_create_kubernetes_secret_before_helm() -> None:
    expected_key_names = (
        "database-url",
        "redis-url",
        "api-key",
        "jwt-secret",
        "encryption-key",
        "audit-hmac-secret",
        "langfuse-public-key",
        "langfuse-secret-key",
        "sentry-dsn",
        "workflow-event-rabbitmq-url",
    )

    for workflow, expected_helm_keys in WORKFLOWS.items():
        text = _text(workflow)

        assert "kubectl create secret generic xagent-secrets" in text
        assert "--dry-run=client" in text
        assert "-o yaml | kubectl apply -f -" in text
        for key_name in expected_key_names:
            assert f"--from-literal={key_name}=" in text
        for secret_name in expected_helm_keys.values():
            assert f"secrets.{secret_name}" in text


def test_deployment_workflows_do_not_pass_raw_secrets_through_helm_values() -> None:
    workflow_text = "\n".join(_text(path) for path in WORKFLOWS)

    for expected_helm_keys in WORKFLOWS.values():
        for helm_key in expected_helm_keys:
            assert f"--set-string {helm_key}=" not in workflow_text
    assert "--set-string secrets.existingSecretName=xagent-secrets" in workflow_text


def test_helm_readme_does_not_recommend_raw_secret_helm_values() -> None:
    readme = _text(HELM_README)

    for expected_helm_keys in WORKFLOWS.values():
        for helm_key in expected_helm_keys:
            assert f"--set-string {helm_key}=" not in readme
    assert "kubectl create secret generic xagent-secrets" in readme
    assert "--set-string secrets.existingSecretName=xagent-secrets" in readme


def test_deployment_workflows_reject_legacy_secret_values_keys() -> None:
    workflow_text = "\n".join(_text(path) for path in WORKFLOWS)

    for legacy_key in FORBIDDEN_LEGACY_KEYS:
        assert legacy_key not in workflow_text


def test_deployment_workflow_helm_keys_match_secret_template_consumers() -> None:
    workflow_text = "\n".join(_text(path) for path in WORKFLOWS)
    template = _text(HELM_SECRET_TEMPLATE)

    for helm_key in next(iter(WORKFLOWS.values())):
        assert f".Values.{helm_key}" in template
    assert "secrets.existingSecretName" in workflow_text


def test_helm_secret_template_fails_closed_for_enabled_external_dependencies() -> None:
    template = _text(HELM_SECRET_TEMPLATE)

    assert "{{- if .Values.secrets.create }}" in template
    assert 'include "xagent.secretName"' in template
    for helm_key in next(iter(WORKFLOWS.values())):
        assert f'required "{helm_key} is required' in template
    assert "when observability.traces.enabled=true" in template
    assert "when observability.errors.enabled=true" in template
    assert "when workflowEvents.backend=rabbitmq" in template
    assert 'workflow-event-rabbitmq-url: {{ required "' in template


def test_helm_runtime_observability_env_uses_xagent_prefixes() -> None:
    template = _text(HELM_DEPLOYMENT_TEMPLATE)

    assert 'include "xagent.secretName"' in template
    assert "- name: XAGENT_LANGFUSE_PUBLIC_KEY" in template
    assert "- name: XAGENT_LANGFUSE_SECRET_KEY" in template
    assert "- name: XAGENT_LANGFUSE_HOST" in template
    assert "- name: XAGENT_DATABASE_URL" in template
    assert "- name: XAGENT_REDIS_URL" in template
    assert "- name: XAGENT_BOOTSTRAP_API_KEY" in template
    assert "- name: XAGENT_JWT_SECRET" in template
    assert "- name: XAGENT_ENCRYPTION_KEY" in template
    assert "- name: XAGENT_AUDIT_HMAC_SECRET" in template
    assert "- name: XAGENT_SENTRY_DSN" in template
    assert "- name: XAGENT_WORKFLOW_EVENT_BROKER_BACKEND" in template
    assert "- name: XAGENT_WORKFLOW_EVENT_RABBITMQ_URL" in template
    assert "- name: DATABASE_URL" not in template
    assert "- name: REDIS_URL" not in template
    assert "- name: API_KEY" not in template
    assert "- name: LANGFUSE_PUBLIC_KEY" not in template
    assert "- name: LANGFUSE_SECRET_KEY" not in template


def test_helm_prometheus_scrape_path_matches_backend_metrics_route() -> None:
    values = "\n".join(
        _text(path)
        for path in (
            HELM_VALUES,
            HELM_STAGING_VALUES,
            HELM_PRODUCTION_VALUES,
            HELM_README,
        )
    )

    assert 'prometheus.io/path: "/api/v1/metrics/prometheus"' in values
    assert "path: /api/v1/metrics/prometheus" in values
    assert "metrics_path: /api/v1/metrics/prometheus" in values
    assert 'prometheus.io/path: "/metrics"' not in values
    assert "metrics_path: /metrics" not in values


def test_github_secrets_doc_tracks_ci_helm_secret_contract() -> None:
    doc = _text(SECRETS_DOC)

    assert "secrets.enabled=true" in doc
    assert "secrets.create=false" in doc
    assert "secrets.existingSecretName" in doc
    assert "kubectl create secret generic xagent-secrets" in doc
    for expected_helm_keys in WORKFLOWS.values():
        for helm_key, secret_name in expected_helm_keys.items():
            assert helm_key in doc
            assert secret_name in doc
    for legacy_key in FORBIDDEN_LEGACY_KEYS:
        assert legacy_key in doc
