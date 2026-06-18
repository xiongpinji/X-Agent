from __future__ import annotations

from backend.app.core.deployment_security_contracts import (
    evaluate_deployment_security_contracts,
    required_deployment_security_paths,
)


def test_deployment_security_contracts_pass_with_required_markers() -> None:
    report = evaluate_deployment_security_contracts(_valid_files())

    assert report["kind"] == "deployment_security_contracts"
    assert report["ok"] is True
    assert report["status"] == "passed"
    assert report["summary"] == {
        "total": 6,
        "passed": 6,
        "failed": 0,
        "failed_checks": [],
    }


def test_deployment_security_contracts_report_missing_k8s_prod_mode() -> None:
    files = _valid_files()
    files["deploy/kubernetes/overlays/staging/kustomization.yaml"] = files[
        "deploy/kubernetes/overlays/staging/kustomization.yaml"
    ].replace("path: /data/XAGENT_SECURITY_MODE\nvalue: production\n", "")

    report = evaluate_deployment_security_contracts(files)
    result = _result(report, "deployment_k8s_security_mode")

    assert report["ok"] is False
    assert result["status"] == "failed"
    assert result["details"]["missing_markers"] == {
        "deploy/kubernetes/overlays/staging/kustomization.yaml": [
            "path: /data/XAGENT_SECURITY_MODE",
            "value: production",
        ]
    }


def test_deployment_security_contracts_report_missing_compose_api_key_requirement() -> None:
    files = _valid_files()
    files["docker-compose.prod.yml"] = files["docker-compose.prod.yml"].replace(
        'XAGENT_REQUIRE_API_KEY: "true"\n',
        "",
        1,
    )

    report = evaluate_deployment_security_contracts(files)
    result = _result(report, "deployment_compose_security_mode")

    assert result["status"] == "failed"
    assert result["details"]["missing_markers"] == {
        "docker-compose.prod.yml": ['XAGENT_REQUIRE_API_KEY: "true"']
    }
    assert "compose overrides" in result["error"]


def test_deployment_security_contracts_report_missing_single_tenant_marker() -> None:
    files = _valid_files()
    files[".env.example"] = files[".env.example"].replace("XAGENT_DEPLOYMENT_TENANCY=single\n", "")

    report = evaluate_deployment_security_contracts(files)
    result = _result(report, "deployment_single_tenant_cloud_contract")

    assert result["status"] == "failed"
    assert result["details"]["missing_markers"] == {
        ".env.example": ["XAGENT_DEPLOYMENT_TENANCY=single"]
    }


def test_deployment_security_contracts_report_missing_observability_marker() -> None:
    files = _valid_files()
    files["docker-compose.prod.yml"] = files["docker-compose.prod.yml"].replace(
        "XAGENT_DEPLOYMENT_ENVIRONMENT: production\n",
        "",
        1,
    )

    report = evaluate_deployment_security_contracts(files)
    result = _result(report, "deployment_production_observability_contract")

    assert result["status"] == "failed"
    assert result["details"]["missing_markers"] == {
        "docker-compose.prod.yml": ["XAGENT_DEPLOYMENT_ENVIRONMENT: production"]
    }


def test_deployment_security_contracts_report_missing_ops_runbook_marker() -> None:
    files = _valid_files()
    files[".env.example"] = files[".env.example"].replace(
        "XAGENT_BACKUP_RESTORE_RUNBOOK=docs/04-实施文档/V2-单租户云端部署说明.md\n",
        "",
    )

    report = evaluate_deployment_security_contracts(files)
    result = _result(report, "deployment_production_ops_runbook_contract")

    assert result["status"] == "failed"
    assert result["details"]["missing_markers"] == {
        ".env.example": ["XAGENT_BACKUP_RESTORE_RUNBOOK=docs/04-实施文档/V2-单租户云端部署说明.md"]
    }
    assert "secret rotation" in result["error"]


def test_required_deployment_security_paths_are_normalized_and_unique() -> None:
    paths = required_deployment_security_paths()

    assert len(paths) == len(set(paths))
    assert ".env.example" in paths
    assert all("\\" not in path for path in paths)


def _result(report: dict, name: str) -> dict:
    return next(item for item in report["results"] if item["name"] == name)


def _valid_files() -> dict[str, str]:
    base_env = "\n".join(
        [
            "XAGENT_SECURITY_MODE=local",
            "XAGENT_DEPLOYMENT_TENANCY=single",
            "XAGENT_REQUIRE_API_KEY=false",
            "XAGENT_BOOTSTRAP_API_KEY_SHA256=",
            "XAGENT_AUDIT_HMAC_SECRET=replace-with-random-production-secret",
            "XAGENT_DATA_DIR=./data",
            "XAGENT_BACKUP_RESTORE_RUNBOOK=",
            "XAGENT_BACKUP_RESTORE_RUNBOOK=docs/04-实施文档/V2-单租户云端部署说明.md",
            "XAGENT_GIT_PROVIDER=manual",
            "XAGENT_DEPLOYMENT_ENVIRONMENT=local",
            "XAGENT_SENTRY_DSN=",
            "XAGENT_LANGFUSE_PUBLIC_KEY=",
            "XAGENT_MEMORY_BACKEND=memory",
            "XAGENT_WORKFLOW_EVENT_BROKER_BACKEND=local",
            "",
        ]
    )
    compose_service = """
  backend:
    environment:
      XAGENT_SECURITY_MODE: production
      XAGENT_REQUIRE_API_KEY: "true"
      XAGENT_DEPLOYMENT_ENVIRONMENT: {environment}
      XAGENT_MEMORY_BACKEND: {memory_backend}
      XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: rabbitmq
  workflow-worker:
    environment:
      XAGENT_SECURITY_MODE: production
      XAGENT_REQUIRE_API_KEY: "true"
      XAGENT_DEPLOYMENT_ENVIRONMENT: {environment}
      XAGENT_MEMORY_BACKEND: {memory_backend}
      XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: rabbitmq
"""
    kustomize = """
path: /data/XAGENT_SECURITY_MODE
value: production
path: /data/XAGENT_DEPLOYMENT_ENVIRONMENT
value: {environment}
path: /data/XAGENT_MEMORY_BACKEND
value: postgres
path: /data/XAGENT_WORKFLOW_EVENT_BROKER_BACKEND
value: rabbitmq
"""
    return {
        ".env.example": base_env,
        "docker-compose.yml": """
XAGENT_DEPLOYMENT_TENANCY: ${XAGENT_DEPLOYMENT_TENANCY:-single}
XAGENT_DATA_DIR: ${XAGENT_DATA_DIR:-/app/data}
XAGENT_REQUIRE_API_KEY: ${XAGENT_REQUIRE_API_KEY:-true}
XAGENT_DEPLOYMENT_ENVIRONMENT: ${XAGENT_DEPLOYMENT_ENVIRONMENT:-local}
XAGENT_SENTRY_DSN: ${XAGENT_SENTRY_DSN:-}
XAGENT_MEMORY_BACKEND: ${XAGENT_MEMORY_BACKEND:-memory}
XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: ${XAGENT_WORKFLOW_EVENT_BROKER_BACKEND:-local}
healthcheck:
http://127.0.0.1:8000/health
./data:/app/data
workflow-worker:
""",
        "docker-compose.staging.yml": compose_service.format(environment="staging", memory_backend="postgres"),
        "docker-compose.prod.yml": compose_service.format(environment="production", memory_backend="postgres"),
        "deploy/kubernetes/overlays/staging/kustomization.yaml": kustomize.format(environment="staging"),
        "deploy/kubernetes/overlays/prod/kustomization.yaml": kustomize.format(environment="production"),
        "deploy/kubernetes/base/configmap.yaml": """
XAGENT_DEPLOYMENT_TENANCY: "single"
XAGENT_DATA_DIR: "/app/data"
XAGENT_REQUIRE_API_KEY: "true"
XAGENT_ENABLE_SHELL_TOOL: "false"
XAGENT_SHELL_JOB_APPLY_MODE: "manifest"
""",
        "deploy/kubernetes/base/secret.example.yaml": """
XAGENT_BOOTSTRAP_API_KEY_SHA256
XAGENT_AUDIT_HMAC_SECRET
XAGENT_DATABASE_URL
""",
        "deploy/kubernetes/base/deployment.yaml": """
readOnlyRootFilesystem: true
mountPath: /app/data
claimName: x-agent-data
path: /health
path: /ready
""",
        "deploy/kubernetes/base/pvc.yaml": """
name: x-agent-data
storage: 10Gi
""",
        "deploy/kubernetes/shell-job-worker/deployment.yaml": """
name: x-agent-shell-job-worker
mountPath: /app/data
claimName: x-agent-data
""",
        "deploy/kubernetes/backup/postgres-backup-cronjob.yaml": """
kind: CronJob
pg_dump
-Fc
claimName: x-agent-backup
""",
        "deploy/kubernetes/tool-isolation/shell-exec-job-template.yaml": """
kind: Job
suspend: true
readOnlyRootFilesystem: true
""",
        "deploy/kubernetes/overlays/staging/externalsecret.yaml": """
secretKey: XAGENT_AUDIT_HMAC_SECRET
secretKey: XAGENT_BOOTSTRAP_API_KEY_SHA256
""",
        "deploy/kubernetes/overlays/prod/externalsecret.yaml": """
secretKey: XAGENT_AUDIT_HMAC_SECRET
secretKey: XAGENT_BOOTSTRAP_API_KEY_SHA256
""",
    }
