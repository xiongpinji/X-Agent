from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _service_environment(service_name: str) -> dict[str, object]:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    environment = compose["services"][service_name]["environment"]
    assert isinstance(environment, dict)
    return environment


def test_api_compose_environment_exposes_commercial_rc_settings() -> None:
    environment = _service_environment("xagent-api")

    required = {
        "XAGENT_APP_MODE",
        "XAGENT_DATABASE_URL",
        "XAGENT_REDIS_URL",
        "XAGENT_QDRANT_URL",
        "XAGENT_MEMORY_BACKEND",
        "XAGENT_TRACE_BACKEND",
        "XAGENT_LLM_BACKEND",
        "XAGENT_LLM_FALLBACK_ORDER",
        "XAGENT_OPENAI_API_KEY",
        "XAGENT_DEEPSEEK_API_KEY",
        "XAGENT_LANGFUSE_PUBLIC_KEY",
        "XAGENT_LANGFUSE_SECRET_KEY",
        "XAGENT_AUDIT_HMAC_SECRET",
        "XAGENT_JWT_SECRET",
        "XAGENT_ENCRYPTION_KEY",
        "XAGENT_REQUIRE_API_KEY",
        "XAGENT_BOOTSTRAP_API_KEY",
        "XAGENT_CORS_ORIGINS",
        "XAGENT_ENABLE_HIGH_RISK_TOOLS",
        "XAGENT_GITHUB_TOKEN",
        "XAGENT_GITHUB_WEBHOOK_SECRET",
        "XAGENT_FEISHU_APP_ID",
        "XAGENT_FEISHU_APP_SECRET",
        "XAGENT_FEISHU_ENCRYPT_KEY",
    }

    assert required <= set(environment)


def test_worker_compose_environment_matches_backend_runtime_dependencies() -> None:
    environment = _service_environment("xagent-worker")

    required = {
        "XAGENT_APP_MODE",
        "XAGENT_DATABASE_URL",
        "XAGENT_REDIS_URL",
        "XAGENT_QDRANT_URL",
        "XAGENT_MEMORY_BACKEND",
        "XAGENT_TRACE_BACKEND",
        "XAGENT_LLM_BACKEND",
        "XAGENT_LLM_FALLBACK_ORDER",
        "XAGENT_OPENAI_API_KEY",
        "XAGENT_OPENAI_MODEL",
        "XAGENT_DEEPSEEK_API_KEY",
        "XAGENT_DEEPSEEK_MODEL",
        "XAGENT_AUDIT_HMAC_SECRET",
        "XAGENT_JWT_SECRET",
        "XAGENT_ENCRYPTION_KEY",
        "XAGENT_REQUIRE_API_KEY",
        "XAGENT_ENABLE_HIGH_RISK_TOOLS",
        "XAGENT_PLAYWRIGHT_HEADLESS",
        "XAGENT_LANGFUSE_PUBLIC_KEY",
        "XAGENT_LANGFUSE_SECRET_KEY",
    }

    assert required <= set(environment)
