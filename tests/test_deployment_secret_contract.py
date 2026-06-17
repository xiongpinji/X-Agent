from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.app.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = ROOT / "deployment" / "k8s"
KUBERNETES_DIR = ROOT / "deployment" / "kubernetes"
CANARY_DIR = ROOT / "deployment" / "canary"

SPLIT_SECRET_KEYS = {
    "DB_PASSWORD",
    "REDIS_PASSWORD",
    "QDRANT_API_KEY",
    "NEO4J_PASSWORD",
    "SECRET_KEY",
}
URL_STYLE_SECRET_KEYS = {
    "database-url",
    "redis-url",
    "qdrant-url",
    "qdrant-api-key",
    "neo4j-uri",
    "secret-key",
    "sentry-dsn",
}
PRODUCTION_WORKLOADS = [
    K8S_DIR / "xagent-api-deployment.yaml",
    K8S_DIR / "xagent-worker-deployment.yaml",
    K8S_DIR / "xagent-beat-deployment.yaml",
    KUBERNETES_DIR / "deployment.yaml",
    CANARY_DIR / "canary-deployment.yaml",
]
SETTINGS_BACKED_RUNTIME_ENVS = {
    "database_url": "XAGENT_DATABASE_URL",
    "redis_url": "XAGENT_REDIS_URL",
    "qdrant_url": "XAGENT_QDRANT_URL",
    "qdrant_api_key": "XAGENT_QDRANT_API_KEY",
}


def _load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    return [
        doc
        for doc in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if isinstance(doc, dict)
    ]


def _external_secret_keys(path: Path, *, name: str, namespace: str) -> set[str]:
    for doc in _load_yaml_documents(path):
        metadata = doc.get("metadata") or {}
        if (
            doc.get("kind") == "ExternalSecret"
            and metadata.get("name") == name
            and metadata.get("namespace") == namespace
        ):
            return {
                item["secretKey"]
                for item in (doc.get("spec") or {}).get("data") or []
                if isinstance(item, dict) and item.get("secretKey")
            }
    raise AssertionError(f"ExternalSecret {namespace}/{name} not found in {path}")


def _configmap_keys(path: Path, *, name: str, namespace: str) -> set[str]:
    for doc in _load_yaml_documents(path):
        metadata = doc.get("metadata") or {}
        if (
            doc.get("kind") == "ConfigMap"
            and metadata.get("name") == name
            and metadata.get("namespace") == namespace
        ):
            return set((doc.get("data") or {}).keys())
    raise AssertionError(f"ConfigMap {namespace}/{name} not found in {path}")


def _deployment_containers(path: Path) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    for doc in _load_yaml_documents(path):
        if doc.get("kind") != "Deployment":
            continue
        pod_spec = (((doc.get("spec") or {}).get("template") or {}).get("spec") or {})
        containers.extend(pod_spec.get("containers") or [])
    return containers


def _env_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for container in _deployment_containers(path):
        entries.extend(entry for entry in container.get("env") or [] if isinstance(entry, dict))
    return entries


def _env_map(path: Path) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in _env_entries(path) if entry.get("name")}


def _secret_key_refs(path: Path, *, secret_name: str) -> set[str]:
    refs: set[str] = set()
    for entry in _env_entries(path):
        secret_ref = ((entry.get("valueFrom") or {}).get("secretKeyRef") or {})
        if secret_ref.get("name") == secret_name and secret_ref.get("key"):
            refs.add(secret_ref["key"])
    return refs


def _configmap_key_refs(path: Path, *, configmap_name: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for entry in _env_entries(path):
        config_ref = ((entry.get("valueFrom") or {}).get("configMapKeyRef") or {})
        if config_ref.get("name") == configmap_name and config_ref.get("key"):
            refs[entry["name"]] = config_ref["key"]
    return refs


def _literal_env_value(path: Path, name: str) -> str | None:
    entry = _env_map(path).get(name)
    if entry is None:
        return None
    value = entry.get("value")
    return str(value).strip().strip("\"'").lower() if value is not None else None


def _env_source(entry: dict[str, Any] | None) -> Any:
    if entry is None:
        return None
    if "valueFrom" in entry:
        return entry["valueFrom"]
    return entry.get("value")


def test_k8s_split_secret_refs_are_backed_by_external_secret() -> None:
    provided = _external_secret_keys(K8S_DIR / "secret.yaml", name="xagent-secrets", namespace="xagent")
    referenced = {
        key
        for path in K8S_DIR.glob("*.yaml")
        if path.name != "secret.yaml"
        for key in _secret_key_refs(path, secret_name="xagent-secrets")
    }

    assert provided == SPLIT_SECRET_KEYS
    assert referenced <= provided
    assert SPLIT_SECRET_KEYS <= referenced


def test_k8s_database_identity_is_non_secret_configmap_contract() -> None:
    provided = _configmap_keys(K8S_DIR / "configmap.yaml", name="xagent-config", namespace="xagent")
    refs = {
        path.name: _configmap_key_refs(path, configmap_name="xagent-config")
        for path in K8S_DIR.glob("*.yaml")
        if path.name not in {"configmap.yaml", "secret.yaml"}
    }

    assert {"DB_USER", "DB_NAME"} <= provided
    for path_name, path_refs in refs.items():
        if "DB_USER" in path_refs or "DB_NAME" in path_refs:
            assert path_refs.get("DB_USER") == "DB_USER", path_name
            assert path_refs.get("DB_NAME") == "DB_NAME", path_name

    secret_refs = {
        key
        for path in K8S_DIR.glob("*.yaml")
        if path.name != "secret.yaml"
        for key in _secret_key_refs(path, secret_name="xagent-secrets")
    }
    assert "DB_USER" not in secret_refs
    assert "DB_NAME" not in secret_refs


def test_kubernetes_and_canary_url_style_secret_refs_are_backed_by_external_secret() -> None:
    provided = _external_secret_keys(
        KUBERNETES_DIR / "secret.yaml",
        name="xagent-secrets",
        namespace="production",
    )
    workload_paths = [KUBERNETES_DIR / "deployment.yaml", CANARY_DIR / "canary-deployment.yaml"]
    referenced = {
        key
        for path in workload_paths
        for key in _secret_key_refs(path, secret_name="xagent-secrets")
    }

    assert provided == URL_STYLE_SECRET_KEYS
    assert referenced <= provided
    assert URL_STYLE_SECRET_KEYS <= referenced


def test_production_workloads_fail_closed_for_auth_and_mode_env() -> None:
    settings_fields = set(Settings.model_fields)
    assert {"app_mode", "mode", "require_api_key"} <= settings_fields

    failures: list[str] = []
    for path in PRODUCTION_WORKLOADS:
        env = _env_map(path)
        if _literal_env_value(path, "XAGENT_REQUIRE_API_KEY") != "true":
            failures.append(f"{path.relative_to(ROOT)} must set XAGENT_REQUIRE_API_KEY=true")
        if _literal_env_value(path, "XAGENT_APP_MODE") != "production":
            failures.append(f"{path.relative_to(ROOT)} must set XAGENT_APP_MODE=production")
        if _literal_env_value(path, "XAGENT_MODE") != "production":
            failures.append(f"{path.relative_to(ROOT)} must set XAGENT_MODE=production")
        if "APP_MODE" in env:
            failures.append(f"{path.relative_to(ROOT)} uses APP_MODE, but Settings reads XAGENT_APP_MODE")
        if "REQUIRE_API_KEY" in env:
            failures.append(
                f"{path.relative_to(ROOT)} uses REQUIRE_API_KEY, but Settings reads XAGENT_REQUIRE_API_KEY"
            )

    assert failures == []


def test_production_workloads_export_settings_runtime_env_names() -> None:
    settings_fields = set(Settings.model_fields)
    assert {"database_url", "redis_url", "qdrant_url", "qdrant_api_key"} <= settings_fields

    failures: list[str] = []
    for path in PRODUCTION_WORKLOADS:
        env = _env_map(path)
        for base_name in ("DATABASE_URL", "REDIS_URL", "QDRANT_URL"):
            xagent_name = f"XAGENT_{base_name}"
            if base_name not in env and xagent_name not in env:
                continue
            if xagent_name not in env:
                failures.append(
                    f"{path.relative_to(ROOT)} must set {xagent_name} for Settings.{base_name.lower()}"
                )
                continue
            if base_name in env and _env_source(env[xagent_name]) != _env_source(env[base_name]):
                failures.append(
                    f"{path.relative_to(ROOT)} must source {xagent_name} from the same value as {base_name}"
                )
        if "QDRANT_API_KEY" in env:
            if "XAGENT_QDRANT_API_KEY" not in env:
                failures.append(
                    f"{path.relative_to(ROOT)} must set XAGENT_QDRANT_API_KEY for Settings.qdrant_api_key"
                )
            elif _env_source(env["XAGENT_QDRANT_API_KEY"]) != _env_source(env["QDRANT_API_KEY"]):
                failures.append(
                    f"{path.relative_to(ROOT)} must source XAGENT_QDRANT_API_KEY from the same secret as QDRANT_API_KEY"
                )

    assert failures == []


def test_production_workloads_use_xagent_prefixed_runtime_env_names() -> None:
    settings_fields = set(Settings.model_fields)
    assert set(SETTINGS_BACKED_RUNTIME_ENVS) <= settings_fields

    failures: list[str] = []
    for path in PRODUCTION_WORKLOADS:
        env = _env_map(path)
        rel_path = path.relative_to(ROOT)
        references = {
            "database_url": "DATABASE_URL" in env or "XAGENT_DATABASE_URL" in env,
            "redis_url": "REDIS_URL" in env or "XAGENT_REDIS_URL" in env,
            "qdrant_url": "QDRANT_URL" in env or "XAGENT_QDRANT_URL" in env,
            "qdrant_api_key": (
                "QDRANT_API_KEY" in env
                or "XAGENT_QDRANT_API_KEY" in env
                or "QDRANT_API_KEY" in _secret_key_refs(path, secret_name="xagent-secrets")
                or "qdrant-api-key" in _secret_key_refs(path, secret_name="xagent-secrets")
            ),
        }

        for settings_field, required_env in SETTINGS_BACKED_RUNTIME_ENVS.items():
            if references[settings_field] and required_env not in env:
                failures.append(
                    f"{rel_path} references {settings_field} but must inject {required_env}; "
                    "unprefixed compatibility envs do not satisfy Settings(env_prefix='XAGENT_')"
                )

    assert failures == []
