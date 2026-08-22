from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_alembic_has_single_commercial_head_and_runtime_gate() -> None:
    versions = ROOT / "backend/migrations/versions"
    migrations = list(versions.glob("*.py"))
    commercial = [path for path in migrations if "commercial" in path.name]

    assert len(commercial) == 1
    migration = commercial[0].read_text(encoding="utf-8")
    assert "down_revision: str | None = \"0001_initial\"" in migration
    for table in (
        "admin_users",
        "admin_tenants",
        "rbac_roles",
        "rbac_user_roles",
        "workflow_definitions",
        "workflow_runs",
        "workflow_schedules",
        "chat_sessions",
        "chat_messages",
        "usage_reservations",
        "usage_reservation_ledger",
        "usage_reservation_audit_outbox",
        "feedback",
        "feedback_analysis",
        "memories",
        "trace_events",
        "agent_run_records",
        "commercial_audit_events",
    ):
        assert table in migration
    assert 'sa.Column("trace_id", sa.String(128), nullable=False)' in migration

    gate = _read("backend/app/ops/migration_gate.py")
    assert 'command.upgrade(config, "head")' in gate
    assert "check_heads=True" in gate
    assert "return 0" not in gate.split("except", 1)[-1]


def test_deployment_scripts_never_skip_migrations() -> None:
    deploy = _read("deployment/scripts/deploy.sh")
    migrate = _read("deployment/scripts/migrate-db.sh")
    for script in (deploy, migrate):
        assert "backend/migrations/alembic.ini" in script
        assert "alembic.ini \u4e0d\u5b58\u5728, \u8df3\u8fc7" not in script
        assert "kubectl exec -it" not in script
    assert "--wait-for-jobs" in deploy
    assert "xagent:latest" not in deploy
    assert "docker build" not in deploy
    assert "XAGENT_IMAGE_REPOSITORY" in deploy
    assert "XAGENT_PRE_MIGRATION_BACKUP_ID" in deploy
    assert "XAGENT_BACKUP_S3_BUCKET" in deploy
    assert "XAGENT_BACKUP_ROLE_ARN" in deploy
    assert "Environment-specific values file not found" in deploy
    assert "--dry-run" in migrate
    assert "XAGENT_PRE_MIGRATION_BACKUP_ID" in migrate
    assert "rollback_migrations" not in migrate


def test_helm_blocks_workloads_until_migrations_reach_head() -> None:
    migration_job = _read("deployment/helm/templates/migration-job.yaml")
    assert "kind: Job" in migration_job
    assert "backend.app.ops.migration_gate" in migration_job
    assert "upgrade" in migration_job

    for template in (
        "deployment/helm/templates/api-deployment.yaml",
        "deployment/helm/templates/worker-deployment.yaml",
        "deployment/helm/templates/beat-deployment.yaml",
    ):
        text = _read(template)
        assert "initContainers:" in text
        assert "backend.app.ops.migration_gate" in text
        assert "wait" in text


def test_production_values_fail_closed_without_operator_configuration() -> None:
    values = yaml.safe_load(_read("deployment/helm/values-production.yaml"))
    assert values["postgres"]["enabled"] is False
    assert values["redis"]["enabled"] is False
    assert values["qdrant"]["enabled"] is False
    assert values["external"]["postgresHost"] == ""
    assert values["external"]["redisHost"] == ""
    assert values["external"]["qdrantHost"] == ""
    assert values["image"]["repository"] == ""
    assert values["ingress"]["hosts"][0]["host"] == ""
    assert values["secrets"]["existingSecret"] == ""
    assert values["appEnv"]["workflowStoreBackend"] == "db"
    assert values["appEnv"]["memoryBackend"] == "postgres"
    assert values["appEnv"]["traceBackend"] == "postgres"
    assert values["appEnv"]["adminStoreBackend"] == "postgres"
    assert values["appEnv"]["feedbackStoreBackend"] == "postgres"
    assert values["appEnv"]["runStoreBackend"] == "postgres"
    assert values["appEnv"]["auditStoreBackend"] == "postgres"
    assert values["artifacts"]["existingClaim"] == ""
    assert values["migration"]["verifiedBackupId"] == ""
    # The realtime collaboration bus is process-local. Production must stay on
    # one API process until a distributed stream backend is implemented.
    assert values["api"]["replicas"] == 1
    assert values["api"]["workers"] == 1
    assert values["api"]["autoscaling"]["enabled"] is False
    assert values["runtime"]["mountPath"] == "/var/lib/xagent"
    assert values["backup"]["s3"]["enabled"] is True
    assert values["backup"]["s3"]["bucket"] == ""
    assert values["backup"]["serviceAccount"]["roleArn"] == ""
    text = _read("deployment/helm/values-production.yaml")
    assert "CHANGE_ME" not in text
    assert "example.com" not in text
    assert "your-registry" not in text


def test_chart_requires_external_endpoints_image_ingress_and_existing_secret() -> None:
    helpers = _read("deployment/helm/templates/_helpers.tpl")
    secret = _read("deployment/helm/templates/secret.yaml")
    ingress = _read("deployment/helm/templates/ingress.yaml")
    for required_value in (
        "image.repository",
        "secrets.existingSecret",
        "ingress.hosts[0].host",
        "artifacts.existingClaim",
        "migration.verifiedBackupId",
        "backup.s3.bucket",
        "backup.serviceAccount.roleArn",
    ):
        assert required_value in helpers
    assert "kind: Secret" not in secret
    assert 'include "xagent.ingressHost"' in ingress
    assert helpers.count('regexMatch "^sha-[0-9a-f]{40}$"') == 2


def test_chart_mounts_writable_runtime_state_and_uses_real_gunicorn_worker_env() -> None:
    config = _read("deployment/helm/templates/configmap.yaml")
    assert "API_WORKERS:" in config
    assert "XAGENT_API_WORKERS:" not in config
    for variable in (
        "XAGENT_API_KEY_STORE_PATH",
        "XAGENT_APPROVAL_STORE_PATH",
        "XAGENT_TOOL_EXECUTION_STORE_PATH",
        "XAGENT_AGENT_CONTEXT_STORE_PATH",
        "XAGENT_CONTEXT_SESSION_STORE_PATH",
        "X_AGENT_GOALS_STORE_PATH",
    ):
        assert variable in config

    for template in (
        "deployment/helm/templates/api-deployment.yaml",
        "deployment/helm/templates/worker-deployment.yaml",
        "deployment/helm/templates/beat-deployment.yaml",
    ):
        text = _read(template)
        assert ".Values.runtime.mountPath" in text
        assert 'include "xagent.artifactsClaim"' in text

    for template in (
        "deployment/helm/templates/api-deployment.yaml",
        "deployment/helm/templates/worker-deployment.yaml",
    ):
        text = _read(template)
        assert "name: XAGENT_QDRANT_API_KEY" in text
        assert "key: QDRANT_API_KEY" in text
        assert "name: XAGENT_NEO4J_PASSWORD" in text
        assert "key: NEO4J_PASSWORD" in text
        assert "name: XAGENT_NEO4J_URL" in text
        assert "name: XAGENT_NEO4J_URI" not in text


def test_production_workflow_uses_local_chart_and_operator_url_without_cli_secrets() -> None:
    workflow = _read(".github/workflows/deploy-production.yml")
    assert "https://api.example.com" not in workflow
    assert "HELM_REPO_URL" not in workflow
    assert "xagent/xagent" not in workflow
    assert "deployment/helm" in workflow
    assert "vars.PRODUCTION_API_URL" in workflow
    assert "needs.build.outputs.image-repository" in workflow
    assert "needs.build.outputs.image-tag" in workflow
    assert "--set secrets." not in workflow
    assert "--wait-for-jobs" in workflow
    assert "vars.XAGENT_ARTIFACTS_PVC" in workflow
    assert "vars.XAGENT_PRE_MIGRATION_BACKUP_ID" in workflow
    assert "vars.PRODUCTION_BACKUP_S3_BUCKET" in workflow
    assert "vars.XAGENT_BACKUP_ROLE_ARN" in workflow
    assert "--set-string migration.verifiedBackupId=" in workflow
    assert "--set-string backup.s3.bucket=" in workflow
    assert "--set-string backup.serviceAccount.roleArn=" in workflow


def test_production_workflow_uses_safe_pinned_test_inputs_and_hard_security_gates() -> None:
    workflow = _read(".github/workflows/deploy-production.yml")
    assert "pip install -r requirements-lock.txt" in workflow
    assert "pip install --no-deps --no-build-isolation -e ." in workflow
    assert "XAGENT_LLM_BACKEND: mock" in workflow
    assert "XAGENT_OPENAI_API_KEY: \"\"" in workflow
    assert "XAGENT_DEEPSEEK_API_KEY: \"\"" in workflow
    assert "--ignore=tests/test_trace_audit_integration.py" in workflow
    assert "bandit -r backend/ -lll" in workflow
    assert "bandit==1.9.4" in workflow
    assert "bandit -r backend/ -f json -o bandit-report.json || true" not in workflow
    assert "safety check --json > safety-report.json || true" not in workflow


def test_production_migration_gate_requires_verified_backup_reference() -> None:
    gate = _read("backend/app/ops/migration_gate.py")
    job = _read("deployment/helm/templates/migration-job.yaml")
    assert "XAGENT_PRE_MIGRATION_BACKUP_ID" in gate
    assert "XAGENT_PRE_MIGRATION_BACKUP_ID" in job


def test_production_migration_gate_checks_backup_before_database(monkeypatch) -> None:
    from backend.app.ops import migration_gate

    called = False

    def unexpected_config():
        nonlocal called
        called = True
        raise AssertionError("database migration must not start without backup evidence")

    monkeypatch.setenv("XAGENT_APP_MODE", "production")
    monkeypatch.delenv("XAGENT_PRE_MIGRATION_BACKUP_ID", raising=False)
    monkeypatch.setattr(migration_gate, "_config", unexpected_config)

    with pytest.raises(RuntimeError, match="XAGENT_PRE_MIGRATION_BACKUP_ID"):
        migration_gate._upgrade()
    assert called is False


@pytest.mark.asyncio
async def test_production_rbac_storage_failure_does_not_fallback_to_memory(monkeypatch) -> None:
    import asyncpg

    from backend.app import dependencies

    async def fail_pool(*args, **kwargs):
        raise OSError("private-database-detail")

    monkeypatch.setattr(asyncpg, "create_pool", fail_pool)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(
            app_mode="production",
            admin_store_backend="postgres",
            database_url="postgresql+asyncpg://user:pass@db.internal:5432/xagent",
        ),
    )
    dependencies._rbac_engine = None
    try:
        with pytest.raises(RuntimeError, match="RBAC storage is unavailable") as exc_info:
            await dependencies.get_rbac_engine()
        assert "private-database-detail" not in str(exc_info.value)
        assert dependencies._rbac_engine is None
    finally:
        dependencies._rbac_engine = None


def test_production_redis_session_failure_is_fail_closed(monkeypatch) -> None:
    from backend.app.api import auth

    class BrokenRedis:
        def setex(self, *args, **kwargs):
            raise OSError("private-redis-write-detail")

        def get(self, *args, **kwargs):
            raise OSError("private-redis-read-detail")

    monkeypatch.setattr(auth, "_production_mode", lambda: True, raising=False)
    monkeypatch.setattr(auth, "_use_redis", True)
    monkeypatch.setattr(auth, "_redis_client", BrokenRedis())
    auth._token_expiry["memory-fallback-token"] = 9_999_999_999.0
    auth._token_users["memory-fallback-token"] = "memory-user"
    try:
        with pytest.raises(RuntimeError, match="Redis session storage is unavailable") as exc_info:
            auth._issue_token()
        assert "private-redis-write-detail" not in str(exc_info.value)
        assert auth._is_token_valid("memory-fallback-token") is False
        with pytest.raises(RuntimeError, match="Redis session storage is unavailable"):
            auth._store_token_user("new-token", "user-a")
        with pytest.raises(RuntimeError, match="Redis session storage is unavailable"):
            auth._revoke_token("memory-fallback-token")
        assert auth._get_token_user("memory-fallback-token") is None
    finally:
        auth._token_expiry.pop("memory-fallback-token", None)
        auth._token_users.pop("memory-fallback-token", None)


def test_prometheus_uses_file_backed_api_key_header() -> None:
    config = yaml.safe_load(_read("monitoring/prometheus.yml"))
    assert config["rule_files"] == [
        "/etc/prometheus/alert_rules.yml",
        "/etc/prometheus/recording_rules.yml",
    ]
    app_job = next(job for job in config["scrape_configs"] if job["job_name"] == "x-agent-api")
    assert app_job["static_configs"][0]["targets"] == ["${XAGENT_METRICS_TARGET}"]
    header = app_job["http_headers"]["X-Api-Key"]
    assert header == {"files": ["/run/secrets/xagent_metrics_api_key"]}

    compose = _read("monitoring/docker-compose.monitoring.yml")
    assert "xagent_metrics_api_key" in compose
    assert "/run/secrets/xagent_metrics_api_key:ro" in compose
    assert "XAGENT_METRICS_API_KEY_FILE" in _read("monitoring/.env.example")
    assert "XAGENT_METRICS_TARGET" in _read("monitoring/.env.example")
    startup = _read("monitoring/start-prometheus.sh")
    assert "XAGENT_METRICS_TARGET" in startup
    assert "prometheus.rendered.yml" in startup
    for compose_path in (
        "monitoring/docker-compose.monitoring.yml",
        "monitoring/docker-compose.yml",
    ):
        compose = _read(compose_path)
        assert "./start-prometheus.sh:/etc/prometheus/start-prometheus.sh:ro" in compose
        assert "entrypoint: [\"/bin/sh\", \"/etc/prometheus/start-prometheus.sh\"]" in compose


def test_backup_and_restore_have_non_mutating_dry_run_contract(tmp_path: Path) -> None:
    backup = _read("deployment/scripts/backup-database.sh")
    restore = _read("deployment/scripts/restore-database.sh")
    for script in (backup, restore):
        assert "--dry-run" in script
        assert "XAGENT_DATABASE_PASSWORD" in script
        assert "must be set" in script
    assert "XAGENT_RESTORE_CONFIRMATION" in restore
    assert "gzip -t" in restore
    assert "pg_restore --list" in restore
    assert "--exit-on-error" in restore
    cron_backup = _read("deployment/backup/backup.sh")
    assert 'pg_restore --list "$BACKUP_PATH/database.dump"' in cron_backup
    assert 'redis-check-rdb "$BACKUP_PATH/redis.rdb"' in cron_backup
    assert "Redis backup failed (continuing" not in cron_backup
    assert "Qdrant backup incomplete (continuing" not in cron_backup
    assert "AWS CLI not found, skipping S3 upload" not in cron_backup
    backup_dockerfile = _read("deployment/backup/Dockerfile")
    assert "FROM redis:7.4-bookworm@sha256:" in backup_dockerfile
    assert "FROM postgres:16-bookworm@sha256:" in backup_dockerfile
    assert "awscli" in backup_dockerfile
    assert "COPY backup.sh /usr/local/bin/backup.sh" in backup_dockerfile
    assert "COPY deployment/backup/backup.sh" not in backup_dockerfile
    assert "USER 10001:10001" in backup_dockerfile
    backup_cronjob = _read("deployment/helm/templates/backup-cronjob.yaml")
    assert "fsGroup: 10001" in backup_cronjob
    assert "runAsUser: 10001" in backup_cronjob
    assert "readOnlyRootFilesystem: true" in backup_cronjob

    archive = ROOT / ".xagent_runtime" / "reports" / f"{tmp_path.name}-invalid-backup.sql.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"not-a-real-archive")
    env = {
        **os.environ,
        "XAGENT_DATABASE_PASSWORD": "dry-run-only",
        "XAGENT_DATABASE_NAME": "xagent_dry_run",
        "WSLENV": "XAGENT_DATABASE_PASSWORD:XAGENT_DATABASE_NAME",
    }
    try:
        result = subprocess.run(
            [
                "bash",
                "deployment/scripts/restore-database.sh",
                "--dry-run",
                archive.relative_to(ROOT).as_posix(),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    finally:
        archive.unlink(missing_ok=True)
    assert result.returncode != 0
    assert "invalid gzip backup" in (result.stdout + result.stderr).lower()


def test_legacy_migration_cli_rejects_mutating_commands_before_initialization() -> None:
    env = dict(os.environ)
    env.pop("XAGENT_DATABASE_URL", None)
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [
            sys.executable,
            "deployment/migrations/migrate.py",
            "restore",
            "PRIVATE_BACKUP_PATH.dump",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "legacy mutating command is disabled" in output.lower()
    assert "PRIVATE_BACKUP_PATH" not in output


def test_legacy_rollback_entrypoint_cannot_downgrade_the_database() -> None:
    legacy = _read("deployment/rollback.sh")
    assert 'exec "$SCRIPT_DIR/scripts/rollback.sh"' in legacy
    assert "migrate.py rollback" not in legacy
    assert "--database" not in legacy


def test_production_dependency_lock_targets_supported_linux_runtimes() -> None:
    lock = _read("requirements-lock.txt")
    assert "--python-version 3.11" in lock
    assert "--python-platform linux" in lock
    assert "\npywin32==" not in lock
    assert "\nsentence-transformers==" not in lock
    assert "\ntorch==" not in lock
    assert "\nnvidia-" not in lock
    assert "\ngunicorn==" in lock
    assert "\nauthlib==" in lock
    assert "\npsutil==" in lock
    assert "\ncroniter==" in lock
    assert "\nasyncpg==0.31.0" in lock
    assert "\ngreenlet==3.5.5" in lock
    assert "\nplaywright==1.62.0" in lock

    dockerfile = _read("Dockerfile")
    requirements_copy = dockerfile.index("COPY requirements-lock.txt pyproject.toml ./")
    dependency_install = dockerfile.index("pip install --prefix=/install -r requirements-lock.txt")
    source_copy = dockerfile.index("COPY backend/ ./backend/")
    assert requirements_copy < dependency_install < source_copy
    assert "--no-build-isolation" in dockerfile
    assert "PYTHONPATH=/install/lib/python3.14/site-packages" in dockerfile
    assert "pip install --no-cache-dir --upgrade" not in dockerfile


def test_production_container_builds_pin_every_base_image_by_digest() -> None:
    dockerfile = _read("Dockerfile")
    assert dockerfile.startswith("# syntax=docker/dockerfile:1.7@sha256:")

    for path in ("Dockerfile", "deployment/backup/Dockerfile"):
        from_lines = [line for line in _read(path).splitlines() if line.startswith("FROM ")]
        assert from_lines
        assert all("@sha256:" in line for line in from_lines)


def test_production_runtime_uses_cve_bounded_python_base() -> None:
    dockerfile = _read("Dockerfile")
    builder_base = (
        "cgr.dev/chainguard/python:latest-dev@sha256:"
        "e80d78c70f4d71290b8ea7adbe2b510a14b0fa87f422be76d0d7c76b2e0fd9f7"
    )
    runtime_base = (
        "cgr.dev/chainguard/python:latest@sha256:"
        "e15765ff7066a0eaf91e1b6fd5000c1bba47d62b9f9731f2da560711d910c4f3"
    )

    assert f"FROM {builder_base} AS builder" in dockerfile
    assert f"FROM {runtime_base} AS runtime" in dockerfile
    assert "apt-get" not in dockerfile
    assert "apk add" not in dockerfile
    assert "PYTHONPATH=/install/lib/python3.14/site-packages" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/python"]' in dockerfile
    assert "USER 65532:65532" in dockerfile
