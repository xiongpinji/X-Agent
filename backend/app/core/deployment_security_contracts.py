from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


SECURITY_MODE_KEY = "XAGENT_SECURITY_MODE"
DEPLOYMENT_ENVIRONMENT_KEY = "XAGENT_DEPLOYMENT_ENVIRONMENT"
TENANCY_KEY = "XAGENT_DEPLOYMENT_TENANCY"
PRODUCTION_VALUE = "production"
STAGING_VALUE = "staging"
SINGLE_TENANT_VALUE = "single"

K8S_PRODUCTION_OVERLAYS = (
    "deploy/kubernetes/overlays/staging/kustomization.yaml",
    "deploy/kubernetes/overlays/prod/kustomization.yaml",
)
COMPOSE_PRODUCTION_OVERRIDES = ("docker-compose.staging.yml", "docker-compose.prod.yml")
COMPOSE_RUNTIME_SERVICES = ("backend", "workflow-worker")


@dataclass(frozen=True)
class DeploymentSecurityCheck:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "passed"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "details": self.details,
        }
        if self.error:
            payload["error"] = self.error
        return payload


def evaluate_deployment_security_contracts(files: Mapping[str, str]) -> dict[str, Any]:
    normalized_files = {_normalize_path(path): text for path, text in files.items()}
    checks = [
        _check_k8s_production_security_mode(normalized_files),
        _check_compose_production_security_mode(normalized_files),
        _check_env_example_security_mode(normalized_files),
        _check_single_tenant_cloud_contract(normalized_files),
        _check_production_observability_contract(normalized_files),
        _check_production_ops_runbook_contract(normalized_files),
    ]
    failed = [check for check in checks if not check.ok]
    return {
        "kind": "deployment_security_contracts",
        "version": 1,
        "ok": not failed,
        "status": "passed" if not failed else "failed",
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "failed_checks": [check.name for check in failed],
        },
        "results": [check.as_dict() for check in checks],
    }


def required_deployment_security_paths() -> tuple[str, ...]:
    paths: list[str] = []
    for path in (
        *K8S_PRODUCTION_OVERLAYS,
        *COMPOSE_PRODUCTION_OVERRIDES,
        ".env.example",
        "docker-compose.yml",
        "deploy/kubernetes/base/configmap.yaml",
        "deploy/kubernetes/base/secret.example.yaml",
        "deploy/kubernetes/base/deployment.yaml",
        "deploy/kubernetes/base/pvc.yaml",
        "deploy/kubernetes/backup/postgres-backup-cronjob.yaml",
        "deploy/kubernetes/tool-isolation/shell-exec-job-template.yaml",
        "deploy/kubernetes/shell-job-worker/deployment.yaml",
        "deploy/kubernetes/overlays/staging/externalsecret.yaml",
        "deploy/kubernetes/overlays/prod/externalsecret.yaml",
    ):
        normalized = _normalize_path(path)
        if normalized not in paths:
            paths.append(normalized)
    return tuple(paths)


def _check_k8s_production_security_mode(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    required = (f"path: /data/{SECURITY_MODE_KEY}", f"value: {PRODUCTION_VALUE}")
    missing = _missing_markers(files, K8S_PRODUCTION_OVERLAYS, required)
    if missing:
        return DeploymentSecurityCheck(
            "deployment_k8s_security_mode",
            "failed",
            {"missing_markers": missing},
            "Prod and staging Kubernetes overlays must set XAGENT_SECURITY_MODE=production.",
        )
    return DeploymentSecurityCheck(
        "deployment_k8s_security_mode",
        "passed",
        {"overlays": list(K8S_PRODUCTION_OVERLAYS), "required": f"{SECURITY_MODE_KEY}={PRODUCTION_VALUE}"},
    )


def _check_compose_production_security_mode(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    missing: dict[str, list[str]] = {}
    for path in COMPOSE_PRODUCTION_OVERRIDES:
        text = files.get(_normalize_path(path), "")
        if not text:
            missing[path] = ["<file>"]
            continue
        for service in COMPOSE_RUNTIME_SERVICES:
            marker = f"  {service}:"
            if marker not in text:
                missing.setdefault(path, []).append(marker.strip())
        if text.count(f"{SECURITY_MODE_KEY}: {PRODUCTION_VALUE}") < len(COMPOSE_RUNTIME_SERVICES):
            missing.setdefault(path, []).append(f"{SECURITY_MODE_KEY}: {PRODUCTION_VALUE}")
        if text.count('XAGENT_REQUIRE_API_KEY: "true"') < len(COMPOSE_RUNTIME_SERVICES):
            missing.setdefault(path, []).append('XAGENT_REQUIRE_API_KEY: "true"')
    if missing:
        return DeploymentSecurityCheck(
            "deployment_compose_security_mode",
            "failed",
            {"missing_markers": missing},
            "Prod and staging compose overrides must set XAGENT_SECURITY_MODE=production for runtime services.",
        )
    return DeploymentSecurityCheck(
        "deployment_compose_security_mode",
        "passed",
        {"compose_files": list(COMPOSE_PRODUCTION_OVERRIDES), "services": list(COMPOSE_RUNTIME_SERVICES)},
    )


def _check_env_example_security_mode(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    marker = f"{SECURITY_MODE_KEY}=local"
    if marker not in files.get(".env.example", ""):
        return DeploymentSecurityCheck(
            "deployment_env_example_security_mode",
            "failed",
            {"missing_marker": marker},
            ".env.example must document the local security-mode default.",
        )
    return DeploymentSecurityCheck("deployment_env_example_security_mode", "passed", {"local_default": marker})


def _check_single_tenant_cloud_contract(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    required = {
        ".env.example": (
            f"{TENANCY_KEY}={SINGLE_TENANT_VALUE}",
            "XAGENT_REQUIRE_API_KEY=false",
            "XAGENT_BOOTSTRAP_API_KEY_SHA256=",
            "XAGENT_AUDIT_HMAC_SECRET=replace-with-random-production-secret",
            "XAGENT_DATA_DIR=./data",
            "XAGENT_BACKUP_RESTORE_RUNBOOK=",
            "XAGENT_GIT_PROVIDER=manual",
        ),
        "docker-compose.yml": (
            f"{TENANCY_KEY}: ${{{TENANCY_KEY}:-{SINGLE_TENANT_VALUE}}}",
            "XAGENT_DATA_DIR: ${XAGENT_DATA_DIR:-/app/data}",
            "XAGENT_REQUIRE_API_KEY: ${XAGENT_REQUIRE_API_KEY:-true}",
            "healthcheck:",
            "http://127.0.0.1:8000/health",
            "./data:/app/data",
            "workflow-worker:",
        ),
        "deploy/kubernetes/base/configmap.yaml": (
            'XAGENT_DEPLOYMENT_TENANCY: "single"',
            'XAGENT_DATA_DIR: "/app/data"',
            'XAGENT_REQUIRE_API_KEY: "true"',
            'XAGENT_ENABLE_SHELL_TOOL: "false"',
            'XAGENT_SHELL_JOB_APPLY_MODE: "manifest"',
        ),
        "deploy/kubernetes/base/secret.example.yaml": (
            "XAGENT_BOOTSTRAP_API_KEY_SHA256",
            "XAGENT_AUDIT_HMAC_SECRET",
            "XAGENT_DATABASE_URL",
        ),
        "deploy/kubernetes/base/deployment.yaml": (
            "readOnlyRootFilesystem: true",
            "mountPath: /app/data",
            "claimName: x-agent-data",
            "path: /health",
            "path: /ready",
        ),
        "deploy/kubernetes/base/pvc.yaml": ("name: x-agent-data", "storage: 10Gi"),
        "deploy/kubernetes/shell-job-worker/deployment.yaml": (
            "name: x-agent-shell-job-worker",
            "mountPath: /app/data",
            "claimName: x-agent-data",
        ),
        "deploy/kubernetes/backup/postgres-backup-cronjob.yaml": ("kind: CronJob", "pg_dump", "claimName: x-agent-backup"),
        "deploy/kubernetes/tool-isolation/shell-exec-job-template.yaml": (
            "kind: Job",
            "suspend: true",
            "readOnlyRootFilesystem: true",
        ),
    }
    missing = _missing_markers_by_file(files, required)
    if missing:
        return DeploymentSecurityCheck(
            "deployment_single_tenant_cloud_contract",
            "failed",
            {"missing_markers": missing},
            "V2 cloud deployment must be single-tenant ready; multi-tenant isolation and billing are not required.",
        )
    return DeploymentSecurityCheck(
        "deployment_single_tenant_cloud_contract",
        "passed",
        {"tenancy": SINGLE_TENANT_VALUE, "not_required": ["multi_tenant", "billing"]},
    )


def _check_production_observability_contract(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    required = {
        ".env.example": (
            f"{DEPLOYMENT_ENVIRONMENT_KEY}=local",
            "XAGENT_SENTRY_DSN=",
            "XAGENT_LANGFUSE_PUBLIC_KEY=",
            "XAGENT_MEMORY_BACKEND=memory",
            "XAGENT_WORKFLOW_EVENT_BROKER_BACKEND=local",
        ),
        "docker-compose.yml": (
            f"{DEPLOYMENT_ENVIRONMENT_KEY}: ${{{DEPLOYMENT_ENVIRONMENT_KEY}:-local}}",
            "XAGENT_SENTRY_DSN: ${XAGENT_SENTRY_DSN:-}",
            "XAGENT_MEMORY_BACKEND: ${XAGENT_MEMORY_BACKEND:-memory}",
            "XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: ${XAGENT_WORKFLOW_EVENT_BROKER_BACKEND:-local}",
        ),
        "deploy/kubernetes/overlays/staging/kustomization.yaml": (
            f"path: /data/{DEPLOYMENT_ENVIRONMENT_KEY}",
            f"value: {STAGING_VALUE}",
            "path: /data/XAGENT_WORKFLOW_EVENT_BROKER_BACKEND",
            "value: rabbitmq",
        ),
        "deploy/kubernetes/overlays/prod/kustomization.yaml": (
            f"path: /data/{DEPLOYMENT_ENVIRONMENT_KEY}",
            f"value: {PRODUCTION_VALUE}",
            "path: /data/XAGENT_MEMORY_BACKEND",
            "value: postgres",
            "path: /data/XAGENT_WORKFLOW_EVENT_BROKER_BACKEND",
            "value: rabbitmq",
        ),
    }
    missing = _missing_markers_by_file(files, required)
    for path, marker_counts in {
        "docker-compose.staging.yml": {
            f"{DEPLOYMENT_ENVIRONMENT_KEY}: {STAGING_VALUE}": len(COMPOSE_RUNTIME_SERVICES),
            "XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: rabbitmq": len(COMPOSE_RUNTIME_SERVICES),
        },
        "docker-compose.prod.yml": {
            f"{DEPLOYMENT_ENVIRONMENT_KEY}: {PRODUCTION_VALUE}": len(COMPOSE_RUNTIME_SERVICES),
            "XAGENT_MEMORY_BACKEND: postgres": len(COMPOSE_RUNTIME_SERVICES),
            "XAGENT_WORKFLOW_EVENT_BROKER_BACKEND: rabbitmq": len(COMPOSE_RUNTIME_SERVICES),
        },
    }.items():
        text = files.get(_normalize_path(path), "")
        for marker, expected_count in marker_counts.items():
            if text.count(marker) < expected_count:
                missing.setdefault(path, []).append(marker)
    if missing:
        return DeploymentSecurityCheck(
            "deployment_production_observability_contract",
            "failed",
            {"missing_markers": missing},
            "Prod and staging must declare strict observability mode and avoid local-only broker defaults.",
        )
    return DeploymentSecurityCheck(
        "deployment_production_observability_contract",
        "passed",
        {"strict_environments": [STAGING_VALUE, PRODUCTION_VALUE], "required_broker": "rabbitmq"},
    )


def _check_production_ops_runbook_contract(files: Mapping[str, str]) -> DeploymentSecurityCheck:
    required = {
        ".env.example": (
            "XAGENT_BACKUP_RESTORE_RUNBOOK=docs/04-实施文档/V2-单租户云端部署说明.md",
            "XAGENT_SENTRY_DSN=",
            "XAGENT_LANGFUSE_PUBLIC_KEY=",
            "XAGENT_AUDIT_HMAC_SECRET=replace-with-random-production-secret",
        ),
        "deploy/kubernetes/backup/postgres-backup-cronjob.yaml": ("kind: CronJob", "pg_dump", "-Fc", "claimName: x-agent-backup"),
        "deploy/kubernetes/overlays/staging/externalsecret.yaml": (
            "secretKey: XAGENT_AUDIT_HMAC_SECRET",
            "secretKey: XAGENT_BOOTSTRAP_API_KEY_SHA256",
        ),
        "deploy/kubernetes/overlays/prod/externalsecret.yaml": (
            "secretKey: XAGENT_AUDIT_HMAC_SECRET",
            "secretKey: XAGENT_BOOTSTRAP_API_KEY_SHA256",
        ),
    }
    missing = _missing_markers_by_file(files, required)
    if missing:
        return DeploymentSecurityCheck(
            "deployment_production_ops_runbook_contract",
            "failed",
            {"missing_markers": missing},
            "Production deployments must retain enforceable ops hooks for monitoring, restore drills, incidents, upgrades, rollback, and secret rotation.",
        )
    return DeploymentSecurityCheck(
        "deployment_production_ops_runbook_contract",
        "passed",
        {"runbook": "docs/04-实施文档/V2-单租户云端部署说明.md"},
    )


def _missing_markers(files: Mapping[str, str], paths: Sequence[str], markers: Sequence[str]) -> dict[str, list[str]]:
    return _missing_markers_by_file(files, {path: markers for path in paths})


def _missing_markers_by_file(files: Mapping[str, str], required: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for path, markers in required.items():
        text = files.get(_normalize_path(path), "")
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[path] = absent
    return missing


def _normalize_path(path: str) -> str:
    return str(path).strip().replace("\\", "/")
